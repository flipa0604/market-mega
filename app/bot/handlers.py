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
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import delete, select
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
from app.models import CartItem, Order, OrderItem, OrderStatus, User
from app.utils.admin_lookup import get_admin_chat_ids, is_admin_user

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
        "Doʻkonga kirish uchun pastda chap tomondagi <b>Menu (☰)</b> tugmasini bosing.",
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


@router.message(F.text == "🛒 Buyurtma yuborish")
async def submit_order_btn(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi cart'ini Order'ga aylantirib, lokatsiya so'raydi."""
    tg_user = message.from_user
    if not tg_user:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("Avval /start yuboring.")
            return

        if not user.phone:
            await message.answer(
                "📱 Buyurtma berishdan oldin telefon raqamingizni yuboring:",
                reply_markup=phone_request_kb(),
            )
            return

        # Cart o'qish
        cart_result = await db.execute(
            select(CartItem)
            .where(CartItem.user_id == user.id)
            .options(selectinload(CartItem.product))
        )
        cart_items = list(cart_result.scalars().all())
        active_items = [
            ci for ci in cart_items if ci.product and ci.product.is_active
        ]

        if not active_items:
            await message.answer(
                "🛒 <b>Savatingiz boʻsh.</b>\n\n"
                "Pastdagi <b>Menu (☰)</b> tugmasini bosib doʻkon ochiladi.\n"
                "Mahsulot tanlang va qaytadan urinib koʻring."
            )
            return

        # Order yaratish
        order = Order(
            user_id=user.id,
            status=OrderStatus.pending_location,
            customer_name=user.full_name,
            customer_phone=user.phone,
            total_price=0,
        )
        db.add(order)
        await db.flush()

        total = Decimal("0")
        item_lines = []
        for ci in active_items:
            unit = Decimal(str(ci.product.price))
            line_total = unit * ci.quantity
            total += line_total
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=ci.product_id,
                    product_name=ci.product.name,
                    unit_price=unit,
                    quantity=ci.quantity,
                )
            )
            item_lines.append(
                f"  • {ci.product.name} × {ci.quantity} = "
                f"{float(line_total):,.0f} so'm"
            )
        order.total_price = float(total)

        # Cart'ni tozalash
        await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
        await db.commit()
        await db.refresh(order)

        order_id = order.id
        items_text = "\n".join(item_lines)
        total_float = float(total)

    await state.update_data(order_id=order_id)
    await state.set_state(OrderFlow.waiting_for_location)

    await message.answer(
        f"📦 <b>Buyurtma #{order_id}</b>\n\n"
        f"{items_text}\n\n"
        f"<b>Jami: {total_float:,.0f} so'm</b>\n\n"
        f"📍 Yetkazib berish uchun <b>lokatsiyangizni</b> yuboring:",
        reply_markup=location_request_kb(),
    )


@router.message(F.text == "📞 Yordam")
async def help_btn(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Buyurtma berish tartibi</b>\n\n"
        "1. Pastda chap tomondagi <b>Menu (☰)</b> tugmasini bosing — doʻkon ochiladi\n"
        "2. Kategoriyani tanlang, mahsulotlardan <b>+</b> bilan soni oshiring\n"
        "3. Mini appni yoping va chatdagi «<b>🛒 Buyurtma yuborish</b>» tugmasini bosing\n"
        "4. Bot soʻraganda <b>lokatsiyangizni</b> yuboring\n"
        "5. Admin siz bilan bogʻlanadi\n\n"
        "<b>💬 Chat:</b> Mini app'ning «Chat» tab'i orqali admin'ga xabar yozishingiz mumkin."
    )


# ---------------------------------------------------------------
# Mini App'dan keladigan data (tg.sendData)
# ---------------------------------------------------------------


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message) -> None:
    """Eski mini app versiyalari uchun fallback (foydalanmaydi)."""
    await message.answer(
        "ℹ️ Endi buyurtma yuborish boshqa usulda ishlaydi.\n\n"
        "Pastdagi <b>«🛒 Buyurtma yuborish»</b> tugmasini bosing.",
        reply_markup=main_menu_kb(),
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

    # Admin xabarnomasi (barcha admin'larga)
    async with AsyncSessionLocal() as adb:
        admin_ids = await get_admin_chat_ids(adb)
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 <b>Yangi buyurtma #{order.id}</b>\n\n"
                f"👤 {customer_name}\n"
                f"📞 {customer_phone}\n\n"
                f"{items_text}\n\n"
                f"💰 Jami: <b>{float(order.total_price):,.0f} so'm</b>",
            )
            await bot.send_location(
                admin_id,
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
