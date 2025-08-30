import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from loader import dp, db, bot
from states.admin_states import AddRegionStates, AddDistrictStates
from keyboards.admin_btns import admin_main_menu, cancel_keyboard, confirmation_keyboard
from keyboards.defaultbtns import get_passenger_keyboard, get_driver_keyboard
from data.config import OWNER_ID

# Admin ID lar ro'yxati
ADMIN_IDS = list(map(int, OWNER_ID))

async def check_admin_access(user_id: int) -> bool:
    """Foydalanuvchining admin huquqlarini tekshirish"""
    try:
        user = await db.user.find_unique(where={'telegramId': str(user_id)})
        return user and user.role in ["ADMIN", "SUPER_ADMIN"]
    except Exception as e:
        logging.error(f"Admin huquqlarini tekshirishda xato: {e}")
        return False

async def notify_admins(message_text: str, exclude_user_id: int = None):
    """Barcha adminlarga xabar yuborish"""
    try:
        admins = await db.user.find_many(where={
            'OR': [
                {'role': 'ADMIN'},
                {'role': 'SUPER_ADMIN'}
            ]
        })
        
        for admin in admins:
            admin_id = int(admin.telegramId)
            if exclude_user_id and admin_id == exclude_user_id:
                continue
                
            try:
                await bot.send_message(admin_id, message_text, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")
    except Exception as e:
        logging.error(f"Adminlarni olishda xato: {e}")

# ++++++++++++++++++++ VILOYAT QO'SHISH HANDLERLARI ++++++++++++++++++++

@dp.message_handler(lambda m: m.text == "➕ Viloyat qo'shish", state="*")
async def start_add_region(message: types.Message, state: FSMContext):
    """Viloyat qo'shishni boshlash"""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    await message.answer(
        "Yangi viloyat nomini kiriting:",
        reply_markup=cancel_keyboard()
    )
    await AddRegionStates.waiting_for_region_name.set()

@dp.message_handler(state=AddRegionStates.waiting_for_region_name)
async def process_region_name(message: types.Message, state: FSMContext):
    """Viloyat nomini qayta ishlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=admin_main_menu())
        return
    
    region_name = message.text.strip()
    
    if len(region_name) < 2:
        await message.answer("❌ Viloyat nomi juda qisqa. Iltimos, qayta kiriting:")
        return
    
    try:
        existing_region = await db.region.find_first(where={"name": region_name})
        if existing_region:
            await message.answer("❌ Bu viloyat allaqachon mavjud. Boshqa nom kiriting:")
            return
    except Exception as e:
        logging.error(f"Viloyat mavjudligini tekshirishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring:")
        return
    
    await state.update_data(region_name=region_name)
    
    await message.answer(
        f"Viloyat nomi: <b>{region_name}</b>\n\nQo'shishni tasdiqlaysizmi?",
        reply_markup=confirmation_keyboard(),
        parse_mode="HTML"
    )
    await AddRegionStates.confirm_region.set()

# Tasdiqlash bosqichida Bekor qilish tugmasi
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state=AddRegionStates.confirm_region)
async def cancel_region_confirm(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Viloyat qo'shish bekor qilindi.", reply_markup=admin_main_menu())

@dp.callback_query_handler(lambda c: c.data in ["confirm_yes", "confirm_no"], state=AddRegionStates.confirm_region)
async def confirm_region_addition(callback: types.CallbackQuery, state: FSMContext):
    """Viloyat qo'shishni tasdiqlash"""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    if callback.data == "confirm_yes":
        data = await state.get_data()
        region_name = data.get('region_name')
        
        try:
            await db.region.create(data={"name": region_name})
            await callback.message.edit_text(
                f"✅ Viloyat muvaffaqiyatli qo'shildi: <b>{region_name}</b>",
                parse_mode="HTML"
            )
            notification_text = (f"📢 Yangi viloyat qo'shildi:\n\n"
                               f"🏛️ Viloyat: <b>{region_name}</b>\n"
                               f"👤 Qo'shgan admin: @{callback.from_user.username or callback.from_user.first_name}")
            await notify_admins(notification_text, callback.from_user.id)
        except Exception as e:
            logging.error(f"Viloyat qo'shishda xato: {e}")
            await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    else:
        await callback.message.edit_text("❌ Viloyat qo'shish bekor qilindi.")
    
    await state.finish()
    await callback.message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())
    await callback.answer()

# ++++++++++++++++++++ TUMAN QO'SHISH HANDLERLARI ++++++++++++++++++++

@dp.message_handler(lambda m: m.text == "➕ Tuman qo'shish", state="*")
async def start_add_district(message: types.Message, state: FSMContext):
    """Tuman qo'shishni boshlash"""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    try:
        regions = await db.region.find_many()
        if not regions:
            await message.answer("❌ Avval viloyat qo'shishingiz kerak.", reply_markup=admin_main_menu())
            return
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        for region in regions:
            keyboard.add(InlineKeyboardButton(region.name, callback_data=f"region_{region.id}"))
        keyboard.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_district"))
        
        await message.answer("Tuman qo'shish uchun viloyatni tanlang:", reply_markup=keyboard)
        await AddDistrictStates.waiting_for_region_selection.set()
    except Exception as e:
        logging.error(f"Viloyatlarni olishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("region_") or c.data == "cancel_district", 
                          state=AddDistrictStates.waiting_for_region_selection)
