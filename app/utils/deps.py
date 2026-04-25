"""FastAPI dependencylar."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.utils.security import current_admin
from app.utils.telegram_auth import TelegramAuthError, verify_init_data


async def require_admin(request: Request) -> str:
    """HTML sahifa uchun — agar login qilinmagan bo'lsa, /admin/login'ga yo'naltiradi."""
    admin = current_admin(request)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"},
        )
    return admin


async def require_admin_api(request: Request) -> str:
    """API endpointlari uchun — JSON 401 qaytaradi."""
    admin = current_admin(request)
    if not admin:
        raise HTTPException(status_code=401, detail="Auth kerak")
    return admin


async def get_webapp_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Mini app so'rovlarida foydalanuvchini aniqlash.

    Klient `X-Telegram-Init-Data` sarlavhasida initData yuboradi.
    Biz uni tekshiramiz va `users` jadvalidan User qaytaramiz.
    """
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        raise HTTPException(status_code=401, detail="initData yo'q")

    try:
        parsed = verify_init_data(init_data, settings.BOT_TOKEN)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=f"Auth xato: {exc}") from exc

    tg_user = parsed.get("user") or {}
    tg_id = tg_user.get("id")
    if not tg_id:
        raise HTTPException(status_code=401, detail="user.id topilmadi")

    result = await db.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if user is None:
        # Agar mini app /start'dan oldin ochilsa, demo holatda user'ni avto yaratamiz
        user = User(
            telegram_id=tg_id,
            full_name=f"{tg_user.get('first_name', '')} {tg_user.get('last_name', '')}".strip()
            or "Noma'lum",
            username=tg_user.get("username"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


# Yordamchi: redirect qilish kerak bo'lganda
def redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/admin/login", status_code=302)
