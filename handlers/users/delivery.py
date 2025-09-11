import logging
import asyncio
import json
import os
from datetime import datetime, date, timedelta
from aiogram import types
from loader import dp, db, bot
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states.registerstates import DeliveryState
from utils.userordercontrol import send_order_reminder
from dotenv import load_dotenv

load_dotenv()
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))
BOT_USERNAME = os.getenv("BOT_USERNAME")

# Processing holatidagi pochta buyurtmalari uchun timer
delivery_processing_timers = {}

# Kanal xabar ID larini saqlash uchun
delivery_channel_messages = {}

# Paket turlari
PACKAGE_TYPES = {
    "DOCUMENT": {"name": "📄 Hujjat", "emoji": "📄"},
    "PARCEL": {"name": "📦 Posilka", "emoji": "📦"},
    "FRAGILE": {"name": "🔸 Mo'rt buyum", "emoji": "🔸"},
    "VALUABLE": {"name": "💎 Qimmatbaho", "emoji": "💎"},
    "OTHER": {"name": "📋 Boshqa", "emoji": "📋"}
}

# Paket hajmlari
PACKAGE_SIZES = {
    "SMALL": {"name": "📦 Kichik (10kg gacha)", "emoji": "📦", "weight": "10kg gacha"},
    "MEDIUM": {"name": "📦 O'rta (10-25kg)", "emoji": "📦", "weight": "10-25kg"},
    "LARGE": {"name": "📦 Katta (25-50kg)", "emoji": "📦", "weight": "25-50kg"},
    "EXTRA_LARGE": {"name": "📦 Juda katta (50kg+)", "emoji": "📦", "weight": "50kg dan ortiq"}
}

async def get_regions_and_districts():
    """Bazadan viloyat va tumanlarni to'g'ridan-to'g'ri o'qib olish"""
    try:
        # Viloyatlarni bazadan olish
        regions = await db.region.find_many(order={"name": "asc"})
        regions_dict = {region.id: region.name for region in regions}
        
        # Tumanlarni bazadan olish va viloyat ID bo'yicha guruhlash
        districts = await db.district.find_many(
            include={"region": True},
            order={"name": "asc"}
        )
        
        districts_dict = {}
        for district in districts:
            region_name = district.region.name
            if region_name not in districts_dict:
                districts_dict[region_name] = []
            districts_dict[region_name].append(district.name)
            
        logging.info(f"Bazadan {len(regions_dict)} ta viloyat va {sum(len(d) for d in districts_dict.values())} ta tuman yuklandi")
        return regions_dict, districts_dict
        
    except Exception as e:
        logging.error(f"Viloyat va tumanlarni yuklashda xato: {e}")
        # Fallback
        try:
            with open("regions.json", "r", encoding="utf-8") as file:
                fallback_data = json.load(file)
                regions_dict = {i: name for i, name in enumerate(fallback_data.keys(), 1)}
            logging.info("Fallback: JSON fayldan viloyat va tumanlar yuklandi")
            return regions_dict, fallback_data
        except Exception as json_error:
            logging.error(f"JSON fayldan ham yuklab bo'lmadi: {json_error}")
            return {}, {}

async def get_channel_url():
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        return f"https://t.me/{chat.username.replace('@', '')}" if chat.username else f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
    except Exception as e:
        logging.error(f"Kanal ma'lumotlarini olishda xato: {e}")
        return f"https://t.me/c/{str(CHANNEL_ID)[4:]}"

async def delivery_processing_timer(order_id, channel_message_id):
    """5 daqiqa kutib, pochta buyurtmasini yana NEW holatiga o'tkazish"""
    try:
        await asyncio.sleep(300)  # 5 daqiqa kutish
        
        # Buyurtma holatini tekshirish
        order = await db.order.find_unique(
            where={"id": order_id},
            include={
                "status": True,
                "fromDistrict": True,
                "toDistrict": True
            }
        )
        
        if not order or not order.status:
            logging.warning(f"Delivery order {order_id} yoki status topilmadi")
            return
            
        # Agar hali ham processing holatida bo'lsa, NEW ga qaytarish
        if order.status.status == "processing":
            await db.orderstatus.update(
                where={"orderId": order_id},
                data={"status": "initiated"}
            )
            
            # Yangilangan buyurtmani olish
            updated_order = await db.order.find_unique(
                where={"id": order_id},
                include={
                    "status": True,
                    "fromDistrict": True,
                    "toDistrict": True
                }
            )
            
            # Kanal xabarini yangilash
            await update_channel_delivery_status(updated_order, channel_message_id)
            logging.info(f"Delivery order {order_id} 5 daqiqa o'tgach NEW holatiga qaytarildi")
            
        # Timer ro'yxatdan o'chirish
        if order_id in delivery_processing_timers:
            del delivery_processing_timers[order_id]
            
    except Exception as e:
        logging.error(f"Delivery processing timer error for order {order_id}: {e}")
        if order_id in delivery_processing_timers:
            del delivery_processing_timers[order_id]

