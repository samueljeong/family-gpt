"""
Family GPT - 가족용 GPT 채팅 서비스
"""

import os
import sqlite3
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
from dotenv import load_dotenv
from logging_config import setup_logging, get_logger
from error_handlers import error_response, safe_error_message, ERROR_MESSAGES
from config import DEFAULT_USERS, USER_PROFILES, get_system_prompt_for_user
from services.gpt_service import analyze_question_complexity
from services.math_utils import process_math_response
from services import db_helpers

load_dotenv()

# 로깅 설정 (앱 시작 시 한 번만)
setup_logging("family-gpt")
logger = get_logger(__name__)


def validate_environment():
    """필수 환경변수 검증"""
    errors = []
    warnings = []

    # LAOZHANG_API_KEY - 필수 (LAOZHANG 사설 API 사용)
    if not os.getenv("LAOZHANG_API_KEY"):
        if os.getenv("TESTING"):
            warnings.append("LAOZHANG_API_KEY가 설정되지 않았습니다. (테스트 모드)")
        else:
            errors.append("LAOZHANG_API_KEY가 설정되지 않았습니다.")

    # SECRET_KEY - 프로덕션에서 필수
    if not os.getenv("SECRET_KEY"):
        if os.getenv("TESTING") or os.getenv("FLASK_ENV") == "development":
            warnings.append("SECRET_KEY가 설정되지 않아 기본값을 사용합니다.")
        else:
            errors.append("SECRET_KEY가 설정되지 않았습니다. 프로덕션에서는 필수입니다.")

    # DATABASE_URL - 선택 (없으면 SQLite 사용)
    if not os.getenv("DATABASE_URL"):
        warnings.append("DATABASE_URL이 설정되지 않아 SQLite를 사용합니다.")

    # 경고 로깅
    for warning in warnings:
        logger.warning(warning)

    # 에러 발생 시 종료
    if errors:
        for error in errors:
            logger.error(error)
        raise ValueError("\n".join(errors))


# 환경변수 검증 (테스트 모드가 아닐 때)
if not os.getenv("TESTING"):
    validate_environment()

app = Flask(__name__)

# ===== 설정 =====
DATABASE_URL = os.getenv("DATABASE_URL")
LAOZHANG_API_KEY = os.getenv("LAOZHANG_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-for-testing-only")
USE_POSTGRES = bool(DATABASE_URL)

app.config["SECRET_KEY"] = SECRET_KEY

# PostgreSQL 사용 시에만 import
if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

# LAOZHANG 사설 API 클라이언트 (OpenAI 호환)
openai_client = OpenAI(
    api_key=LAOZHANG_API_KEY,
    base_url="https://api.laozhang.ai/v1"
) if LAOZHANG_API_KEY else None

# LAOZHANG 모델 매핑 (OpenAI 모델명 그대로 사용 가능)
OPENROUTER_MODELS = {
    "gpt-5.2": "gpt-4o",  # 고급 추론용 (gpt-4o로 대체)
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini"
}

# SQLite 경로
SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'family_gpt.db')

# ===== DB 연결 =====
def dict_factory(cursor, row):
    """SQLite dict factory"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_db_connection():
    """DB 연결 (PostgreSQL 또는 SQLite)"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = dict_factory
    return conn


def init_db():
    """DB 테이블 초기화"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            # PostgreSQL
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gpt_users (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gpt_conversations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL,
                    conversation_id VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, conversation_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gpt_messages (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL,
                    conversation_id VARCHAR(100) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    model VARCHAR(50),
                    has_image BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # SQLite
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gpt_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gpt_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, conversation_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gpt_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    has_image INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] 테이블 초기화 완료")
    except Exception as e:
        print(f"[DB] 초기화 실패: {e}")


# ===== 헬퍼 함수 =====
def load_gpt_users():
    """사용자 목록 로드"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM gpt_users ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if rows:
            return [row['user_id'] for row in rows]
        else:
            save_gpt_users(DEFAULT_USERS)
            return DEFAULT_USERS.copy()
    except Exception as e:
        print(f"[GPT] 사용자 로드 실패: {e}")
        return DEFAULT_USERS.copy()


