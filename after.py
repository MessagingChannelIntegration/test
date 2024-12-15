import logging
import requests
from abc import ABC, abstractmethod
from utils import handle_error, format_timestamp
from flask import Flask, render_template
from flask_socketio import SocketIO
from sklearn.feature_extraction.text import TfidfVectorizer
import nltk
from collections import defaultdict
import threading

# NLTK 데이터 다운로드
nltk.download('stopwords')
nltk.download('punkt')
nltk.download('wordnet')
from nltk.stem import WordNetLemmatizer

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)


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
            handle_error("Slack", response)

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
                    "time": format_timestamp(msg["ts"]),
                    "text": msg.get("text", "")
                }
                for msg in messages
            ]
        else:
            handle_error("Slack", response)


# TelegramHandler
class TelegramHandler(MessagingServiceHandler):
    def __init__(self, api_key, chat_id):
        super().__init__(api_key)
        self.chat_id = chat_id
        self.offset = None  # 메시지 오프셋 추가

    def connect(self):
        url = f"https://api.telegram.org/bot{self.api_key}/getMe"
        response = requests.get(url)
        if response.status_code == 200 and response.json().get("ok"):
            logging.info("Telegram 연결 성공!")
        else:
            handle_error("Telegram", response)

    def fetch_messages(self):
        url = f"https://api.telegram.org/bot{self.api_key}/getUpdates"
        if self.offset:
            url += f"?offset={self.offset}"
        response = requests.get(url)
        if response.status_code == 200:
            updates = response.json().get("result", [])
            messages = [update["message"] for update in updates if "message" in update]
            filtered_messages = [
                {
                    "source": "Telegram",
                    "id": f"{msg['chat']['id']}_{msg['message_id']}",
                    "timestamp": float(msg["date"]),
                    "time": format_timestamp(msg["date"]),
                    "text": msg.get("text", "")
                }
                for msg in messages if msg.get("chat", {}).get("id") == self.chat_id
            ]
            if updates:
                self.offset = updates[-1]['update_id'] + 1  # 마지막 메시지 ID 업데이트
            if not filtered_messages:
                logging.info(f"No messages found for chat_id {self.chat_id}")
            return filtered_messages
        else:
            handle_error("Telegram", response)


class MessageManager:
    def __init__(self, handlers):
        self.handlers = handlers
        self.messages = []
        self.message_ids = set()
        self.subscribers = []

    def fetch_messages(self):
        for handler in self.handlers:
            try:
                new_messages = handler.fetch_messages()
                for message in new_messages:
                    self.add_message(message)
            except Exception as e:
                logging.error(f"Error fetching messages from {handler.__class__.__name__}: {e}")

    def add_message(self, message):
        if message['id'] not in self.message_ids:
            self.messages.append(message)
            self.message_ids.add(message['id'])
            self.messages.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            self.notify_subscribers(message)

    def subscribe(self, observer):
        self.subscribers.append(observer)

    def notify_subscribers(self, message):
        for subscriber in self.subscribers:
            subscriber.update(message)

    def get_messages(self, count=5):
        return self.messages[:count]


class KeywordAnalysisModule:
    def __init__(self):
        self.stop_words = set(nltk.corpus.stopwords.words('english'))
        self.lemmatizer = WordNetLemmatizer()
        self.vectorizer = TfidfVectorizer(stop_words='english')

    def preprocess_text(self, text):
        tokens = nltk.word_tokenize(text.lower())
        filtered_tokens = [self.lemmatizer.lemmatize(word) for word in tokens if word.isalnum() and word not in self.stop_words]
        return ' '.join(filtered_tokens)

    def extract_keywords(self, messages):
        processed_texts = [self.preprocess_text(msg['text']) for msg in messages]
        tfidf_matrix = self.vectorizer.fit_transform(processed_texts)
        feature_names = self.vectorizer.get_feature_names_out()
        scores = tfidf_matrix.sum(axis=0).A1
        keyword_scores = {feature_names[i]: scores[i] for i in range(len(feature_names))}
        return keyword_scores


class RecommendationService:
    def __init__(self, keyword_analyzer, socketio):
        self.keyword_analyzer = keyword_analyzer
        self.socketio = socketio
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
        
        # 추천 생성
        recommendations = self._generate_recommendations(user_keywords)

        # 실시간으로 추천 결과 전송
        self.socketio.emit('recommendations', {'data': recommendations})

    def _generate_recommendations(self, user_keywords):
        """
        관심 키워드를 기반으로 추천 목록 생성
        """
        recommendations = []
        for platform, channels in self.recommendations.items():
            for channel in channels:
                score = len(set(user_keywords.keys()) & set(channel["keywords"]))
                if score > 0:
                    recommendations.append({"name": channel["name"], "source": platform, "score": score})
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations



app = Flask(__name__)
socketio = SocketIO(app)

"""slack_handler = SlackHandler(api_key="", channel_id="")
telegram_handler = TelegramHandler(api_key="", chat_id="")
message_manager = MessageManager(handlers=[slack_handler, telegram_handler])"""

keyword_analyzer = KeywordAnalysisModule()
recommendation_service = RecommendationService(keyword_analyzer, socketio)

message_manager.subscribe(recommendation_service)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    logging.info("Client connected.")

def background_fetch():
    while True:
        message_manager.fetch_messages()
        socketio.sleep(10)  # 10초마다 메시지 갱신

socketio.start_background_task(background_fetch)

if __name__ == '__main__':
    socketio.run(app, debug=True)
