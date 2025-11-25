import atexit
from flask import Flask, render_template, request, jsonify, g
from flask_cors import CORS
import os
from common import model
from chatbot import Chatbot
from characters import developer_role, instruction
# dotenv 설정 로드
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

# 전역 챗봇 인스턴스 (상태를 저장하지 않으므로 하나만 있으면 됨)
# api_type 파라미터 추가: "responses" (기본값) 또는 "assistant" 선택 가능
# assistant_id: 기존 Assistant를 사용할 경우 ID 지정
chatbot = Chatbot(
    model=model, 
    developer_role=developer_role, 
    instruction=instruction, 
    user='브라이언', 
    assistant='테오',
    api_type="assistant",
    #api_type="responses"  # "responses" 또는 "assistant" 선택
    # assistant_id="asst_xxx"  # Assistant API 사용 시 기존 Assistant ID (선택사항)
)

@app.route("/")
def index():
    return render_template("chat.html")

@app.post("/chat")
def chat():
    data = request.get_json(force=True)
    message = (data or {}).get("message", "").strip()
    previous_response_id = (data or {}).get("previous_response_id")
    
    if not message:
        return jsonify({"ok": False, "error": "메시지를 입력해주세요."}), 400
    
    # 챗봇으로 메시지 처리
    resp = chatbot.chat(message, previous_response_id)
    
    try:
        reply = resp.output[-1].content[0].text
        response_id = getattr(resp, 'id', None)  # OpenAI API 스타일로 id 사용
    except Exception:
        reply = "[테오] 응답 처리 중 문제가 발생했습니다."
        response_id = None
    
    return jsonify({
        "ok": True, 
        "reply": reply,
        "response_id": response_id
    })

@atexit.register
def shutdown():
    """서버 종료 시 대화 내용 저장"""
    try:
        chatbot.save_chat()
        print("Chat history saved on shutdown.")
    except Exception:
       import traceback; traceback.print_exc()

@app.teardown_appcontext
def _persist_on_teardown(exc):
    # 너무 자주 쓰기 싫다면 내부에서 'dirty' 플래그로 조건부 저장
    try:
        chatbot.save_chat()
        print("Chat history saved on teardown.")
    except Exception:
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5070")), debug=True)
