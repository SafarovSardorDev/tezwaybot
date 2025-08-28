import asyncio
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loader import dp, db, bot
import logging
from dotenv import load_dotenv
import os

load_dotenv()
BOT_USERNAME = os.getenv("BOT_USERNAME")

ORDER_EXPIRY_TIME = int(os.getenv("ORDER_EXPIRY_TIME", 1200))
ORDER_REMINDER_TIME = int(os.getenv("ORDER_REMINDER_TIME", 900))

async def send_order_reminder(order_id: int, user_id: str):
    """Buyurtma eslatmasini yuborish va avtomatik bekor qilish."""
    try:
        order = await db.order.find_unique(where={"id": order_id}, include={"status": True})
        
        if not order or (order.status and order.status.status != "initiated"):
            return

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Complete", callback_data=f"complete_order_{order_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_order_{order_id}")
        )
        
        await asyncio.sleep(ORDER_REMINDER_TIME)
        
        updated_order = await db.order.find_unique(where={"id": order_id}, include={"status": True})
        if updated_order and updated_order.status and updated_order.status.status == "initiated":
            await bot.send_message(
                user_id,
                (
                    f"📋 *Buyurtma ma'lumotlari:*\n"
                    f"📍 Qayerdan: {updated_order.fromDistrict}\n"
                    f"📍 Qayerga: {updated_order.toDistrict}\n"
                    f"🕒 Chiqish vaqti: {updated_order.departureTime.strftime('%Y-%m-%d %H:%M')}\n"
                    f"👥 Yo'lovchilar soni: {updated_order.passengers}\n\n"
                    "⏳ Buyurtmangiz hali tasdiqlanmagan. Iltimos, 'Complete' yoki 'Cancel' tugmalaridan birini bosing."
                ),
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        await asyncio.sleep(ORDER_EXPIRY_TIME - ORDER_REMINDER_TIME)
        
        final_order = await db.order.find_unique(where={"id": order_id}, include={"status": True})
        if final_order and final_order.status and final_order.status.status == "initiated":
            await db.orderstatus.update(
                where={"orderId": order_id},
                data={"status": "canceled"}
            )
            await bot.send_message(
                user_id,
                (
                    f"📋 *Buyurtma ma'lumotlari:*\n"
                    f"📍 Qayerdan: {final_order.fromDistrict}\n"
                    f"📍 Qayerga: {final_order.toDistrict}\n"
                    f"🕒 Chiqish vaqti: {final_order.departureTime.strftime('%Y-%m-%d %H:%M')}\n"
                    f"👥 Yo'lovchilar soni: {final_order.passengers}\n\n"
                    f"❌ Buyurtmangiz {ORDER_EXPIRY_TIME} daqiqa ichida tasdiqlanmadi va avtomatik bekor qilindi."
                ),
                reply_markup=None,
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logging.error(f"Order reminder error: {e}")