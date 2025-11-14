from typing import Optional
from types import SimpleNamespace
import time
import threading
from common import client, gpt_num_tokens, Model
import json
from function_tools import FUNCTION_DEFINITIONS, FUNCTION_MAP
from memory_manager import MemoryManager

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
    def __init__(self, model: Model, developer_role: str, instruction: str, max_rounds: int = 40, **kwargs):
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

    def _chat(self, message: str, previous_response_id: Optional[str] = None) -> SimpleNamespace:
        """메시지를 처리하고 응답 생성 - OpenAI Function Calling 지원"""
        try:
            print(f"Chat called with message: {message}, previous_response_id: {previous_response_id}")
            
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
            error_msg = f"[테오 오류] 잠시 후 다시 시도해주세요. 상세: {type(e).__name__}: {e}"
            print(f"Chat error: {error_msg}")
            return makeup_response(error_msg)
    
    def chat(self, message: str, previous_response_id: Optional[str] = None) -> SimpleNamespace:
        print(f'> [chat 메서드] 입력된 message: {message}')
        memory_instruction = self.retrieve_memory(message)
        if memory_instruction is not None:
            message += memory_instruction
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








