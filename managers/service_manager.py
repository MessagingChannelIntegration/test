class MessagingServiceManager:
    def __init__(self, handler):
        self.handler = handler

    def process_messages(self):
        self.handler.connect()
        return self.handler.fetch_messages()
