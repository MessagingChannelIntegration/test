import logging
import requests
from abc import ABC, abstractmethod
from flask import Flask, render_template
from flask_socketio import SocketIO
from collections import Counter
from kiwipiepy import Kiwi

# Kiwi 형태소 분석기 초기화
kiwi = Kiwi()

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# Abstract Base Class for Messaging Handlers
class MessagingServiceHandler(ABC):
    def __init__(self, api_key):
        self.api_key = api_key

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def fetch_messages(self):
        pass


# SlackHandler
class SlackHandler(MessagingServiceHandler):
    def __init__(self, api_key, channel_id):
        super().__init__(api_key)
        self.channel_id = channel_id

    def connect(self):
        url = "https://slack.com/api/auth.test"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json().get("ok"):
            logging.info("Slack 연결 성공!")
        else:
            logging.error(f"Slack 연결 실패: {response.json()}")

    def fetch_messages(self):
        url = f"https://slack.com/api/conversations.history?channel={self.channel_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json().get("ok"):
            messages = response.json().get("messages", [])
            return [
                {
                    "source": "Slack",
                    "id": f"{self.channel_id}_{msg['ts']}",
                    "timestamp": float(msg["ts"]),
                    "text": msg.get("text", "")
                }
                for msg in messages
            ]
        else:
            logging.error(f"Slack 메시지 가져오기 실패: {response.json()}")
            return []

class MessageManager:
    def __init__(self, handlers):
        self.handlers = handlers
        self.messages = []
        self.message_ids = set()

    def fetch_messages(self):
        new_messages = []
        for handler in self.handlers:
            try:
                fetched_messages = handler.fetch_messages()
                filtered_messages = [
                    msg for msg in fetched_messages if msg["id"] not in self.message_ids
                ]
                for message in filtered_messages:
                    self.add_message(message)
                    new_messages.append(message)
            except Exception as e:
                logging.error(f"Error fetching messages from {handler.__class__.__name__}: {e}")
        return new_messages

    def add_message(self, message):
        if message['id'] not in self.message_ids:
            self.messages.append(message)
            self.message_ids.add(message['id'])
            self.messages.sort(key=lambda x: x.get('timestamp', 0), reverse=True)


class KeywordAnalysisModule:
    def extract_nouns_and_count(self, messages):
        noun_counts = Counter()

        # 불필요한 단어 필터링
        stop_words = set([
            "중인데", "있어요", "있을까요", "싶습니다", "있으신가요", "분", "데", 
            "관련", "자료", "발표", "책", "하는", "에서", "고", "이", "그", 
            "및", "것", "중", "을", "로", "은", "는", "가", "도", "에", 
            "의", "들", "면", "대해", "방법", "내용", "어떻게", "왜", "더"
        ])

        for msg in messages:
            text = msg.get("text", "").strip()
            if not text or "<@" in text:  # 사용자 태그 제외
                continue

            # Kiwi를 이용한 명사 추출
            analysis = kiwi.analyze(text)[0][0]  # 첫 번째 분석 결과의 토큰 리스트
            nouns = [
                token.form for token in analysis
                if token.tag.startswith("N")  # 명사(NNG, NNP 등)
                and len(token.form) > 1  # 단어 길이가 1 이상
                and token.form not in stop_words
            ]
            noun_counts.update(nouns)

        # 내림차순으로 정렬된 딕셔너리 반환
        sorted_nouns = dict(sorted(noun_counts.items(), key=lambda x: x[1], reverse=True))
        return sorted_nouns



# Flask 앱 설정
app = Flask(__name__)
socketio = SocketIO(app)

import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 읽기
slack_api_key = os.getenv("SLACK_API_KEY")
if not slack_api_key:
    raise ValueError("환경 변수 'SLACK_API_KEY'가 설정되지 않았습니다.")


# 핸들러, 매니저, 분석 모듈 초기화
slack_handler = SlackHandler(api_key=slack_api_key, channel_id="C0853ENPA2Z")
message_manager = MessageManager(handlers=[slack_handler])
keyword_analyzer = KeywordAnalysisModule()


@app.route('/slack')
def slack():
    # Slack 메시지 필터링
    slack_messages = [msg for msg in message_manager.messages if msg["source"] == "Slack"]
    slack_keywords = keyword_analyzer.extract_nouns_and_count(slack_messages)
    return render_template('index.html', title="Slack Keywords", keywords=slack_keywords)

@socketio.on('connect')
def handle_connect():
    logging.info("Client connected.")


def background_fetch():
    while True:
        try:
            new_messages = message_manager.fetch_messages()
            if new_messages:
                logging.info(f"새로운 메시지: {[msg['text'] for msg in new_messages]}")
            socketio.sleep(10)
        except Exception as e:
            logging.error(f"Error during background fetch: {e}")


socketio.start_background_task(background_fetch)

if __name__ == '__main__':
    socketio.run(app, debug=True)

