"""
Telegram bot handlerlari.

Oqim:
1. /start            -> telefon so'rash
2. contact            -> user ro'yxatdan o'tadi, "Do'konni ochish" tugmasi
3. web_app_data       -> mini app'dan order_id keladi, lokatsiya so'raladi
4. location           -> buyurtma yakunlanadi, admin xabardor qilinadi
"""
import json
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.bot import bot
from app.bot.keyboards import (
    admin_menu_kb,
    admin_panel_inline_kb,
    location_request_kb,
    main_menu_kb,
    phone_request_kb,
    remove_kb,
)
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Order, OrderStatus, User
from app.utils.admin_lookup import get_admin_chat_id, is_admin_user

router = Router(name="main")


class OrderFlow(StatesGroup):
    waiting_for_location = State()


# ---------------------------------------------------------------
# /start — ro'yxatdan o'tish
# ---------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
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
        "Doʻkonga kirish uchun pastdagi tugmani bosing.",
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
        "✅ Ro'yxatdan o'tdingiz!\n\nEndi do'konni ochib, mahsulotlarni ko'rishingiz mumkin.",
        reply_markup=main_menu_kb(),
    )


# ---------------------------------------------------------------
# Yordam tugmasi
# ---------------------------------------------------------------


# Admin tugmalari
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


@router.message(F.text == "📞 Yordam")
async def help_btn(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "1. «🛍 Do'konni ochish» tugmasini bosing\n"
        "2. Kategoriyani tanlang, mahsulotlardan <b>+</b> bilan soni oshiring\n"
        "3. «Tanladim» tugmasini bosing\n"
        "4. Bot so'raganda <b>lokatsiyangizni</b> yuboring\n"
        "5. Admin siz bilan bog'lanadi"
    )


# ---------------------------------------------------------------
# Mini App'dan keladigan data (tg.sendData)
# ---------------------------------------------------------------


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, state: FSMContext) -> None:
    raw = message.web_app_data.data if message.web_app_data else None
    if not raw:
        return
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await message.answer("❌ Noto'g'ri ma'lumot keldi.")
        return

    order_id = payload.get("order_id")
    if not order_id:
        await message.answer("❌ Buyurtma ID topilmadi.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
        )
        order = result.scalar_one_or_none()
        if not order:
            await message.answer("❌ Buyurtma topilmadi.")
            return

        items_text = "\n".join(
            f"  • {it.product_name} × {it.quantity} = "
            f"{float(it.unit_price) * it.quantity:,.0f} so'm"
            for it in order.items
        )
        total = float(order.total_price)

    await state.update_data(order_id=order_id)
    await state.set_state(OrderFlow.waiting_for_location)

    await message.answer(
        f"📦 <b>Buyurtma #{order_id} qabul qilindi!</b>\n\n"
        f"{items_text}\n\n"
        f"<b>Jami: {total:,.0f} so'm</b>\n\n"
        f"📍 Yetkazib berish uchun <b>lokatsiyangizni</b> yuboring:",
        reply_markup=location_request_kb(),
    )


# ---------------------------------------------------------------
# Lokatsiya qabul qilish
# ---------------------------------------------------------------


@router.message(OrderFlow.waiting_for_location, F.text == "❌ Bekor qilish")
async def cancel_order(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")

    async with AsyncSessionLocal() as db:
        order = await db.get(Order, order_id) if order_id else None
        if order and order.status == OrderStatus.pending_location:
            order.status = OrderStatus.canceled
            await db.commit()

    await state.clear()
    await message.answer(
        "❌ Buyurtma bekor qilindi.",
        reply_markup=main_menu_kb(),
    )


@router.message(OrderFlow.waiting_for_location, F.location)
async def handle_location(message: Message, state: FSMContext) -> None:
    loc = message.location
    tg_user = message.from_user
    if not loc or not tg_user:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("❌ Buyurtma ma'lumoti yo'qolgan. /start ni qayta bosing.")
        await state.clear()
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.user))
        )
        order = result.scalar_one_or_none()
        if not order:
            await message.answer("❌ Buyurtma topilmadi.")
            await state.clear()
            return

        order.latitude = loc.latitude
        order.longitude = loc.longitude
        order.status = OrderStatus.new
        order.completed_at = datetime.now(timezone.utc)
        if order.user and order.user.phone and not order.customer_phone:
            order.customer_phone = order.user.phone
        if order.user and not order.customer_name:
            order.customer_name = order.user.full_name
        await db.commit()
        await db.refresh(order, attribute_names=["items", "user"])

        customer_name = order.customer_name or (order.user.full_name if order.user else "—")
        customer_phone = order.customer_phone or (order.user.phone if order.user else "—")
        items_text = "\n".join(
            f"  • {it.product_name} × {it.quantity} = "
            f"{float(it.unit_price) * it.quantity:,.0f} so'm"
            for it in order.items
        )

    await state.clear()
    await message.answer(
        "✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"Buyurtma raqami: <b>#{order.id}</b>\n"
        "Tez orada operator siz bilan bog'lanadi.",
        reply_markup=main_menu_kb(),
    )

    # Admin xabarnomasi (.env: ADMIN_TELEGRAM_ID yoki ADMIN_TG_USERNAME orqali)
    async with AsyncSessionLocal() as adb:
        admin_chat_id = await get_admin_chat_id(adb)
    if admin_chat_id:
        try:
            await bot.send_message(
                admin_chat_id,
                f"🆕 <b>Yangi buyurtma #{order.id}</b>\n\n"
                f"👤 {customer_name}\n"
                f"📞 {customer_phone}\n\n"
                f"{items_text}\n\n"
                f"💰 Jami: <b>{float(order.total_price):,.0f} so'm</b>",
            )
            await bot.send_location(
                admin_chat_id,
                latitude=loc.latitude,
                longitude=loc.longitude,
            )
        except Exception:  # noqa: BLE001
            pass


@router.message(OrderFlow.waiting_for_location)
async def wrong_location(message: Message) -> None:
    await message.answer(
        "Iltimos, <b>lokatsiya</b> yuboring yoki «❌ Bekor qilish» tugmasini bosing.",
        reply_markup=location_request_kb(),
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
