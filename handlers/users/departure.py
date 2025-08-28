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

async def get_channel_url():
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        return f"https://t.me/{chat.username.replace('@', '')}" if chat.username else f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
    except Exception as e:
        logging.error(f"Kanal ma'lumotlarini olishda xato: {e}")
        return f"https://t.me/c/{str(CHANNEL_ID)[4:]}"

async def update_channel_order_status(order, channel_message_id=None):
    try:
        if not channel_message_id:
            if hasattr(order, 'channelMessageId') and order.channelMessageId:
                channel_message_id = order.channelMessageId
            else:
                logging.warning(f"Order {order.id} uchun channel_message_id topilmadi")
                return
        
        status_mapping = {
            "initiated": {"status": "NEW", "emoji": "🆕"},
            "completed": {"status": "YAKUNLANDI", "emoji": "✅"},
            "canceled": {"status": "BEKOR QILINDI", "emoji": "❌"}
        }
        
        current_status = order.status.status if order.status else "initiated"
        status_info = status_mapping.get(current_status, {"status": "NOMA'LUM", "emoji": "❓"})
        
        new_text = f"""{status_info['emoji']} *Buyurtma - {status_info['status']}*  
🚦 Holati: *{status_info['status']}*  
📍 Qayerdan: {order.fromDistrict}  
📍 Qayerga: {order.toDistrict}  
🕒 Chiqish vaqti: {order.departureTime.strftime('%Y-%m-%d %H:%M')}  
👥 Yo'lovchilar soni: {order.passengers}"""
        
        reply_markup = None
        if current_status == "initiated":
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("📞 Yo'lovchi bilan bog'lanish", callback_data=f"contact_passenger_{order.id}"))
            reply_markup = keyboard
        
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

order_channel_messages = {}

with open("regions.json", "r", encoding="utf-8") as file:
    regions = json.load(file)

@dp.message_handler(lambda message: message.text == "Yo'lga otlanish", state="*")
async def start_trip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    old_msg_id = data.get("last_inline_message_id")
    if old_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old_msg_id)
        except:
            pass

    keyboard = InlineKeyboardMarkup(row_width=2)
    for region in regions.keys():
        keyboard.insert(InlineKeyboardButton(text=region, callback_data=f"from_{region}"))
    
    msg = await message.answer("Qaysi viloyatdan ketmoqchisiz?", reply_markup=keyboard)
    await state.update_data(last_inline_message_id=msg.message_id)
    await OrderState.from_region.set()