async def update_channel_delivery_status(order, channel_message_id=None):
    """Kanal pochta xabarini yangilash"""
    try:
        if not channel_message_id:
            logging.warning(f"Delivery order {order.id} uchun channel_message_id topilmadi")
            return
        
        status_mapping = {
            "initiated": {"status": "NEW", "emoji": "🆕"},
            "processing": {"status": "JARAYONDA", "emoji": "🔄"},
            "completed": {"status": "YAKUNLANDI", "emoji": "✅"},
            "canceled": {"status": "BEKOR QILINDI", "emoji": "❌"},
            "failed": {"status": "XATOLIK", "emoji": "⚠️"}
        }
        
        current_status = order.status.status if order.status else "initiated"
        status_info = status_mapping.get(current_status, {"status": "NOMA'LUM", "emoji": "❓"})
        
        from_district_name = order.fromDistrict.name if hasattr(order, 'fromDistrict') and order.fromDistrict else "Noma'lum"
        to_district_name = order.toDistrict.name if hasattr(order, 'toDistrict') and order.toDistrict else "Noma'lum"
        
        # Paket ma'lumotlarini tayyorlash
        package_info = ""
        if order.packageType:
            package_info += f"\n📦 Turi: {PACKAGE_TYPES.get(order.packageType, {}).get('name', 'Nomalum')}"
        if order.packageSize:
            package_info += f"\n📏 Hajmi: {PACKAGE_SIZES.get(order.packageSize, {}).get('name', 'Nomalum')}"
        if order.packageWeight:
            package_info += f"\n⚖️ Og'irligi: {order.packageWeight} kg"
        if order.receiverName:
            package_info += f"\n👤 Qabul qiluvchi: {order.receiverName}"
        
        new_text = f"""{status_info['emoji']} *Pochta buyurtma - {status_info['status']}*  
🚦 Holati: *{status_info['status']}*  
📍 Qayerdan: {from_district_name}  
📍 Qayerga: {to_district_name}{package_info}"""
        
        reply_markup = None
        # Faqat initiated holatida tugma ko'rsatish
        if current_status == "initiated":
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("📞 Jo'natuvchi bilan bog'lanish", callback_data=f"contact_sender_{order.id}"))
            reply_markup = keyboard
        
        # Canceled buyurtmalarni o'chirish
        if current_status == "canceled":
            try:
                await bot.delete_message(chat_id=CHANNEL_ID, message_id=channel_message_id)
                logging.info(f"Bekor qilingan pochta buyurtma {order.id} kanaldan o'chirildi")
                return
            except Exception as delete_error:
                logging.error(f"Pochta xabarini o'chirishda xato: {delete_error}")
        
        await bot.edit_message_text(
            chat_id=CHANNEL_ID,
            message_id=channel_message_id,
            text=new_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        logging.info(f"Pochta kanal posti muvaffaqiyatli yangilandi: Order {order.id}, Status: {current_status}")
        
    except Exception as e:
        logging.error(f"Pochta kanal postini yangilashda xato: Order {order.id}, Error: {e}")

@dp.message_handler(lambda message: message.text == "📦 Pochta jonatish", state="*")
async def start_delivery(message: types.Message, state: FSMContext):
    """Pochta jo'natish jarayonini boshlash"""
    regions_dict, districts_dict = await get_regions_and_districts()
    
    data = await state.get_data()
    old_msg_id = data.get("last_inline_message_id")
    if old_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old_msg_id)
        except:
            pass

    keyboard = InlineKeyboardMarkup(row_width=2)
    for region_name in districts_dict.keys():
        keyboard.insert(InlineKeyboardButton(text=region_name, callback_data=f"delivery_from_{region_name}"))
    
    msg = await message.answer("📦 Qaysi viloyatdan pochta jo'natmoqchisiz?", reply_markup=keyboard)
    await state.update_data(last_inline_message_id=msg.message_id)
    await DeliveryState.from_region.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delivery_from_"), state=DeliveryState.from_region)
