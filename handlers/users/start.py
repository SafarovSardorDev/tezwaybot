import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from loader import dp, db, bot
from states.registerstates import RegistrationForm, DriverState
from keyboards.defaultbtns import get_role_keyboard, get_phone_keyboard, get_driver_keyboard, get_passenger_keyboard
from keyboards.admin_btns import admin_main_menu
from utils.validators import normalize_phone, validate_phone
from dotenv import load_dotenv
import os

load_dotenv()
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_IDS = list(map(int, os.getenv("OWNER_ID", "").split(','))) if os.getenv("OWNER_ID") else []

async def get_channel_url():
    """Kanalning URL manzilini olish"""
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        return f"https://t.me/{chat.username.replace('@', '')}" if chat.username else f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
    except Exception as e:
        logging.error(f"Kanal ma'lumotlarini olishda xato: {e}")
        return f"https://t.me/c/{str(CHANNEL_ID)[4:]}"

async def create_admin_user(user_id, first_name, last_name, username):
    """Admin foydalanuvchini yaratish"""
    try:
        # Prisma orqali foydalanuvchini yaratish
        user = await db.user.create({
            'firstName': first_name,
            'lastName': last_name or '',
            'telegramId': user_id,
            'phoneNumber': 'admin',
            'username': username,
            'role': 'ADMIN'
        })
        return user
    except Exception as e:
        logging.error(f"Admin foydalanuvchini yaratishda xato: {e}")
        return None

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    username = message.from_user.username
    
    # Agar foydalanuvchi OWNER_ID lar ro'yxatida bo'lsa
    if user_id in OWNER_IDS:
        user = await db.user.find_unique(
            where={'telegramId': str(user_id)}
        )
        
        # Agar foydalanuvchi bazada yo'q bo'lsa, uni admin sifatida yaratish
        if not user:
            user = await create_admin_user(str(user_id), first_name, last_name, username)
            
            if user:
                await message.answer(f"Salom {first_name}! Siz admin sifatida ro'yxatdan o'tdingiz. Admin paneliga xush kelibsiz!", 
                                    reply_markup=admin_main_menu())
            else:
                await message.answer("Xatolik yuz berdi. Iltimos, qayta urunib ko'ring.")
            return
        
        # Agar foydalanuvchi allaqachon mavjud bo'lsa
        if user.role == "ADMIN" or user.role == "SUPER_ADMIN":
            greeting = f"Salom ADMIN @{username}" if username else f"Salom ADMIN {first_name}"
            await message.answer(f"{greeting}. Admin paneliga xush kelibsiz!", 
                                reply_markup=admin_main_menu())
        else:
            # Agar foydalanuvchi admin emas bo'lsa, rolini yangilash
            await db.user.update(
                where={'telegramId': str(user_id)},
                data={'role': 'ADMIN'}
            )
            await message.answer(f"Salom {first_name}! Sizning profilingiz admin sifatida yangilandi. Admin paneliga xush kelibsiz!", 
                                reply_markup=admin_main_menu())
        return
    
    # Oddiy foydalanuvchilar uchun
    user = await db.user.find_unique(
        where={'telegramId': str(user_id)}
    )
    
    if user:
        if user.role == "DRIVER":
            await message.answer(f"Salom, {user.firstName}! Haydovchi sifatida tizimga kirdingiz.", 
                                reply_markup=get_driver_keyboard())
        elif user.role == "PASSENGER":
            await message.answer(f"Salom, {user.firstName}! Yo'lovchi sifatida tizimga kirdingiz.", 
                                reply_markup=get_passenger_keyboard())
        elif user.role in ["ADMIN", "SUPER_ADMIN"]:
            greeting = f"Salom ADMIN @{username}" if username else f"Salom ADMIN {first_name}"
            await message.answer(f"{greeting}. Admin paneliga xush kelibsiz!", 
                                reply_markup=admin_main_menu())
    else:
        await message.answer("Salom! Botimizga xush kelibsiz. Iltimos, rolni tanlang:", 
                            reply_markup=get_role_keyboard())
        await RegistrationForm.role.set()

        #####################################

@dp.message_handler(state=RegistrationForm.role)
async def process_role(message: types.Message, state: FSMContext):
    if message.text not in ["Haydovchi", "Yo'lovchi"]:
        await message.answer("Iltimos, quyidagi tugmalardan birini tanlang!", 
                           reply_markup=get_role_keyboard())
        return
    
    await state.update_data(role="DRIVER" if message.text == "Haydovchi" else "PASSENGER")
    await message.answer("Ismingizni kiriting:", reply_markup=ReplyKeyboardRemove())
    await RegistrationForm.first_name.set()

