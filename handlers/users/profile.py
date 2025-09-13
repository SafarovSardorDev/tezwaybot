from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from loader import dp, db, bot
from keyboards.defaultbtns import get_driver_keyboard, get_passenger_keyboard, get_phone_keyboard
from keyboards.edit_profile import get_profile_keyboard, get_edit_field_keyboard, get_back_to_profile_keyboard
from utils.validators import normalize_phone, validate_phone
from states.registerstates import EditProfile
from dotenv import load_dotenv
import os
import logging

# Profile text formatter
async def format_profile_text(user):
    role_text = {
        "DRIVER": "Haydovchi", 
        "PASSENGER": "Yo'lovchi", 
        "ADMIN": "Admin", 
        "SUPER_ADMIN": "Super Admin"
    }
    
    return (
        f"👤 <b>Profil Ma'lumotlari</b>\n\n"
        f"🏷️ Ism: {user.firstName}\n"
        f"🏷️ Familiya: {user.lastName}\n"
        f"📱 Telefon: {user.phoneNumber}\n"
        f"👨‍💻 Maqom: {role_text.get(user.role, user.role)}\n"
        f"📅 Ro'yxatdan o'tilgan: {user.createdAt.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Quyidagi tugmalar orqali ma'lumotlaringizni tahrirlashingiz mumkin:"
    )

# Profile handlers
@dp.message_handler(lambda message: message.text == "⚙️ Profilim", state="*")
async def show_profile(message: types.Message, state: FSMContext):
    """Display user profile with edit options"""
    await state.finish()  # Clear any previous states
    
    user = await db.user.find_unique(where={'telegramId': str(message.from_user.id)})
    
    if not user:
        await message.answer("Siz ro'yxatdan o'tmagansiz. /start buyrug'ini bosing.")
        return

    profile_text = await format_profile_text(user)
    markup = get_profile_keyboard()
    
    await message.answer(profile_text, reply_markup=markup, parse_mode=types.ParseMode.HTML)

# Edit field handlers
@dp.callback_query_handler(lambda c: c.data == "edit_first_name")
async def edit_first_name(callback_query: types.CallbackQuery, state: FSMContext):
    """Edit first name"""
    await callback_query.message.edit_text(
        "Yangi ismingizni kiriting:",
        reply_markup=get_edit_field_keyboard("first_name")
    )
    await EditProfile.first_name.set()
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "edit_last_name")
async def edit_last_name(callback_query: types.CallbackQuery, state: FSMContext):
    """Edit last name"""
    await callback_query.message.edit_text(
        "Yangi familiyangizni kiriting:",
        reply_markup=get_edit_field_keyboard("last_name")
    )
    await EditProfile.last_name.set()
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "edit_phone")
async def edit_phone(callback_query: types.CallbackQuery, state: FSMContext):
    """Edit phone number"""
    await callback_query.message.edit_text(
        "Yangi telefon raqamingizni yuboring yoki tugma orqali ulashing:",
        reply_markup=get_edit_field_keyboard("phone")
    )
    await EditProfile.phone.set()
    await callback_query.answer()

# Field value handlers
@dp.message_handler(state=EditProfile.first_name)
async def process_first_name(message: types.Message, state: FSMContext):
    """Process new first name"""
    new_first_name = message.text.strip()
    
    if len(new_first_name) < 2:
        await message.answer("Ism juda qisqa. Iltimos, qaytadan kiriting:")
        return
    
    try:
        user = await db.user.update(
            where={'telegramId': str(message.from_user.id)},
            data={'firstName': new_first_name}
        )
        
        await message.answer("✅ Ismingiz muvaffaqiyatli yangilandi!", 
                           reply_markup=get_back_to_profile_keyboard())
        
    except Exception as e:
        logging.error(f"Ismni yangilashda xato: {e}")
        await message.answer("⚠️ Ismni yangilashda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.",
                           reply_markup=get_back_to_profile_keyboard())
    
    await state.finish()

