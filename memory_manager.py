
import os
import json
from pprint import pprint
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from common import today, client, model, today, yesterday
from pinecone.grpc import PineconeGRPC as Pinecone
# dotenv 설정 로드
from dotenv import load_dotenv
load_dotenv()

# Pinecone 클라이언트 및 인덱스 초기화
pinecone = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
pinecone_index = pinecone.Index('agent-memory')

# Create a new client and connect to the server
uri = os.getenv("MONGO_CLUSTER_URI")
mongo_cluster = MongoClient(uri, server_api=ServerApi('1'))
mongo_chats_collection = mongo_cluster['OPENAI_AGENT_CHAT']['chats']
mongo_memory_collection = mongo_cluster['OPENAI_AGENT_CHAT']['memory']

embedding_model = 'text-embedding-ada-002'

# 아래 사용자 질의가 오늘 이전의 기억에 대해 묻는 것인지 참/거짓으로만 응답하세요.
NEEDS_MEMORY_TEMPLATE = """
아래 사용자 질의가 오늘 이전의 기억에 대해 묻는 것인지 TRUE/FALSE으로만 응답하세요. 현재 대화맥락에서 더 과거를 의미하는 경우에는 기억을 찾을 필요가 있으니 TRUE로 응답하는것을 권장합니다.
```
{message}
"""

# statement1은 기억에 대한 질문입니다.
# statement2는 브라이언와 테오가 공유하는 기억입니다.
# statment2는 statement1에 대한 가억으로 적절한지 아래 json 포맷으로 답하세요
# {'0과 1 사이의 확률': <확률값>}
MEASURING_SIMILARITY_SYSTEM_ROLE = """
statement1 is a question about memory.
statement2 is a memory shared by '브라이언' and '테오'.
Answer whether statement2 is appropriate as a memory for statement1 in the following JSON format
{"probability": <between 0 and 1>}
"""

SUMMARIZING_TEMPLATE = """
당신은 사용자의 메시지를 아래의 JSON 형식으로 대화 내용을 주제별로 요약하는 기계입니다.
1. 주제는 구체적이며 의미가 있는 것이어야 합니다.
2. 요약 내용에는 '브라이언은...', '테오는...'처럼 대화자의 이름이 들어가야 합니다.
3. 원문을 최대한 유지하며 요약해야 합니다. 
4. 주제의 갯수는 무조건 5개를 넘지 말아야 하며 비슷한 내용은 하나로 묶어야 합니다. 
5. "```json"과 같은 부가 정보를 포함하지 않습니다.
```
{
    "data":
            [
                {"주제":<주제>, "요약":<요약>},
                {"주제":<주제>, "요약":<요약>},
            ]
}
"""

