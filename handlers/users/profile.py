from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from loader import dp, db, bot
from keyboards.defaultbtns import get_role_keyboard, get_phone_keyboard, get_driver_keyboard, get_passenger_keyboard
from utils.validators import normalize_phone, validate_phone
from dotenv import load_dotenv
import os
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
OWNER_ID = int(os.getenv("OWNER_ID"))
BOT_USERNAME = os.getenv("BOT_USERNAME")

class EditProfile(StatesGroup):
    first_name = State()
    last_name = State()
    phone_number = State()

class ChangeRole(StatesGroup):
    role = State()

@dp.message_handler(lambda message: message.text == "⚙️ Profilim", state="*")
async def show_profile(message: types.Message, state: FSMContext):
    """Foydalanuvchi profilini ko'rsatish va tahrirlash/rol o'zgartirish imkoniyatini berish."""

    user = await db.user.find_unique(where={'telegramId': str(message.from_user.id)})
    
    if not user:
        await message.answer("Siz ro'yxatdan o'tmagansiz. /start buyrug'ini bosing.")
        return

    role_text = {"DRIVER": "Haydovchi", "PASSENGER": "Yo'lovchi", "ADMIN": "Admin", "SUPER_ADMIN": "Super Admin"}
    profile_text = (
        f"👤 Ism: {user.firstName}\n"
        f"👤 Familiya: {user.lastName}\n"
        f"📱 Telefon: {user.phoneNumber}\n"
        f"📅 Ro'yxatdan o'tilgan sana: {user.createdAt.strftime('%d.%m.%Y')}"
    )
    
    markup = InlineKeyboardMarkup(row_width=1) 
    markup.add(
        InlineKeyboardButton("✏️ Profilni tahrirlash", callback_data="edit_profile"),
        # InlineKeyboardButton("🔄 Rolni o'zgartirish", callback_data="change_role"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
    )
    
    await message.answer(profile_text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "edit_profile")
async def start_edit_profile(callback_query: types.CallbackQuery, state: FSMContext):
    """Profil tahrirlash jarayonini boshlash."""
    await callback_query.message.edit_text("Ismingizni kiriting:")
    await EditProfile.first_name.set()

@dp.message_handler(state=EditProfile.first_name)
async def process_edit_first_name(message: types.Message, state: FSMContext):
    """Yangi ismni saqlash va familiya so'rash."""
    await state.update_data(first_name=message.text)
    await message.answer("Familiyangizni kiriting:")
    await EditProfile.last_name.set()

@dp.message_handler(state=EditProfile.last_name)
async def process_edit_last_name(message: types.Message, state: FSMContext):
    """Yangi familiyani saqlash va telefon raqamini so'rash."""
    await state.update_data(last_name=message.text)
    await message.answer("Telefon raqamingizni yuborish uchun quyidagi tugmani bosing:", 
                        reply_markup=get_phone_keyboard())
    await EditProfile.phone_number.set()

@dp.message_handler(content_types=types.ContentType.CONTACT, state=EditProfile.phone_number)
@dp.message_handler(state=EditProfile.phone_number)
async def process_edit_phone(message: types.Message, state: FSMContext):
    """Telefon raqamini tekshirish va profilni yangilash."""
    phone = message.contact.phone_number if message.content_type == types.ContentType.CONTACT else message.text
    phone = normalize_phone(phone)
    is_valid, error_message = validate_phone(phone)
    
    if not is_valid:
        await message.answer(f"❌ {error_message}")
        return
    
    user_data = await state.get_data()
    try:
        user = await db.user.update(
            where={'telegramId': str(message.from_user.id)},
            data={
                'firstName': user_data['first_name'],
                'lastName': user_data['last_name'],
                'phoneNumber': phone
            }
        )
        role = user.role
        await message.answer(
            "✅ Profil ma'lumotlari muvaffaqiyatli yangilandi!",
            reply_markup=get_driver_keyboard() if role == "DRIVER" else get_passenger_keyboard()
        )
        await state.finish()
    except Exception as e:
        logging.error(f"Profilni tahrirlashda xato: {e}")
        await message.answer("⚠️ Profilni yangilashda xatolik yuz berdi.")
        await state.finish()

# @dp.callback_query_handler(lambda c: c.data == "change_role")
# async def start_change_role(callback_query: types.CallbackQuery, state: FSMContext):
#     """Rolni o'zgartirish jarayonini boshlash."""
#     user = await db.user.find_unique(where={'telegramId': str(callback_query.from_user.id)})
    
#     if not user:
#         await callback_query.answer("❌ Siz ro'yxatdan o'tmagansiz.", show_alert=True)
#         return
    
#     if user.role != "SUPER_ADMIN":
#         markup = InlineKeyboardMarkup(row_width=1)
#         markup.add(
#             InlineKeyboardButton("📞 Admin bilan bog'lanish", url=f"tg://user?id={OWNER_ID}"),
#             InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
#         )
#         await callback_query.message.edit_text(
#             "⛔️ Faqat Super Adminlar rolni o'zgartira oladi. Iltimos, admin bilan bog'laning.",
#             reply_markup=markup
#         )
#         await callback_query.answer()
#         return
    
#     await callback_query.message.edit_text("Yangi rolni tanlang:", reply_markup=get_role_keyboard())
#     await ChangeRole.role.set()

# @dp.message_handler(state=ChangeRole.role)
# async def process_change_role(message: types.Message, state: FSMContext):
#     """Yangi rolni saqlash."""
#     if message.text not in ["Haydovchi", "Yo'lovchi"]:
#         await message.answer("Iltimos, quyidagi tugmalardan birini tanlang!", reply_markup=get_role_keyboard())
#         return
    
#     role = "DRIVER" if message.text == "Haydovchi" else "PASSENGER"
#     try:
#         user = await db.user.update(
#             where={'telegramId': str(message.from_user.id)},
#             data={'role': role}
#         )
#         await message.answer(
#             f"✅ Rol {message.text} ga o'zgartirildi!",
#             reply_markup=get_driver_keyboard() if role == "DRIVER" else get_passenger_keyboard()
#         )
#         await state.finish()
#     except Exception as e:
#         logging.error(f"Rolni o'zgartirishda xato: {e}")
#         await message.answer("⚠️ Rolni o'zgartirishda xatolik yuz berdi.")
#         await state.finish()

@dp.callback_query_handler(lambda c: c.data == "back_to_main", state="*")
async def back_to_main(callback_query: types.CallbackQuery, state: FSMContext):
    """Asosiy menyu - profile xabarini o'chirish va keyboard qaytarish."""
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
    elif user.role == "PASSENGER":
        keyboard = get_passenger_keyboard()
        welcome_text = f"Yaxshi {user.firstName} keyingi qadamni tanlashingiz mumkin."
    else:
        keyboard = None
        welcome_text = f"Yaxshi {user.firstName} keyingi qadamni tanlashingiz mumkin."
    
    await bot.send_message(
        chat_id=callback_query.from_user.id,
        text=welcome_text,
        reply_markup=keyboard
    )
    
    await callback_query.answer()