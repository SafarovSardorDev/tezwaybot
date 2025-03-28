import logging
import json
from datetime import datetime, date, timedelta
from aiogram import types
from utils.notifications import notify_drivers_about_order
from loader import dp, db, bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from states.registerstates import OrderState
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup


with open("regions.json", "r", encoding="utf-8") as file:
    regions = json.load(file)

# 🚀 Yo'lga o'tishni boshlash
@dp.message_handler(lambda message: message.text == "Yo'lga otlanish")
async def start_trip(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    for region in regions.keys():
        keyboard.insert(InlineKeyboardButton(text=region, callback_data=f"from_{region}"))
    
    await message.answer("Qaysi viloyatdan ketmoqchisiz?", reply_markup=keyboard)
    await OrderState.from_region.set()

# 📍 Viloyat tanlanganda tumanlar chiqadi
@dp.callback_query_handler(lambda c: c.data.startswith("from_"), state=OrderState.from_region)
async def select_from_district(callback_query: types.CallbackQuery, state: FSMContext):
    viloyat = callback_query.data.split("_")[1]
    await state.update_data(from_region=viloyat)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in regions[viloyat]:
        keyboard.insert(InlineKeyboardButton(text=district, callback_data=f"from_district_{district}"))

    await callback_query.message.edit_text(f"{viloyat} viloyati, qaysi tumandan ketmoqchisiz?", reply_markup=keyboard)
    await OrderState.from_district.set()

# 👥 Passajirlar sonini so'rash
# 👥 Passajirlar sonini inline buttonlar bilan so'ralash
@dp.callback_query_handler(lambda c: c.data.startswith("from_district_"), state=OrderState.from_district)
async def ask_passengers(callback_query: types.CallbackQuery, state: FSMContext):
    tuman = callback_query.data.split("_")[2]
    await state.update_data(from_district=tuman)
    
    keyboard = InlineKeyboardMarkup(row_width=4)
    for i in range(1, 5):  # 1 dan 4 gacha
        keyboard.insert(InlineKeyboardButton(text=str(i), callback_data=f"passengers_{i}"))
    
    await callback_query.message.edit_text("Necha kishi ketmoqchisiz?", reply_markup=keyboard)
    await OrderState.passengers.set()

# 🔢 Passajirlar sonini qabul qilish
@dp.callback_query_handler(lambda c: c.data.startswith("passengers_"), state=OrderState.passengers)
async def set_passengers(callback_query: types.CallbackQuery, state: FSMContext):
    passengers = int(callback_query.data.split("_")[1])
    user_data = await state.get_data()
    from_region = user_data.get("from_region")  # User tanlagan viloyat

    await state.update_data(passengers=passengers)

    keyboard = InlineKeyboardMarkup(row_width=2)
    for region in regions.keys():
        if region != from_region:  # from_regionni chiqarib tashlaymiz
            keyboard.insert(InlineKeyboardButton(text=region, callback_data=f"to_{region}"))

    await callback_query.message.edit_text(
        f"👥 Passajirlar soni: {passengers}\n\n"
        "Qaysi viloyatga borasiz?",  
        reply_markup=keyboard
    )
    await OrderState.to_region.set()


# 📍 Boriladigan viloyatni tanlash
@dp.callback_query_handler(lambda c: c.data.startswith("to_"), state=OrderState.to_region)
async def select_to_district(callback_query: types.CallbackQuery, state: FSMContext):
    viloyat = callback_query.data.split("_")[1]
    user_data = await state.get_data()
    from_district = user_data.get("from_district")  # User tanlagan tuman
    
    await state.update_data(to_region=viloyat)

    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in regions[viloyat]:
        if district != from_district:  # from_districtni chiqarib tashlaymiz
            keyboard.insert(InlineKeyboardButton(text=district, callback_data=f"to_district_{district}"))

    await callback_query.message.edit_text(f"{viloyat} viloyati, qaysi tumanga borasiz?", reply_markup=keyboard)
    await OrderState.to_district.set()


# 📅 Sana va vaqtni so'rash
@dp.callback_query_handler(lambda c: c.data.startswith("to_district_"), state=OrderState.to_district)
async def ask_datetime(callback_query: types.CallbackQuery, state: FSMContext):
    tuman = callback_query.data.split("_")[2]
    await state.update_data(to_district=tuman)
    
    today = date.today()
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for i in range(5):  # Bugundan boshlab 5 kunlik variant
        departure_date = today + timedelta(days=i)
        keyboard.insert(InlineKeyboardButton(
            text=departure_date.strftime("%Y-%m-%d"),
            callback_data=f"date_{departure_date}"
        ))
    
    await callback_query.message.edit_text(
        "📆 Jo'natish sanasini tanlang yoki YYYY-MM-DD formatida yozing:",
        reply_markup=keyboard
    )
    await OrderState.datetime.set()

# ⏰ Sana tanlash (inline button)
@dp.callback_query_handler(lambda c: c.data.startswith("date_"), state=OrderState.datetime)
async def process_date(callback_query: types.CallbackQuery, state: FSMContext):
    selected_date = callback_query.data.split("_")[1]
    await state.update_data(departure_date=selected_date)
    
    await callback_query.message.edit_text("⏰ Jo'natish vaqtini HH:MM formatida kiriting (masalan, 14:30):")
    await OrderState.time.set()

# ⏱ Qo‘lda vaqt kiritish
@dp.message_handler(state=OrderState.time)
async def process_manual_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")  # Vaqt formatini tekshirish
        user_data = await state.get_data()
        departure_datetime = f"{user_data['departure_date']} {message.text}"
        await update_order_and_confirm(message, state, departure_datetime)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Iltimos, vaqtni HH:MM formatida kiriting (masalan, 14:30).")

async def update_order_and_confirm(message, state, departure_datetime):
    """ Buyurtmani shakllantirish va tasdiqlash bosqichiga o'tkazish """
    await state.update_data(departure_time=departure_datetime)
    user_data = await state.get_data()

    order_info = (
        f"📋 Buyurtma ma'lumotlari:\n"
        f"📍 Yo'nalish: {user_data['from_region']}, {user_data['from_district']} -> "
        f"{user_data['to_region']}, {user_data['to_district']}\n"
        f"👥 Passajirlar soni: {user_data['passengers']}\n"
        f"⏰ Jo'nash vaqti: {departure_datetime}\n\n"
        f"Ma'lumotlar to'g'rimi?"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_order"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_order")
    )

    await message.answer(order_info, reply_markup=keyboard)
    await OrderState.confirmation.set()

