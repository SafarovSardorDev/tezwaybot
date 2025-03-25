import os
import logging
import json
from datetime import datetime, date, timedelta
from aiogram import types
from utils.notifications import notify_drivers_about_order
# from aiogram.dispatcher.filters.builtin import CommandStart
from loader import dp, db, bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from states.registerstates import RegistrationForm, OrderState
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from keyboards.defaultbtns import (
                                    get_role_keyboard, 
                                    get_phone_keyboard, 
                                    get_driver_keyboard, 
                                    get_passenger_keyboard
)
load_dotenv()

OWNER_ID = int(os.getenv("OWNER_ID"))



# async def save_user_to_db(user: types.User):
#     """Foydalanuvchi ma'lumotlarini saqlash funksiyasi"""
#     try:
#         print(f"Saving user {user.id} to the database...")

#         if user.id == OWNER_ID:
#             role = "owner"
#         else:
#             existing_admin = await db.user.find_first(where={"telegramId": user.id, "role": "admin"})
#             role = "admin" if existing_admin else "user"

#         existing_user = await db.user.find_first(where={"telegramId": user.id})

#         if existing_user:
#             print(f"User {user.id} exists, updating...")
#             await db.user.update(
#                 where={"telegramId": user.id},
#                 data={
#                     "firstName": user.first_name,
#                     "lastName": user.last_name,
#                     "isPremium": False,
#                     "isBot": user.is_bot,
#                     "languageCode": user.language_code,
#                     "username": user.username,
#                     "role": role, 
#                     "updatedAt": datetime.now()
#                 }
#             )
#         else:
#             print(f"User {user.id} not found, creating...")
#             await db.user.create(
#                 data={
#                     "telegramId": user.id,
#                     "firstName": user.first_name,
#                     "lastName": user.last_name,
#                     "isPremium": False,
#                     "isBot": user.is_bot,
#                     "languageCode": user.language_code,
#                     "username": user.username,
#                     "role": role
#                 }
#             )
#     except Exception as e:
#         print(f"Error saving user to database: {e}")


# Start buyrug'i
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    
    # Foydalanuvchi mavjudligini tekshirish
    user = await db.user.find_unique(
        where={
            'telegramId': str(message.from_user.id)
        }
    )
    
    if user:
        # Mavjud foydalanuvchi uchun tegishli klaviaturani ko'rsatish
        if user.role == "DRIVER":
            await message.answer(f"Salom, {user.firstName}! Haydovchi sifatida tizimga kirdingiz.", 
                                reply_markup=get_driver_keyboard())
        elif user.role == "PASSENGER":
            await message.answer(f"Salom, {user.firstName}! Yo'lovchi sifatida tizimga kirdingiz.", 
                                reply_markup=get_passenger_keyboard())
        else:
            # Admin va Super Admin uchun logika
            await message.answer(f"Salom, {user.firstName}! Admin paneliga xush kelibsiz.")
    else:
        # Yangi foydalanuvchi uchun ro'yxatdan o'tish
        await message.answer("Salom! Botimizga xush kelibsiz. Iltimos, rolni tanlang:", 
                            reply_markup=get_role_keyboard())
        await RegistrationForm.role.set()
    

# Rol tanlash
@dp.message_handler(state=RegistrationForm.role)
async def process_role(message: types.Message, state: FSMContext):
    if message.text not in ["Haydovchi", "Yo'lovchi"]:
        await message.answer("Iltimos, quyidagi tugmalardan birini tanlang!", 
                           reply_markup=get_role_keyboard())
        return
    
    await state.update_data(role="DRIVER" if message.text == "Haydovchi" else "PASSENGER")
    await message.answer("Ismingizni kiriting:", reply_markup=ReplyKeyboardRemove())
    await RegistrationForm.first_name.set()

