class NotificationObserver:
    def update(self, message):
        print(f"[{message['source']}] 새 메시지 알림: {message['text']}")
