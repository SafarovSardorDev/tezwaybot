from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import dp, db, bot
from states.registerstates import OrderState, HistoryState
from datetime import datetime


def get_order_status_text(status):
    """OrderStatus holatini foydalanuvchi uchun tushunarli matn formatiga o'giradi."""
    status_translations = {
        'initiated': '🆕 Yangi',
        'completed': '✔️ Yakunlangan',
        'failed': '❌ Muvaffaqiyatsiz',
        'canceled': '🚫 Bekor qilingan'
    }
    return status_translations.get(status, 'Holati noma\'lum')

def format_datetime(dt, default_text="Belgilanmagan"):
    """Datetime obyektini formatlab, None bo'lsa default text qaytaradi."""
    if dt is None:
        return default_text
    try:
        return dt.strftime('%Y-%m-%d %H:%M')
    except (AttributeError, TypeError):
        return default_text

def format_order_info(order):
    """Buyurtma turiga qarab ma'lumotlarni formatlab chiqaradi"""
    # Region va district ma'lumotlarini olish
    from_region = getattr(order.fromRegion, 'name', 'Noma\'lum') if order.fromRegion else 'Noma\'lum'
    from_district = getattr(order.fromDistrict, 'name', 'Noma\'lum') if order.fromDistrict else 'Noma\'lum'
    to_region = getattr(order.toRegion, 'name', 'Noma\'lum') if order.toRegion else 'Noma\'lum'
    to_district = getattr(order.toDistrict, 'name', 'Noma\'lum') if order.toDistrict else 'Noma\'lum'
    
    # Buyurtma turini aniqlash
    order_type = getattr(order, 'orderType', 'PASSENGER')
    
    order_info = []
    
    if order_type == "DELIVERY":
        # Pochta buyurtmasi uchun ma'lumotlar
        order_info.append(f"📦 Pochta buyurtma № {order.id}")
        order_info.append(f"📍 Qayerdan: {from_region}, {from_district}")
        order_info.append(f"🏁 Qayerga: {to_region}, {to_district}")
        
        # Paket ma'lumotlari
        if order.packageType:
            package_types = {
                "DOCUMENT": "📄 Hujjat",
                "PARCEL": "📦 Posilka", 
                "FRAGILE": "🔸 Mo'rt buyum",
                "VALUABLE": "💎 Qimmatbaho",
                "OTHER": "📋 Boshqa"
            }
            order_info.append(f"📦 Turi: {package_types.get(order.packageType, 'Nomalum')}")
        
        if order.packageSize:
            package_sizes = {
                "SMALL": "📦 Kichik (10kg gacha)",
                "MEDIUM": "📦 O'rta (10-25kg)",
                "LARGE": "📦 Katta (25-50kg)", 
                "EXTRA_LARGE": "📦 Juda katta (50kg+)"
            }
            order_info.append(f"📏 Hajmi: {package_sizes.get(order.packageSize, 'Nomalum')}")
        
        if order.packageWeight:
            order_info.append(f"⚖️ Og'irligi: {order.packageWeight} kg")
        
        if order.receiverName:
            order_info.append(f"👤 Qabul qiluvchi: {order.receiverName}")
        
        if order.receiverPhone:
            order_info.append(f"📞 Telefon: {order.receiverPhone}")
        
        if order.packageDescription:
            order_info.append(f"📝 Tavsifi: {order.packageDescription}")
            
    else:
        # Yo'lovchi buyurtmasi uchun ma'lumotlar
        order_info.append(f"🚗 Yo'lovchi buyurtma № {order.id}")
        order_info.append(f"📍 Qayerdan: {from_region}, {from_district}")
        order_info.append(f"🏁 Qayerga: {to_region}, {to_district}")
        
        # Yo'lovchilar soni
        passengers_count = getattr(order, 'passengers', 1)
        order_info.append(f"👥 Yo'lovchilar soni: {passengers_count}")
        
        # Ketish vaqti
        departure_time = format_datetime(getattr(order, 'departureTime', None), "Belgilanmagan")
        order_info.append(f"⏰ Ketish vaqti: {departure_time}")
    
    # Umumiy ma'lumotlar
    order_info.append(f"📊 Holat: {get_order_status_text(order.status.status if order.status else 'initiated')}")
    
    # Haydovchi ma'lumotlari
    if order.driver:
        driver_first_name = getattr(order.driver, 'firstName', 'Noma\'lum')
        driver_last_name = getattr(order.driver, 'lastName', '')
        driver_phone = getattr(order.driver, 'phoneNumber', 'Noma\'lum')
        
        order_info.extend([
            f"👤 Haydovchi: {driver_first_name} {driver_last_name}",
            f"📞 Telefon: {driver_phone}"
        ])
    
    # Yaratilgan sana
    created_at = format_datetime(getattr(order, 'createdAt', None), "Noma'lum")
    order_info.append(f"📅 Yaratilgan sana: {created_at}")
    
    return '\n'.join(order_info)

@dp.message_handler(lambda message: message.text == "📋 Buyurtma tarixi", state="*")
async def show_history(message: types.Message, state: FSMContext):
    user = await db.user.find_unique(where={'telegramId': str(message.from_user.id)})
    
    if not user or user.role != "PASSENGER":
        await message.answer("Bu funksiya faqat yo'lovchilar uchun mavjud.")
        return

    orders = await db.order.find_many(
        where={'passengerId': user.id},
        include={
            'driver': True, 
            'status': True, 
            'fromRegion': True, 
            'fromDistrict': True, 
            'toRegion': True, 
            'toDistrict': True
        }
    )
    orders = sorted(orders, key=lambda x: x.createdAt, reverse=True)

    if not orders:
        await message.answer("⭕️ Sizda hech qanday buyurtma tarixi yo'q.")
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
        order_messages.append(format_order_info(order))

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