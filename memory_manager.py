
import os
from pprint import pprint
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from common import today
# dotenv 설정 로드
from dotenv import load_dotenv
load_dotenv()

uri = os.getenv("MONGO_CLUSTER_URI")

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
mongo_chats_collection = client['OPENAI_AGENT_CHAT']['chats']

class MemoryManager:

    def save_chat(self, context):        
        messages = []
        for message in context:
            if message.get('saved', True): 
                continue
            messages.append({'date': today(), 'role': message['role'], 'content': message['content']})
        try:
            if len(messages) > 0:           
                mongo_chats_collection.insert_many(messages)
        except Exception as e:
            pprint(e)
            return
        msgs = []
        for message in messages:
            print(message)
            message['saved'] = True
            msgs.append(message)
        return msgs

    def restore_chat(self, date=None):
        search_date = date if date is not None else today()        
        search_results = mongo_chats_collection.find({'date': search_date})
        restored_chat = [ {'role': v['role'], 'content': v['content'], 'saved': True} for v in search_results ]
        print(f"Restored {len(restored_chat)} messages from date {search_date}")
        return restored_chat