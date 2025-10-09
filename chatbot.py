from typing import Optional
from types import SimpleNamespace
from common import client, gpt_num_tokens
import secrets

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
    def __init__(self, model: str, developer_role: str, instruction: str, max_rounds: int = 40):
        self.model = model
        self.developer_role = developer_role
        self.instruction = instruction
        self.max_rounds = max_rounds
        self.max_token_size = 16 * 1024

    def chat(self, message: str, previous_response_id: Optional[str] = None) -> SimpleNamespace:
        """메시지를 처리하고 응답 생성 - OpenAI API 스타일"""
        try:
            # 개발자 역할과 사용자 메시지로 기본 입력 구성
            input_data = [
                {"role": "developer", "content": self.developer_role},
                {"role": "user", "content": message + "\n\n" + self.instruction}
            ]
            
            # API 요청 매개변수 구성
            request_params = {
                "model": self.model,
                "input": input_data
            }
            
            # previous_response_id가 있으면 추가 (OpenAI API 스타일)
            if previous_response_id:
                request_params["previous_response_id"] = previous_response_id
            
            # API 요청
            resp = client.responses.create(**request_params)
            
            # API에서 반환된 응답에는 이미 id가 포함되어 있음
            return resp
            
        except Exception as e:
            # 오류 발생시 임시 응답 생성
            return makeup_response(f"[테오 오류] 잠시 후 다시 시도해주세요. 상세: {type(e).__name__}: {e}")
