import logging
import requests
from abc import ABC, abstractmethod
from flask import Flask, render_template
from flask_socketio import SocketIO
from collections import Counter
from kiwipiepy import Kiwi
from dotenv import load_dotenv
import os

# 초기 설정
logging.basicConfig(level=logging.INFO)
kiwi = Kiwi()
app = Flask(__name__)
socketio = SocketIO(app)
load_dotenv()

# 환경 변수 읽기
slack_api_key = os.getenv("SLACK_API_KEY")
news_api_key = os.getenv("NEWS_API_KEY")
telegram_api_key = os.getenv("TELEGRAM_API_KEY")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

if not slack_api_key:
    raise ValueError("환경 변수 'SLACK_API_KEY'가 설정되지 않았습니다.")
if not news_api_key:
    raise ValueError("환경 변수 'NEWS_API_KEY'가 설정되지 않았습니다.")
if not telegram_api_key:
    raise ValueError("환경 변수 'TELEGRAM_API_KEY'가 설정되지 않았습니다.")
if not telegram_chat_id:
    raise ValueError("환경 변수 'TELEGRAM_CHAT_ID'가 설정되지 않았습니다.")

# 불용어 리스트
def get_stop_words():
    return set([
        "중인데", "있어요", "있을까요", "싶습니다", "있으신가요", "분", "데", 
        "관련", "자료", "하는", "에서", "고", "이", "그", 
        "및", "것", "중", "을", "로", "은", "는", "가", "도", "에", 
        "의", "들", "면", "대해", "방법", "내용", "어떻게", "왜", "더", "무엇"
    ])

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

# TelegramHandler
class TelegramHandler(MessagingServiceHandler):
    def __init__(self, api_key, chat_id):
        super().__init__(api_key)
        self.chat_id = chat_id
        self.offset = None

    def connect(self):
        url = f"https://api.telegram.org/bot{self.api_key}/getMe"
        response = requests.get(url)
        if response.status_code == 200 and response.json().get("ok"):
            logging.info("Telegram 연결 성공!")
        else:
            logging.error(f"Telegram 연결 실패: {response.json()}")

    def fetch_messages(self):
        url = f"https://api.telegram.org/bot{self.api_key}/getUpdates"
        if self.offset:
            url += f"?offset={self.offset}"
        response = requests.get(url)
        if response.status_code == 200:
            updates = response.json().get("result", [])
            messages = [update["message"] for update in updates if "message" in update]
            if updates:
                self.offset = updates[-1]['update_id'] + 1
            return [
                {
                    "source": "Telegram",
                    "id": f"{msg['chat']['id']}_{msg['message_id']}",
                    "timestamp": float(msg["date"]),
                    "text": msg.get("text", ""),
                    "user": msg.get("from", {}).get("username", "Unknown User")
                }
                for msg in messages if msg.get("chat", {}).get("id") == int(self.chat_id)
            ]
        else:
            logging.error(f"Telegram 메시지 가져오기 실패: {response.json()}")
            return []

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
                    "text": msg.get("text", ""),
                    "user": msg.get("user", "Unknown User")
                }
                for msg in messages
            ]
        else:
            logging.error(f"Slack 메시지 가져오기 실패: {response.json()}")
            return []

# Message Manager
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

# 키워드 분석 모듈
class KeywordAnalysisModule:
    def extract_nouns_and_count(self, messages):
        stop_words = get_stop_words()
        noun_counts = Counter()
        for msg in messages:
            text = msg.get("text", "").strip()
            if not text or "<@" in text:
                continue
            analysis = kiwi.analyze(text)[0][0]
            nouns = [
                token.form for token in analysis
                if token.tag.startswith("N")
                and len(token.form) > 1
                and token.form not in stop_words
            ]
            noun_counts.update(nouns)
        return dict(sorted(noun_counts.items(), key=lambda x: x[1], reverse=True))

