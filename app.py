from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from common import model
from chatbot import Chatbot
from characters import developer_role, instruction, function_instruction

app = Flask(__name__)
CORS(app)

# 전역 챗봇 인스턴스 (상태를 저장하지 않으므로 하나만 있으면 됨)
chatbot = Chatbot(model, developer_role, instruction, function_instruction)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
