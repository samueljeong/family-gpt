"""
로깅 설정 모듈
모든 모듈에서 import하여 사용
"""
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(app_name: str = "family-gpt", log_dir: str = None):
    """
    애플리케이션 로깅 설정

    Args:
        app_name: 로그 파일명에 사용될 앱 이름
        log_dir: 로그 파일 저장 디렉토리 (기본: 프로젝트루트/logs)

    Returns:
        설정된 logger 인스턴스
    """
    # 로그 디렉토리 설정
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')

    os.makedirs(log_dir, exist_ok=True)

    # 로그 포맷 설정
    log_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # 콘솔 핸들러 (화면 출력)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (파일 저장, 10MB마다 로테이션, 최대 5개 보관)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f'{app_name}.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)

    # 에러 전용 파일 (ERROR 이상만)
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, f'{app_name}-error.log'),
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    root_logger.addHandler(error_handler)

    return logging.getLogger(app_name)


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거 반환

    Usage:
        from logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("메시지")
    """
    return logging.getLogger(name)