@dp.message_handler(state=EditProfile.last_name)
async def process_last_name(message: types.Message, state: FSMContext):
    """Process new last name"""
    new_last_name = message.text.strip()
    
    if len(new_last_name) < 2:
        await message.answer("Familiya juda qisqa. Iltimos, qaytadan kiriting:")
        return
    
    try:
        user = await db.user.update(
            where={'telegramId': str(message.from_user.id)},
            data={'lastName': new_last_name}
        )
        
        await message.answer("✅ Familiyangiz muvaffaqiyatli yangilandi!", 
                           reply_markup=get_back_to_profile_keyboard())
        
    except Exception as e:
        logging.error(f"Familiyani yangilashda xato: {e}")
        await message.answer("⚠️ Familiyani yangilashda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.",
                           reply_markup=get_back_to_profile_keyboard())
    
    await state.finish()

@dp.message_handler(state=EditProfile.phone, content_types=types.ContentType.ANY)
async def process_phone(message: types.Message, state: FSMContext):
    """Process new phone number"""
    if message.content_type == types.ContentType.CONTACT:
        phone = message.contact.phone_number
    else:
        phone = message.text
    
    phone = normalize_phone(phone)
    is_valid, error_message = validate_phone(phone)
    
    if not is_valid:
        await message.answer(f"❌ {error_message}\nIltimos, qaytadan kiriting:")
        return
    
    try:
        user = await db.user.update(
            where={'telegramId': str(message.from_user.id)},
            data={'phoneNumber': phone}
        )
        
        await message.answer("✅ Telefon raqamingiz muvaffaqiyatli yangilandi!", 
                           reply_markup=get_back_to_profile_keyboard())
        
    except Exception as e:
        logging.error(f"Telefon raqamini yangilashda xato: {e}")
        await message.answer("⚠️ Telefon raqamini yangilashda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.",
                           reply_markup=get_back_to_profile_keyboard())
    
    await state.finish()

# Cancel edit handlers
@dp.callback_query_handler(lambda c: c.data.startswith("cancel_edit_"), state="*")
async def cancel_edit(callback_query: types.CallbackQuery, state: FSMContext):
    """Cancel editing and return to profile"""
    await state.finish()
    
    user = await db.user.find_unique(where={'telegramId': str(callback_query.from_user.id)})
    
    if not user:
        await callback_query.message.edit_text("Siz ro'yxatdan o'tmagansiz.")
        return

    profile_text = await format_profile_text(user)
    markup = get_profile_keyboard()
    
    await callback_query.message.edit_text(profile_text, reply_markup=markup, parse_mode=types.ParseMode.HTML)
    await callback_query.answer("Tahrirlash bekor qilindi")

# Back to profile handler
@dp.callback_query_handler(lambda c: c.data == "back_to_profile")
async def back_to_profile(callback_query: types.CallbackQuery, state: FSMContext):
    """Return to profile view"""
    await state.finish()
    
    user = await db.user.find_unique(where={'telegramId': str(callback_query.from_user.id)})
    
    if not user:
        await callback_query.message.edit_text("Siz ro'yxatdan o'tmagansiz.")
        return

    profile_text = await format_profile_text(user)
    markup = get_profile_keyboard()
    
    await callback_query.message.edit_text(profile_text, reply_markup=markup, parse_mode=types.ParseMode.HTML)
    await callback_query.answer()

# Back to main menu handler
@dp.callback_query_handler(lambda c: c.data == "back_to_main")
async def back_to_main_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """Return to main menu"""
    await state.finish()
    
    try:
        await callback_query.message.delete()
    except Exception as e:
        logging.error(f"Xabarni o'chirishda xato: {e}")

    user = await db.user.find_unique(where={'telegramId': str(callback_query.from_user.id)})
    
    if not user:
        await bot.send_message(
            chat_id=callback_query.from_user.id,
            text="Siz ro'yxatdan o'tmagansiz. /start buyrug'ini bosing."
        )
        return

    if user.role == "DRIVER":
        keyboard = get_driver_keyboard()
        welcome_text = f"Yaxshi {user.firstName} keyingi qadamni tanlashingiz mumkin."
    else:
        keyboard = get_passenger_keyboard()
        welcome_text = f"Yaxshi {user.firstName} keyingi qadamni tanlashingiz mumkin."
    
    await bot.send_message(
        chat_id=callback_query.from_user.id,
        text=welcome_text,
        reply_markup=keyboard
    )
    
    await callback_query.answer()