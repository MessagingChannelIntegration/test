import threading

class ChannelRepository:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance.channels = []  # Top 5 채널 저장
                    cls._instance.observers = []  # 옵저버 리스트
        return cls._instance

    def add_observer(self, observer):
        """옵저버 추가"""
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer):
        """옵저버 제거"""
        if observer in self.observers:
            self.observers.remove(observer)

    def notify_observers(self):
        """옵저버들에게 알림"""
        for observer in self.observers:
            observer.update_channels(self.channels)

    def update_channels(self, new_channels):
        # 새로운 채널로 업데이트 (키워드 점수 기준 상위 5개 선택)
        self.channels = sorted(new_channels, key=lambda x: x['score'], reverse=True)[:5]

    def get_channels(self):
        # 현재 채널 목록 반환
        return self.channels
