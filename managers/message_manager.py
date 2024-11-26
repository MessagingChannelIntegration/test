class MessageManager:
    def __init__(self):
        self.messages = []
        self.message_ids = set()
        self.subscribers = []
        self.notifier = None

    def add_message(self, message):
        if message['id'] not in self.message_ids:
            self.messages.append(message)
            self.message_ids.add(message['id'])
            self.messages.sort(key=lambda x: x['timestamp'], reverse=True)
            self.notify_subscribers(message)
            if self.notifier:
                self.notifier(message)

    def subscribe(self, observer):
        self.subscribers.append(observer)

    def set_notifier(self, notifier_func):
        self.notifier = notifier_func

    def notify_subscribers(self, message):
        for subscriber in self.subscribers:
            subscriber.update(message)

    def get_all_messages(self):
        return self.messages
