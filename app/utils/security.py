"""Admin session yordamida login/logout."""
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

SESSION_COOKIE = "mm_admin_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 soat


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt="admin-session")


def create_session_token(username: str) -> str:
    return _serializer().dumps({"u": username})


def verify_session_token(token: str) -> str | None:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("u")


def check_credentials(username: str, password: str) -> bool:
    # .env dan to'g'ridan-to'g'ri konstanta taqqoslash (timing-safe)
    import hmac
    u_ok = hmac.compare_digest(username.encode(), settings.ADMIN_USERNAME.encode())
    p_ok = hmac.compare_digest(password.encode(), settings.ADMIN_PASSWORD.encode())
    return u_ok and p_ok


def current_admin(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return verify_session_token(token)