@dp.message_handler(state=RegistrationForm.first_name)
async def process_first_name(message: types.Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("Familiyangizni kiriting:")
    await RegistrationForm.last_name.set()

@dp.message_handler(state=RegistrationForm.last_name)
async def process_last_name(message: types.Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("Telefon raqamingizni yuborish uchun quyidagi tugmani bosing:", 
                       reply_markup=get_phone_keyboard())
    await RegistrationForm.phone_number.set()

@dp.message_handler(state=RegistrationForm.phone_number)
async def process_phone(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text)
    if not validate_phone(phone):
        await message.answer("❌ Noto'g'ri telefon raqam formati. Iltimos, qayta kiriting:")
        return
    
    await create_user(message, state, phone)

@dp.message_handler(content_types=types.ContentType.CONTACT, state=RegistrationForm.phone_number)
async def process_phone_number(message: types.Message, state: FSMContext):
    phone_number = normalize_phone(message.contact.phone_number)
    if not validate_phone(phone_number):
        await message.answer("❌ Noto'g'ri telefon raqam formati. Iltimos, qayta kiriting:")
        return
    await create_user(message, state, phone_number)

async def create_user(message: types.Message, state: FSMContext, phone_number: str):
    user_data = await state.get_data()
    
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
        
        if role_value == "DRIVER":
            channel_url = await get_channel_url()
            welcome_text = (
                f"Tabriklaymiz, {new_user.firstName}! Siz haydovchi sifatida ro'yxatdan o'tdingiz.\n\n"
                f"Buyurtmalarni olish uchun maxsus haydovchilar kanaliga obuna bo'lishingiz kerak.\n"
                f"Kanal orqali yangi yo'lovchi buyurtmalaridan xabardor bo'lasiz."
            )
            
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton("➕ Kanalga obuna bo'lish", url=channel_url))
            markup.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
            
            sent_message = await message.answer(welcome_text, reply_markup=markup)
            
            await state.update_data(
                drivers_channel=CHANNEL_ID, 
                welcome_message_id=sent_message.message_id,
                user_name=new_user.firstName
            )
            await DriverState.waiting_subscription.set()
        else:
            await message.answer(
                f"Tabriklaymiz, {new_user.firstName}! Siz yo'lovchi sifatida ro'yxatdan o'tdingiz.",
                reply_markup=get_passenger_keyboard()
            )
            await state.finish()
            
    except Exception as e:
        logging.error(f"Ro'yxatdan o'tkazishda xatolik: {e}")
        await message.answer("Ro'yxatdan o'tkazishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == "check_subscription", state=DriverState.waiting_subscription)
async def check_driver_subscription(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    state_data = await state.get_data()
    drivers_channel = state_data.get('drivers_channel', CHANNEL_ID)
    welcome_message_id = state_data.get('welcome_message_id')
    user_name = state_data.get('user_name', 'Haydovchi')
    
    try:
        member = await bot.get_chat_member(chat_id=drivers_channel, user_id=user_id)
        
        if member.status in ["member", "administrator", "creator"]:
            success_text = (
                f"✅ Tabriklaymiz, {user_name}!\n\n"
                f"Kanalga muvaffaqiyatli obuna bo'ldingiz. "
                f"Endi buyurtmalarni qabul qilishingiz mumkin!"
            )
            
            try:
                await callback_query.message.edit_text(
                    text=success_text,
                    reply_markup=None
                )
                
                await bot.send_message(
                    chat_id=user_id,
                    text="Haydovchi paneliga xush kelibsiz:",
                    reply_markup=get_driver_keyboard()
                )

                await state.finish()
                await callback_query.answer("🎉 Obuna tasdiqlandi!", show_alert=False)
                
            except Exception as edit_error:
                logging.error(f"Xabarni edit qilishda xato: {edit_error}")
                await bot.send_message(
                    chat_id=user_id,
                    text=success_text,
                    reply_markup=get_driver_keyboard()
                )
                await state.finish()
                await callback_query.answer("🎉 Obuna tasdiqlandi!")
                
        else:
            await callback_query.answer(
                "❌ Siz hali kanalga obuna bo'lmagansiz!\n\n"
                "Iltimos, avval kanalga obuna bo'ling, keyin yana 'Obunani tekshirish' tugmasini bosing.",
                show_alert=True
            )
            
    except Exception as e:
        logging.error(f"Kanal obunasini tekshirishda xato: {e}")
        await callback_query.answer(
            "⚠️ Obunani tekshirishda xatolik yuz berdi.\n"
            "Iltimos, bir oz kuting va qayta urinib ko'ring.",
            show_alert=True
        )

@dp.message_handler(commands=['check_subscription'])
async def manual_subscription_check(message: types.Message):
    """Haydovchi qo'lda obunani tekshirish uchun"""
    user = await db.user.find_unique(
        where={'telegramId': str(message.from_user.id)}
    )
    
    if not user or user.role != "DRIVER":
        await message.answer("Bu buyruq faqat haydovchilar uchun!")
        return
    
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=message.from_user.id)
        
        if member.status in ["member", "administrator", "creator"]:
            await message.answer(
                f"✅ {user.firstName}, siz kanalga obuna bo'lgansiz!\n"
                f"Haydovchi paneliga xush kelibsiz:",
                reply_markup=get_driver_keyboard()
            )
        else:
            channel_url = await get_channel_url()
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("➕ Kanalga obuna bo'lish", url=channel_url))
            
            await message.answer(
                f"❌ {user.firstName}, siz hali kanalga obuna bo'lmagansiz.\n"
                f"Buyurtmalarni olish uchun kanalga obuna bo'ling:",
                reply_markup=markup
            )
            
    except Exception as e:
        logging.error(f"Manual obuna tekshirishda xato: {e}")
        await message.answer("Obunani tekshirishda xatolik yuz berdi.")