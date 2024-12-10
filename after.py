from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from abc import ABC, abstractmethod
import requests
import time
import threading
from datetime import datetime
from bs4 import BeautifulSoup  # �� ��ũ������ ���� �߰�
import re
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
nltk.download('punkt')
nltk.download('stopwords')

class MessagingServiceHandler(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def fetch_messages(self):
        pass

# SlackHandler ����
class SlackHandler(MessagingServiceHandler):
    def __init__(self, api_key, channel_id):
        self.api_key = api_key
        self.channel_id = channel_id

    def connect(self):
        # Slack API ���� �׽�Ʈ
        url = "https://slack.com/api/auth.test"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json().get("ok"):
            print("Slack ���� ����!")
        else:
            raise Exception("Slack ���� ����:", response.json())

    def fetch_messages(self):
        # Ư�� ä���� �޽��� ��������
        url = f"https://slack.com/api/conversations.history?channel={self.channel_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json().get("ok"):
            messages = response.json().get("messages", [])
            for msg in messages:
                msg['source'] = 'Slack'
                msg['id'] = f"{self.channel_id}_{msg['ts']}"
                msg['timestamp'] = float(msg['ts'])
                msg['time'] = datetime.fromtimestamp(float(msg['ts'])).strftime('%Y-%m-%d %H:%M:%S')
            return messages
        else:
            raise Exception("Slack �޽��� �������� ����:", response.json())

# TelegramHandler ����
class TelegramHandler(MessagingServiceHandler):
    def __init__(self, api_key, chat_id):
        self.api_key = api_key
        self.chat_id = chat_id

    def connect(self):
        # Telegram API ���� �׽�Ʈ
        url = f"https://api.telegram.org/bot{self.api_key}/getMe"
        response = requests.get(url)
        if response.status_code == 200 and response.json().get("ok"):
            print("Telegram ���� ����!")
        else:
            raise Exception("Telegram ���� ����:", response.json())

    def fetch_messages(self):
        # Ư�� ä���� �޽��� ��������
        url = f"https://api.telegram.org/bot{self.api_key}/getUpdates"
        response = requests.get(url)
        if response.status_code == 200:
            updates = response.json().get("result", [])
            messages = [update["message"] for update in updates if "message" in update]
            for msg in messages:
                msg['source'] = 'Telegram'
                msg['id'] = f"{msg['chat']['id']}_{msg['message_id']}"
                msg['timestamp'] = float(msg['date'])
                msg['time'] = datetime.fromtimestamp(float(msg['date'])).strftime('%Y-%m-%d %H:%M:%S')
            return [{"text": msg.get("text", ""), "source": msg.get("source", ""), "id": msg.get("id", ""), "timestamp": msg.get("timestamp", 0.0), "time": msg.get("time", "") } for msg in messages if msg.get("chat", {}).get("id") == self.chat_id]
        else:
            raise Exception("Telegram �޽��� �������� ����:", response.json())
        
        
class Observer(ABC):
    @abstractmethod
    def update(self, message):
        pass

# ��ü���� ������ (�˸� �ý���)
class NotificationObserver(Observer):
    def update(self, message):
        source = message.get('source', 'Unknown')
        print(f"[{source}] �� �޽��� �˸�: {message}")
        

