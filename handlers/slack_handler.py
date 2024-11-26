import requests
from datetime import datetime
from base_handler import MessagingServiceHandler

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