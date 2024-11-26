import requests
from datetime import datetime
from base_handler import MessagingServiceHandler

class TelegramHandler(MessagingServiceHandler):
    def __init__(self, api_key, chat_id):
        self.api_key = api_key
        self.chat_id = chat_id

    def connect(self):
        url = f"https://api.telegram.org/bot{self.api_key}/getMe"
        response = requests.get(url)
        if not (response.status_code == 200 and response.json().get("ok")):
            raise Exception(f"Telegram 연결 실패: {response.json()}")

    def fetch_messages(self):
        url = f"https://api.telegram.org/bot{self.api_key}/getUpdates"
        response = requests.get(url)
        if response.status_code == 200:
            updates = response.json().get("result", [])
            messages = [
                {
                    "text": update["message"].get("text", ""),
                    "source": "Telegram",
                    "id": f"{update['message']['chat']['id']}_{update['message']['message_id']}",
                    "timestamp": float(update['message']['date']),
                    "time": datetime.fromtimestamp(float(update['message']['date'])).strftime('%Y-%m-%d %H:%M:%S')
                }
                for update in updates if "message" in update
            ]
            return messages
        else:
            raise Exception(f"Telegram 메시지 가져오기 실패: {response.json()}")
