from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re

# Firebase 초기화
cred = credentials.Certificate("highschool-chatbot-firebase-adminsdk-fbsvc-104e944d53.py")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)

# ✅ 자연어 처리: 질문에서 의미 있는 단어 추출
def extract_keywords(text):
    # 한글 2글자 이상 단어 추출 (간단한 명사 필터링)
    return re.findall(r"[가-힣]{2,}", text)

# ✅ 공지사항 크롤링
def crawl_haseong_notices():
    url = "https://school.gyo6.net/haseong-h/board/notice"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    notices = []
    notice_items = soup.select(".board_list li a")

    for item in notice_items:
        title = item.text.strip()
        link = item.get("href")
        full_link = f"https://school.gyo6.net{link}" if link.startswith("/") else link
        notices.append({
            "title": title,
            "link": full_link
        })

    return notices

# ✅ 질문 저장 + 자동 답변
@app.route("/ask", methods=["POST"])
def handle_question():
    data = request.json
    question = data.get("question")

    # 질문 저장
    doc_ref = db.collection("questions").add({
        "question": question,
        "timestamp": datetime.now().isoformat()
    })

    # 공지사항 크롤링
    notices = crawl_haseong_notices()

    # 질문에서 키워드 추출
    keywords = extract_keywords(question)

    # 공지 제목과 키워드 비교
    related = [n for n in notices if any(k in n["title"] for k in keywords)]

    # 자동 답변 생성
    if related:
        answer_text = "관련 공지사항이 있어요:\n" + "\n".join(
            [f"- {n['title']}: {n['link']}" for n in related]
        )
        db.collection("questions").document(doc_ref.id).update({
            "answer": answer_text,
            "answered_at": datetime.now().isoformat()
        })

    return jsonify({"message": "질문이 저장되었습니다. 관련 정보가 있으면 자동으로 답변됩니다."})

# ✅ 질문 + 답변 목록 조회
@app.route("/get_answers", methods=["GET"])
def get_answers():
    docs = db.collection("questions").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    result = []
    for doc in docs:
        item = doc.to_dict()
        item["id"] = doc.id
        result.append(item)
    return jsonify(result)

# ✅ 기본 페이지
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
