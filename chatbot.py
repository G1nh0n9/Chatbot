from typing import Optional
from types import SimpleNamespace
from common import client, gpt_num_tokens, Model
import json
from function_tools import FUNCTION_DEFINITIONS, FUNCTION_MAP

def dict_to_namespace(data):
    if isinstance(data, dict):
        return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in data.items()})
    elif isinstance(data, list):
        return [dict_to_namespace(i) for i in data]
    else:
        return data

def makeup_response(message: str, response_id: str = None):
    if not response_id:
        response_id = None
    data = {
        "output": [ { "content": [ { "text": message } ], "role": "assistant" } ],
        "usage": {"total_tokens": 0},
        "id": response_id,  # OpenAI API 스타일로 id 속성 사용
    }
    return dict_to_namespace(data)

class Chatbot:
    def __init__(self, model: Model, developer_role: str, instruction: str, max_rounds: int = 40):
        self.model = model
        self.developer_role = developer_role
        self.instruction = instruction
        self.max_rounds = max_rounds
        self.max_token_size = 16 * 1024

    def chat(self, message: str, previous_response_id: Optional[str] = None) -> SimpleNamespace:
        """메시지를 처리하고 응답 생성 - OpenAI Function Calling 지원"""
        try:
            input_list = []
            print(f"Chat called with message: {message}, previous_response_id: {previous_response_id}")
            # Function Calling 여부 결정
            function_call_response = client.responses.create(
                model = self.model.basic,
                input = [
                    {"role": "user", "content": message}
                ],
                tools = FUNCTION_DEFINITIONS,
                tool_choice = "auto"
            )
            input_list += function_call_response.output
            print(function_call_response.model_dump())
            print("\n\n")

            for item in function_call_response.output:
                if item.type == 'function_call':
                    print("Function call detected:", item)
                    # execute the function call
                    function_name = item.name
                    function_args = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                    if function_name in FUNCTION_MAP:
                        result = FUNCTION_MAP[function_name](**function_args)
                        input_list.append({
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": json.dumps(result, ensure_ascii=False)
                        })
                    else:
                        input_list.append({
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": json.dumps({"error": "Function not found"}, ensure_ascii=False)
                        })
            # insert instruction and developer role
            input_list.insert(0, {"role": "developer", "content": self.developer_role})
            input_list.append({"role": "user", "content": message + "\n\n" + self.instruction})

            print("Final input list:", input_list)
            return client.responses.create(
                    model=self.model.advanced,
                    input=input_list,
                    previous_response_id=previous_response_id
                )
        except Exception as e:
            # 오류 발생시 임시 응답 생성
            return makeup_response(f"[테오 오류] 잠시 후 다시 시도해주세요. 상세: {type(e).__name__}: {e}")












