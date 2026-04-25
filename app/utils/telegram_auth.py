"""
Telegram Mini App initData tekshirish.

Har bir mini app so'rovi bilan `initData` satri keladi.
Biz uni bot tokeni bilan HMAC-SHA256 orqali tekshiramiz.
Rasmiy hujjat: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class TelegramAuthError(Exception):
    """Telegram init data haqiqiy emas."""


def verify_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 24 * 60 * 60,
) -> dict[str, Any]:
    """
    Verify Telegram Mini App init data and return the parsed user dict.

    Raises TelegramAuthError agar hash noto'g'ri bo'lsa yoki muddati tugagan bo'lsa.
    """
    if not init_data:
        raise TelegramAuthError("init data bo'sh")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("hash yo'q")

    # auth_date tekshirish (eskirmaganligi)
    auth_date = parsed.get("auth_date")
    if auth_date:
        try:
            auth_ts = int(auth_date)
        except ValueError as exc:
            raise TelegramAuthError("auth_date noto'g'ri") from exc
        if time.time() - auth_ts > max_age_seconds:
            raise TelegramAuthError("init data muddati tugagan")

    # Data-check-string yig'ish
    data_check_string = "\n".join(
        f"{k}={parsed[k]}" for k in sorted(parsed.keys())
    )

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise TelegramAuthError("hash mos kelmadi")

    # User JSON ni parse qilish
    user_data: dict[str, Any] = {}
    if "user" in parsed:
        try:
            user_data = json.loads(parsed["user"])
        except json.JSONDecodeError as exc:
            raise TelegramAuthError("user JSON noto'g'ri") from exc

    return {
        "user": user_data,
        "auth_date": int(parsed.get("auth_date", 0)),
        "query_id": parsed.get("query_id"),
    }