# ✅ Buyurtmani tasdiqlash
@dp.callback_query_handler(lambda c: c.data == "confirm_order", state=OrderState.confirmation)
async def confirm_order(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    try:
        # Foydalanuvchi ma'lumotlarini olish
        user = await db.user.find_unique(where={"telegramId": callback_query.from_user.id})
        
        # Agar foydalanuvchi bazada yo'q bo'lsa, yangi yaratish
        if not user:
            user = await db.user.create({
                "telegramId": callback_query.from_user.id,
                "firstName": callback_query.from_user.first_name or "",
                "lastName": callback_query.from_user.last_name or "",
                "username": callback_query.from_user.username,
                "role": "PASSENGER"
            })
        
        passenger_info = callback_query.from_user.full_name
        if callback_query.from_user.username:
            passenger_info += f" (@{callback_query.from_user.username})\n+{user.phoneNumber}"
        
        # Buyurtma yaratish
        order = await db.order.create({
            "passengerId": user.id,
            "fromRegion": data["from_region"],
            "fromDistrict": data["from_district"],
            "toRegion": data["to_region"],
            "toDistrict": data["to_district"],
            "passengers": data["passengers"],
            "departureTime": datetime.strptime(data["departure_time"], "%Y-%m-%d %H:%M"),
            "status": "NEW"
        })
        
        # Haydovchilarga xabar yuborish
        await notify_drivers_about_order(
            bot=bot,
            db=db,
            order_id=order.id,
            passenger_info=passenger_info,
            from_region=data["from_region"],
            from_district=data["from_district"],
            to_region=data["to_region"],
            to_district=data["to_district"],
            departure_time=data["departure_time"]
        )
        
        await callback_query.message.edit_text("✅ Buyurtma yaratildi! Haydovchilar javobini kuting...")
    
    except Exception as e:
        logging.error(f"Buyurtma yaratishda xato: {e}")
        await callback_query.message.edit_text("❌ Xatolik yuz berdi! Iltimos, qayta urinib ko'ring.")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "cancel_order", state="*")
async def cancel_order(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()  # State-ni tozalaymiz
    await callback_query.message.edit_text("❌ Buyurtma bekor qilindi.")