async def process_region_selection(callback: types.CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    if callback.data == "cancel_district":
        await state.finish()
        await callback.message.edit_text("❌ Tuman qo'shish bekor qilindi.")
        await callback.answer()
        return
    
    try:
        region_id = int(callback.data.split("_")[1])
        region = await db.region.find_unique(where={"id": region_id})
        if not region:
            await callback.answer("❌ Viloyat topilmadi")
            return
        
        await state.update_data(region_id=region_id, region_name=region.name)
        
        await callback.message.edit_text(f"Tanlangan viloyat: <b>{region.name}</b>", parse_mode="HTML")
        await callback.message.answer("Tuman nomini kiriting:", reply_markup=cancel_keyboard())
        
        await AddDistrictStates.waiting_for_district_name.set()
        await callback.answer()
    except Exception as e:
        logging.error(f"Viloyat tanlashda xato: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
        await state.finish()
        await callback.answer()

@dp.message_handler(state=AddDistrictStates.waiting_for_district_name)
async def process_district_name(message: types.Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=admin_main_menu())
        return
    
    district_name = message.text.strip()
    if len(district_name) < 2:
        await message.answer("❌ Tuman nomi juda qisqa. Iltimos, qayta kiriting:")
        return
    
    data = await state.get_data()
    region_id = data.get('region_id')
    region_name = data.get('region_name')
    
    try:
        existing_district = await db.district.find_first(where={"name": district_name, "regionId": region_id})
        if existing_district:
            await message.answer("❌ Bu tuman allaqachon mavjud. Boshqa nom kiriting:")
            return
    except Exception as e:
        logging.error(f"Tuman mavjudligini tekshirishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring:")
        return
    
    await state.update_data(district_name=district_name)
    await message.answer(
        f"Viloyat: <b>{region_name}</b>\nTuman: <b>{district_name}</b>\n\nQo'shishni tasdiqlaysizmi?",
        reply_markup=confirmation_keyboard(),
        parse_mode="HTML"
    )
    await AddDistrictStates.confirm_district.set()

# Tasdiqlash bosqichida Bekor qilish tugmasi
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state=AddDistrictStates.confirm_district)
async def cancel_district_confirm(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Tuman qo'shish bekor qilindi.", reply_markup=admin_main_menu())

@dp.callback_query_handler(lambda c: c.data in ["confirm_yes", "confirm_no"], state=AddDistrictStates.confirm_district)
async def confirm_district_addition(callback: types.CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    if callback.data == "confirm_yes":
        data = await state.get_data()
        region_id = data.get('region_id')
        region_name = data.get('region_name')
        district_name = data.get('district_name')
        
        try:
            await db.district.create(data={"name": district_name, "regionId": region_id})
            await callback.message.edit_text(
                f"✅ Tuman muvaffaqiyatli qo'shildi:\n\n"
                f"🏛️ Viloyat: <b>{region_name}</b>\n"
                f"🏘️ Tuman: <b>{district_name}</b>",
                parse_mode="HTML"
            )
            notification_text = (f"📢 Yangi tuman qo'shildi:\n\n"
                               f"🏛️ Viloyat: <b>{region_name}</b>\n"
                               f"🏘️ Tuman: <b>{district_name}</b>\n"
                               f"👤 Qo'shgan admin: @{callback.from_user.username or callback.from_user.first_name}")
            await notify_admins(notification_text, callback.from_user.id)
        except Exception as e:
            logging.error(f"Tuman qo'shishda xato: {e}")
            await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    else:
        await callback.message.edit_text("❌ Tuman qo'shish bekor qilindi.")
    
    await state.finish()
    await callback.message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())
    await callback.answer()

# ++++++++++++++++++++ QO'SHIMCHA HANDLERLAR ++++++++++++++++++++

@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    await message.answer(
        "👨‍💻 Admin paneliga xush kelibsiz!\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=admin_main_menu()
    )

@dp.message_handler(lambda m: m.text == "🔙 Bosh menyu", state="*")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()
    
    try:
        user = await db.user.find_unique(where={'telegramId': str(message.from_user.id)})
        if user:
            if user.role == "DRIVER":
                await message.answer("Haydovchi paneliga qaytdingiz:", reply_markup=get_driver_keyboard())
            elif user.role == "PASSENGER":
                await message.answer("Yo'lovchi paneliga qaytdingiz:", reply_markup=get_passenger_keyboard())
            elif user.role in ["ADMIN", "SUPER_ADMIN"]:
                await message.answer("Admin paneliga qaytdingiz:", reply_markup=admin_main_menu())
        else:
            await message.answer("Bosh menyuga qaytdingiz.")
    except Exception as e:
        logging.error(f"Foydalanuvchini tekshirishda xato: {e}")
        await message.answer("Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