class MemoryManager:
    def __init__(self, **kwargs):
        self.user = kwargs['user']
        self.assistant = kwargs['assistant']

    def search_mongo_db(self, _id):
        search_result = mongo_memory_collection.find_one({'_id': int(_id)})
        print('search_result', search_result)
        return search_result['summary']
    
    def search_vector_db(self, message, vector_threshold=0.7):
        print('=' * 80)
        print('> [Vector DB 검색]')
        print(f'> 검색 메시지: {message}')
        
        query_vector = ( 
            client.embeddings.create(input=message, model=embedding_model).data[0].embedding
        )
        print(f'> 임베딩 벡터 생성 완료 (차원: {len(query_vector)})')
        
        results = pinecone_index.query(top_k=3, vector=query_vector, include_metadata=True)
        print(f'> 검색 결과 수: {len(results["matches"])}')
        
        # 임계값을 통과한 모든 후보 수집
        candidates = []
        for i, match in enumerate(results['matches'], 1):
            print(f'  [{i}] ID: {match["id"]}, Score: {match["score"]:.4f}')
            if 'metadata' in match:
                print(f'      메타데이터: {match["metadata"]}')
            
            if match['score'] > vector_threshold:
                candidates.append({'id': match['id'], 'score': match['score']})
                print(f'      → 벡터 임계값({vector_threshold}) 통과 ✓')
            else:
                print(f'      → 벡터 임계값({vector_threshold}) 미달 ✗')
        
        print(f'> 벡터 임계값 통과 후보 수: {len(candidates)}')
        print('=' * 80)
        return candidates
    
    def filter(self, message, memory, threshhold=0.6):
        print('=' * 80)
        print('> [질문과 대화 요약 간 유사도 계산]')
        print(f'> 질문: {message}')
        print(f'> 대화 요약: {memory[:200]}...' if len(memory) > 200 else f'> 대화 요약: {memory}')
        print(f'> 임계값(threshold): {threshhold}')
        
        try:
            response = client.responses.create(
                model=model.advanced,
                input=[
                    {'role': 'developer', 'content': MEASURING_SIMILARITY_SYSTEM_ROLE},
                    {'role': 'user',   'content': f'{{"statement1": "{message}", "statement2": "{memory}"}}'},
                ],
            )
            response_text = response.output_text
            print(f'> API 응답: {response_text}')
            
            prob = json.loads(response_text)['probability']
            print(f'> 계산된 유사도(probability): {prob}')
            print(f'> 임계값 통과 여부: {"통과 ✓" if prob >= threshhold else "실패 ✗"}')
            
        except Exception as e:
            print(f'> filter error: {e}')
            prob = 0
            print(f'> 에러로 인한 기본값 설정: {prob}')
        
        print('=' * 80)
        return prob >= threshhold

    def retrieve_memory(self, message):
        candidates = self.search_vector_db(message)
        if not candidates:
            print('> 벡터 검색 결과 없음')
            return None

        print(f'> {len(candidates)}개 후보에 대해 유사도 필터 검사 시작')
        
        # 모든 후보를 filter로 검사
        for i, candidate in enumerate(candidates, 1):
            print(f'\n> [후보 {i}/{len(candidates)}] ID: {candidate["id"]}, Vector Score: {candidate["score"]:.4f}')
            memory = self.search_mongo_db(candidate['id'])
            
            if self.filter(message, memory):
                print(f'> ✓ 최종 선택됨: ID={candidate["id"]}')
                return memory
            else:
                print(f'> ✗ 유사도 필터 통과 실패, 다음 후보 검사...')
        
        print('> 모든 후보가 유사도 필터를 통과하지 못함')
        return None

    def needs_memory(self, message):
        print('> needs_memory check for message:', message)
        try:
            response = client.responses.create(
                model=model.advanced, 
                input=NEEDS_MEMORY_TEMPLATE.format(message=message),
            )

            print('> needs_memory:', response.output_text)
            return (True if response.output_text.upper() == 'TRUE' else False)

        except Exception as e:
            print(f"> needs_memory error: {e}")
            return False

    def save_chat(self, context):      
        response_context = []  
        messages = []
        for message in context:
            if message.get('saved', True): 
                response_context.append(message)
            else:
                messages.append({'date': today(), 'role': message['role'], 'content': message['content']})
                message['saved'] = True
                response_context.append(message)
        try:
            if len(messages) > 0:           
                mongo_chats_collection.insert_many(messages)
        except Exception as e:
            pprint(e)
            return context

        return response_context

    def restore_chat(self, date=None):
        search_date = date if date is not None else today()        
        search_results = mongo_chats_collection.find({'date': search_date})
        restored_chat = [ {'role': v['role'], 'content': v['content'], 'saved': True} for v in search_results ]
        print(f"Restored {len(restored_chat)} messages from date {search_date}")
        return restored_chat
    
    def summarize(self, messages):
        altered_messages = [ 
            {
                f"{self.user if message['role'] == 'user' else self.assistant}": message['content'] 
            } for message in messages
        ]
        
        try:
            context = [ {'role': 'developer', 'content': SUMMARIZING_TEMPLATE},
                        {'role': 'user', 'content': json.dumps(altered_messages, ensure_ascii=False)} ]
            response = client.responses.create(
                model=model.basic,
                input=context,
            )
            print('> summarize:', response.output_text)
            return json.loads(response.output_text)['data']
        except Exception as e:
            print('> Exception:', e)
            return []

    def delete_by_date(self, date):
        search_results = mongo_chats_collection.find({'date': date})
        ids = [str(v['_id']) for v in search_results]
        if len(ids) == 0:
            return

        pinecone_index.delete(ids=ids)
        mongo_chats_collection.delete_many({'date': date})

    def save_to_memory(self, summaries, date):
        next_id = self.next_memory_id()

        for summary in summaries:
            vector = client.embeddings.create(
                input=summary['요약'], 
                model=embedding_model
            ).data[0].embedding
            metadata = {'date': date, 'keyword': summary['주제']}
            pinecone_index.upsert([(str(next_id), vector, metadata)])

            query = {'_id': next_id}  # 조회조건
            newvalues = {'$set': {'date': date, 'keyword': summary['주제'], 'summary': summary['요약']} }
            mongo_memory_collection.update_one(query, newvalues, upsert=True)
            next_id += 1

    def next_memory_id(self):
        result = mongo_memory_collection.find_one(sort=[('_id', -1)])
        return 1 if result is None else result['_id'] + 1

    def build_memory(self):
        print(f'build_memory started...')
        date = yesterday()
        #date = today()    # 테스트 용도

        memory_results = mongo_memory_collection.find({'date': date})
        if len(list(memory_results)) > 0:
            return

        chats_results = self.restore_chat(date)
        if len(list(chats_results)) == 0:
            return

        summaries = self.summarize(chats_results)    # 주제별 요약하기

        self.delete_by_date(date)                    # 날짜별 삭제하기

        self.save_to_memory(summaries, date)         # Database에 저장하기

