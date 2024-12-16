from managers.message_manager import MessageManager
from services.analytics_service import KeywordAnalysisModule
from services.channel_repository import ChannelRepository

class RecommendationService ():
    def __init__(self, keyword_analyzer, socketio):
        self.keyword_analyzer = keyword_analyzer
        self.socketio = socketio
        self.channel_repository = ChannelRepository()
        self.recommendations = {
            "Slack": [
                {"name": "AI Research Group", "keywords": ["AI", "machine learning", "research"]},
                {"name": "Python Developers", "keywords": ["Python", "programming", "developers"]},
            ],
            "Telegram": [
                {"name": "Deep Learning Bot", "keywords": ["deep learning", "neural networks", "AI"]},
                {"name": "Tech News Channel", "keywords": ["technology", "news", "innovation"]},
            ],
        }

    def update(self, message):
        """
        새로운 메시지가 추가되었을 때 호출됩니다.
        메시지를 분석하고 추천 결과를 실시간으로 전송합니다.
        """
        # 관심 키워드 추출
        user_keywords = self.keyword_analyzer.extract_keywords([message])

        # 싱글톤 클래스에서 현재 채널 정보 가져오기
        current_channels = self.channel_repository.get_channels()

        # 사용자 키워드를 기반으로 추천 채널 목록 생성
        recommendations = self._generate_recommendations(user_keywords, current_channels)

        # 싱글톤 클래스에 업데이트된 채널 저장 (Top 5만)
        self.channel_repository.update_channels(recommendations)

        # 클라이언트로 실시간 추천 결과 전송
        self.socketio.emit('recommendations', {'data': recommendations})

    def _generate_recommendations(self, user_keywords, current_channels):
        """
        관심 키워드를 기반으로 추천 목록 생성
        """
        recommendations = []


    # 기존 관리 중인 채널에 대한 점수 다시 계산
        for channel in current_channels:
            score = len(set(user_keywords.keys()) & set(channel.get("keywords", [])))
            recommendations.append({
                "name": channel["name"],
                "source": channel.get("source", "unknown"),
                "score": score,
            })

    # 새로운 채널에 대한 점수 계산
        for platform, channels in self.recommendations.items():
            for channel in channels:
                # 현재 채널 목록에 없는 경우도 포함해서 점수 계산
                score = len(set(user_keywords.keys()) & set(channel["keywords"]))
                recommendations.append({
                    "name": channel["name"],
                    "source": platform,
                    "score": score,
                })


        # 점수 기준으로 정렬 후 반환
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations