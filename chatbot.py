from typing import Optional
from types import SimpleNamespace
import time
import threading
from common import client, gpt_num_tokens, Model
import json
from function_tools import FUNCTION_DEFINITIONS, FUNCTION_MAP
from memory_manager import MemoryManager
from retry import retry
import openai
from openai import OpenAI

def dict_to_namespace(data):
    if isinstance(data, dict):
        return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in data.items()})
    elif isinstance(data, list):
        return [dict_to_namespace(i) for i in data]
    else:
        return data

def makeup_response(message: str, response_id: str = None):
    data = {
        "output": [ { "content": [ { "text": message } ], "role": "assistant" } ],
        "output_text": message,
        "usage": {"total_tokens": 0}
    }
    return dict_to_namespace(data)

class Chatbot:
    def __init__(self, model: Model, developer_role: str, instruction: str, max_rounds: int = 40, api_type: str = "responses", assistant_id: str = None, **kwargs):
        self.model = model
        self.developer_role = developer_role
        self.instruction = instruction
        self.max_rounds = max_rounds
        self.max_token_size = 16 * 1024
        self.memoryManager = MemoryManager(**kwargs)
        self.user = kwargs['user']
        self.assistant = kwargs['assistant']
        self.context = [{'role': 'developer', 'content': developer_role}]
        self.context.extend(self.memoryManager.restore_chat())
        
        # API 타입 설정
        self.api_type = api_type
        
        # Assistant API 사용 시 초기화
        if self.api_type == "assistant":
            self.openai_client = OpenAI()
            if assistant_id:
                self.openai_assistant = self.openai_client.beta.assistants.retrieve(assistant_id=assistant_id)
            else:
                # Assistant API에서 지원하는 모델 사용
                assistant_model = "gpt-4o-mini"  # Assistant API에서 지원하는 모델로 변경
                
                # Function definitions을 Assistant API 호환 포맷으로 변환
                assistant_tools = []
                for func_def in FUNCTION_DEFINITIONS:
                    assistant_tools.append({
                        "type": "function",
                        "function": {
                            "name": func_def["name"],
                            "description": func_def["description"],
                            "parameters": func_def["parameters"]
                        }
                    })
                
                self.openai_assistant = self.openai_client.beta.assistants.create(
                    name=f"{self.assistant} Assistant",
                    instructions=f"{developer_role}\n\n{instruction}",
                    model=assistant_model,
                    tools=assistant_tools
                )
            
            # 새 스레드 생성
            self.thread = self.openai_client.beta.threads.create()
            self.runs = []
        
        # 데몬 구동
        bg_thread = threading.Thread(target=self.background_task)
        bg_thread.daemon = True
        bg_thread.start()

    def background_task(self):
        while True:
            self.save_chat()
            self.context = [ {'role': v['role'], 'content': v['content'], 'saved': True} for v in self.context ]
            self.memoryManager.build_memory()
            time.sleep(3600)     # 1시간마다 반복

    def _as_api_messages(self):
        api_msgs = []
        for m in self.context:
            role = m.get("role")
            content = m.get("content")
            if role in ("developer", "system", "user", "assistant") and isinstance(content, str):
                api_msgs.append({"role": role, "content": content})
        return api_msgs

    @retry(tries=3, delay=2)
    def _add_user_message_to_thread(self, user_message):
        """Assistant API용 사용자 메시지 추가"""
        try:
            self.openai_client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role='user',
                content=user_message,
            )
        except openai.BadRequestError as e:
            if len(self.runs) > 0:
                print('add_user_message BadRequestError', e)
                self.openai_client.beta.threads.runs.cancel(thread_id=self.thread.id, run_id=self.runs[0])
            raise e 

    @retry(tries=3, delay=2)
    def _create_assistant_run(self):
        """Assistant API용 실행 생성"""
        try:
            run = self.openai_client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.openai_assistant.id,
            )
            self.runs.append(run.id)
            return run
        except openai.BadRequestError as e:
            if len(self.runs) > 0:
                print('create_run BadRequestError', e)
                self.openai_client.beta.threads.runs.cancel(thread_id=self.thread.id, run_id=self.runs[0])
            raise e

    def _handle_function_calls(self, run):
        """Assistant API에서 function calling 처리"""
        try:
            required_actions = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            
            for tool_call in required_actions:
                func_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                print(f"Executing function: {func_name} with arguments: {arguments}")
                
                try:
                    # 함수 실행
                    if func_name in FUNCTION_MAP:
                        result = FUNCTION_MAP[func_name](**arguments)
                    else:
                        result = {"error": "Function not found"}
                except Exception as e:
                    result = {"error": str(e)}
                
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(result, ensure_ascii=False)
                })
            
            # Tool outputs 제출
            self.openai_client.beta.threads.runs.submit_tool_outputs(
                thread_id=self.thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
            
        except Exception as e:
            print(f"Function calling error: {e}")
            # 에러가 발생해도 run을 취소하거나 처리를 중단하지 않음
    
    def _get_assistant_response_content(self, run):
        """Assistant API용 응답 내용 가져오기"""
        max_polling_time = 60    # 최대 1분 동안 폴링
        start_time = time.time()
        retrieved_run = run

        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > max_polling_time:
                return retrieved_run, '대기 시간 초과(retrieve)입니다.'
            
            retrieved_run = self.openai_client.beta.threads.runs.retrieve(
                thread_id=self.thread.id,
                run_id=run.id
            )            
            print(f'run status: {retrieved_run.status}, 경과: {elapsed_time: .2f}초')
                  
            if retrieved_run.status == 'completed':
                break
            elif retrieved_run.status == 'requires_action':
                # Function calling 처리
                print("Function calling required...")
                self._handle_function_calls(retrieved_run)
            elif retrieved_run.status in ['failed', 'cancelled', 'expired']:
                # 실패, 취소, 만료 등 오류 상태 처리
                code = retrieved_run.last_error.code
                message = retrieved_run.last_error.message
                return retrieved_run, f'{code}: {message}'
            
            time.sleep(1) 
            
        # Run이 완료된 후 메시지를 가져옴
        messages = self.openai_client.beta.threads.messages.list(thread_id=self.thread.id)
        resp_message = [m.content[0].text for m in messages if m.run_id == run.id][0]
        return retrieved_run, resp_message.value

    def _chat_with_assistant(self, message: str) -> SimpleNamespace:
        """Assistant API를 사용한 채팅"""
        try:
            print(f"Assistant API: Chat called with message: {message}")
            
            # 사용자 메시지를 스레드에 추가
            self._add_user_message_to_thread(message)
            
            # 실행 생성
            run = self._create_assistant_run()
            
            # 응답 가져오기
            _, response_content = self._get_assistant_response_content(run)
            
            # 컨텍스트에 메시지 추가
            self.context.append({"role": "user", "content": message, "saved": False})
            self.context.append({"role": "assistant", "content": response_content, "saved": False})
            
            # SimpleNamespace 형태로 반환
            data = {
                "output": [{"content": [{"text": response_content}], "role": "assistant"}],
                "output_text": response_content,
                "usage": {"total_tokens": 0}
            }
            return dict_to_namespace(data)
            
        except Exception as e:
            error_msg = f"[Assistant API 오류] 잠시 후 다시 시도해주세요. 상세: {type(e).__name__}: {e}"
            print(f"Assistant API Chat error: {error_msg}")
            return makeup_response(error_msg)
    def _chat(self, message: str, previous_response_id: Optional[str] = None) -> SimpleNamespace:
        """메시지를 처리하고 응답 생성 - OpenAI Function Calling 지원 (Responses API)"""
        try:
            print(f"Responses API: Chat called with message: {message}, previous_response_id: {previous_response_id}")
            
            self.context.append({"role": "user", "content": message, "saved": False})
            input_data = self._as_api_messages()
            
            # 첫 번째 API 호출 - Function calling 가능성 확인
            first = client.responses.create(
                model=self.model.basic,
                input=input_data,
                tools=FUNCTION_DEFINITIONS,
                tool_choice="auto"
            )
            
            print("First API response received")

            tool_outputs = []
            if hasattr(first, "output") and first.output:
                for item in first.output:
                    print(f"Processing output item: {item.name if hasattr(item, 'name') else item}")
                # Responses API에서는 function call이 별도 item(type='function_call')로 옴
                    if getattr(item, "type", None) == "function_call":
                        fn_name = item.name
                        args = json.loads(item.arguments) if isinstance(item.arguments, str) else (item.arguments or {})
                        try:
                            result = FUNCTION_MAP[fn_name](**args) if fn_name in FUNCTION_MAP else {"error": "Function not found"}
                        except Exception as e:
                            result = {"error": str(e)}

                        tool_outputs.append({
                            "type": "function_call_output",
                            "call_id": item.call_id,             # ← 반드시 첫 호출의 call_id 그대로
                            "output": json.dumps(result, ensure_ascii=False)
                        })

            # Function call이 있었다면 최종 응답 생성
            if tool_outputs:
                print("Generating final response after function execution")
                final = client.responses.create(
                    model=self.model.advanced,
                    instructions=self.instruction,
                    input=tool_outputs,
                    previous_response_id=first.id
                )
                result_response = final
            else:
                print("No function calls, using original response")
                result_response = first
            
            if hasattr(result_response, 'output') and result_response.output:
                for output in result_response.output:
                    if hasattr(output, 'role') and output.role == 'assistant':
                        content = ""
                        if hasattr(output, 'content') and output.content:
                            if isinstance(output.content, list) and len(output.content) > 0:
                                content = output.content[0].text if hasattr(output.content[0], 'text') else str(output.content[0])
                            else:
                                content = str(output.content)
                        self.context.append({"role": "assistant", "content": content, "saved": False})
            
            return result_response
            
        except Exception as e:
            error_msg = f"[Responses API 오류] 잠시 후 다시 시도해주세요. 상세: {type(e).__name__}: {e}"
            print(f"Responses API Chat error: {error_msg}")
            return makeup_response(error_msg)
    
    def chat(self, message: str, previous_response_id: Optional[str] = None) -> SimpleNamespace:
        print(f'> [chat 메서드] 입력된 message: {message}')
        print(f'> [chat 메서드] API 타입: {self.api_type}')
        
        memory_instruction = self.retrieve_memory(message)
        if memory_instruction is not None:
            message += memory_instruction
        
        # API 타입에 따라 다른 메서드 호출
        if self.api_type == "assistant":
            return self._chat_with_assistant(message)
        else:  # "responses" (기본값)
            return self._chat(message, previous_response_id)
    
    def retrieve_memory(self, user_message):
        print(f'> [retrieve_memory] 실제 검색할 메시지: {user_message}')
        if not self.memoryManager.needs_memory(user_message):
            return None

        memory = self.memoryManager.retrieve_memory(user_message)  
        if memory is not None:
            whisper = (f'[귓속말]\n{self.assistant} 기억 속 대화 내용이야. 앞으로 이 내용을 참조하면서 답해줘. '
                       f'알마 전에 나누었던 대화라는 점을 자연스럽게 말해줘:\n{memory}')
            self.add_user_message(whisper)
            return None
        else:
            return '[기억이 안난다고 답할 것!]'
        
    def add_user_message(self, message: str):
        self.context.append({'role': 'user', 'content': message, 'saved': False})

    def save_chat(self):
        """대화 내용을 저장"""
        self.context =self.memoryManager.save_chat(self.context)