async def select_delivery_from_district(callback_query: types.CallbackQuery, state: FSMContext):
    viloyat = callback_query.data.split("_")[2]
    await state.update_data(from_region=viloyat)
    
    regions_dict, districts_dict = await get_regions_and_districts()
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in districts_dict.get(viloyat, []):
        keyboard.insert(InlineKeyboardButton(text=district, callback_data=f"delivery_from_district_{district}"))

    await callback_query.message.edit_text(f"📦 {viloyat} viloyati, qaysi tumandan pochta jo'natmoqchisiz?", reply_markup=keyboard)
    await DeliveryState.from_district.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delivery_from_district_"), state=DeliveryState.from_district)
async def ask_delivery_to_region(callback_query: types.CallbackQuery, state: FSMContext):
    tuman = callback_query.data.split("_")[3]
    await state.update_data(from_district=tuman)
    
    user_data = await state.get_data()
    from_region = user_data.get("from_region")
    
    regions_dict, districts_dict = await get_regions_and_districts()
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for region_name in districts_dict.keys():
        if region_name != from_region:
            keyboard.insert(InlineKeyboardButton(text=region_name, callback_data=f"delivery_to_{region_name}"))

    await callback_query.message.edit_text("📦 Qaysi viloyatga pochta jo'natmoqchisiz?", reply_markup=keyboard)
    await DeliveryState.to_region.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delivery_to_"), state=DeliveryState.to_region)
async def select_delivery_to_district(callback_query: types.CallbackQuery, state: FSMContext):
    viloyat = callback_query.data.split("_")[2]
    user_data = await state.get_data()
    from_district = user_data.get("from_district")
    
    await state.update_data(to_region=viloyat)

    regions_dict, districts_dict = await get_regions_and_districts()
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in districts_dict.get(viloyat, []):
        if district != from_district:
            keyboard.insert(InlineKeyboardButton(text=district, callback_data=f"delivery_to_district_{district}"))

    await callback_query.message.edit_text(f"📦 {viloyat} viloyati, qaysi tumanga pochta jo'natmoqchisiz?", reply_markup=keyboard)
    await DeliveryState.to_district.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delivery_to_district_"), state=DeliveryState.to_district)
async def ask_package_type(callback_query: types.CallbackQuery, state: FSMContext):
    tuman = callback_query.data.split("_")[3]
    await state.update_data(to_district=tuman)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, value in PACKAGE_TYPES.items():
        keyboard.insert(InlineKeyboardButton(text=value["name"], callback_data=f"package_type_{key}"))
    
    await callback_query.message.edit_text("📦 Pochta turini tanlang:", reply_markup=keyboard)
    await DeliveryState.package_type.set()

@dp.callback_query_handler(lambda c: c.data.startswith("package_type_"), state=DeliveryState.package_type)
async def ask_package_size(callback_query: types.CallbackQuery, state: FSMContext):
    package_type = callback_query.data.split("_")[2]
    await state.update_data(package_type=package_type)
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for key, value in PACKAGE_SIZES.items():
        keyboard.insert(InlineKeyboardButton(text=value["name"], callback_data=f"package_size_{key}"))
    
    await callback_query.message.edit_text("📏 Pochta hajmini tanlang:", reply_markup=keyboard)
    await DeliveryState.package_size.set()

@dp.callback_query_handler(lambda c: c.data.startswith("package_size_"), state=DeliveryState.package_size)
async def ask_package_weight(callback_query: types.CallbackQuery, state: FSMContext):
    package_size = callback_query.data.split("_")[2]
    await state.update_data(package_size=package_size)
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_weight"))
    
    await callback_query.message.edit_text(
        "⚖️ Pochta og'irligini kg da kiriting yoki o'tkazib yuboring:\n"
        "(Masalan: 2.5 yoki 15)",
        reply_markup=keyboard
    )
    await DeliveryState.package_weight.set()

@dp.callback_query_handler(lambda c: c.data == "skip_weight", state=DeliveryState.package_weight)
async def skip_weight(callback_query: types.CallbackQuery, state: FSMContext):
    await ask_package_description_step(callback_query, state)

@dp.message_handler(state=DeliveryState.package_weight)
async def process_package_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
        if weight <= 0 or weight > 1000:
            await message.answer("❌ Og'irlik 0 dan katta va 1000 kg dan kichik bo'lishi kerak. Qayta kiriting:")
            return
        
        await state.update_data(package_weight=weight)
        await ask_package_description_step(message, state)
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Og'irlikni raqam bilan kiriting (masalan: 2.5):")

