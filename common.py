from dataclasses import dataclass
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Model:
    basic: str = "gpt-5-mini"
    advanced: str = "gpt-5"

model = Model()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=30, max_retries=3)

import tiktoken

def gpt_num_tokens(messages, model='gpt-4o'):
    encoding = tiktoken.encoding_for_model(model)
    tokens_per_message = 3    # 모든 메시지는 다음 형식을 따른다: <|start|>{role/name}\n{content}<|end|>\n
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for _, value in message.items():
            num_tokens += len(encoding.encode(value))
    num_tokens += 3    # 모든 메시지는 다음 형식으로 assistant의 답변을 준비한다: <|start|>assistant<|message|>
    return num_tokens
