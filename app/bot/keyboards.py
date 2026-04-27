from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
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
    """Oddiy foydalanuvchi uchun: faqat market"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛍 Doʻkonni ochish",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL),
                )
            ],
            [KeyboardButton(text="📞 Yordam")],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    """Admin uchun: market + admin paneliga link"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛍 Doʻkonni ochish",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL),
                )
            ],
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
