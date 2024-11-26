# 채널 관리자 정의
from abc import ABC, abstractmethod

class MessagingServiceHandler(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def fetch_messages(self):
        pass

