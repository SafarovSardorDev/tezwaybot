from aiogram import types, Dispatcher
from datetime import datetime, timedelta
from loader import dp, db

@dp.message_handler(lambda message: message.text == "📊 Statistika")
async def show_statistics(message: types.Message):
    """Statistika tugmasi bosilganda barcha statistikani ko'rsatish"""
    
    try:
        # Foydalanuvchini bazadan topish va adminligini tekshirish
        user = await db.user.find_unique(where={"telegramId": message.from_user.id})
        
        if not user or user.role not in ["ADMIN", "SUPER_ADMIN"]:
            await message.answer("❌ Sizda bu amalni bajarish uchun ruxsat yo'q")
            return
        
        # 1. Foydalanuvchilar statistikasi
        total_users = await db.user.count()
        drivers_count = await db.user.count(where={"role": "DRIVER"})
        passengers_count = await db.user.count(where={"role": "PASSENGER"})
        admins_count = await db.user.count(where={"role": {"in": ["ADMIN", "SUPER_ADMIN"]}})
        
        # 2. Buyurtmalar statistikasi
        total_orders = await db.order.count()
        
        # Bugungi buyurtmalar
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_orders = await db.order.count(where={"createdAt": {"gte": today_start}})
        
        # Oxirgi 7 kun buyurtmalari
        week_ago = datetime.now() - timedelta(days=7)
        weekly_orders = await db.order.count(where={"createdAt": {"gte": week_ago}})
        
        # Xabar tayyorlash
        response = (
            "📊 <b>Bot Statistikasi</b>\n\n"
            
            "👥 <b>Umumiy foydalanuvchilar statistikasi:</b>\n"
            f"   • Jami foydalanuvchilar soni: {total_users}\n"
            "   <b>Rollar bo'yicha taqsimot:</b>\n"
            f"      🚖 Haydovchilar: {drivers_count}\n"
            f"      👤 Yo'lovchilar: {passengers_count}\n"
            f"      👨‍💼 Adminlar: {admins_count}\n\n"
            
            "📦 <b>Buyurtmalar statistikasi:</b>\n"
            f"   • Jami buyurtmalar soni: {total_orders}\n"
            f"   • Bugungi buyurtmalar soni: {today_orders}\n"
            f"   • Oxirgi 7 kun ichida buyurtmalar soni: {weekly_orders}"
        )
        
        await message.answer(response, parse_mode='HTML')
        
    except Exception as e:
        await message.answer(f"❌ Statistika yuklashda xatolik: {str(e)}")
