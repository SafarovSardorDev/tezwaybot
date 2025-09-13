from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_menu():
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )
    keyboard.add(
        KeyboardButton("Viloyatlar"),
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

def back_keyboard(callback_data="back"):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data=callback_data))
    return keyboard

def region_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📋 Viloyatlar ro'yxati", callback_data="region_list"),
        InlineKeyboardButton("➕ Viloyat qo'shish", callback_data="add_region")
    )
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
    return keyboard

def region_actions_keyboard(region_id, has_districts=False):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_region_{region_id}"),
        InlineKeyboardButton("🗑️ O'chirish", callback_data=f"delete_region_{region_id}")
    )
    keyboard.add(
        InlineKeyboardButton("🏘️ Tumanlar", callback_data=f"region_districts_{region_id}"),
        InlineKeyboardButton("➕ Tuman qo'shish", callback_data=f"add_district_{region_id}")
    )
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_regions"))
    return keyboard

def district_actions_keyboard(district_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_district_{district_id}"),
        InlineKeyboardButton("🗑️ O'chirish", callback_data=f"delete_district_{district_id}")
    )
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_region_districts"))
    return keyboard

def regions_list_keyboard(regions, page=0, items_per_page=8):
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    paginated_regions = regions[start_idx:end_idx]
    
    for region in paginated_regions:
        has_districts = hasattr(region, 'districts') and len(region.districts) > 0
        btn_text = f"{region.name} {'⚠️' if not has_districts else ''}"
        keyboard.add(InlineKeyboardButton(btn_text, callback_data=f"region_{region.id}"))
    
    # Navigation buttons
    row_buttons = []
    if page > 0:
        row_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"regions_page_{page-1}"))
    if end_idx < len(regions):
        row_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"regions_page_{page+1}"))
    
    if row_buttons:
        keyboard.row(*row_buttons)
    
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_region_menu"))
    return keyboard

# keyboards/admin_btns.py da quyidagilarni qo'shamiz yoki yangilaymiz

def districts_list_keyboard(districts, region_id, page=0, items_per_page=8):
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    paginated_districts = districts[start_idx:end_idx]
    
    for district in paginated_districts:
        keyboard.add(InlineKeyboardButton(district.name, callback_data=f"district_{district.id}"))
    
    # Navigation buttons
    row_buttons = []
    if page > 0:
        row_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"districts_page_{page-1}_{region_id}"))
    if end_idx < len(districts):
        row_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"districts_page_{page+1}_{region_id}"))
    
    if row_buttons:
        keyboard.row(*row_buttons)
    
    # To'g'ri callback_data format
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_to_region_{region_id}"))
    return keyboard
    return keyboard