"""


from typing import Optional
from types import SimpleNamespace
from common import client, gpt_num_tokens, Model
import secrets
import json
from function_tools import FUNCTION_DEFINITIONS, FUNCTION_MAP

def dict_to_namespace(data):
    if isinstance(data, dict):
        return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in data.items()})
    elif isinstance(data, list):
        return [dict_to_namespace(i) for i in data]
    else:
        return data

def makeup_response(message: str, response_id: str = None):
    if not response_id:
        response_id = secrets.token_hex(8)
    data = {
        "output": [ { "content": [ { "text": message } ], "role": "assistant" } ],
        "usage": {"total_tokens": 0},
        "id": response_id,  # OpenAI API 스타일로 id 속성 사용
    }
    return dict_to_namespace(data)

class Chatbot:
    def __init__(self, model: Model, developer_role: str, instruction: str, max_rounds: int = 40):
        self.model = model
        self.developer_role = developer_role
        self.instruction = instruction
        self.max_rounds = max_rounds
        self.max_token_size = 16 * 1024
        self.enable_function_calling = True

    def execute_function_calls(self, function_calls):
        #""""""OpenAI API가 요청한 함수들을 실행""""""
        function_results = []
        
        for call in function_calls:
            function_name = call.function.name
            function_args = json.loads(call.function.arguments)
            
            if function_name in FUNCTION_MAP:
                try:
                    # 함수 실행
                    result = FUNCTION_MAP[function_name](**function_args)
                    function_results.append({
                        "tool_call_id": call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                except Exception as e:
                    function_results.append({
                        "tool_call_id": call.id,
                        "role": "tool", 
                        "name": function_name,
                        "content": json.dumps({"error": str(e)}, ensure_ascii=False)
                    })
            else:
                function_results.append({
                    "tool_call_id": call.id,
                    "role": "tool",
                    "name": function_name, 
                    "content": json.dumps({"error": f"Unknown function: {function_name}"}, ensure_ascii=False)
                })
        
        return function_results
    
    def format_function_results(self, function_results):
        """"""Function 실행 결과를 텍스트로 포맷팅""""""
        if not function_results:
            return ""
        
        formatted_parts = []
        for result_data in function_results:
            try:
                content = json.loads(result_data["content"])
                if "error" in content:
                    formatted_parts.append(f"[오류] {content['error']}")
                else:
                    source = content.get("source", "알 수 없는 소스")
                    result_content = content.get("content", "내용 없음")
                    timestamp = content.get("timestamp", "")
                    
                    formatted_parts.append(f"[{source}] {result_content}")
                    if timestamp:
                        formatted_parts.append(f"(조회 시간: {timestamp})")
            except Exception as e:
                formatted_parts.append(f"[처리 오류] 결과 파싱 실패: {str(e)}")
        
        return "\n".join(formatted_parts)
    
    def chat(self, message: str, previous_response_id: Optional[str] = None) -> SimpleNamespace:
        """"""메시지를 처리하고 응답 생성 - OpenAI Function Calling 지원""""""
        try:
            # 기본 개발자 역할과 사용자 메시지로 입력 구성
            input_data = [
                {"role": "developer", "content": self.developer_role},
                {"role": "user", "content": message + "\n\n" + self.instruction}
            ]
            
            # API 요청 매개변수 구성 
            request_params = {
                "model": self.model.basic,
                "input": input_data
            }
            
            # Function Calling이 활성화된 경우 함수 목록 추가
            if self.enable_function_calling:
                request_params["tools"] = FUNCTION_DEFINITIONS
                request_params["tool_choice"] = "auto"  # 필요시 자동으로 함수 호출
            
            # previous_response_id가 있으면 추가 (기존 스타일 유지)
            if previous_response_id:
                request_params["previous_response_id"] = previous_response_id
            
            # 첫 번째 API 요청
            resp = client.responses.create(**request_params)
            
            # Function Call이 있는지 확인 (응답 구조에 따라 조정 필요)
            if hasattr(resp, 'output') and resp.output and len(resp.output) > 0:
                last_output = resp.output[-1]
                # Function calls가 있는지 확인 (실제 API 응답 구조에 따라 조정)
                if hasattr(last_output, 'tool_calls') and last_output.tool_calls:
                    # Function calls 실행
                    function_results = self.execute_function_calls(last_output.tool_calls)
                    
                    # Function 실행 결과를 텍스트로 변환
                    function_text = self.format_function_results(function_results)
                    
                    # Function 결과와 함께 두 번째 API 호출
                    second_input_data = [
                        {"role": "developer", "content": self.developer_role},
                        {"role": "user", "content": message + "\n\n" + self.instruction},
                        {"role": "assistant", "content": "[Function 호출 완료]"},
                        {"role": "user", "content": f"다음 정보를 참고해서 답변해주세요:\n\n{function_text}"}
                    ]
                    
                    second_request_params = {
                        "model": self.model.basic,
                        "input": second_input_data
                    }
                    
                    if previous_response_id:
                        second_request_params["previous_response_id"] = previous_response_id
                    
                    # 두 번째 API 호출로 최종 응답 생성
                    final_resp = client.responses.create(**second_request_params)
                    return final_resp
            
            # Function Call이 없으면 기본 응답 반환
            return resp
            
        except Exception as e:
            # 오류 발생시 임시 응답 생성
            return makeup_response(f"[테오 오류] 잠시 후 다시 시도해주세요. 상세: {type(e).__name__}: {e}")

    
"""