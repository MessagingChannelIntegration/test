from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from abc import ABC, abstractmethod
import requests
import time
import threading
from datetime import datetime

# Flask 및 SocketIO 설정
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 공통 인터페이스 정의
class MessagingServiceHandler(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def fetch_messages(self):
        pass

# SlackHandler 구현
class SlackHandler(MessagingServiceHandler):
    def __init__(self, api_key, channel_id):
        self.api_key = api_key
        self.channel_id = channel_id

    def connect(self):
        # Slack API 연결 테스트
        url = "https://slack.com/api/auth.test"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json().get("ok"):
            print("Slack 연결 성공!")
        else:
            raise Exception("Slack 연결 실패:", response.json())

    def fetch_messages(self):
        # 특정 채널의 메시지 가져오기
        url = f"https://slack.com/api/conversations.history?channel={self.channel_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json().get("ok"):
            messages = response.json().get("messages", [])
            for msg in messages:
                msg['source'] = 'Slack'  # 출처 정보 추가
                msg['id'] = f"{self.channel_id}_{msg['ts']}"  # 메시지의 고유 ID로 채널 ID와 'ts' 조합 사용
                msg['timestamp'] = float(msg['ts'])  # 타임스탬프를 정렬에 사용하기 위해 추가
                msg['time'] = datetime.fromtimestamp(float(msg['ts'])).strftime('%Y-%m-%d %H:%M:%S')  # 사람이 읽을 수 있는 형식의 시간 추가
            return messages
        else:
            raise Exception("Slack 메시지 가져오기 실패:", response.json())

# TelegramHandler 구현
class TelegramHandler(MessagingServiceHandler):
    def __init__(self, api_key, chat_id):
        self.api_key = api_key
        self.chat_id = chat_id

    def connect(self):
        # Telegram API 연결 테스트
        url = f"https://api.telegram.org/bot{self.api_key}/getMe"
        response = requests.get(url)
        if response.status_code == 200 and response.json().get("ok"):
            print("Telegram 연결 성공!")
        else:
            raise Exception("Telegram 연결 실패:", response.json())

    def fetch_messages(self):
        # 특정 채팅의 메시지 가져오기
        url = f"https://api.telegram.org/bot{self.api_key}/getUpdates"
        response = requests.get(url)
        if response.status_code == 200:
            updates = response.json().get("result", [])
            messages = [update["message"] for update in updates if "message" in update]
            for msg in messages:
                msg['source'] = 'Telegram'  # 출처 정보 추가
                msg['id'] = f"{msg['chat']['id']}_{msg['message_id']}"  # 메시지의 고유 ID로 'chat_id'와 'message_id' 조합 사용
                msg['timestamp'] = float(msg['date'])  # 타임스탬프를 정렬에 사용하기 위해 추가
                msg['time'] = datetime.fromtimestamp(float(msg['date'])).strftime('%Y-%m-%d %H:%M:%S')  # 사람이 읽을 수 있는 형식의 시간 추가
            return [{"text": msg.get("text", ""), "source": msg.get("source", ""), "id": msg.get("id", ""), "timestamp": msg.get("timestamp", 0.0), "time": msg.get("time", "") } for msg in messages if msg.get("chat", {}).get("id") == self.chat_id]
        else:
            raise Exception("Telegram 메시지 가져오기 실패:", response.json())

# Observer 인터페이스 정의
class Observer(ABC):
    @abstractmethod
    def update(self, message):
        pass

# 구체적인 관찰자 (알림 시스템)
class NotificationObserver(Observer):
    def update(self, message):
        source = message.get('source', 'Unknown')  # 출처 정보 사용
        print(f"[{source}] 새 메시지 알림: {message}")

# MessagingServiceManager (핸들러를 통합 관리)
class MessagingServiceManager:
    def __init__(self, handler: MessagingServiceHandler):
        self.handler = handler

    def process_messages(self):
        self.handler.connect()
        return self.handler.fetch_messages()

# MessageManager (주체, Subject 역할)
class MessageManager:
    def __init__(self):
        self.messages = []
        self.message_ids = set()  # 중복 메시지 방지를 위한 메시지 ID 집합
        self.subscribers = []

    def add_message(self, message):
        if message['id'] not in self.message_ids:
            self.messages.append(message)
            self.message_ids.add(message['id'])
            self.messages.sort(key=lambda x: x.get('timestamp', 0), reverse=True)  # 타임스탬프를 기준으로 내림차순 정렬
            self.notify_subscribers(message)  # 새로운 메시지를 추가할 때 관찰자에게 알림
            notify_new_message(message)  # 실시간 웹 알림

    def subscribe(self, observer):
        self.subscribers.append(observer)

    def notify_subscribers(self, message):
        for subscriber in self.subscribers:
            subscriber.update(message)

    def get_messages(self, count=5):
        return self.messages[:count]  # 최신 'count'개의 메시지만 반환

    def get_all_messages(self):
        return self.messages  # 모든 메시지를 반환

# 새 메시지를 실시간으로 브라우저에 전송
def notify_new_message(message):
    print(f"Sending message to clients: {message}")  # 디버깅을 위해 메시지 전송 로그 추가
    socketio.emit('new_message', {'text': message.get('text', ''), 'source': message.get('source', 'Unknown'), 'time': message.get('time', '')}, namespace='/')

# FrontendVisualizer 클래스 정의
class FrontendVisualizer:
    def __init__(self, message_manager):
        self.message_manager = message_manager

    def render_html(self):
        messages = self.message_manager.get_all_messages()
        load_more_button_visible = len(messages) > 5
        html_template = """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
            <title>Messaging Dashboard</title>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
            <script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
            <script type="text/javascript">
              document.addEventListener("DOMContentLoaded", function() {
                  var socket = io();
                  socket.on("connect", function() {
                      console.log("Connected to server");
                  });
                  socket.on("new_message", function(data) {
                      console.log("New message received:", data);
                      var messageList = document.getElementById("message-list");
                      var newItem = document.createElement("li");
                      newItem.className = "list-group-item";
                      newItem.innerHTML = "<strong>[" + data.source + "]</strong> " + data.text + " <span class='float-right'>" + data.time + "</span>";
                      messageList.insertBefore(newItem, messageList.firstChild);
                      if (messageList.children.length > 5) {
                          messageList.children[5].style.display = "none";
                          messageList.children[5].classList.add("hidden-message");
                      }
                      updateLoadMoreButton();
                  });
                  updateLoadMoreButton();
              });

              function loadMoreMessages() {
                  const allMessages = document.getElementsByClassName("hidden-message");
                  let count = 0;
                  for (let i = 0; i < allMessages.length; i++) {
                      if (allMessages[i].style.display === "none" && count < 5) {
                          allMessages[i].style.display = "list-item";
                          count++;
                      }
                  }
                  updateLoadMoreButton();
              }

              function collapseMessages() {
                  const allMessages = document.getElementsByClassName("hidden-message");
                  for (let i = 0; i < allMessages.length; i++) {
                      allMessages[i].style.display = "none";
                  }
                  updateLoadMoreButton();
              }

              function updateLoadMoreButton() {
                  const allMessages = document.getElementsByClassName("hidden-message");
                  let hiddenCount = 0;
                  for (let i = 0; i < allMessages.length; i++) {
                      if (allMessages[i].style.display === "none") {
                          hiddenCount++;
                      }
                  }
                  const loadMoreButton = document.getElementById("load-more-button");
                  const collapseButton = document.getElementById("collapse-button");
                  if (hiddenCount === 0) {
                      if (loadMoreButton) loadMoreButton.style.display = "none";
                      if (collapseButton) collapseButton.style.display = "block";
                  } else {
                      if (loadMoreButton) loadMoreButton.style.display = "block";
                      if (collapseButton) collapseButton.style.display = "none";
                  }
              }
            </script>
          </head>
          <body>
            <div class="container">
              <h1 class="mt-5">Messages</h1>
              <ul id="message-list" class="list-group mt-3">
                {% for message in messages[:5] %}
                  <li class="list-group-item">
                    <strong>[{{ message['source'] }}]</strong> {{ message['text'] }} <span class='float-right'>{{ message['time'] }}</span>
                  </li>
                {% endfor %}
                {% for message in messages[5:] %}
                  <li class="list-group-item hidden-message" style="display: none;">
                    <strong>[{{ message['source'] }}]</strong> {{ message['text'] }} <span class='float-right'>{{ message['time'] }}</span>
                  </li>
                {% endfor %}
              </ul>
              {% if load_more_button_visible %}
                <button id="load-more-button" class="btn btn-primary mt-3" onclick="loadMoreMessages()">더보기 ↓</button>
                <button id="collapse-button" class="btn btn-secondary mt-3" onclick="collapseMessages()" style="display: none;">접기 ↑</button>
              {% endif %}
            </div>
          </body>
        </html>
        """
        return render_template_string(html_template, messages=messages, load_more_button_visible=load_more_button_visible)

# Slack 및 Telegram 핸들러 설정 및 메시지 추가
message_manager = MessageManager()
notifier = NotificationObserver()
message_manager.subscribe(notifier)

frontend_visualizer = FrontendVisualizer(message_manager)

slack_handler = SlackHandler(api_key="xoxb-8074700828402-8087394180673-Lk6nBqmP71Jn1a4isCY6PmyB", channel_id="C0826LNBL7L")
slack_manager = MessagingServiceManager(slack_handler)

telegram_handler = TelegramHandler(api_key="7561927766:AAGe1SfBg3Ab7Pgps1kMWiG3RAtpZtLKIN0", chat_id=7848217593)
telegram_manager = MessagingServiceManager(telegram_handler)

# Slack 메시지 주기적 폴링 추가
def poll_slack_messages():
    while True:
        time.sleep(10)  # 10초마다 폴링
        new_messages = slack_manager.process_messages()
        for message in new_messages:
            message_manager.add_message(message)

# 스레드에서 Slack 메시지 폴링 시작
threading.Thread(target=poll_slack_messages, daemon=True).start()

# Telegram 메시지 주기적 폴링 추가
def poll_telegram_messages():
    while True:
        time.sleep(10)  # 10초마다 폴링
        new_messages = telegram_manager.process_messages()
        for message in new_messages:
            message_manager.add_message(message)

threading.Thread(target=poll_telegram_messages, daemon=True).start()

# Flask 라우트 설정
@app.route('/')
def display_messages():
    return frontend_visualizer.render_html()

# Flask-SocketIO 실행
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
