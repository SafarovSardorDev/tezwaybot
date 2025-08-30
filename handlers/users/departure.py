import logging
import asyncio
import json
import os
from datetime import datetime, date, timedelta
from aiogram import types
from loader import dp, db, bot
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states.registerstates import OrderState
from utils.userordercontrol import send_order_reminder
from dotenv import load_dotenv

load_dotenv()
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))
BOT_USERNAME = os.getenv("BOT_USERNAME")

# Processing holatidagi buyurtmalar uchun timer
processing_timers = {}

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

async def processing_timer(order_id, channel_message_id):
    """5 daqiqa kutib, buyurtmani yana NEW holatiga o'tkazish"""
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
            logging.warning(f"Order {order_id} yoki status topilmadi")
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
            await update_channel_order_status(updated_order, channel_message_id)
            logging.info(f"Order {order_id} 5 daqiqa o'tgach NEW holatiga qaytarildi")
            
        # Timer ro'yxatdan o'chirish
        if order_id in processing_timers:
            del processing_timers[order_id]
            
    except Exception as e:
        logging.error(f"Processing timer error for order {order_id}: {e}")
        if order_id in processing_timers:
            del processing_timers[order_id]

async def update_channel_order_status(order, channel_message_id=None):
    """Kanal xabarini yangilash"""
    try:
        if not channel_message_id:
            logging.warning(f"Order {order.id} uchun channel_message_id topilmadi")
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
        
        new_text = f"""{status_info['emoji']} *Buyurtma - {status_info['status']}*  
🚦 Holati: *{status_info['status']}*  
📍 Qayerdan: {from_district_name}  
📍 Qayerga: {to_district_name}  
🕒 Chiqish vaqti: {order.departureTime.strftime('%Y-%m-%d %H:%M')}  
👥 Yo'lovchilar soni: {order.passengers}"""
        
        reply_markup = None
        # Faqat initiated holatida tugma ko'rsatish
        if current_status == "initiated":
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("📞 Yo'lovchi bilan bog'lanish", callback_data=f"contact_passenger_{order.id}"))
            reply_markup = keyboard
        
        # Canceled buyurtmalarni o'chirish
        if current_status == "canceled":
            try:
                await bot.delete_message(chat_id=CHANNEL_ID, message_id=channel_message_id)
                logging.info(f"Bekor qilingan buyurtma {order.id} kanaldan o'chirildi")
                return
            except Exception as delete_error:
                logging.error(f"Xabarni o'chirishda xato: {delete_error}")
                # Agar o'chirish muvaffaqiyatsiz bo'lsa, oddiy yangilash
        
        await bot.edit_message_text(
            chat_id=CHANNEL_ID,
            message_id=channel_message_id,
            text=new_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        logging.info(f"Kanal posti muvaffaqiyatli yangilandi: Order {order.id}, Status: {current_status}")
        
    except Exception as e:
        logging.error(f"Kanal postini yangilashda xato: Order {order.id}, Error: {e}")

# Kanal xabar ID larini saqlash uchun
order_channel_messages = {}

@dp.message_handler(lambda message: message.text == "Yo'lga otlanish", state="*")
async def start_trip(message: types.Message, state: FSMContext):
    """Yo'lga otlanish jarayonini boshlash"""
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
        keyboard.insert(InlineKeyboardButton(text=region_name, callback_data=f"from_{region_name}"))
    
    msg = await message.answer("Qaysi viloyatdan ketmoqchisiz?", reply_markup=keyboard)
    await state.update_data(last_inline_message_id=msg.message_id)
    await OrderState.from_region.set()

@dp.callback_query_handler(lambda c: c.data.startswith("from_"), state=OrderState.from_region)
async def select_from_district(callback_query: types.CallbackQuery, state: FSMContext):
    viloyat = callback_query.data.split("_")[1]
    await state.update_data(from_region=viloyat)
    
    regions_dict, districts_dict = await get_regions_and_districts()
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in districts_dict.get(viloyat, []):
        keyboard.insert(InlineKeyboardButton(text=district, callback_data=f"from_district_{district}"))

    await callback_query.message.edit_text(f"{viloyat} viloyati, qaysi tumandan ketmoqchisiz?", reply_markup=keyboard)
    await OrderState.from_district.set()

@dp.callback_query_handler(lambda c: c.data.startswith("from_district_"), state=OrderState.from_district)
async def ask_passengers(callback_query: types.CallbackQuery, state: FSMContext):
    tuman = callback_query.data.split("_")[2]
    await state.update_data(from_district=tuman)
    
    keyboard = InlineKeyboardMarkup(row_width=4)
    for i in range(1, 5):
        keyboard.insert(InlineKeyboardButton(text=str(i), callback_data=f"passengers_{i}"))
    
    await callback_query.message.edit_text("Necha kishi ketmoqchisiz?", reply_markup=keyboard)
    await OrderState.passengers.set()

@dp.callback_query_handler(lambda c: c.data.startswith("passengers_"), state=OrderState.passengers)
async def set_passengers(callback_query: types.CallbackQuery, state: FSMContext):
    passengers = int(callback_query.data.split("_")[1])
    user_data = await state.get_data()
    from_region = user_data.get("from_region")

    await state.update_data(passengers=passengers)

    regions_dict, districts_dict = await get_regions_and_districts()
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for region_name in districts_dict.keys():
        if region_name != from_region:
            keyboard.insert(InlineKeyboardButton(text=region_name, callback_data=f"to_{region_name}"))

    await callback_query.message.edit_text(
        f"👥 Passajirlar soni: {passengers}\n\n"
        "Qaysi viloyatga borasiz?",  
        reply_markup=keyboard
    )
    await OrderState.to_region.set()

@dp.callback_query_handler(lambda c: c.data.startswith("to_"), state=OrderState.to_region)
async def select_to_district(callback_query: types.CallbackQuery, state: FSMContext):
    viloyat = callback_query.data.split("_")[1]
    user_data = await state.get_data()
    from_district = user_data.get("from_district")
    
    await state.update_data(to_region=viloyat)

    regions_dict, districts_dict = await get_regions_and_districts()
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in districts_dict.get(viloyat, []):
        if district != from_district:
            keyboard.insert(InlineKeyboardButton(text=district, callback_data=f"to_district_{district}"))

    await callback_query.message.edit_text(f"{viloyat} viloyati, qaysi tumanga borasiz?", reply_markup=keyboard)
    await OrderState.to_district.set()

@dp.callback_query_handler(lambda c: c.data.startswith("to_district_"), state=OrderState.to_district)
async def ask_datetime(callback_query: types.CallbackQuery, state: FSMContext):
    tuman = callback_query.data.split("_")[2]
    await state.update_data(to_district=tuman)
    
    today = date.today()
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for i in range(5):
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

@dp.callback_query_handler(lambda c: c.data.startswith("date_"), state=OrderState.datetime)
async def process_date(callback_query: types.CallbackQuery, state: FSMContext):
    selected_date = callback_query.data.split("_")[1]
    await state.update_data(departure_date=selected_date)
    
    await callback_query.message.edit_text("⏰ Jo'natish vaqtini HH:MM formatida kiriting (masalan, 14:30):")
    await OrderState.time.set()

@dp.message_handler(state=OrderState.time)
async def process_manual_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        user_data = await state.get_data()
        departure_datetime = f"{user_data['departure_date']} {message.text}"
        await update_order_and_confirm(message, state, departure_datetime)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Iltimos, vaqtni HH:MM formatida kiriting (masalan, 14:30).")

async def update_order_and_confirm(message, state, departure_datetime):
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

@dp.callback_query_handler(lambda c: c.data == "confirm_order", state=OrderState.confirmation)
async def confirm_order(callback_query: types.CallbackQuery, state: FSMContext):
    """Buyurtmani tasdiqlash va yaratish"""
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

        # Buyurtma yaratish
        order = await db.order.create({
            "passengerId": user.id,
            "fromRegionId": from_region.id,
            "fromDistrictId": from_district.id,
            "toRegionId": to_region.id,
            "toDistrictId": to_district.id,
            "passengers": data.get("passengers"),
            "departureTime": datetime.strptime(data.get("departure_time"), "%Y-%m-%d %H:%M")
        })

        # Status yaratish (initiated holatida)
        order_status = await db.orderstatus.create({
            "status": "initiated",
            "orderId": order.id,
            "userId": user.id
        })

        # Kanal uchun klaviatura
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📞 Yo'lovchi bilan bog'lanish", callback_data=f"contact_passenger_{order.id}"))

        # Kanalga xabar yuborish
        channel_message = await bot.send_message(
            chat_id=CHANNEL_ID,  
            text=f"""🆕 *Yangi buyurtma!*  
🚦 Holati: *NEW*  
📍 Qayerdan: {data["from_district"]}  
📍 Qayerga: {data["to_district"]}  
🕒 Chiqish vaqti: {data["departure_time"]}  
👥 Yo'lovchilar soni: {data["passengers"]}""",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        # Channel message ID ni saqlash
        order_channel_messages[order.id] = channel_message.message_id

        # Foydalanuvchi uchun klaviatura
        user_keyboard = InlineKeyboardMarkup(row_width=2)
        user_keyboard.add(
            InlineKeyboardButton("✅ Complete", callback_data=f"complete_order_{order.id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_order_{order.id}")
        )

        await callback_query.message.edit_text(
            "✅ Buyurtma yaratildi! Haydovchilar javobini kuting...\n\n"
            "🚖 Haydovchi bilan kelishgan bo'lsangiz, *Complete* tugmasini bosing.\n"
            "🔄 Agar fikringizdan qaytgan bo'lsangiz, *Cancel* tugmasini bosing.",
            reply_markup=user_keyboard,
            parse_mode="Markdown"
        )
        
        # Order reminder yuborish
        bg_task = asyncio.create_task(send_order_reminder(order.id, user.telegramId))
        bg_task.add_done_callback(lambda t: logging.error(f"Order reminder task error: {t.exception()}") if t.exception() else None)
        
    except Exception as e:
        logging.error(f"Buyurtma yaratishda xato: {e}")
        await callback_query.message.edit_text("❌ Xatolik yuz berdi! Iltimos, qayta urinib ko'ring.")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "cancel_order", state="*")
async def cancel_order_creation(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback_query.message.edit_text("❌ Buyurtma bekor qilindi.")

@dp.callback_query_handler(lambda c: c.data.startswith("contact_passenger_"))
async def send_passenger_info(callback_query: types.CallbackQuery):
    """Haydovchi yo'lovchi bilan bog'lanish tugmasini bosganda"""
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
    
    # Yo'lovchining o'z buyurtmasiga ruxsat
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
        channel_message_id = order_channel_messages.get(order_id)
        if channel_message_id:
            await update_channel_order_status(updated_order, channel_message_id)
        
        # 5 daqiqalik timer o'rnatish
        if order_id in processing_timers:
            processing_timers[order_id].cancel()
        
        timer_task = asyncio.create_task(processing_timer(order_id, channel_message_id))
        processing_timers[order_id] = timer_task
        
        # Haydovchiga yo'lovchi ma'lumotlarini yuborish
        passenger_info = (
            f"🚖 *Yo'lovchi ma'lumotlari:*\n"
            f"📍 Qayerdan: {order.fromDistrict.name if order.fromDistrict else 'Nomalum'}\n"
            f"📍 Qayerga: {order.toDistrict.name if order.toDistrict else 'Nomalum'}\n"
            f"🕒 Chiqish vaqti: {order.departureTime.strftime('%Y-%m-%d %H:%M')}\n"
            f"👥 Yo'lovchilar soni: {order.passengers}\n"
            f"🚦 Buyurtma holati: *JARAYONDA*\n\n"
            f"👤 Ism: {order.passenger.firstName} {order.passenger.lastName}\n"
            f"📞 Telefon: {order.passenger.phoneNumber}\n"
        )
        if order.passenger.username:
            passenger_info += f"🔗 Telegram: @{order.passenger.username}"

        await bot.send_message(callback_query.from_user.id, passenger_info, parse_mode="Markdown")
        await callback_query.answer("✅ Buyurtma jarayonga olindi! Yo'lovchi ma'lumotlari yuborildi. 5 daqiqa vaqtingiz bor.", show_alert=True)
    
    elif current_status == "processing":
        # Agar boshqa haydovchi processing qilayotgan bo'lsa
        processing_user = order.status.user
        if processing_user and processing_user.telegramId != user_id:
            await callback_query.answer("⏳ Bu buyurtma boshqa haydovchi tomonidan ko'rib chiqilmoqda.", show_alert=True)
        else:
            # O'sha haydovchi yana bosgan bo'lsa
            await callback_query.answer("⏳ Siz allaqachon bu buyurtmani jarayonga oldingiz.", show_alert=True)
    
    else:
        # Boshqa statuslar uchun
        await update_channel_order_status(order, callback_query.message.message_id if hasattr(callback_query, 'message') else None)
        
        status_messages = {
            "canceled": "❌ Buyurtma bekor qilindi! (CANCELED)",
            "completed": "❗️😢 Buyurtma yakunlandi! \nMijoz haydovchi bilan kelishib bo'ldi. (COMPLETED)",
            "failed": "⚠️ Buyurtmada xatolik yuz berdi! (FAILED)"
        }
        
        status_message = status_messages.get(current_status, "Holati noma'lum")
        await callback_query.answer(status_message, show_alert=True)

async def get_channel_message_id(order_id):
    """Order uchun channel message ID ni olish"""
    return order_channel_messages.get(order_id)

@dp.callback_query_handler(lambda c: c.data.startswith("complete_order_"))
async def complete_order(callback_query: types.CallbackQuery, state: FSMContext):
    """Buyurtmani yakunlash"""
    order_id = int(callback_query.data.split("_")[-1])

    order = await db.order.find_unique(
        where={"id": order_id}, 
        include={"status": True, "fromDistrict": True, "toDistrict": True}
    )
    
    if not order or (order.status and order.status.status not in ["initiated", "processing"]):
        await callback_query.answer("❌ Buyurtma allaqachon o'zgartirilgan yoki mavjud emas.", show_alert=True)
        return

    # Timer ni to'xtatish
    if order_id in processing_timers:
        processing_timers[order_id].cancel()
        del processing_timers[order_id]

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
    channel_message_id = await get_channel_message_id(order_id)
    if channel_message_id:
        await update_channel_order_status(updated_order, channel_message_id)
    else:
        logging.warning(f"Order {order_id} uchun channel_message_id topilmadi")

    await callback_query.message.edit_text("✅ Buyurtma muvaffaqiyatli yakunlandi!", reply_markup=None)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_order_"))
async def cancel_order_status(callback_query: types.CallbackQuery, state: FSMContext):
    """Buyurtmani bekor qilish"""
    order_id = int(callback_query.data.split("_")[-1])

    order = await db.order.find_unique(
        where={"id": order_id}, 
        include={"status": True, "fromDistrict": True, "toDistrict": True}
    )
    
    if not order or (order.status and order.status.status not in ["initiated", "processing"]):
        await callback_query.answer("❌ Buyurtma allaqachon o'zgartirilgan yoki mavjud emas.", show_alert=True)
        return

    # Timer ni to'xtatish
    if order_id in processing_timers:
        processing_timers[order_id].cancel()
        del processing_timers[order_id]

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
    channel_message_id = await get_channel_message_id(order_id)
    if channel_message_id:
        await update_channel_order_status(updated_order, channel_message_id)
        # Channel messages ro'yxatdan o'chirish
        if order_id in order_channel_messages:
            del order_channel_messages[order_id]
    else:
        logging.warning(f"Order {order_id} uchun channel_message_id topilmadi")

    await callback_query.message.edit_text("❌ Buyurtma bekor qilindi.", reply_markup=None)
    await callback_query.answer()

# Qo'shimcha utility funksiyalar

async def cleanup_expired_timers():
    """Eskirgan timerlarni tozalash"""
    expired_orders = []
    for order_id, task in processing_timers.items():
        if task.done():
            expired_orders.append(order_id)
    
    for order_id in expired_orders:
        del processing_timers[order_id]
        logging.info(f"Expired timer cleaned up for order {order_id}")

async def get_order_statistics():
    """Buyurtma statistikalarini olish"""
    try:
        total_orders = await db.order.count()
        
        status_counts = {}
        for status in ["initiated", "processing", "completed", "canceled", "failed"]:
            count = await db.orderstatus.count(where={"status": status})
            status_counts[status] = count
        
        return {
            "total_orders": total_orders,
            "status_distribution": status_counts,
            "active_processing": len(processing_timers)
        }
    except Exception as e:
        logging.error(f"Statistika olishda xato: {e}")
        return None

# Debugging va monitoring uchun
async def monitor_processing_orders():
    """Processing holatidagi buyurtmalarni monitoring qilish"""
    try:
        processing_orders = await db.orderstatus.find_many(
            where={"status": "processing"},
            include={"order": True}
        )
        
        logging.info(f"Hozirda {len(processing_orders)} ta buyurtma processing holatida")
        
        for status in processing_orders:
            order_id = status.orderId
            if order_id not in processing_timers:
                logging.warning(f"Processing order {order_id} uchun timer topilmadi, qayta ishga tushirilmoqda")
                # Timer qayta ishga tushirish
                channel_message_id = order_channel_messages.get(order_id)
                if channel_message_id:
                    timer_task = asyncio.create_task(processing_timer(order_id, channel_message_id))
                    processing_timers[order_id] = timer_task
                    
    except Exception as e:
        logging.error(f"Processing orders monitoring xato: {e}")

# Startup cleanup function
async def cleanup_orphaned_processing_orders():
    """Dastur qayta ishga tushganda orphaned processing orderlarni tozalash"""
    try:
        orphaned_orders = await db.orderstatus.find_many(
            where={"status": "processing"},
            include={
                "order": {
                    "include": {
                        "fromDistrict": True,
                        "toDistrict": True
                    }
                }
            }
        )
        
        for status in orphaned_orders:
            order_id = status.orderId
            # Bu orderlarni initiated ga qaytarish
            await db.orderstatus.update(
                where={"orderId": order_id},
                data={"status": "initiated"}
            )
            
            logging.info(f"Orphaned processing order {order_id} initiated holatiga qaytarildi")
            
    except Exception as e:
        logging.error(f"Orphaned orders cleanup xato: {e}")

# Error handling wrapper
def handle_errors(func):
    """Error handling decorator"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {e}")
            if len(args) > 0 and hasattr(args[0], 'answer'):
                try:
                    await args[0].answer("❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.")
                except:
                    pass
    return wrapper

# Cleanup function to be called on startup
async def initialize_departure_module():
    """Departure moduli ishga tushirilganda chaqiriladigan funksiya"""
    await cleanup_orphaned_processing_orders()
    await cleanup_expired_timers()
    logging.info("Departure module initialized successfully")