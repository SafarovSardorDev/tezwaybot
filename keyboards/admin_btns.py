from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_menu():
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2   # Har qatorga maksimal nechta tugma chiqishini belgilaydi
    )
    keyboard.add(
        KeyboardButton("➕ Viloyat qo'shish"),
        KeyboardButton("➕ Tuman qo'shish")
    )
    keyboard.add(
        KeyboardButton("📊 Statistika")
    )
    return keyboard


def cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Bekor qilish"))
    return keyboard

def confirmation_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Ha", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Yo'q", callback_data="confirm_no")
    )
    return keyboard