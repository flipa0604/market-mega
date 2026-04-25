"""Admin'ning Telegram chat ID'sini topish.

Avval .env'dagi ADMIN_TELEGRAM_ID'ga qaraydi.
Bo'lmasa, ADMIN_TG_USERNAME bo'yicha users jadvalidan qidiradi
(bu user oldindan botga /start yuborgan bo'lishi kerak).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User


async def get_admin_chat_id(db: AsyncSession) -> int | None:
    if settings.ADMIN_TELEGRAM_ID:
        return settings.ADMIN_TELEGRAM_ID
    if not settings.ADMIN_TG_USERNAME:
        return None
    # username bo'yicha topish (case-insensitive)
    uname = settings.ADMIN_TG_USERNAME.lstrip("@").lower()
    result = await db.execute(
        select(User.telegram_id).where(User.username.ilike(uname))
    )
    return result.scalar_one_or_none()


def is_admin_user(tg_user) -> bool:
    """Kelayotgan Telegram user adminmi tekshirish (username yoki ID bo'yicha)."""
    if not tg_user:
        return False
    if settings.ADMIN_TELEGRAM_ID and tg_user.id == settings.ADMIN_TELEGRAM_ID:
        return True
    if settings.ADMIN_TG_USERNAME and tg_user.username:
        return tg_user.username.lower() == settings.ADMIN_TG_USERNAME.lstrip("@").lower()
    return False
