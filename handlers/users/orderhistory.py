from aiogram import types
from loader import dp, db, bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Buyurtma tarixi
@dp.message_handler(lambda message: message.text == "Buyurtma tarixi")
async def show_history(message: types.Message):
    user = await db.user.find_unique(
        where={
            'telegramId': str(message.from_user.id)
        }
    )
    
    if not user or user.role != "PASSENGER":
        await message.answer("Bu funksiya faqat yo'lovchilar uchun mavjud.")
        return

    # Fetch all orders for this passenger with driver details
    orders = await db.order.find_many(
        where={
            'passengerId': user.id
        },
        include={
            'driver': True  # Include driver information
        }
    )

    # Sort orders manually by creation date (most recent first)
    orders = sorted(orders, key=lambda x: x.createdAt, reverse=True)

    if not orders:
        await message.answer("Sizda hech qanday buyurtma tarixi yo'q.")
        return

    # Prepare message for each order
    order_messages = []
    for order in orders:
        # Base order information
        order_info = [
            f"🚗 Buyurtma № {order.id}",
            f"📍 Qayerdan: {order.fromRegion}, {order.fromDistrict}",
            f"🏁 Qayerga: {order.toRegion}, {order.toDistrict}",
            f"👥 Yo'lovchilar soni: {order.passengers}",
            f"⏰ Ketish vaqti: {order.departureTime.strftime('%Y-%m-%d %H:%M')}",
            f"📊 Holat: {get_order_status_text(order.status)}"
        ]

        # Add driver information for accepted and completed orders
        if order.status in ['ACCEPTED', 'COMPLETED'] and order.driver:
            driver_info = [
                f"👤 Haydovchi: {order.driver.firstName} {order.driver.lastName}",
                f"📞 Telefon: +{order.driver.phoneNumber}"
            ]
            order_info.extend(driver_info)

        # Add creation date and separator
        order_info.extend([
            f"📅 Yaratilgan sana: {order.createdAt.strftime('%Y-%m-%d %H:%M')}",
            "-------------------"
        ])

        # Join the order information
        order_messages.append('\n'.join(order_info))

    # Combine all order messages
    full_history = "📋 Sizning buyurtmalar tarixi:\n\n" + '\n\n'.join(order_messages)

    # Send the history in chunks if it's too long
    if len(full_history) > 4096:
        for x in range(0, len(full_history), 4096):
            await message.answer(full_history[x:x+4096])
    else:
        await message.answer(full_history)

def get_order_status_text(status):
    """Convert OrderStatus enum to user-friendly text."""
    status_translations = {
        'NEW': '🆕 Yangi',
        'ACCEPTED': '✅ Qabul qilingan',
        'IN_PROGRESS': '🚦 Bajarilmoqda',
        'COMPLETED': '✔️ Yakunlangan',
        'CANCELLED': '❌ Bekor qilingan',
        'REJECTED': '🚫 Rad etilgan'
    }
    return status_translations.get(status, status)