async def ask_package_description_step(message_or_callback, state):
    """Paket tavsifi so'rash"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_description"))
    
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(
            "📝 Pochta haqida qo'shimcha ma'lumot kiriting yoki o'tkazib yuboring:\n"
            "(Masalan: Shisha idish, ehtiyot qilish kerak)",
            reply_markup=keyboard
        )
    else:
        await message_or_callback.answer(
            "📝 Pochta haqida qo'shimcha ma'lumot kiriting yoki o'tkazib yuboring:\n"
            "(Masalan: Shisha idish, ehtiyot qilish kerak)",
            reply_markup=keyboard
        )
    await DeliveryState.package_description.set()

@dp.callback_query_handler(lambda c: c.data == "skip_description", state=DeliveryState.package_description)
async def skip_description(callback_query: types.CallbackQuery, state: FSMContext):
    await ask_receiver_info_step(callback_query, state)

@dp.message_handler(state=DeliveryState.package_description)
async def process_package_description(message: types.Message, state: FSMContext):
    description = message.text.strip()
    if len(description) > 200:
        await message.answer("❌ Tavsif 200 belgidan oshmasligi kerak. Qisqaroq yozing:")
        return
    
    await state.update_data(package_description=description)
    await ask_receiver_info_step(message, state)

async def ask_receiver_info_step(message_or_callback, state):
    """Qabul qiluvchi ma'lumotlarini so'rash"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_receiver"))
    
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(
            "👤 Qabul qiluvchi ismini kiriting yoki o'tkazib yuboring:\n"
            "(Masalan: Akmal Karimov)",
            reply_markup=keyboard
        )
    else:
        await message_or_callback.answer(
            "👤 Qabul qiluvchi ismini kiriting yoki o'tkazib yuboring:\n"
            "(Masalan: Akmal Karimov)",
            reply_markup=keyboard
        )
    await DeliveryState.receiver_name.set()

@dp.callback_query_handler(lambda c: c.data == "skip_receiver", state=DeliveryState.receiver_name)
async def skip_receiver(callback_query: types.CallbackQuery, state: FSMContext):
    await update_delivery_and_confirm(callback_query, state)

@dp.message_handler(state=DeliveryState.receiver_name)
async def process_receiver_name(message: types.Message, state: FSMContext):
    receiver_name = message.text.strip()
    if len(receiver_name) > 100:
        await message.answer("❌ Ism 100 belgidan oshmasligi kerak. Qisqaroq yozing:")
        return
    
    await state.update_data(receiver_name=receiver_name)
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_receiver_phone"))
    
    await message.answer(
        "📞 Qabul qiluvchi telefon raqamini kiriting yoki o'tkazib yuboring:\n"
        "(Masalan: +998901234567)",
        reply_markup=keyboard
    )
    await DeliveryState.receiver_phone.set()

@dp.callback_query_handler(lambda c: c.data == "skip_receiver_phone", state=DeliveryState.receiver_phone)
async def skip_receiver_phone(callback_query: types.CallbackQuery, state: FSMContext):
    await update_delivery_and_confirm(callback_query, state)

@dp.message_handler(state=DeliveryState.receiver_phone)
async def process_receiver_phone(message: types.Message, state: FSMContext):
    receiver_phone = message.text.strip()
    await state.update_data(receiver_phone=receiver_phone)
    await update_delivery_and_confirm(message, state)

async def update_delivery_and_confirm(message_or_callback, state):
    """Pochta buyurtmasini tasdiqlash"""
    user_data = await state.get_data()
    
    # Ma'lumotlarni tayyorlash
    package_type_name = PACKAGE_TYPES.get(user_data.get('package_type', ''), {}).get('name', 'Tanlanmagan')
    package_size_name = PACKAGE_SIZES.get(user_data.get('package_size', ''), {}).get('name', 'Tanlanmagan')
    
    order_info = f"""📦 Pochta buyurtma ma'lumotlari:

📍 Jo'natish manzili: {user_data['from_region']}, {user_data['from_district']}
📍 Qabul qilish manzili: {user_data['to_region']}, {user_data['to_district']}

📦 Pochta ma'lumotlari:
• Turi: {package_type_name}
• Hajmi: {package_size_name}"""

    if user_data.get('package_weight'):
        order_info += f"\n• Og'irligi: {user_data['package_weight']} kg"
    
    if user_data.get('package_description'):
        order_info += f"\n• Tavsifi: {user_data['package_description']}"
    
    if user_data.get('receiver_name'):
        order_info += f"\n\n👤 Qabul qiluvchi: {user_data['receiver_name']}"
    
    if user_data.get('receiver_phone'):
        order_info += f"\n📞 Telefon: {user_data['receiver_phone']}"
    
    order_info += "\n\nMa'lumotlar to'g'rimi?"

    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_delivery"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_delivery")
    )

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(order_info, reply_markup=keyboard)
    else:
        await message_or_callback.answer(order_info, reply_markup=keyboard)
    
    await DeliveryState.confirmation.set()