# 사용자별 키워드 분석
class UserKeywordAnalysis:
    def analyze_user_keywords(self, messages):
        user_keywords = {}
        stop_words = get_stop_words()
        for msg in messages:
            user_id = msg.get("user", "Unknown User")
            text = msg.get("text", "").strip()
            if not text:
                continue
            analysis = kiwi.analyze(text)[0][0]
            nouns = [
                token.form for token in analysis
                if token.tag.startswith("N")
                and len(token.form) > 1
                and token.form not in stop_words
            ]
            if user_id not in user_keywords:
                user_keywords[user_id] = Counter()
            user_keywords[user_id].update(nouns)
        return {user: dict(sorted(keywords.items(), key=lambda x: x[1], reverse=True))
                for user, keywords in user_keywords.items()}

# 뉴스 검색 모듈
class NewsFetcher:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"

    def fetch_news(self, query, max_articles=5):
        params = {
            "q": query,
            "language": "ko",
            "sortBy": "relevancy",
            "apiKey": self.api_key
        }
        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            return articles[:max_articles]
        else:
            logging.error(f"뉴스 API 요청 실패: {response.json()}")
            return []

@app.route('/slack_user_keywords')
def slack_user_keywords():
    slack_messages = [msg for msg in message_manager.messages if msg["source"] == "Slack"]
    user_keywords = UserKeywordAnalysis().analyze_user_keywords(slack_messages)
    return render_template('user_keywords.html', user_data=user_keywords)

@app.route('/slack_newslist')
def slack_newslist():
    slack_messages = [msg for msg in message_manager.messages if msg["source"] == "Slack"]
    user_keywords = UserKeywordAnalysis().analyze_user_keywords(slack_messages)
    personalized_news = fetch_personalized_news_with_keywords(user_keywords)
    return render_template('user_newslist.html', title="Slack Personalized News", user_news=personalized_news)

@app.route('/telegram_user_keywords')
def telegram_user_keywords():
    telegram_messages = [msg for msg in message_manager.messages if msg["source"] == "Telegram"]
    user_keywords = UserKeywordAnalysis().analyze_user_keywords(telegram_messages)
    return render_template('user_keywords.html', user_data=user_keywords)

@app.route('/telegram_newslist')
def telegram_newslist():
    telegram_messages = [msg for msg in message_manager.messages if msg["source"] == "Telegram"]
    user_keywords = UserKeywordAnalysis().analyze_user_keywords(telegram_messages)
    personalized_news = fetch_personalized_news_with_keywords(user_keywords)
    return render_template('user_newslist.html', title="Telegram Personalized News", user_news=personalized_news)

def fetch_personalized_news_with_keywords(user_keywords, max_articles=3):
    personalized_news = {}
    for user, keywords in user_keywords.items():
        top_keywords = list(keywords.keys())[:3]
        articles = []
        for keyword in top_keywords:
            articles.extend(news_fetcher.fetch_news(keyword, max_articles=max_articles))
        personalized_news[user] = {"keywords": top_keywords, "articles": articles}
    return personalized_news

# 실시간 백그라운드 작업
def background_fetch():
    while True:
        try:
            new_messages = message_manager.fetch_messages()
            if new_messages:
                logging.info(f"새로운 메시지: {[msg['text'] for msg in new_messages]}")
                slack_messages = [msg for msg in message_manager.messages if msg["source"] == "Slack"]
                telegram_messages = [msg for msg in message_manager.messages if msg["source"] == "Telegram"]
                updated_slack_keywords = keyword_analyzer.extract_nouns_and_count(slack_messages)
                updated_telegram_keywords = keyword_analyzer.extract_nouns_and_count(telegram_messages)
                socketio.emit('update_keywords', {
                    'slack': updated_slack_keywords,
                    'telegram': updated_telegram_keywords
                })
            socketio.sleep(10)
        except Exception as e:
            logging.error(f"Error during background fetch: {e}")

# 초기화
slack_handler = SlackHandler(api_key=slack_api_key, channel_id="C0853ENPA2Z")
telegram_handler = TelegramHandler(api_key=telegram_api_key, chat_id=telegram_chat_id)
message_manager = MessageManager(handlers=[slack_handler, telegram_handler])
keyword_analyzer = KeywordAnalysisModule()
news_fetcher = NewsFetcher(api_key=news_api_key)
socketio.start_background_task(background_fetch)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
