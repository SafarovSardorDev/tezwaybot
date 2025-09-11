import asyncio
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loader import dp, db, bot
import logging
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()
BOT_USERNAME = os.getenv("BOT_USERNAME")

ORDER_EXPIRY_TIME = int(os.getenv("ORDER_EXPIRY_TIME", 1200))
ORDER_REMINDER_TIME = int(os.getenv("ORDER_REMINDER_TIME", 900))

async def send_order_reminder(order_id: int, user_id: str):
    """Buyurtma eslatmasini yuborish va avtomatik bekor qilish."""
    try:
        order = await db.order.find_unique(
            where={"id": order_id}, 
            include={"status": True, "fromDistrict": True, "toDistrict": True}
        )
        
        if not order or (order.status and order.status.status != "initiated"):
            return

        # DepartureTime ni tekshirish va formatlash
        departure_time_str = "Belgilanmagan"
        if order.departureTime:
            try:
                departure_time_str = order.departureTime.strftime('%Y-%m-%d %H:%M')
            except AttributeError:
                departure_time_str = "Noto'g'ri format"
        
        # District nomlarini olish
        from_district = order.fromDistrict.name if order.fromDistrict else "Noma'lum"
        to_district = order.toDistrict.name if order.toDistrict else "Noma'lum"
        
        # Passengers sonini olish (agar mavjud bo'lsa)
        passengers_count = getattr(order, 'passengers', 1)
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Complete", callback_data=f"complete_order_{order_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_order_{order_id}")
        )
        
        await asyncio.sleep(ORDER_REMINDER_TIME)
        
        updated_order = await db.order.find_unique(
            where={"id": order_id}, 
            include={"status": True, "fromDistrict": True, "toDistrict": True}
        )
        
        if updated_order and updated_order.status and updated_order.status.status == "initiated":
            # Yangilangan ma'lumotlarni olish
            updated_from_district = updated_order.fromDistrict.name if updated_order.fromDistrict else "Noma'lum"
            updated_to_district = updated_order.toDistrict.name if updated_order.toDistrict else "Noma'lum"
            
            # DepartureTime ni yangilangan holda tekshirish
            updated_departure_time_str = "Belgilanmagan"
            if updated_order.departureTime:
                try:
                    updated_departure_time_str = updated_order.departureTime.strftime('%Y-%m-%d %H:%M')
                except AttributeError:
                    updated_departure_time_str = "Noto'g'ri format"
            
            updated_passengers_count = getattr(updated_order, 'passengers', 1)
            
            await bot.send_message(
                user_id,
                (
                    f"📋 *Buyurtma ma'lumotlari:*\n"
                    f"📍 Qayerdan: {updated_from_district}\n"
                    f"📍 Qayerga: {updated_to_district}\n"
                    f"🕒 Chiqish vaqti: {updated_departure_time_str}\n"
                    f"👥 Yo'lovchilar soni: {updated_passengers_count}\n\n"
                    "⏳ Buyurtmangiz hali tasdiqlanmagan. Iltimos, 'Complete' yoki 'Cancel' tugmalaridan birini bosing."
                ),
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        await asyncio.sleep(ORDER_EXPIRY_TIME - ORDER_REMINDER_TIME)
        
        final_order = await db.order.find_unique(
            where={"id": order_id}, 
            include={"status": True, "fromDistrict": True, "toDistrict": True}
        )
        
        if final_order and final_order.status and final_order.status.status == "initiated":
            await db.orderstatus.update(
                where={"orderId": order_id},
                data={"status": "canceled"}
            )
            
            # Final ma'lumotlarni olish
            final_from_district = final_order.fromDistrict.name if final_order.fromDistrict else "Noma'lum"
            final_to_district = final_order.toDistrict.name if final_order.toDistrict else "Noma'lum"
            
            final_departure_time_str = "Belgilanmagan"
            if final_order.departureTime:
                try:
                    final_departure_time_str = final_order.departureTime.strftime('%Y-%m-%d %H:%M')
                except AttributeError:
                    final_departure_time_str = "Noto'g'ri format"
            
            final_passengers_count = getattr(final_order, 'passengers', 1)
            
            await bot.send_message(
                user_id,
                (
                    f"📋 *Buyurtma ma'lumotlari:*\n"
                    f"📍 Qayerdan: {final_from_district}\n"
                    f"📍 Qayerga: {final_to_district}\n"
                    f"🕒 Chiqish vaqti: {final_departure_time_str}\n"
                    f"👥 Yo'lovchilar soni: {final_passengers_count}\n\n"
                    f"❌ Buyurtmangiz {ORDER_EXPIRY_TIME//60} daqiqa ichida tasdiqlanmadi va avtomatik bekor qilindi."
                ),
                reply_markup=None,
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logging.error(f"Order reminder error: {e}")