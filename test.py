from abc import ABC, abstractmethod
import requests

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
            return [{"text": msg.get("text", ""), "source": msg.get("source", "")} for msg in messages if msg.get("chat", {}).get("id") == self.chat_id]
        else:
            raise Exception("Telegram 메시지 가져오기 실패:", response.json())

# MessagingServiceManager (핸들러를 통합 관리)
class MessagingServiceManager:
    def __init__(self, handler: MessagingServiceHandler):
        self.handler = handler

    def process_messages(self):
        self.handler.connect()
        return self.handler.fetch_messages()

# 관찰자(Observer) 인터페이스
class Observer:
    def update(self, message):
        pass

# 구체적인 관찰자 (알림 시스템)
class NotificationObserver(Observer):
    def update(self, message):
        preview = message.get('text', '')[:20]  # 메시지 앞부분 20글자만 추출
        source = message.get('source', 'Unknown')  # 출처 정보 사용
        print(f"[{source}] 새 메시지 알림: {preview}...")
        
# MessageManager (주체, Subject 역할)
class MessageManager:
    def __init__(self):
        self.messages = []
        self.subscribers = []  # 관찰자 리스트

    def add_message(self, message):
        self.messages.append(message)
        self.notify_subscribers(message)

    def subscribe(self, observer: Observer):
        self.subscribers.append(observer)

    def notify_subscribers(self, message):
        for subscriber in self.subscribers:
            subscriber.update(message)

    def get_messages(self):
        return self.messages

# FrontendVisualizer 정의
class FrontendVisualizer:
    def __init__(self, message_manager):
        self.message_manager = message_manager

    def renderHTML(self):
        messages = self.message_manager.get_messages()
        html = "<html><body><h1>Messages</h1><ul>"
        for message in messages:
            html += f"<li>{message.get('text', 'No text')}</li>"
        html += "</ul></body></html>"
        return html

    def renderHTMLToFile(self, filename="messages.html"):
        """
        저장된 메시지를 HTML 파일로 저장하고 실제로 브라우저에서 열 수 있게 함.
        """
        html_content = self.renderHTML()
        with open(filename, "w", encoding="utf-8") as file:
            file.write(html_content)
        print(f"HTML 파일 '{filename}'로 저장되었습니다.")
        # 파일을 실제로 열기
        import webbrowser
        webbrowser.open(filename)

# 사용 예시
# Slack 및 Telegram 핸들러 설정
slack_handler = SlackHandler(api_key="", channel_id="")
slack_manager = MessagingServiceManager(slack_handler)
slack_messages = slack_manager.process_messages()
print("Slack 메시지:", slack_messages)

telegram_handler = TelegramHandler(api_key="", chat_id="")
telegram_manager = MessagingServiceManager(telegram_handler)
telegram_messages = telegram_manager.process_messages()
print("Telegram 메시지:", telegram_messages)

# MessageManager 및 Notification 설정
message_manager = MessageManager()
notifier = NotificationObserver()
message_manager.subscribe(notifier)

# Slack 및 Telegram 메시지를 MessageManager에 추가
for message in slack_messages:
    message_manager.add_message(message)

for message in telegram_messages:
    message_manager.add_message(message)

# FrontendVisualizer 생성 및 출력
frontend_visualizer = FrontendVisualizer(message_manager)
html_output = frontend_visualizer.renderHTML()
print(html_output)
frontend_visualizer.renderHTMLToFile()

# Slack 채널 ID 확인 코드 (참고용)
"""
api_key = "your_slack_api_key"
url = "https://slack.com/api/conversations.list"
headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    channels = response.json().get("channels", [])
    for channel in channels:
        print(f"Name: {channel['name']}, ID: {channel['id']}")
else:
    print("Failed to fetch channels:", response.json())
"""

# Telegram chat ID 확인 코드 (참고용)

api_token = '7561927766:AAGe1SfBg3Ab7Pgps1kMWiG3RAtpZtLKIN0'
url = f'https://api.telegram.org/bot{api_token}/getUpdates'

response = requests.get(url)
updates = response.json()

# 업데이트에 포함된 채팅 ID 확인
for update in updates['result']:
    chat_id = update['message']['chat']['id']
    print(f"Chat ID: {chat_id}")

