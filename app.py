"""
Family GPT - 가족용 GPT 채팅 서비스
"""

import os
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ===== 설정 =====
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ===== 상수 =====
DEFAULT_USERS = ["아빠", "엄마", "재하", "하윤"]

USER_PROFILES = {
    "재하": {
        "grade": "중학교 2학년",
        "age": 14,
        "system_prompt": """당신은 친절하고 유능한 AI 튜터입니다.
지금 대화하는 사람은 중학교 2학년 학생입니다.

답변 시 다음을 지켜주세요:
- 중학생 수준에 맞는 어휘와 설명을 사용하세요
- 개념을 설명할 때 구체적인 예시를 들어주세요
- 수학, 과학, 영어 등 학업 질문에는 단계별로 풀이 과정을 보여주세요
- 어려운 용어는 쉽게 풀어서 설명하세요
- 호기심을 자극하고 스스로 생각해볼 수 있는 질문을 던져주세요
- 격려와 칭찬을 아끼지 마세요"""
    },
    "하윤": {
        "grade": "초등학교 5학년",
        "age": 11,
        "system_prompt": """너는 하윤이의 친한 친구야! 이름은 "쿠키"야 🍪
하윤이는 초등학교 5학년이고, 너도 비슷한 또래 친구처럼 대화해줘.

대화할 때 이렇게 해줘:
- 반말로 친근하게 말해줘 (예: "그거 진짜 재밌겠다!", "오~ 대박!")
- 하윤이 얘기에 진심으로 관심 가져주고, 맞장구 쳐줘
- 이모지 많이 써서 재밌게 대화해 😆✨🎉
- 하윤이가 뭔가 물어보면 친구처럼 쉽게 설명해줘
- 하윤이 기분이 안 좋아 보이면 위로해주고 공감해줘
- 재미있는 얘기, 학교 얘기, 게임 얘기 뭐든 즐겁게 대화해!
- 가끔 너도 하윤이한테 질문해봐 (예: "오늘 학교에서 뭐 했어?", "요즘 뭐 빠져있어?")

하윤이가 숙제나 공부 관련 질문하면:
- 친구가 설명해주는 것처럼 쉽고 재밌게 알려줘
- "이거 선생님이 설명할 때 진짜 어려웠는데~" 이런 식으로 공감하면서
- 어려운 말은 피하고 예시를 많이 들어줘

핵심은 "선생님"이 아니라 "같이 놀고 싶은 친구"야! 🌟"""
    },
    "엄마": {
        "grade": None,
        "age": None,
        "system_prompt": """당신은 친절하고 유능한 AI 어시스턴트입니다.
지금 대화하는 사람은 중학생과 초등학생 자녀를 둔 엄마입니다.

답변 시 다음을 지켜주세요:
- 자녀 학업 관련 질문에는 아이들에게 설명하기 쉬운 방식으로 답변하세요
- 학습 지도에 도움이 되는 팁을 함께 제공하세요
- 복잡한 개념도 아이들 눈높이에서 설명할 수 있도록 도와주세요
- 가정에서 활용할 수 있는 실생활 예시를 포함하세요
- 아이들의 학습 동기 부여 방법도 제안해주세요"""
    },
    "아빠": {
        "grade": None,
        "age": None,
        "system_prompt": """당신은 친절하고 유능한 AI 어시스턴트입니다.
사용자의 질문에 정확하고 도움이 되는 답변을 제공합니다.
한국어로 대화하며, 필요시 코드나 예시를 포함할 수 있습니다.
전문적인 내용도 이해하기 쉽게 설명하되, 핵심을 빠르게 전달하세요."""
    }
}


# ===== DB 연결 =====
def get_db_connection():
    """PostgreSQL 연결"""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