@dp.callback_query_handler(lambda c: c.data == "confirm_delivery", state=DeliveryState.confirmation)
async def confirm_delivery(callback_query: types.CallbackQuery, state: FSMContext):
    """Pochta buyurtmasini tasdiqlash va yaratish"""
    data = await state.get_data()

    try:
        user = await db.user.find_unique(where={"telegramId": callback_query.from_user.id})

        if not user:
            user = await db.user.create({
                "telegramId": callback_query.from_user.id,
                "firstName": callback_query.from_user.first_name or "",
                "lastName": callback_query.from_user.last_name or "",
                "username": callback_query.from_user.username,
                "phoneNumber": "",
                "role": "PASSENGER"
            })

        # Viloyat va tuman ID larini topish
        from_region = await db.region.find_first(where={"name": data.get("from_region")})
        to_region = await db.region.find_first(where={"name": data.get("to_region")})
        
        from_district = await db.district.find_first(
            where={
                "name": data.get("from_district"),
                "regionId": from_region.id
            }
        )
        
        to_district = await db.district.find_first(
            where={
                "name": data.get("to_district"),
                "regionId": to_region.id
            }
        )

        # Pochta buyurtmasini yaratish
        order_data = {
            "passengerId": user.id,
            "orderType": "DELIVERY",
            "fromRegionId": from_region.id,
            "fromDistrictId": from_district.id,
            "toRegionId": to_region.id,
            "toDistrictId": to_district.id,
            "packageType": data.get("package_type"),
            "packageSize": data.get("package_size")
        }
        
        # Optional fieldlarni qo'shish
        if data.get("package_weight"):
            order_data["packageWeight"] = data.get("package_weight")
        if data.get("package_description"):
            order_data["packageDescription"] = data.get("package_description")
        if data.get("receiver_name"):
            order_data["receiverName"] = data.get("receiver_name")
        if data.get("receiver_phone"):
            order_data["receiverPhone"] = data.get("receiver_phone")

        order = await db.order.create(order_data)

        # Status yaratish (initiated holatida)
        order_status = await db.orderstatus.create({
            "status": "initiated",
            "orderId": order.id,
            "userId": user.id
        })

        # Kanalga xabar yuborish uchun ma'lumotlarni tayyorlash
        package_type_name = PACKAGE_TYPES.get(data.get("package_type", ""), {}).get("name", "Noma'lum")
        package_size_name = PACKAGE_SIZES.get(data.get("package_size", ""), {}).get("name", "Noma'lum")
        
        channel_text = f"""📦 *Yangi pochta buyurtma!*  
🚦 Holati: *NEW*  
📍 Qayerdan: {data["from_district"]}  
📍 Qayerga: {data["to_district"]}  
📦 Turi: {package_type_name}  
📏 Hajmi: {package_size_name}"""

        if data.get("package_weight"):
            channel_text += f"\n⚖️ Og'irligi: {data['package_weight']} kg"

        # Kanal uchun klaviatura
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📞 Jo'natuvchi bilan bog'lanish", callback_data=f"contact_sender_{order.id}"))

        # Kanalga xabar yuborish
        channel_message = await bot.send_message(
            chat_id=CHANNEL_ID,  
            text=channel_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        # Channel message ID ni saqlash
        delivery_channel_messages[order.id] = channel_message.message_id

        # Foydalanuvchi uchun klaviatura
        user_keyboard = InlineKeyboardMarkup(row_width=2)
        user_keyboard.add(
            InlineKeyboardButton("✅ Complete", callback_data=f"complete_delivery_{order.id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_delivery_{order.id}")
        )

        await callback_query.message.edit_text(
            "✅ Pochta buyurtma yaratildi! Haydovchilar javobini kuting...\n\n"
            "🚖 Haydovchi bilan kelishgan bo'lsangiz, *Complete* tugmasini bosing.\n"
            "🔄 Agar fikringizdan qaytgan bo'lsangiz, *Cancel* tugmasini bosing.",
            reply_markup=user_keyboard,
            parse_mode="Markdown"
        )
        
        # Order reminder yuborish
        bg_task = asyncio.create_task(send_order_reminder(order.id, user.telegramId))
        bg_task.add_done_callback(lambda t: logging.error(f"Delivery order reminder task error: {t.exception()}") if t.exception() else None)
        
    except Exception as e:
        logging.error(f"Pochta buyurtma yaratishda xato: {e}")
        await callback_query.message.edit_text("❌ Xatolik yuz berdi! Iltimos, qayta urinib ko'ring.")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "cancel_delivery", state="*")
