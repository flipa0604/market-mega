"""Admin'larning Telegram chat ID'larini topish.

`.env`'dagi ADMIN_TELEGRAM_ID — bir nechta ID'lar (vergul bilan)
ADMIN_TG_USERNAME — bitta username, DB'dan qidiriladi.
Ikkala manba ham qo'llab-quvvatlanadi va birlashtiriladi.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User


async def get_admin_chat_ids(db: AsyncSession) -> list[int]:
    """Barcha admin'larning telegram_id'sini qaytaradi."""
    ids: set[int] = set(settings.ADMIN_TELEGRAM_ID or [])

    if settings.ADMIN_TG_USERNAME:
        uname = settings.ADMIN_TG_USERNAME.lstrip("@").lower()
        result = await db.execute(
            select(User.telegram_id).where(User.username.ilike(uname))
        )
        tid = result.scalar_one_or_none()
        if tid:
            ids.add(tid)

    return list(ids)


async def get_admin_chat_id(db: AsyncSession) -> int | None:
    """Birinchi admin chat_id (eski koddan moslik uchun)."""
    ids = await get_admin_chat_ids(db)
    return ids[0] if ids else None


def is_admin_user(tg_user) -> bool:
    """Kelayotgan Telegram user adminmi tekshirish (username yoki ID bo'yicha)."""
    if not tg_user:
        return False
    if settings.ADMIN_TELEGRAM_ID and tg_user.id in settings.ADMIN_TELEGRAM_ID:
        return True
    if settings.ADMIN_TG_USERNAME and tg_user.username:
        return tg_user.username.lower() == settings.ADMIN_TG_USERNAME.lstrip("@").lower()
    return False
