"""
DB 헬퍼 모듈
GPT 사용자/대화/메시지 CRUD 함수
"""
from logging_config import get_logger

logger = get_logger(__name__)

# 의존성 (init()으로 주입)
_get_db_connection = None
_use_postgres = False
_default_users = []


def init(get_db_connection_func, use_postgres: bool, default_users: list):
    """
    DB 헬퍼 초기화

    Args:
        get_db_connection_func: DB 연결 함수
        use_postgres: PostgreSQL 사용 여부
        default_users: 기본 사용자 목록
    """
    global _get_db_connection, _use_postgres, _default_users
    _get_db_connection = get_db_connection_func
    _use_postgres = use_postgres
    _default_users = default_users


def _ph():
    """placeholder: PostgreSQL은 %s, SQLite는 ?"""
    return "%s" if _use_postgres else "?"


def load_gpt_users():
    """사용자 목록 로드"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM gpt_users ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if rows:
            return [row['user_id'] for row in rows]
        else:
            save_gpt_users(_default_users)
            return _default_users.copy()
    except Exception as e:
        logger.error(f"사용자 로드 실패: {e}")
        return _default_users.copy()


def save_gpt_users(users):
    """사용자 목록 저장"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        for user_id in users:
            if _use_postgres:
                cursor.execute(
                    "INSERT INTO gpt_users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO gpt_users (user_id) VALUES (?)",
                    (user_id,)
                )

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"사용자 저장 실패: {e}")
        return False


def load_gpt_conversations_for_user(user_id: str):
    """특정 사용자의 대화 목록 로드 (N+1 쿼리 최적화: JOIN 사용)"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        ph = _ph()

        cursor.execute(
            f"""SELECT c.conversation_id, c.created_at as conv_created, c.updated_at as conv_updated,
                       m.role, m.content, m.model, m.has_image, m.created_at as msg_created
               FROM gpt_conversations c
               LEFT JOIN gpt_messages m ON c.user_id = m.user_id AND c.conversation_id = m.conversation_id
               WHERE c.user_id = {ph}
               ORDER BY c.updated_at DESC, m.created_at ASC""",
            (user_id,)
        )
        rows = cursor.fetchall()

        result = {}
        for row in rows:
            conv_id = row['conversation_id']

            if conv_id not in result:
                conv_created = row['conv_created']
                conv_updated = row['conv_updated']
                result[conv_id] = {
                    'created_at': conv_created.isoformat() if hasattr(conv_created, 'isoformat') else str(conv_created) if conv_created else None,
                    'updated_at': conv_updated.isoformat() if hasattr(conv_updated, 'isoformat') else str(conv_updated) if conv_updated else None,
                    'messages': []
                }

            if row['role'] is not None:
                msg_created = row['msg_created']
                result[conv_id]['messages'].append({
                    'role': row['role'],
                    'content': row['content'],
                    'model': row['model'],
                    'has_image': bool(row['has_image']),
                    'timestamp': msg_created.isoformat() if hasattr(msg_created, 'isoformat') else str(msg_created) if msg_created else None
                })

        cursor.close()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"대화 로드 실패: {e}")
        return {}


def save_gpt_message(user_id: str, conversation_id: str, role: str, content: str, model: str = None, has_image: bool = False):
    """메시지 저장"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        if _use_postgres:
            cursor.execute(
                """INSERT INTO gpt_conversations (user_id, conversation_id)
                   VALUES (%s, %s)
                   ON CONFLICT (user_id, conversation_id)
                   DO UPDATE SET updated_at = CURRENT_TIMESTAMP""",
                (user_id, conversation_id)
            )
            cursor.execute(
                """INSERT INTO gpt_messages (user_id, conversation_id, role, content, model, has_image)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, conversation_id, role, content, model, has_image)
            )
        else:
            cursor.execute(
                """INSERT OR REPLACE INTO gpt_conversations (user_id, conversation_id, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (user_id, conversation_id)
            )
            cursor.execute(
                """INSERT INTO gpt_messages (user_id, conversation_id, role, content, model, has_image)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, conversation_id, role, content, model, 1 if has_image else 0)
            )

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"메시지 저장 실패: {e}")
        return False


def delete_gpt_conversation(user_id: str, conversation_id: str):
    """대화 삭제"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        ph = _ph()

        cursor.execute(
            f"DELETE FROM gpt_messages WHERE user_id = {ph} AND conversation_id = {ph}",
            (user_id, conversation_id)
        )
        cursor.execute(
            f"DELETE FROM gpt_conversations WHERE user_id = {ph} AND conversation_id = {ph}",
            (user_id, conversation_id)
        )

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"대화 삭제 실패: {e}")
        return False


def delete_gpt_user(user_id: str):
    """사용자 삭제"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        ph = _ph()

        cursor.execute(f"DELETE FROM gpt_messages WHERE user_id = {ph}", (user_id,))
        cursor.execute(f"DELETE FROM gpt_conversations WHERE user_id = {ph}", (user_id,))
        cursor.execute(f"DELETE FROM gpt_users WHERE user_id = {ph}", (user_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"사용자 삭제 실패: {e}")
        return False