@dp.callback_query_handler(lambda c: c.data.startswith("from_"), state=OrderState.from_region)
async def select_from_district(callback_query: types.CallbackQuery, state: FSMContext):
    viloyat = callback_query.data.split("_")[1]
    await state.update_data(from_region=viloyat)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in regions[viloyat]:
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

    keyboard = InlineKeyboardMarkup(row_width=2)
    for region in regions.keys():
        if region != from_region:
            keyboard.insert(InlineKeyboardButton(text=region, callback_data=f"to_{region}"))

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

    keyboard = InlineKeyboardMarkup(row_width=2)
    for district in regions[viloyat]:
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
    data = await state.get_data()

    try:
        user = await db.user.find_unique(where={"telegramId": str(callback_query.from_user.id)})

        if not user:
            user = await db.user.create({
                "telegramId": str(callback_query.from_user.id),
                "firstName": callback_query.from_user.first_name or "",
                "lastName": callback_query.from_user.last_name or "",
                "username": callback_query.from_user.username,
                "phoneNumber": "",
                "role": "PASSENGER"
            })

        order = await db.order.create({
            "passengerId": user.id,
            "fromRegion": data.get("from_region"),
            "fromDistrict": data.get("from_district"),
            "toRegion": data.get("to_region"),
            "toDistrict": data.get("to_district"),
            "passengers": data.get("passengers"),
            "departureTime": datetime.strptime(data.get("departure_time"), "%Y-%m-%d %H:%M")
        })

        order_status = await db.orderstatus.create({
            "status": "initiated",
            "orderId": order.id,
            "userId": user.id
        })

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📞 Yo'lovchi bilan bog'lanish", callback_data=f"contact_passenger_{order.id}"))

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

        try:
            await db.order.update(
                where={"id": order.id},
                data={"channelMessageId": channel_message.message_id}
            )
        except Exception as e:
            logging.warning(f"Database schema'da channelMessageId maydoni topilmadi: {e}")
            order_channel_messages[order.id] = channel_message.message_id

        await state.update_data(channel_message_id=channel_message.message_id)

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
    user_id = callback_query.from_user.id
    order_id = int(callback_query.data.split("_")[-1])

    try:
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

    user = await db.user.find_unique(where={"telegramId": str(user_id)})
    if not user:
        await callback_query.answer(
            f"❌ Siz botda ro'yxatdan o'tmagansiz. Iltimos, botni ishlatish uchun ro'yxatdan o'ting: {BOT_USERNAME}",
            show_alert=True
        )
        return

    order = await db.order.find_unique(
        where={"id": order_id},
        include={"passenger": True, "status": True}
    )

    if not order:
        await callback_query.answer("❌ Buyurtma topilmadi yoki allaqachon o'chirilgan.", show_alert=True)
        return
    
    if user.role == "PASSENGER" and order.passenger.telegramId != str(user_id):
        await callback_query.answer(
            "⛔️ Siz faqat o'zingizning buyurtmangiz haqida ma'lumot olishingiz mumkin.",
            show_alert=True
        )
        return

    current_status = order.status.status if order.status else "initiated"
    
    if current_status == "initiated":
        passenger_info = (
            f"🚖 *Yo'lovchi ma'lumotlari:*\n"
            f"📍 Qayerdan: {order.fromDistrict}\n"
            f"📍 Qayerga: {order.toDistrict}\n"
            f"🕒 Chiqish vaqti: {order.departureTime.strftime('%Y-%m-%d %H:%M')}\n"
            f"👥 Yo'lovchilar soni: {order.passengers}\n"
            f"🚦 Buyurtma holati: *NEW*\n\n"
            f"👤 Ism: {order.passenger.firstName} {order.passenger.lastName}\n"
            f"📞 Telefon: {order.passenger.phoneNumber}\n"
        )
        if order.passenger.username:
            passenger_info += f"🔗 Telegram: @{order.passenger.username}"

        await bot.send_message(callback_query.from_user.id, passenger_info, parse_mode="Markdown")
        await callback_query.answer("✅ Faol buyurtma. Ma'lumotlar bot orqali profilingizga yuborildi. (NEW)", show_alert=True)
    
    else:
        await update_channel_order_status(order, callback_query.message.message_id)
        
        status_messages = {
            "canceled": "❌ Buyurtma bekor qilindi! (CANCELED)",
            "completed": "❗️😢 Buyurtma yakunlandi! \nMijoz haydovchi bilan kelishib bo'ldi. (COMPLETED)"
        }
        
        status_message = status_messages.get(current_status, "Holati noma'lum")
        await callback_query.answer(status_message, show_alert=True)

async def get_channel_message_id(order_id):
    try:
        order = await db.order.find_unique(where={"id": order_id})
        if hasattr(order, 'channelMessageId') and order.channelMessageId:
            return order.channelMessageId
    except:
        pass
    
    return order_channel_messages.get(order_id)

@dp.callback_query_handler(lambda c: c.data.startswith("complete_order_"))
async def complete_order(callback_query: types.CallbackQuery, state: FSMContext):
    order_id = int(callback_query.data.split("_")[-1])

    order = await db.order.find_unique(where={"id": order_id}, include={"status": True})
    
    if not order or (order.status and order.status.status != "initiated"):
        await callback_query.answer("❌ Buyurtma allaqachon o'zgartirilgan yoki mavjud emas.", show_alert=True)
        return

    await db.orderstatus.update(
        where={"orderId": order_id},
        data={"status": "completed"}
    )

    updated_order = await db.order.find_unique(where={"id": order_id}, include={"status": True})

    channel_message_id = await get_channel_message_id(order_id)
    
    if channel_message_id:
        await update_channel_order_status(updated_order, channel_message_id)
    else:
        logging.warning(f"Order {order_id} uchun channel_message_id topilmadi, kanal posti yangilanmadi")

    await callback_query.message.edit_text("✅ Buyurtma muvaffaqiyatli yakunlandi!", reply_markup=None)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_order_"))
async def cancel_order_status(callback_query: types.CallbackQuery, state: FSMContext):
    order_id = int(callback_query.data.split("_")[-1])

    order = await db.order.find_unique(where={"id": order_id}, include={"status": True})
    
    if not order or (order.status and order.status.status != "initiated"):
        await callback_query.answer("❌ Buyurtma allaqachon o'zgartirilgan yoki mavjud emas.", show_alert=True)
        return

    await db.orderstatus.update(
        where={"orderId": order_id},
        data={"status": "canceled"}
    )

    updated_order = await db.order.find_unique(where={"id": order_id}, include={"status": True})

    channel_message_id = await get_channel_message_id(order_id)

    if channel_message_id:
        await update_channel_order_status(updated_order, channel_message_id)
    else:
        logging.warning(f"Order {order_id} uchun channel_message_id topilmadi, kanal posti yangilanmadi")
    await callback_query.message.edit_text("❌ Buyurtma bekor qilindi.", reply_markup=None)
    await callback_query.answer()