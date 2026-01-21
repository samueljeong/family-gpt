"""
에러 응답 표준화 모듈
- 내부 에러 상세 정보는 로그에만 기록
- 클라이언트에는 안전한 메시지만 반환
"""
import os
from functools import wraps
from flask import jsonify
from logging_config import get_logger

logger = get_logger(__name__)

# 개발 모드 여부 (True면 상세 에러 노출)
DEBUG_MODE = os.getenv('FLASK_ENV') == 'development' or os.getenv('TESTING')


def safe_error_message(e: Exception, default_message: str = "처리 중 오류가 발생했습니다.") -> str:
    """
    에러를 안전한 메시지로 변환
    - 개발 모드: 상세 에러 표시
    - 프로덕션: 일반 메시지만 표시
    """
    if DEBUG_MODE:
        return f"{default_message} ({type(e).__name__}: {str(e)})"
    return default_message


def error_response(e: Exception, message: str, status_code: int = 500, log_prefix: str = ""):
    """
    표준화된 에러 응답 생성
    - 내부 에러는 로그에 기록
    - 클라이언트에는 안전한 메시지 반환
    """
    # 에러 로깅 (상세 정보 포함)
    log_message = f"[{log_prefix}] {type(e).__name__}: {str(e)}" if log_prefix else f"{type(e).__name__}: {str(e)}"
    logger.error(log_message, exc_info=True)

    # 클라이언트 응답 (안전한 메시지만)
    response_message = safe_error_message(e, message)

    return jsonify({
        "ok": False,
        "error": response_message
    }), status_code


def handle_errors(default_message: str = "처리 중 오류가 발생했습니다.", log_prefix: str = ""):
    """
    데코레이터: API 엔드포인트의 에러를 표준화된 방식으로 처리

    사용법:
        @app.route('/api/example')
        @handle_errors("예제 처리 실패", log_prefix="EXAMPLE")
        def example_api():
            # 에러가 발생하면 자동으로 표준화된 응답 반환
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                return error_response(e, default_message, 500, log_prefix)
        return wrapper
    return decorator


# 자주 사용되는 에러 메시지 상수
ERROR_MESSAGES = {
    "chat": "채팅 처리 중 오류가 발생했습니다.",
    "save": "저장 중 오류가 발생했습니다.",
    "delete": "삭제 중 오류가 발생했습니다.",
    "api": "API 호출 중 오류가 발생했습니다.",
    "db": "데이터베이스 처리 중 오류가 발생했습니다.",
}
