"""
Telegram bot handlerlari.

Yangi oqim:
1. /start              -> telefon so'rash
2. contact             -> ro'yxatdan o'tkazish, asosiy menyu
3. 📍 Lokatsiya         -> user.last_lat/last_lng saqlanadi (admin'ga xabar yo'q)
4. Mini app savatida   -> buyurtma yuborish API'si chaqiriladi, admin xabardor qilinadi
"""
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select

from app.bot.keyboards import (
    admin_menu_kb,
    admin_panel_inline_kb,
    main_menu_kb,
    phone_request_kb,
)
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import User
from app.utils.admin_lookup import is_admin_user

router = Router(name="main")


# ---------------------------------------------------------------
# /start — ro'yxatdan o'tish
# ---------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_user = message.from_user
    if not tg_user:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=tg_user.id,
                full_name=tg_user.full_name or "Noma'lum",
                username=tg_user.username,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

    # ============ ADMIN ============
    if is_admin_user(tg_user):
        await message.answer(
            f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
            "Siz <b>admin</b> sifatida tizimga kirgansiz.\n"
            "Quyidagi tugmalardan birini tanlang:",
            reply_markup=admin_menu_kb(),
        )
        await message.answer(
            "🛠 <b>Admin panelni ochish:</b>",
            reply_markup=admin_panel_inline_kb(),
        )
        return

    # ============ ODDIY FOYDALANUVCHI ============
    if not user.phone:
        await message.answer(
            f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
            "Buyurtma berish uchun avval telefon raqamingizni yuboring.\n"
            "Quyidagi tugmani bosing:",
            reply_markup=phone_request_kb(),
        )
        return

    await message.answer(
        f"Xush kelibsiz, <b>{user.full_name}</b>! 🛍\n\n"
        "Doʻkonni ochish uchun pastda chap tomondagi <b>Menu (☰)</b> tugmasini bosing.\n"
        "Buyurtma yuborishdan oldin <b>📍 Lokatsiya yuborish</b> tugmasini bosib lokatsiyangizni yuboring.",
        reply_markup=main_menu_kb(),
    )


# ---------------------------------------------------------------
# Contact (telefon) qabul qilish
# ---------------------------------------------------------------


@router.message(F.contact)
async def handle_contact(message: Message) -> None:
    tg_user = message.from_user
    contact = message.contact
    if not tg_user or not contact:
        return
    if contact.user_id and contact.user_id != tg_user.id:
        await message.answer("Iltimos, <b>o'z</b> telefon raqamingizni yuboring.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                telegram_id=tg_user.id,
                full_name=tg_user.full_name or contact.first_name or "Noma'lum",
                username=tg_user.username,
            )
            db.add(user)
        user.phone = contact.phone_number
        if contact.first_name and not user.full_name:
            user.full_name = (
                f"{contact.first_name} {contact.last_name or ''}".strip()
            )
        await db.commit()

    await message.answer(
        "✅ Ro'yxatdan o'tdingiz!\n\n"
        "Endi do'konni ochib, mahsulotlarni tanlang.\n"
        "Buyurtmadan oldin <b>📍 Lokatsiya yuborish</b> tugmasini bosing.",
        reply_markup=main_menu_kb(),
    )


# ---------------------------------------------------------------
# Admin tugmalari
# ---------------------------------------------------------------


@router.message(F.text == "🛠 Admin panel")
async def admin_panel_btn(message: Message) -> None:
    if not is_admin_user(message.from_user):
        return
    await message.answer(
        "🛠 <b>Admin panel:</b>",
        reply_markup=admin_panel_inline_kb(),
    )


@router.message(F.text == "📊 Buyurtmalar")
async def admin_orders_btn(message: Message) -> None:
    if not is_admin_user(message.from_user):
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📊 Buyurtmalar ro'yxati", url=f"{settings.admin_url}/orders")
    ]])
    await message.answer("📊 <b>Buyurtmalar:</b>", reply_markup=kb)


# ---------------------------------------------------------------
# Yordam
# ---------------------------------------------------------------


@router.message(F.text == "📞 Yordam")
async def help_btn(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Buyurtma berish tartibi</b>\n\n"
        "1. Pastda chap tomondagi <b>Menu (☰)</b> tugmasini bosing — doʻkon ochiladi\n"
        "2. Kategoriyani tanlang, mahsulotlardan <b>+</b> bilan soni oshiring\n"
        "3. Mini appda <b>«🛒 Savatim»</b> bo'limiga o'ting\n"
        "4. Pastdagi <b>«📍 Lokatsiya yuborish»</b> tugmasi orqali lokatsiyangizni yuboring\n"
        "5. Mini app savatida <b>«🛒 Buyurtma yuborish»</b> tugmasini bosing\n"
        "6. Admin siz bilan bogʻlanadi\n\n"
        "<b>💬 Chat:</b> Mini app'ning «Chat» tab'i orqali admin'ga xabar yozishingiz mumkin."
    )


# ---------------------------------------------------------------
# Lokatsiya qabul qilish — user'ga saqlaymiz, admin'ga xabar yo'q
# ---------------------------------------------------------------


@router.message(F.location)
async def handle_location(message: Message) -> None:
    loc = message.location
    tg_user = message.from_user
    if not loc or not tg_user:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("Avval /start yuboring.")
            return
        user.last_lat = loc.latitude
        user.last_lng = loc.longitude
        await db.commit()

    await message.answer(
        "✅ <b>Lokatsiyangiz saqlandi!</b>\n\n"
        "Endi mini app savatiga o'ting va <b>«🛒 Buyurtma yuborish»</b> tugmasini bosing.",
        reply_markup=main_menu_kb(),
    )


# ---------------------------------------------------------------
# Eski mini app fallback
# ---------------------------------------------------------------


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message) -> None:
    """Eski mini app versiyalari uchun fallback (foydalanmaydi)."""
    await message.answer(
        "ℹ️ Mini app yangilangan. Iltimos, mini appni qayta oching.",
        reply_markup=main_menu_kb(),
    )


# ---------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Men sizni tushunmadim. /start buyrug'ini yuboring yoki pastdagi tugmalardan foydalaning.",
        reply_markup=main_menu_kb(),
    )


def register_handlers() -> Router:
    return router
