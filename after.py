import logging
import requests
import threading
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


class ChannelRepository:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance.channels = []  # Top 5 채널 저장
                    cls._instance.observers = []  # 옵저버 리스트
        return cls._instance

    def add_observer(self, observer):
        """옵저버 추가"""
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer):
        """옵저버 제거"""
        if observer in self.observers:
            self.observers.remove(observer)

    def notify_observers(self):
        """옵저버들에게 알림"""
        for observer in self.observers:
            observer.update_channels(self.channels)

    def update_channels(self, new_channels):
        # 새로운 채널로 업데이트 (키워드 점수 기준 상위 5개 선택)
        self.channels = sorted(new_channels, key=lambda x: x['score'], reverse=True)[:5]

    def get_channels(self):
        # 현재 채널 목록 반환
        return self.channels

class RecommendationService ():
    def __init__(self, keyword_analyzer, socketio):
        self.keyword_analyzer = keyword_analyzer
        self.socketio = socketio
        self.channel_repository = ChannelRepository()
        
        # RecommendationService를 옵저버로 등록
        self.channel_repository.add_observer(self)

        self.recommendations = {
            "Slack": [
                {"name": "AI Research Group", "keywords": ["AI", "machine learning", "research"]},
                {"name": "Python Developers", "keywords": ["Python", "programming", "developers"]},
            ],
            "Telegram": [
                {"name": "Deep Learning Bot", "keywords": ["deep learning", "neural networks", "AI"]},
                {"name": "Tech News Channel", "keywords": ["technology", "news", "innovation"]},
            ],
        }

    def update(self, message):
        """
        
        새로운 메시지가 추가되었을 때 호출됩니다.
        메시지를 분석하고 추천 결과를 실시간으로 전송합니다.

        """
        # 관심 키워드 추출
        user_keywords = self.keyword_analyzer.extract_keywords([message])
        
        # 싱글톤 클래스에서 현재 채널 정보 가져오기
        current_channels = self.channel_repository.get_channels()

        # 사용자 키워드를 기반으로 추천 채널 목록 생성
        recommendations = self._generate_recommendations(user_keywords, current_channels)

        # 싱글톤 클래스에 업데이트된 채널 저장 (Top 5만)
        self.channel_repository.update_channels(recommendations)

        # 클라이언트로 실시간 추천 결과 전송
        self.socketio.emit('recommendations', {'data': recommendations})
        
        # 추천 생성
        recommendations = self._generate_recommendations(user_keywords)

    def _generate_recommendations(self, user_keywords, current_channels):
        """
        관심 키워드를 기반으로 추천 목록 생성
        """
        recommendations = []

        # 현재 관리 중인 채널 데이터를 순회하며 점수 계산
        for channel in current_channels:
            score = len(set(user_keywords.keys()) & set(channel.get("keywords", [])))
            if score > 0:
                recommendations.append(
                    {
                        "name": channel["name"],
                        "source": channel["source"],
                        "score": score,
                    }
                )

        # for platform, channels in self.recommendations.items():
        #     for channel in channels:
        #         score = len(set(user_keywords.keys()) & set(channel["keywords"]))
        #         if score > 0:
        #             recommendations.append({"name": channel["name"], "source": platform, "score": score})
        # recommendations.sort(key=lambda x: x["score"], reverse=True)

         # 점수 기준으로 정렬 후 반환
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations
    

# Flask 앱 설정
app = Flask(__name__)
socketio = SocketIO(app)
keyword_analyzer = KeywordAnalysisModule()
recommendation_service = RecommendationService(keyword_analyzer, socketio)

# 테스트: 채널 업데이트 시 옵저버 알림
channel_repo = ChannelRepository()

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
# recommendation_service = RecommendationService(keyword_analyzer, socketio)

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
