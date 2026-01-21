"""
GPT 서비스 모듈
질문 복잡도 분석 등 비즈니스 로직
"""


def analyze_question_complexity(message: str, has_image: bool = False) -> str:
    """
    질문 복잡도 분석하여 적절한 모델 선택

    Args:
        message: 사용자 메시지
        has_image: 이미지 포함 여부

    Returns:
        선택된 모델명 (gpt-5.2, gpt-4o, gpt-4o-mini)
    """
    if has_image:
        return 'gpt-4o'

    # 복잡한 질문 패턴 (gpt-5.2 사용)
    complex_patterns = [
        '코드', 'code', '프로그래밍', 'python', 'javascript', 'java', 'c++',
        '함수', 'function', '클래스', 'class', '알고리즘', '구현', 'implement',
        '버그', 'debug', '에러', 'error', 'API', '데이터베이스', 'SQL',
        '분석', 'analyze', '비교', 'compare', '장단점', '차이점', '전략', 'strategy',
        '작성해', 'write', '만들어줘', 'create', '기획', '스토리', 'story',
        '대본', 'script', '에세이', 'essay', '보고서', 'report',
        '증명', 'prove', '통계', 'statistics', '확률', 'probability',
        '자세히', '상세히', 'detailed', '요약', 'summarize',
        # 수학 복잡 패턴 추가
        '방정식', '연립방정식', '인수분해', '미분', '적분',
        '그래프', 'graph', '좌표', '기하', '삼각함수',
    ]

    # 중간 수준 패턴 (gpt-4o 사용)
    medium_patterns = [
        '설명해', 'explain', '알려줘', '가르쳐', '어떻게', 'how',
        '번역', 'translate', '영어로', '한국어로', 'in english',
        '개념', 'concept', '원리', 'principle',
        '왜', 'why', '원인', '이유',
        '계산', 'calculate', '공식', 'formula', '수학', '과학',
        # 수학 중간 패턴 추가
        '분수', '소수', '비율', '퍼센트', '제곱근', '거듭제곱',
        '넓이', '부피', '각도', '둘레', '단위', '약분', '통분',
    ]

    # 간단한 질문 패턴 (gpt-4o-mini 사용)
    simple_patterns = [
        '뭐야', '뭔가요', '무엇', 'what is', '정의', '의미',
        '날씨', 'weather', '시간', 'time', '오늘',
        '안녕', 'hello', 'hi', '고마워', 'thanks', '네', '아니',
        '잘가', 'bye', '좋아', '싫어', '맞아', '틀려',
        '몇', '언제', 'when', '어디', 'where', '누구', 'who',
        '맞아?', '될까?', '있어?', '없어?',
    ]

    message_lower = message.lower()

    # 패턴 매칭
    for pattern in complex_patterns:
        if pattern in message_lower:
            return 'gpt-5.2'

    for pattern in medium_patterns:
        if pattern in message_lower:
            return 'gpt-4o'

    for pattern in simple_patterns:
        if pattern in message_lower:
            return 'gpt-4o-mini'

    # 길이 기반 기본 선택
    if len(message) > 200:
        return 'gpt-5.2'
    elif len(message) > 50:
        return 'gpt-4o'
    else:
        return 'gpt-4o-mini'
