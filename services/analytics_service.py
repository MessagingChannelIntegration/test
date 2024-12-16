import re
from collections import Counter
from kiwipiepy import Kiwi

kiwi = Kiwi()
class KeywordAnalysisModule:
    def extract_nouns_and_count(self, messages):
        noun_counts = Counter()

        # 불필요한 단어 필터링
        stop_words = set([
            "중인데", "있어요", "있을까요", "싶습니다", "있으신가요", "분", "데", 
            "관련", "자료", "발표", "책", "하는", "에서", "고", "이", "그", 
            "및", "것", "중", "을", "로", "은", "는", "가", "도", "에", 
            "의", "들", "면", "대해", "방법", "내용", "어떻게", "왜", "더"
        ])

        for msg in messages:
            text = msg.get("text", "").strip()
            if not text or "<@" in text:  # 사용자 태그 제외
                continue

            # Kiwi를 이용한 명사 추출
            analysis = kiwi.analyze(text)[0][0]  # 첫 번째 분석 결과의 토큰 리스트
            nouns = [
                token.form for token in analysis
                if token.tag.startswith("N")  # 명사(NNG, NNP 등)
                and len(token.form) > 1  # 단어 길이가 1 이상
                and token.form not in stop_words
            ]
            noun_counts.update(nouns)

        # 내림차순으로 정렬된 딕셔너리 반환
        sorted_nouns = dict(sorted(noun_counts.items(), key=lambda x: x[1], reverse=True))
        return sorted_nouns
