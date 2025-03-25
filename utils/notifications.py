from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
from loader import dp, db, bot
import asyncio
from aiogram import types
from datetime import datetime
import logging


async def notify_drivers_about_order(bot, db, order_id, passenger_info, from_region, 
                                   from_district, to_region, to_district, departure_time):
    """
    Haydovchilarga yangi buyurtma haqida xabar yuborish
    """
    try:
        # Vaqtni formatlash
        time_format = '%Y-%m-%d %H:%M'  # Formatni alohida o'zgaruvchiga olamiz
        
        if isinstance(departure_time, str):
            formatted_time = departure_time
        elif isinstance(departure_time, datetime):
            formatted_time = departure_time.strftime(time_format)
        else:
            formatted_time = "Noma'lum vaqt"

        # Xabar matnini tayyorlash (list shaklida, keyin join qilamiz)
        message_lines = [
            "🚖 Yangi buyurtma:",
            f"📍 Yo'nalish: {from_region}, {from_district} -> {to_region}, {to_district}",
            f"⏰ Vaqt: {formatted_time}",
            f"👤 Yo'lovchi: {passenger_info}",
            "",
            "Buyurtmani qabul qilasizmi?"
        ]
        order_info = "\n".join(message_lines)

        # Haydovchilarni olish
        drivers = await db.user.find_many(where={"role": "DRIVER"})

        # Har bir haydovchiga xabar yuborish
        for driver in drivers:
            try:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton("✅ Qabul qilish", callback_data=f"accept_order_{order_id}"),
                    InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_order_{order_id}")
                )
                
                await bot.send_message(
                    chat_id=driver.telegramId,
                    text=order_info,
                    reply_markup=keyboard
                )
            except Exception as e:
                logging.error(f"Xabar yuborishda xato (Haydovchi ID: {driver.id}): {str(e)}")
    
    except Exception as e:
        logging.error(f"Haydovchilarni xabardor qilishda umumiy xato: {str(e)}")


async def set_order_expiry(order_id: int):
    await asyncio.sleep(300)  # 5 daqiqa = 300 soniya
    
    current_order = await db.order.find_unique(where={"id": order_id})
    if current_order and current_order.status == "NEW":
        await db.order.update(
            where={"id": order_id},
            data={"status": "EXPIRED"}
        )
        # Barcha haydovchilarga xabar yuborish
        await notify_order_expired(order_id)

async def notify_order_expired(order_id: int):
    drivers = await db.user.find_many(where={"role": "DRIVER"})
    for driver in drivers:
        try:
            await bot.send_message(
                chat_id=driver.telegramId,
                text=f"⌛ #{order_id} raqamli buyurtma vaqti tugadi va bekor qilindi."
            )
        except Exception as e:
            logging.error(f"Expiry notification error (Driver {driver.id}): {e}")

@dp.callback_query_handler(lambda c: c.data.startswith("accept_order_"))
async def handle_order_acceptance(callback_query: types.CallbackQuery):
    try:
        order_id = int(callback_query.data.split("_")[-1])
        driver = await db.user.find_unique(where={"telegramId": callback_query.from_user.id})
        
        if not driver:
            await callback_query.answer("❌ Siz ro'yxatdan o'tmagan haydovchisiz!", show_alert=True)
            return

        async with db.tx() as transaction:
            # Buyurtma holatini tekshirish
            order = await transaction.order.find_unique(
                where={"id": order_id},
                include={"passenger": True}
            )
            
            if not order:
                await callback_query.answer("❌ Buyurtma topilmadi!", show_alert=True)
                return
                
            if order.status != "NEW":
                await callback_query.answer(
                    f"⚠️ Uzr, buyurtma allaqachon {order.status} holatida!",
                    show_alert=True
                )
                return

            # Vaqtni formatlash
            time_format = '%Y-%m-%d %H:%M'
            formatted_time = order.departureTime.strftime(time_format)

            # Buyurtmani yangilash
            updated_order = await transaction.order.update(
                where={"id": order_id},
                data={
                    "status": "ACCEPTED",
                    "driverId": driver.id,
                    "updatedAt": datetime.now()
                }
            )

            # Yo'lovchiga xabar yuborish
            driver_info = f"{driver.firstName} {driver.lastName}"
            if driver.username:
                driver_info += f" (@{driver.username})"
            
            contact_button = InlineKeyboardButton(
                "📞 Bog'lanish", 
                url=f"https://t.me/{driver.username}" if driver.username else f"tg://user?id={driver.telegramId}"
            )
            
            try:
                await bot.send_message(
                    chat_id=order.passenger.telegramId,
                    text=f"🎉 Haydovchi buyurtmangizni qabul qildi!\n\n"
                         f"🚖 Haydovchi: {driver_info}\n"
                         f"📞 Telefon: +{driver.phoneNumber or 'Korsatilmagan'}\n\n"
                         f"📍 Yo'nalish: {order.fromRegion}, {order.fromDistrict} ➡️ {order.toRegion}, {order.toDistrict}\n"
                         f"⏰ Vaqt: {formatted_time}", 
                         reply_markup=contact_button
                )
            except Exception as e:
                logging.error(f"Yo'lovchiga xabar yuborishda xato: {e}")

            # Haydovchiga tasdiqlash xabari
            await callback_query.message.edit_text(
                f"✅ Siz buyurtmani qabul qildingiz!\n\n"
                f"👤 Yo'lovchi: {order.passenger.firstName} {order.passenger.lastName}\n"
                f"📞 Telefon: +{order.passenger.phoneNumber or 'Korsatilmagan'}\n\n"
                f"📍 Manzil: {order.fromRegion}, {order.fromDistrict}\n"
                f"🏁 Mo'ljal: {order.toRegion}, {order.toDistrict}\n"
                f"⏰ Vaqt: {formatted_time}",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton(
                        "📞 Yo'lovchi bilan bog'lanish",
                        url=f"https://t.me/{order.passenger.username}" if order.passenger.username else f"tg://user?id={order.passenger.telegramId}"
                    )
                )
            )
            
            # Boshqa haydovchilarga xabar yuborish
            # await notify_drivers_order_accepted(order_id, driver.id)
            
    except Exception as e:
        logging.error(f"Buyurtma qabul qilishda xato: {e}")
        await callback_query.answer("❌ Xatolik yuz berdi! Iltimos, qayta urinib ko'ring.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("reject_order_"))
async def handle_order_rejection(callback_query: types.CallbackQuery):
    try:
        order_id = int(callback_query.data.split("_")[-1])
        
        # Buyurtma holatini tekshirish
        order = await db.order.find_unique(where={"id": order_id})
        
        if order and order.status == "NEW":
            await callback_query.message.edit_text(
                "❌ Siz bu buyurtmani rad etdingiz",
                reply_markup=None
            )
        else:
            await callback_query.answer(
                "⚠️ Uzr, bu buyurtma allaqachon boshqa holatda!",
                show_alert=True
            )
            
    except Exception as e:
        logging.error(f"Buyurtma rad etishda xato: {e}")
        await callback_query.answer("❌ Xatolik yuz berdi!", show_alert=True)