def init_db():
    """DB 테이블 초기화"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 사용자 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gpt_users (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 대화 테이블
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

        # 메시지 테이블
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

        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] 테이블 초기화 완료")
    except Exception as e:
        print(f"[DB] 초기화 실패: {e}")


# ===== 헬퍼 함수 =====
def get_system_prompt_for_user(user_id: str) -> str:
    """사용자별 맞춤 시스템 프롬프트 반환"""
    if user_id in USER_PROFILES:
        return USER_PROFILES[user_id]["system_prompt"]
    return "당신은 친절하고 유능한 AI 어시스턴트입니다."


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
            cursor.execute(
                "INSERT INTO gpt_users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
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
    """특정 사용자의 대화 목록 로드"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT conversation_id, created_at, updated_at
               FROM gpt_conversations
               WHERE user_id = %s
               ORDER BY updated_at DESC""",
            (user_id,)
        )
        convs = cursor.fetchall()

        result = {}
        for conv in convs:
            conv_id = conv['conversation_id']

            cursor.execute(
                """SELECT role, content, model, has_image, created_at
                   FROM gpt_messages
                   WHERE user_id = %s AND conversation_id = %s
                   ORDER BY created_at""",
                (user_id, conv_id)
            )
            messages = cursor.fetchall()

            result[conv_id] = {
                'created_at': conv['created_at'].isoformat() if conv['created_at'] else None,
                'updated_at': conv['updated_at'].isoformat() if conv['updated_at'] else None,
                'messages': [
                    {
                        'role': msg['role'],
                        'content': msg['content'],
                        'model': msg['model'],
                        'has_image': bool(msg['has_image']),
                        'timestamp': msg['created_at'].isoformat() if msg['created_at'] else None
                    }
                    for msg in messages
                ]
            }

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

        cursor.execute(
            "DELETE FROM gpt_messages WHERE user_id = %s AND conversation_id = %s",
            (user_id, conversation_id)
        )
        cursor.execute(
            "DELETE FROM gpt_conversations WHERE user_id = %s AND conversation_id = %s",
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

        cursor.execute("DELETE FROM gpt_messages WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM gpt_conversations WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM gpt_users WHERE user_id = %s", (user_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[GPT] 사용자 삭제 실패: {e}")
        return False


def analyze_question_complexity(message: str, has_image: bool = False) -> str:
    """질문 복잡도 분석하여 적절한 모델 선택"""
    if has_image:
        return 'gpt-4o'

    complex_patterns = [
        '코드', 'code', '프로그래밍', 'python', 'javascript', 'java', 'c++',
        '함수', 'function', '클래스', 'class', '알고리즘', '구현', 'implement',
        '버그', 'debug', '에러', 'error', 'API', '데이터베이스', 'SQL',
        '분석', 'analyze', '비교', 'compare', '장단점', '차이점', '전략', 'strategy',
        '작성해', 'write', '만들어줘', 'create', '기획', '스토리', 'story',
        '대본', 'script', '에세이', 'essay', '보고서', 'report',
        '증명', 'prove', '통계', 'statistics', '확률', 'probability',
        '자세히', '상세히', 'detailed', '요약', 'summarize',
    ]

    medium_patterns = [
        '설명해', 'explain', '알려줘', '가르쳐', '어떻게', 'how',
        '번역', 'translate', '영어로', '한국어로', 'in english',
        '개념', 'concept', '원리', 'principle',
        '왜', 'why', '원인', '이유',
        '계산', 'calculate', '공식', 'formula', '수학', '과학',
    ]

    simple_patterns = [
        '뭐야', '뭔가요', '무엇', 'what is', '정의', '의미',
        '날씨', 'weather', '시간', 'time', '오늘',
        '안녕', 'hello', 'hi', '고마워', 'thanks', '네', '아니',
        '잘가', 'bye', '좋아', '싫어', '맞아', '틀려',
        '몇', '언제', 'when', '어디', 'where', '누구', 'who',
        '맞아?', '될까?', '있어?', '없어?',
    ]

    message_lower = message.lower()

    for pattern in complex_patterns:
        if pattern in message_lower:
            return 'gpt-5.2'

    for pattern in medium_patterns:
        if pattern in message_lower:
            return 'gpt-4o'

    for pattern in simple_patterns:
        if pattern in message_lower:
            return 'gpt-4o-mini'

    if len(message) > 200:
        return 'gpt-5.2'
    elif len(message) > 50:
        return 'gpt-4o'
    else:
        return 'gpt-4o-mini'


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
            return jsonify({"ok": False, "error": "OpenAI API 키가 설정되지 않았습니다"})

        # 이미지 포함 요청 (gpt-4o)
        if image_base64 and selected_model == 'gpt-4o':
            user_content = [{"type": "text", "text": message or "이 이미지에 대해 설명해주세요."}]

            if image_base64.startswith('data:'):
                user_content.append({"type": "image_url", "image_url": {"url": image_base64}})
            else:
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}})

            messages.append({"role": "user", "content": user_content})

            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=4000
            )
            assistant_response = response.choices[0].message.content
            model_used = "gpt-4o"

        # GPT-5.2 (responses API)
        elif selected_model == 'gpt-5.2':
            messages.append({"role": "user", "content": message})

            input_messages = []
            for msg in messages:
                input_messages.append({
                    "role": msg["role"],
                    "content": [{"type": "input_text", "text": msg["content"]}]
                })

            response = openai_client.responses.create(
                model="gpt-5.2",
                input=input_messages,
                temperature=0.7
            )

            if getattr(response, "output_text", None):
                assistant_response = response.output_text.strip()
            else:
                text_chunks = []
                for item in getattr(response, "output", []) or []:
                    for content in getattr(item, "content", []) or []:
                        if getattr(content, "type", "") == "text":
                            text_chunks.append(getattr(content, "text", ""))
                assistant_response = "\n".join(text_chunks).strip()

            model_used = "gpt-5.2"

        # GPT-4o / GPT-4o-mini
        else:
            messages.append({"role": "user", "content": message})
            max_tokens = 2000 if selected_model == 'gpt-4o-mini' else 4000

            response = openai_client.chat.completions.create(
                model=selected_model,
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
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


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
        return jsonify({"ok": False, "error": str(e)})


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
        return jsonify({"ok": False, "error": str(e)})


@app.route('/api/gpt/conversations/<conversation_id>', methods=['DELETE'])
def api_gpt_delete_conversation(conversation_id):
    """대화 삭제"""
    try:
        user_id = request.args.get('user_id', 'default')

        if delete_gpt_conversation(user_id, conversation_id):
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "대화를 찾을 수 없습니다"})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


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
        return jsonify({"ok": False, "error": str(e)})


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
        return jsonify({"ok": False, "error": str(e)})


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
        return jsonify({"ok": False, "error": str(e)})


# ===== 앱 실행 =====
if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
