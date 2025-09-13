from aiogram import types

# Inline keyboardlarni to'g'ridan-to'g'ri shu faylda yaratamiz
def get_profile_keyboard():
    """Profil uchun inline keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✏️ Ism", callback_data="edit_first_name"),
        types.InlineKeyboardButton("✏️ Familiya", callback_data="edit_last_name"),
        types.InlineKeyboardButton("✏️ Telefon", callback_data="edit_phone"),
        types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
    )
    return markup

def get_edit_field_keyboard(field):
    """Maydonni tahrirlash uchun keyboard"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Bekor qilish", callback_data=f"cancel_edit_{field}"))
    return markup

def get_back_to_profile_keyboard():
    """Profilga qaytish uchun keyboard"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Profilga qaytish", callback_data="back_to_profile"))
    return markup