async def cancel_delivery_creation(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback_query.message.edit_text("❌ Pochta buyurtma bekor qilindi.")

@dp.callback_query_handler(lambda c: c.data.startswith("contact_sender_"))
async def send_sender_info(callback_query: types.CallbackQuery):
    """Haydovchi jo'natuvchi bilan bog'lanish tugmasini bosganda"""
    user_id = callback_query.from_user.id
    order_id = int(callback_query.data.split("_")[-1])

    try:
        # Kanal a'zoligini tekshirish
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["left", "kicked", "restricted"] and user_id != OWNER_ID:
            channel_url = await get_channel_url()
            await callback_query.answer(
                f"❌ Siz kanalga obuna bo'lmagansiz! Iltimos, avval kanalga obuna bo'ling: {channel_url}",
                show_alert=True
            )
            return
    except Exception as e:
        logging.error(f"Kanalga obunani tekshirishda xatolik: {e}")
        await callback_query.answer("⚠️ Obunani tekshirishda xatolik yuz berdi.", show_alert=True)
        return

    # Foydalanuvchini tekshirish
    user = await db.user.find_unique(where={"telegramId": user_id})
    if not user:
        await callback_query.answer(
            f"❌ Siz botda ro'yxatdan o'tmagansiz. Iltimos, botni ishlatish uchun ro'yxatdan o'ting: {BOT_USERNAME}",
            show_alert=True
        )
        return

    # Buyurtmani olish
    order = await db.order.find_unique(
        where={"id": order_id},
        include={
            "passenger": True,
            "status": True,
            "fromRegion": True,
            "fromDistrict": True,
            "toRegion": True,
            "toDistrict": True
        }
    )

    if not order:
        await callback_query.answer("❌ Buyurtma topilmadi yoki allaqachon o'chirilgan.", show_alert=True)
        return
    
    # Jo'natuvchining o'z buyurtmasiga ruxsat
    if user.role == "PASSENGER" and order.passenger.telegramId != user_id:
        await callback_query.answer(
            "⛔️ Siz faqat o'zingizning buyurtmangiz haqida ma'lumot olishingiz mumkin.",
            show_alert=True
        )
        return

    current_status = order.status.status if order.status else "initiated"
    
    # Faqat initiated holatidagi buyurtmalarga ruxsat
    if current_status == "initiated":
        # Status ni processing ga o'zgartirish
        await db.orderstatus.update(
            where={"orderId": order_id},
            data={
                "status": "processing",
                "userId": user.id  # Kim processing qilayotganini belgilash
            }
        )
        
        # Yangilangan buyurtmani olish
        updated_order = await db.order.find_unique(
            where={"id": order_id},
            include={
                "passenger": True,
                "status": True,
                "fromRegion": True,
                "fromDistrict": True,
                "toRegion": True,
                "toDistrict": True
            }
        )
        
        # Kanal xabarini yangilash (tugmani o'chirish)
        channel_message_id = delivery_channel_messages.get(order_id)
        if channel_message_id:
            await update_channel_delivery_status(updated_order, channel_message_id)
        
        # 5 daqiqalik timer o'rnatish
        if order_id in delivery_processing_timers:
            delivery_processing_timers[order_id].cancel()
        
        timer_task = asyncio.create_task(delivery_processing_timer(order_id, channel_message_id))
        delivery_processing_timers[order_id] = timer_task
        
        # Haydovchiga jo'natuvchi ma'lumotlarini yuborish
        package_type_name = PACKAGE_TYPES.get(order.packageType, {}).get('name', 'Nomalum')
        package_size_name = PACKAGE_SIZES.get(order.packageSize, {}).get('name', 'Nomalum')
        
        sender_info = f"""📦 *Jo'natuvchi ma'lumotlari:*
📍 Qayerdan: {order.fromDistrict.name if order.fromDistrict else 'Nomalum'}
📍 Qayerga: {order.toDistrict.name if order.toDistrict else 'Nomalum'}
📦 Turi: {package_type_name}
📏 Hajmi: {package_size_name}"""

        if order.packageWeight:
            sender_info += f"\n⚖️ Og'irligi: {order.packageWeight} kg"
        
        if order.packageDescription:
            sender_info += f"\n📝 Tavsifi: {order.packageDescription}"
        
        if order.receiverName:
            sender_info += f"\n👤 Qabul qiluvchi: {order.receiverName}"
        
        if order.receiverPhone:
            sender_info += f"\n📞 Qabul qiluvchi tel: {order.receiverPhone}"
        
        sender_info += f"\n🚦 Buyurtma holati: *JARAYONDA*"
        sender_info += f"\n\n👤 Jo'natuvchi: {order.passenger.firstName} {order.passenger.lastName}"
        sender_info += f"\n📞 Telefon: {order.passenger.phoneNumber}"
        
        if order.passenger.username:
            sender_info += f"\n🔗 Telegram: @{order.passenger.username}"

        await bot.send_message(callback_query.from_user.id, sender_info, parse_mode="Markdown")
        await callback_query.answer("✅ Pochta buyurtma jarayonga olindi! Jo'natuvchi ma'lumotlari yuborildi. 5 daqiqa vaqtingiz bor.", show_alert=True)
    
    elif current_status == "processing":
        # Agar boshqa haydovchi processing qilayotgan bo'lsa
        processing_user = order.status.user
        if processing_user and processing_user.telegramId != user_id:
            await callback_query.answer("⏳ Bu pochta buyurtma boshqa haydovchi tomonidan ko'rib chiqilmoqda.", show_alert=True)
        else:
            # O'sha haydovchi yana bosgan bo'lsa
            await callback_query.answer("⏳ Siz allaqachon bu pochta buyurtmani jarayonga oldingiz.", show_alert=True)
    
    else:
        # Boshqa statuslar uchun
        await update_channel_delivery_status(order, callback_query.message.message_id if hasattr(callback_query, 'message') else None)
        
        status_messages = {
            "canceled": "❌ Pochta buyurtma bekor qilindi! (CANCELED)",
            "completed": "❗️😢 Pochta buyurtma yakunlandi! \nJo'natuvchi haydovchi bilan kelishib bo'ldi. (COMPLETED)",
            "failed": "⚠️ Pochta buyurtmada xatolik yuz berdi! (FAILED)"
        }
        
        status_message = status_messages.get(current_status, "Holati noma'lum")
        await callback_query.answer(status_message, show_alert=True)

async def get_delivery_channel_message_id(order_id):
    """Pochta buyurtma uchun channel message ID ni olish"""
    return delivery_channel_messages.get(order_id)

@dp.callback_query_handler(lambda c: c.data.startswith("complete_delivery_"))
async def complete_delivery(callback_query: types.CallbackQuery, state: FSMContext):
    """Pochta buyurtmasini yakunlash"""
    order_id = int(callback_query.data.split("_")[-1])

    order = await db.order.find_unique(
        where={"id": order_id}, 
        include={"status": True, "fromDistrict": True, "toDistrict": True}
    )
    
    if not order or (order.status and order.status.status not in ["initiated", "processing"]):
        await callback_query.answer("❌ Pochta buyurtma allaqachon o'zgartirilgan yoki mavjud emas.", show_alert=True)
        return

    # Timer ni to'xtatish
    if order_id in delivery_processing_timers:
        delivery_processing_timers[order_id].cancel()
        del delivery_processing_timers[order_id]

    # Status ni completed ga o'zgartirish
    await db.orderstatus.update(
        where={"orderId": order_id},
        data={"status": "completed"}
    )

    # Yangilangan buyurtmani olish
    updated_order = await db.order.find_unique(
        where={"id": order_id}, 
        include={"status": True, "fromDistrict": True, "toDistrict": True}
    )

    # Kanal xabarini yangilash
    channel_message_id = await get_delivery_channel_message_id(order_id)
    if channel_message_id:
        await update_channel_delivery_status(updated_order, channel_message_id)
    else:
        logging.warning(f"Delivery order {order_id} uchun channel_message_id topilmadi")

    await callback_query.message.edit_text("✅ Pochta buyurtma muvaffaqiyatli yakunlandi!", reply_markup=None)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_delivery_"))
async def cancel_delivery_status(callback_query: types.CallbackQuery, state: FSMContext):
    """Pochta buyurtmasini bekor qilish"""
    order_id = int(callback_query.data.split("_")[-1])

    order = await db.order.find_unique(
        where={"id": order_id}, 
        include={"status": True, "fromDistrict": True, "toDistrict": True}
    )
    
    if not order or (order.status and order.status.status not in ["initiated", "processing"]):
        await callback_query.answer("❌ Pochta buyurtma allaqachon o'zgartirilgan yoki mavjud emas.", show_alert=True)
        return

    # Timer ni to'xtatish
    if order_id in delivery_processing_timers:
        delivery_processing_timers[order_id].cancel()
        del delivery_processing_timers[order_id]

    # Status ni canceled ga o'zgartirish
    await db.orderstatus.update(
        where={"orderId": order_id},
        data={"status": "canceled"}
    )

    # Yangilangan buyurtmani olish
    updated_order = await db.order.find_unique(
        where={"id": order_id}, 
        include={"status": True, "fromDistrict": True, "toDistrict": True}
    )

    # Kanal xabarini yangilash (canceled xabarlar avtomatik o'chiriladi)
    channel_message_id = await get_delivery_channel_message_id(order_id)
    if channel_message_id:
        await update_channel_delivery_status(updated_order, channel_message_id)
        # Channel messages ro'yxatdan o'chirish
        if order_id in delivery_channel_messages:
            del delivery_channel_messages[order_id]
    else:
        logging.warning(f"Delivery order {order_id} uchun channel_message_id topilmadi")

    await callback_query.message.edit_text("❌ Pochta buyurtma bekor qilindi.", reply_markup=None)
    await callback_query.answer()

# Utility funksiyalar

async def cleanup_expired_delivery_timers():
    """Eskirgan pochta timerlarini tozalash"""
    expired_orders = []
    for order_id, task in delivery_processing_timers.items():
        if task.done():
            expired_orders.append(order_id)
    
    for order_id in expired_orders:
        del delivery_processing_timers[order_id]
        logging.info(f"Expired delivery timer cleaned up for order {order_id}")

async def get_delivery_statistics():
    """Pochta buyurtma statistikalarini olish"""
    try:
        total_deliveries = await db.order.count(where={"orderType": "DELIVERY"})
        
        status_counts = {}
        for status in ["initiated", "processing", "completed", "canceled", "failed"]:
            count = await db.orderstatus.count(
                where={
                    "status": status,
                    "order": {"orderType": "DELIVERY"}
                }
            )
            status_counts[status] = count
        
        return {
            "total_deliveries": total_deliveries,
            "status_distribution": status_counts,
            "active_processing": len(delivery_processing_timers)
        }
    except Exception as e:
        logging.error(f"Pochta statistika olishda xato: {e}")
        return None

async def monitor_processing_deliveries():
    """Processing holatidagi pochta buyurtmalarni monitoring qilish"""
    try:
        processing_deliveries = await db.orderstatus.find_many(
            where={
                "status": "processing",
                "order": {"orderType": "DELIVERY"}
            },
            include={"order": True}
        )
        
        logging.info(f"Hozirda {len(processing_deliveries)} ta pochta buyurtma processing holatida")
        
        for status in processing_deliveries:
            order_id = status.orderId
            if order_id not in delivery_processing_timers:
                logging.warning(f"Processing delivery order {order_id} uchun timer topilmadi, qayta ishga tushirilmoqda")
                # Timer qayta ishga tushirish
                channel_message_id = delivery_channel_messages.get(order_id)
                if channel_message_id:
                    timer_task = asyncio.create_task(delivery_processing_timer(order_id, channel_message_id))
                    delivery_processing_timers[order_id] = timer_task
                    
    except Exception as e:
        logging.error(f"Processing deliveries monitoring xato: {e}")

async def cleanup_orphaned_processing_deliveries():
    """Dastur qayta ishga tushganda orphaned processing pochta orderlarni tozalash"""
    try:
        orphaned_deliveries = await db.orderstatus.find_many(
            where={
                "status": "processing",
                "order": {"orderType": "DELIVERY"}
            },
            include={
                "order": {
                    "include": {
                        "fromDistrict": True,
                        "toDistrict": True
                    }
                }
            }
        )
        
        for status in orphaned_deliveries:
            order_id = status.orderId
            # Bu orderlarni initiated ga qaytarish
            await db.orderstatus.update(
                where={"orderId": order_id},
                data={"status": "initiated"}
            )
            
            logging.info(f"Orphaned processing delivery order {order_id} initiated holatiga qaytarildi")
            
    except Exception as e:
        logging.error(f"Orphaned delivery orders cleanup xato: {e}")

async def initialize_delivery_module():
    """Delivery moduli ishga tushirilganda chaqiriladigan funksiya"""
    await cleanup_orphaned_processing_deliveries()
    await cleanup_expired_delivery_timers()
    logging.info("Delivery module initialized successfully")