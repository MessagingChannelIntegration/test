from flask import Flask, render_template
from flask_socketio import SocketIO
from handlers.slack_handler import SlackHandler
from handlers.telegram_handler import TelegramHandler
from managers.message_manager import MessageManager
from managers.service_manager import MessagingServiceManager
from observers.notification_observer import NotificationObserver
import threading
import time

# Flask 및 SocketIO 초기화
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 메시지 실시간 전송 함수
def notify_new_message(message):
    socketio.emit(
        'new_message',
        {'text': message['text'], 'source': message['source'], 'time': message['time']},
        namespace='/'
    )

# 메시지 매니저 및 옵저버 설정
message_manager = MessageManager()
notifier = NotificationObserver()
message_manager.subscribe(notifier)
message_manager.set_notifier(notify_new_message)

# 핸들러 및 매니저 설정
slack_handler = SlackHandler(api_key="SLACK_API_KEY", channel_id="SLACK_CHANNEL_ID")
slack_manager = MessagingServiceManager(slack_handler)

telegram_handler = TelegramHandler(api_key="TELEGRAM_API_KEY", chat_id="TELEGRAM_CHAT_ID")
telegram_manager = MessagingServiceManager(telegram_handler)

# 메시지 폴링 스레드
def poll_messages(manager):
    while True:
        time.sleep(10)
        try:
            new_messages = manager.process_messages()
            for message in new_messages:
                message_manager.add_message(message)
        except Exception as e:
            print(f"Error polling messages: {e}")

# Slack 및 Telegram 폴링 시작
threading.Thread(target=poll_messages, args=(slack_manager,), daemon=True).start()
threading.Thread(target=poll_messages, args=(telegram_manager,), daemon=True).start()

# HTML 렌더링
@app.route('/')
def index():
    messages = message_manager.get_all_messages()
    return render_template('channel_ui.html', messages=messages)

# 서버 실행
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
