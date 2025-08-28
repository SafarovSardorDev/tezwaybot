from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
from prisma.models import Region, District


def admin_main_menu():
    """Admin asosiy menyu"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🌍 Regionlar", callback_data="manage_regions"),
        InlineKeyboardButton("🏢 Tumanlari", callback_data="manage_districts")
    )
    keyboard.add(
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton("❌ Yopish", callback_data="close_admin")
    )
    return keyboard


def regions_menu():
    """Regionlar boshqaruv menyu"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Region qo'shish", callback_data="add_region"),
        InlineKeyboardButton("📝 Region tahrirlash", callback_data="edit_region")
    )
    keyboard.add(
        InlineKeyboardButton("🗑 Region o'chirish", callback_data="delete_region"),
        InlineKeyboardButton("📋 Regionlar ro'yxati", callback_data="list_regions")
    )
    keyboard.add(
        InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin_main")
    )
    return keyboard


def districts_menu():
    """Tumanlar boshqaruv menyu"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Tuman qo'shish", callback_data="add_district"),
        InlineKeyboardButton("📝 Tuman tahrirlash", callback_data="edit_district")
    )
    keyboard.add(
        InlineKeyboardButton("🗑 Tuman o'chirish", callback_data="delete_district"),
        InlineKeyboardButton("📋 Tumanlar ro'yxati", callback_data="list_districts")
    )
    keyboard.add(
        InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin_main")
    )
    return keyboard


def regions_list_keyboard(regions: List[Region], action: str):
    """Regionlar ro'yxati tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for region in regions:
        callback_data = f"{action}_region_{region.id}"
        keyboard.add(
            InlineKeyboardButton(f"🌍 {region.name}", callback_data=callback_data)
        )
    
    keyboard.add(
        InlineKeyboardButton("⬅️ Orqaga", callback_data="manage_regions")
    )
    return keyboard


def districts_list_keyboard(districts: List[District], action: str):
    """Tumanlar ro'yxati tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for district in districts:
        callback_data = f"{action}_district_{district.id}"
        keyboard.add(
            InlineKeyboardButton(f"🏢 {district.name}", callback_data=callback_data)
        )
    
    keyboard.add(
        InlineKeyboardButton("⬅️ Orqaga", callback_data="manage_districts")
    )
    return keyboard


def confirm_delete_keyboard(item_type: str, item_id: int):
    """O'chirishni tasdiqlash tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Ha", callback_data=f"confirm_delete_{item_type}_{item_id}"),
        InlineKeyboardButton("❌ Yo'q", callback_data=f"cancel_delete_{item_type}")
    )
    return keyboard


def cancel_keyboard():
    """Bekor qilish tugmasi"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_action")
    )
    return keyboard


def regions_for_district_keyboard(regions: List[Region]):
    """Tuman uchun region tanlash tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for region in regions:
        keyboard.add(
            InlineKeyboardButton(f"🌍 {region.name}", callback_data=f"select_region_{region.id}")
        )
    
    keyboard.add(
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_action")
    )
    return keyboard


def back_to_districts_keyboard():
    """Tumanlar menyusiga qaytish"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("⬅️ Tumanlar menyusi", callback_data="manage_districts")
    )
    return keyboard


def back_to_regions_keyboard():
    """Regionlar menyusiga qaytish"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("⬅️ Regionlar menyusi", callback_data="manage_regions")
    )
    return keyboard