# Ism olish
@dp.message_handler(state=RegistrationForm.first_name)
async def process_first_name(message: types.Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("Familiyangizni kiriting:")
    await RegistrationForm.last_name.set()

# Familiya olish
@dp.message_handler(state=RegistrationForm.last_name)
async def process_last_name(message: types.Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("Telefon raqamingizni yuborish uchun quyidagi tugmani bosing:", 
                       reply_markup=get_phone_keyboard())
    await RegistrationForm.phone_number.set()

def validate_phone(phone: str) -> bool:
    """Telefon raqamini tekshirish"""
    # Oddiy tekshirish (+998912345678 yoki 991234567 formatida)
    import re
    pattern = r'^(\+998|998|8|)?[\d]{9}$'
    return bool(re.match(pattern, phone))

@dp.message_handler(state=RegistrationForm.phone_number)
async def process_phone(message: types.Message, state: FSMContext):
    # Telefon raqamini validatsiya qilish
    phone = message.text
    if not validate_phone(phone):  # O'zingizning validatsiya funksiyangiz
        await message.answer("❌ Noto'g'ri telefon raqam formati. Iltimos, qayta kiriting:")
        return
    
    # Telefon raqamini saqlash
    await db.user.update(
        where={"telegramId": message.from_user.id},
        data={"phoneNumber": phone}
    )
    
    await message.answer("📞 Telefon raqamingiz qabul qilindi!")
        # Ma'lumotlarni olish
    user_data = await state.get_data()
    
    # Ro'yxatdan o'tkazish
    
    try:
        role_value = user_data['role']
        new_user = await db.user.create(
            data={
                'firstName': user_data['first_name'],
                'lastName': user_data['last_name'],
                'telegramId': str(message.from_user.id),
                'phoneNumber': phone,
                'username': message.from_user.username or "",
                'role': role_value
            }
        )
        
        # Rol asosida klaviatura tanlash
        if role_value == "DRIVER":
            await message.answer(
                f"Tabriklaymiz, {new_user.firstName}! Siz haydovchi sifatida ro'yxatdan o'tdingiz.",
                reply_markup=get_driver_keyboard()
            )
        else:  # PASSENGER
            await message.answer(
                f"Tabriklaymiz, {new_user.firstName}! Siz yo'lovchi sifatida ro'yxatdan o'tdingiz.",
                reply_markup=get_passenger_keyboard()
            )
            
    except Exception as e:
        logging.error(f"Ro'yxatdan o'tkazishda xatolik: {e}")
        await message.answer("Ro'yxatdan o'tkazishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
    
    await state.finish()

# Telefon raqam olish
@dp.message_handler(content_types=types.ContentType.CONTACT, state=RegistrationForm.phone_number)
async def process_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    
    # Ma'lumotlarni olish
    user_data = await state.get_data()
    
    # Ro'yxatdan o'tkazish
    
    try:
        role_value = user_data['role']
        new_user = await db.user.create(
            data={
                'firstName': user_data['first_name'],
                'lastName': user_data['last_name'],
                'telegramId': str(message.from_user.id),
                'phoneNumber': phone_number,
                'username': message.from_user.username or "",
                'role': role_value
            }
        )
        
        # Rol asosida klaviatura tanlash
        if role_value == "DRIVER":
            await message.answer(
                f"Tabriklaymiz, {new_user.firstName}! Siz haydovchi sifatida ro'yxatdan o'tdingiz.",
                reply_markup=get_driver_keyboard()
            )
        else:  # PASSENGER
            await message.answer(
                f"Tabriklaymiz, {new_user.firstName}! Siz yo'lovchi sifatida ro'yxatdan o'tdingiz.",
                reply_markup=get_passenger_keyboard()
            )
            
    except Exception as e:
        logging.error(f"Ro'yxatdan o'tkazishda xatolik: {e}")
        await message.answer("Ro'yxatdan o'tkazishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
    
    await state.finish()

# Profilni ko'rish
@dp.message_handler(lambda message: message.text == "Profilim")
async def show_profile(message: types.Message):

    
    user = await db.user.find_unique(
        where={
            'telegramId': str(message.from_user.id)
        }
    )
    
    if user:
        profile_text = (
            f"👤 Ism: {user.firstName}\n"
            f"👤 Familiya: {user.lastName}\n"
            f"📱 Telefon: {user.phoneNumber}\n"
            f"""🔑 Rol: {"Haydovchi" if user.role == "DRIVER" else "Yo'lovchi"}\n"""
            f"📅 Ro'yxatdan o'tilgan sana: {user.createdAt.strftime('%d.%m.%Y')}"
        )
        await message.answer(profile_text)
    else:
        await message.answer("Siz ro'yxatdan o'tmagansiz. /start buyrug'ini bosing.")
    

# Foydalanish qo'llanmasi
@dp.message_handler(lambda message: message.text == "Foydalanish qo'llanmasi")
async def show_manual(message: types.Message):

    
    user = await db.user.find_unique(
        where={
            'telegramId': str(message.from_user.id)
        }
    )
    
    if not user:
        await message.answer("Siz ro'yxatdan o'tmagansiz. /start buyrug'ini bosing.")
    else:
        if user.role == "DRIVER":
            manual_text = (
                "🚗 Haydovchi uchun qo'llanma:\n\n"
                "1. 'Profilim' - shaxsiy ma'lumotlarni ko'rish\n"
                "2. 'Foydalanish qo'llanmasi' - ushbu qo'llanmani ko'rish\n"
                "\nQo'shimcha funksiyalar keyinchalik qo'shiladi."
            )
        else:  # PASSENGER
            manual_text = (
                "🚶 Yo'lovchi uchun qo'llanma:\n\n"
                "1. 'Yo'lga otlanish' - yangi yo'l buyurtmasini berish\n"
                "2. 'Profilim' - shaxsiy ma'lumotlarni ko'rish\n"
                "3. 'Buyurtma tarixi' - avvalgi buyurtmalarni ko'rish\n"
                "4. 'Foydalanish qo'llanmasi' - ushbu qo'llanmani ko'rish\n"
                "\nQo'shimcha funksiyalar keyinchalik qo'shiladi."
            )
            
        await message.answer(manual_text)
    





    
