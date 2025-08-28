from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import dp, db, bot
from states.registerstates import OrderState, HistoryState


def get_order_status_text(status):
    """OrderStatus holatini foydalanuvchi uchun tushunarli matn formatiga o'giradi."""
    status_translations = {
        'initiated': '🆕 Yangi',
        'completed': '✔️ Yakunlangan',
        'failed': '❌ Muvaffaqiyatsiz',
        'canceled': '🚫 Bekor qilingan'
    }
    return status_translations.get(status, 'Holati noma\'lum')

@dp.message_handler(lambda message: message.text == "Buyurtma tarixi", state="*")
async def show_history(message: types.Message, state: FSMContext):
    user = await db.user.find_unique(where={'telegramId': str(message.from_user.id)})
    
    if not user or user.role != "PASSENGER":
        await message.answer("Bu funksiya faqat yo'lovchilar uchun mavjud.")
        return

    orders = await db.order.find_many(
        where={'passengerId': user.id},
        include={'driver': True, 'status': True}
    )
    orders = sorted(orders, key=lambda x: x.createdAt, reverse=True)

    if not orders:
        await message.answer("Sizda hech qanday buyurtma tarixi yo'q.")
        return

    await state.update_data(orders=orders, page=0, items_per_page=3)
    await show_paginated_history(message.chat.id, state)
    await HistoryState.pagination.set()

async def show_paginated_history(chat_id, state: FSMContext, message_id=None):
    data = await state.get_data()
    orders = data.get('orders', [])
    page = data.get('page', 0)
    items_per_page = data.get('items_per_page', 3)

    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_page_orders = orders[start_idx:end_idx]
    total_pages = (len(orders) + items_per_page - 1) // items_per_page

    order_messages = []
    for order in current_page_orders:
        order_info = [
            f"🚗 Buyurtma № {order.id}",
            f"📍 Qayerdan: {order.fromRegion}, {order.fromDistrict}",
            f"🏁 Qayerga: {order.toRegion}, {order.toDistrict}",
            f"👥 Yo'lovchilar soni: {order.passengers}",
            f"⏰ Ketish vaqti: {order.departureTime.strftime('%Y-%m-%d %H:%M')}",
            f"📊 Holat: {get_order_status_text(order.status.status if order.status else 'initiated')}"
        ]
        if order.driver:
            driver_info = [
                f"👤 Haydovchi: {order.driver.firstName} {order.driver.lastName}",
                f"📞 Telefon: {order.driver.phoneNumber}"
            ]
            order_info.extend(driver_info)
        order_info.append(f"📅 Yaratilgan sana: {order.createdAt.strftime('%Y-%m-%d %H:%M')}")
        order_messages.append('\n'.join(order_info))

    page_info = f"📋 Buyurtmalar tarixi ({page + 1}/{total_pages})"
    full_history = f"{page_info}:\n\n" + '\n\n'.join(order_messages)

    markup = InlineKeyboardMarkup(row_width=5)
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"history_page:{page - 1}"))
        
        max_buttons = min(5, total_pages)
        start_page = max(0, page - 2)
        end_page = min(start_page + max_buttons, total_pages)
        if end_page - start_page < max_buttons:
            start_page = max(0, end_page - max_buttons)

        page_buttons = []
        for p in range(start_page, end_page):
            text = f"• {p + 1} •" if p == page else f"{p + 1}"
            page_buttons.append(InlineKeyboardButton(text, callback_data=f"history_page:{p}"))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("➡️", callback_data=f"history_page:{page + 1}"))
        
        if total_pages > 5:
            first_last_row = []
            if page > 2:
                first_last_row.append(InlineKeyboardButton("1️⃣", callback_data="history_page:0"))
                if start_page > 1:
                    first_last_row.append(InlineKeyboardButton("...", callback_data="history_none"))
            if page < total_pages - 3 and total_pages > 6:
                if end_page < total_pages - 1:
                    first_last_row.append(InlineKeyboardButton("...", callback_data="history_none"))
                first_last_row.append(InlineKeyboardButton(f"{total_pages}", callback_data=f"history_page:{total_pages - 1}"))
            if first_last_row:
                markup.row(*first_last_row)
        
        markup.row(*page_buttons)
        if nav_row:
            markup.row(*nav_row)
    
    markup.row(InlineKeyboardButton("❌ Yopish", callback_data="history_close"))

    if message_id is None:
        await bot.send_message(chat_id, full_history, reply_markup=markup)
    else:
        await bot.edit_message_text(full_history, chat_id, message_id, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('history_'), state=HistoryState.pagination)
async def process_pagination_callback(callback_query: types.CallbackQuery, state: FSMContext):
    action = callback_query.data.split(':')[0]
    
    if action == "history_close":
        await callback_query.message.delete()
        await callback_query.answer("Buyurtmalar tarixi yopildi")
        await state.finish()
        return
    
    if action == "history_none":
        await callback_query.answer()
        return
    
    if action == "history_page":
        page = int(callback_query.data.split(':')[1])
        await state.update_data(page=page)
        await show_paginated_history(callback_query.message.chat.id, state, callback_query.message.message_id)
        await callback_query.answer()