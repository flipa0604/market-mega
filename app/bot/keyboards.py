from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.config import settings


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Telefon raqamingizni yuboring",
    )


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Oddiy foydalanuvchi uchun: faqat Yordam.
    Doʻkon chap tomondagi Menu (☰) tugmasi orqali ochiladi.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Yordam")],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    """Admin uchun: admin panel + Buyurtmalar + Yordam.
    Doʻkon chap tomondagi Menu (☰) tugmasi orqali ochiladi.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Admin panel"), KeyboardButton(text="📊 Buyurtmalar")],
            [KeyboardButton(text="📞 Yordam")],
        ],
        resize_keyboard=True,
    )


def admin_panel_inline_kb() -> InlineKeyboardMarkup:
    """Admin panel'ga to'g'ridan-to'g'ri inline link tugma"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛠 Admin panelni ochish",
                    url=settings.admin_url,
                )
            ]
        ]
    )


def location_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