def save_gpt_users(users):
    """사용자 목록 저장"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for user_id in users:
            if USE_POSTGRES:
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
        print(f"[GPT] 사용자 저장 실패: {e}")
        return False


def load_gpt_conversations_for_user(user_id: str):
    """특정 사용자의 대화 목록 로드 (N+1 쿼리 최적화: JOIN 사용)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if USE_POSTGRES else "?"

        # 단일 JOIN 쿼리로 모든 데이터 가져오기 (N+1 쿼리 방지)
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

        # 결과를 대화별로 그룹화
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

            # 메시지가 있는 경우에만 추가 (LEFT JOIN으로 메시지 없는 대화도 포함)
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
        print(f"[GPT] 대화 로드 실패: {e}")
        return {}


def save_gpt_message(user_id: str, conversation_id: str, role: str, content: str, model: str = None, has_image: bool = False):
    """메시지 저장"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
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
        print(f"[GPT] 메시지 저장 실패: {e}")
        return False


def delete_gpt_conversation(user_id: str, conversation_id: str):
    """대화 삭제"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if USE_POSTGRES else "?"

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
        print(f"[GPT] 대화 삭제 실패: {e}")
        return False


def delete_gpt_user(user_id: str):
    """사용자 삭제"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if USE_POSTGRES else "?"

        cursor.execute(f"DELETE FROM gpt_messages WHERE user_id = {ph}", (user_id,))
        cursor.execute(f"DELETE FROM gpt_conversations WHERE user_id = {ph}", (user_id,))
        cursor.execute(f"DELETE FROM gpt_users WHERE user_id = {ph}", (user_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[GPT] 사용자 삭제 실패: {e}")
        return False


# ===== 라우트 =====
@app.route('/')
@app.route('/gpt-chat')
def gpt_chat_page():
    """GPT Chat 페이지"""
    return render_template('gpt-chat.html')


@app.route('/health')
def health():
    """헬스체크"""
    return jsonify({"ok": True, "service": "family-gpt"})


@app.route('/api/gpt/chat', methods=['POST'])
def api_gpt_chat():
    """GPT Chat API"""
    try:
        data = request.get_json() or {}
        message = data.get('message', '').strip()
        model_preference = data.get('model', 'auto')
        history = data.get('history', [])
        user_id = data.get('user_id', 'default')
        conversation_id = data.get('conversation_id')
        has_image = data.get('has_image', False)
        image_base64 = data.get('image')

        if not message and not image_base64:
            return jsonify({"ok": False, "error": "메시지를 입력하세요"})

        if model_preference == 'auto':
            selected_model = analyze_question_complexity(message, has_image or bool(image_base64))
        else:
            selected_model = model_preference

        print(f"[GPT] 모델: {selected_model}, 사용자: {user_id}")

        system_prompt = get_system_prompt_for_user(user_id)
        messages = [{"role": "system", "content": system_prompt}]

        for h in history[-10:]:
            messages.append({
                "role": h.get('role', 'user'),
                "content": h.get('content', '')
            })

        if not openai_client:
            return jsonify({"ok": False, "error": "LAOZHANG API 키가 설정되지 않았습니다"})

        # LAOZHANG 모델명으로 변환
        openrouter_model = OPENROUTER_MODELS.get(selected_model, "gpt-4o-mini")

        # 이미지 포함 요청 (gpt-4o)
        if image_base64 and selected_model == 'gpt-4o':
            user_content = [{"type": "text", "text": message or "이 이미지에 대해 설명해주세요."}]

            if image_base64.startswith('data:'):
                user_content.append({"type": "image_url", "image_url": {"url": image_base64}})
            else:
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}})

            messages.append({"role": "user", "content": user_content})

            response = openai_client.chat.completions.create(
                model=openrouter_model,
                messages=messages,
                temperature=0.7,
                max_tokens=4000
            )
            assistant_response = response.choices[0].message.content
            model_used = "gpt-4o"

        # 모든 텍스트 요청 (OpenRouter chat completions 사용)
        else:
            messages.append({"role": "user", "content": message})
            max_tokens = 2000 if selected_model == 'gpt-4o-mini' else 4000

            response = openai_client.chat.completions.create(
                model=openrouter_model,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens
            )
            assistant_response = response.choices[0].message.content
            model_used = selected_model

        # 대화 저장
        if conversation_id:
            try:
                save_gpt_message(user_id, conversation_id, 'user', message, None, bool(image_base64))
                save_gpt_message(user_id, conversation_id, 'assistant', assistant_response, model_used, False)
            except Exception as e:
                print(f"[GPT] 대화 저장 오류: {e}")

        return jsonify({
            "ok": True,
            "response": assistant_response,
            "model_used": model_used
        })

    except Exception as e:
        return error_response(e, ERROR_MESSAGES["chat"], log_prefix="GPT채팅")


@app.route('/api/gpt/conversations', methods=['GET'])
def api_gpt_get_conversations():
    """대화 목록 조회"""
    try:
        user_id = request.args.get('user_id', 'default')
        user_convs = load_gpt_conversations_for_user(user_id)

        result = []
        for conv_id, conv_data in user_convs.items():
            title = "새 대화"
            for msg in conv_data.get('messages', []):
                if msg.get('role') == 'user':
                    title = msg.get('content', '')[:50] + ('...' if len(msg.get('content', '')) > 50 else '')
                    break

            result.append({
                'id': conv_id,
                'title': title,
                'created_at': conv_data.get('created_at'),
                'updated_at': conv_data.get('updated_at'),
                'message_count': len(conv_data.get('messages', []))
            })

        result.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return jsonify({"ok": True, "conversations": result})

    except Exception as e:
        return error_response(e, "처리 중 오류가 발생했습니다.")


@app.route('/api/gpt/conversations/<conversation_id>', methods=['GET'])
def api_gpt_get_conversation(conversation_id):
    """특정 대화 조회"""
    try:
        user_id = request.args.get('user_id', 'default')
        user_convs = load_gpt_conversations_for_user(user_id)
        conv_data = user_convs.get(conversation_id)

        if not conv_data:
            return jsonify({"ok": False, "error": "대화를 찾을 수 없습니다"})

        return jsonify({
            "ok": True,
            "conversation": {
                'id': conversation_id,
                'messages': conv_data.get('messages', []),
                'created_at': conv_data.get('created_at'),
                'updated_at': conv_data.get('updated_at')
            }
        })

    except Exception as e:
        return error_response(e, "처리 중 오류가 발생했습니다.")


@app.route('/api/gpt/conversations/<conversation_id>', methods=['DELETE'])
def api_gpt_delete_conversation(conversation_id):
    """대화 삭제"""
    try:
        user_id = request.args.get('user_id', 'default')

        if delete_gpt_conversation(user_id, conversation_id):
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "대화를 찾을 수 없습니다"})

    except Exception as e:
        return error_response(e, "처리 중 오류가 발생했습니다.")


@app.route('/api/gpt/users', methods=['GET'])
def api_gpt_get_users():
    """사용자 목록 조회"""
    try:
        users = load_gpt_users()

        result = []
        for user_id in users:
            user_convs = load_gpt_conversations_for_user(user_id)
            total_messages = sum(len(c.get('messages', [])) for c in user_convs.values())
            result.append({
                'id': user_id,
                'conversation_count': len(user_convs),
                'total_messages': total_messages
            })

        return jsonify({"ok": True, "users": result})

    except Exception as e:
        return error_response(e, "처리 중 오류가 발생했습니다.")


@app.route('/api/gpt/users', methods=['POST'])
def api_gpt_add_user():
    """사용자 추가"""
    try:
        data = request.get_json() or {}
        user_name = data.get('name', '').strip()

        if not user_name:
            return jsonify({"ok": False, "error": "사용자 이름을 입력하세요"})

        users = load_gpt_users()

        if user_name in users:
            return jsonify({"ok": False, "error": "이미 존재하는 사용자입니다"})

        users.append(user_name)
        save_gpt_users(users)

        return jsonify({"ok": True, "users": users})

    except Exception as e:
        return error_response(e, "처리 중 오류가 발생했습니다.")


@app.route('/api/gpt/users/<user_id>', methods=['DELETE'])
def api_gpt_delete_user(user_id):
    """사용자 삭제"""
    try:
        users = load_gpt_users()

        if user_id not in users:
            return jsonify({"ok": False, "error": "사용자를 찾을 수 없습니다"})

        delete_gpt_user(user_id)
        users = load_gpt_users()
        return jsonify({"ok": True, "users": users})

    except Exception as e:
        return error_response(e, "처리 중 오류가 발생했습니다.")


# ===== 앱 실행 =====
if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
