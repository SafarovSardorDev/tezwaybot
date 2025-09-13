import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardRemove
from loader import dp, db, bot
from states.admin_states import RegionManagementStates, DistrictManagementStates
from keyboards.admin_btns import (
    admin_main_menu, cancel_keyboard, confirmation_keyboard,
    region_main_keyboard, region_actions_keyboard, district_actions_keyboard,
    regions_list_keyboard, districts_list_keyboard, back_keyboard
)
from data.config import OWNER_ID

# Admin ID lar ro'yxati
ADMIN_IDS = list(map(int, OWNER_ID))

async def check_admin_access(user_id: int) -> bool:
    """Foydalanuvchining admin huquqlarini tekshirish"""
    try:
        user = await db.user.find_unique(where={'telegramId': str(user_id)})
        return user and user.role in ["ADMIN", "SUPER_ADMIN"]
    except Exception as e:
        logging.error(f"Admin huquqlarini tekshirishda xato: {e}")
        return False

async def notify_admins(message_text: str, exclude_user_id: int = None):
    """Barcha adminlarga xabar yuborish"""
    try:
        admins = await db.user.find_many(where={
            'OR': [
                {'role': 'ADMIN'},
                {'role': 'SUPER_ADMIN'}
            ]
        })
        
        for admin in admins:
            admin_id = int(admin.telegramId)
            if exclude_user_id and admin_id == exclude_user_id:
                continue
                
            try:
                await bot.send_message(admin_id, message_text, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")
    except Exception as e:
        logging.error(f"Adminlarni olishda xato: {e}")

# ==================== VILOYATLAR BOSHQARUVI ====================

@dp.message_handler(lambda m: m.text == "Viloyatlar")
async def regions_menu(message: types.Message, state: FSMContext):
    """Viloyatlar menyusini ko'rsatish"""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    await message.answer(
        "🏛️ <b>Viloyatlar boshqaruvi</b>\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=region_main_keyboard(),
        parse_mode="HTML"
    )
    await RegionManagementStates.main_menu.set()

# ==================== VILOYATLAR RO'YXATI ====================

@dp.callback_query_handler(lambda c: c.data == "region_list", state=RegionManagementStates.main_menu)
async def show_regions_list(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatlar ro'yxatini ko'rsatish"""
    try:
        regions = await db.region.find_many(include={"districts": True}, order={"name": "asc"})
        
        if not regions:
            await callback.message.edit_text(
                "❌ Hozircha hech qanday viloyat mavjud emas.\n\n"
                "➕ Yangi viloyat qo'shish uchun 'Viloyat qo'shish' tugmasini bosing.",
                reply_markup=region_main_keyboard()
            )
            await callback.answer()
            return
        
        total_regions = len(regions)
        await state.update_data(regions=regions, current_page=0)
        
        keyboard = regions_list_keyboard(regions)
        
        await callback.message.edit_text(
            f"📋 <b>Viloyatlar ro'yxati</b>\n\n"
            f"Jami: {total_regions} ta viloyat\n"
            f"⚠️ Belgisi - tuman biriktirilmagan viloyatlar\n\n"
            f"Quyidagi viloyatlardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await RegionManagementStates.region_list.set()
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Viloyatlar ro'yxatini ko'rsatishda xato: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
        await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("regions_page_"), state=RegionManagementStates.region_list)
async def regions_pagination(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatlar ro'yxati sahifalash"""
    try:
        page = int(callback.data.split("_")[2])
        data = await state.get_data()
        regions = data.get('regions', [])
        
        keyboard = regions_list_keyboard(regions, page)
        total_regions = len(regions)
        
        await callback.message.edit_text(
            f"📋 <b>Viloyatlar ro'yxati</b>\n\n"
            f"Jami: {total_regions} ta viloyat\n"
            f"⚠️ Belgisi - tuman biriktirilmagan viloyatlar\n\n"
            f"Quyidagi viloyatlardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.update_data(current_page=page)
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Sahifalashda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query_handler(lambda c: c.data.startswith("region_"), state=RegionManagementStates.region_list)
async def show_region_detail(callback: types.CallbackQuery, state: FSMContext):
    """Viloyat tafsilotlarini ko'rsatish"""
    try:
        region_id = int(callback.data.split("_")[1])
        
        region = await db.region.find_unique(
            where={"id": region_id},
            include={
                "districts": True,
                "ordersFrom": True,
                "ordersTo": True
            }
        )
        
        if not region:
            await callback.answer("❌ Viloyat topilmadi")
            return
        
        total_districts = len(region.districts)
        total_orders_from = len(region.ordersFrom)
        total_orders_to = len(region.ordersTo)
        
        message_text = (
            f"🏛️ <b>Viloyat ma'lumotlari</b>\n\n"
            f"📛 Nomi: <b>{region.name}</b>\n"
            f"🏘️ Tumanlar soni: <b>{total_districts} ta</b>\n"
            f"📤 Chiqish buyurtmalari: <b>{total_orders_from} ta</b>\n"
            f"📥 Kirish buyurtmalari: <b>{total_orders_to} ta</b>\n"
            f"📅 Qo'shilgan sana: <b>{region.createdAt.strftime('%Y-%m-%d %H:%M')}</b>"
        )
        
        keyboard = region_actions_keyboard(region_id, total_districts > 0)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await RegionManagementStates.region_detail.set()
        await state.update_data(current_region_id=region_id, current_region_name=region.name)
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Viloyat tafsilotlarini ko'rsatishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

# ==================== VILOYAT TAXRIRLASH ====================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_region_"), state=RegionManagementStates.region_detail)
async def start_edit_region(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatni tahrirlashni boshlash"""
    region_id = int(callback.data.split("_")[2])
    
    region = await db.region.find_unique(where={"id": region_id})
    if not region:
        await callback.answer("❌ Viloyat topilmadi")
        return
    
    await state.update_data(editing_region_id=region_id, current_region_name=region.name)
    
    await callback.message.edit_text(
        f"✏️ <b>Viloyatni tahrirlash</b>\n\n"
        f"Joriy nom: <b>{region.name}</b>\n\n"
        f"Yangi nom kiriting:",
        reply_markup=back_keyboard("back_to_region_detail"),
        parse_mode="HTML"
    )
    await RegionManagementStates.waiting_for_edit_region_name.set()
    await callback.answer()

@dp.message_handler(state=RegionManagementStates.waiting_for_edit_region_name)
async def process_edit_region_name(message: types.Message, state: FSMContext):
    """Viloyat nomini tahrirlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=admin_main_menu())
        return
    
    new_name = message.text.strip()
    
    if len(new_name) < 2:
        await message.answer("❌ Viloyat nomi juda qisqa. Iltimos, qayta kiriting:")
        return
    
    data = await state.get_data()
    region_id = data.get('editing_region_id')
    old_name = data.get('current_region_name')
    
    try:
        # Check if name already exists
        existing_region = await db.region.find_first(where={"name": new_name})
        if existing_region and existing_region.id != region_id:
            await message.answer("❌ Bu nom bilan viloyat allaqachon mavjud. Boshqa nom kiriting:")
            return
        
        # Update region
        await db.region.update(
            where={"id": region_id},
            data={"name": new_name}
        )
        
        await message.answer(
            f"✅ Viloyat muvaffaqiyatli yangilandi:\n\n"
            f"📛 Eski nom: <b>{old_name}</b>\n"
            f"📛 Yangi nom: <b>{new_name}</b>",
            parse_mode="HTML"
        )
        
        notification_text = (f"📢 Viloyat yangilandi:\n\n"
                           f"🏛️ Eski nom: <b>{old_name}</b>\n"
                           f"🏛️ Yangi nom: <b>{new_name}</b>\n"
                           f"👤 Yangilagan admin: @{message.from_user.username or message.from_user.first_name}")
        await notify_admins(notification_text, message.from_user.id)
        
    except Exception as e:
        logging.error(f"Viloyatni yangilashda xato: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")
    
    await state.finish()
    await message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())

# ==================== VILOYAT O'CHIRISH ====================

@dp.callback_query_handler(lambda c: c.data.startswith("delete_region_"), state=RegionManagementStates.region_detail)
async def start_delete_region(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatni o'chirishni boshlash"""
    region_id = int(callback.data.split("_")[2])
    
    region = await db.region.find_unique(
        where={"id": region_id},
        include={"districts": True, "ordersFrom": True, "ordersTo": True}
    )
    
    if not region:
        await callback.answer("❌ Viloyat topilmadi")
        return
    
    total_districts = len(region.districts)
    total_orders = len(region.ordersFrom) + len(region.ordersTo)
    
    warning_text = ""
    if total_districts > 0:
        warning_text = f"⚠️ <b>DIQQAT!</b> Ushbu viloyatda {total_districts} ta tuman mavjud. Viloyatni o'chirsangiz, barcha tumanlar ham o'chib ketadi!\n\n"
    if total_orders > 0:
        warning_text += f"⚠️ <b>DIQQAT!</b> Ushbu viloyatga bog'liq {total_orders} ta buyurtma mavjud. Viloyatni o'chirish buyurtmalarga ta'sir qilishi mumkin!\n\n"
    
    await callback.message.edit_text(
        f"🗑️ <b>Viloyatni o'chirish</b>\n\n"
        f"{warning_text}"
        f"Viloyat nomi: <b>{region.name}</b>\n"
        f"Tumanlar soni: {total_districts} ta\n"
        f"Buyurtmalar soni: {total_orders} ta\n\n"
        f"Rostan ham o'chirmoqchimisiz?",
        reply_markup=confirmation_keyboard(),
        parse_mode="HTML"
    )
    
    await RegionManagementStates.confirm_delete_region.set()
    await state.update_data(deleting_region_id=region_id, region_name=region.name)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data in ["confirm_yes", "confirm_no"], state=RegionManagementStates.confirm_delete_region)
async def confirm_region_deletion(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatni o'chirishni tasdiqlash"""
    if callback.data == "confirm_yes":
        data = await state.get_data()
        region_id = data.get('deleting_region_id')
        region_name = data.get('region_name')
        
        try:
            # Delete region (this will cascade delete districts due to Prisma relations)
            await db.region.delete(where={"id": region_id})
            
            await callback.message.edit_text(
                f"✅ Viloyat muvaffaqiyatli o'chirildi: <b>{region_name}</b>",
                parse_mode="HTML"
            )
            
            notification_text = (f"📢 Viloyat o'chirildi:\n\n"
                               f"🏛️ Viloyat: <b>{region_name}</b>\n"
                               f"👤 O'chirgan admin: @{callback.from_user.username or callback.from_user.first_name}")
            await notify_admins(notification_text, callback.from_user.id)
            
        except Exception as e:
            logging.error(f"Viloyatni o'chirishda xato: {e}")
            await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    else:
        await callback.message.edit_text("❌ Viloyat o'chirish bekor qilindi.")
    
    await state.finish()
    await callback.message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())
    await callback.answer()

# ==================== VILOYAT QO'SHISH ====================

@dp.callback_query_handler(lambda c: c.data == "add_region", state=RegionManagementStates.main_menu)
async def start_add_region(callback: types.CallbackQuery, state: FSMContext):
    """Viloyat qo'shishni boshlash"""
    await callback.message.edit_text(
        "Yangi viloyat nomini kiriting:",
        reply_markup=back_keyboard("back_to_region_menu")
    )
    await RegionManagementStates.waiting_for_new_region_name.set()
    await callback.answer()

@dp.message_handler(state=RegionManagementStates.waiting_for_new_region_name)
async def process_new_region_name(message: types.Message, state: FSMContext):
    """Yangi viloyat nomini qayta ishlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=admin_main_menu())
        return
    
    region_name = message.text.strip()
    
    if len(region_name) < 2:
        await message.answer("❌ Viloyat nomi juda qisqa. Iltimos, qayta kiriting:")
        return
    
    try:
        existing_region = await db.region.find_first(where={"name": region_name})
        if existing_region:
            await message.answer("❌ Bu viloyat allaqachon mavjud. Boshqa nom kiriting:")
            return
    except Exception as e:
        logging.error(f"Viloyat mavjudligini tekshirishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring:")
        return
    
    await state.update_data(region_name=region_name)
    
    await message.answer(
        f"Viloyat nomi: <b>{region_name}</b>\n\nQo'shishni tasdiqlaysizmi?",
        reply_markup=confirmation_keyboard(),
        parse_mode="HTML"
    )
    await RegionManagementStates.confirm_add_region.set()

@dp.callback_query_handler(lambda c: c.data in ["confirm_yes", "confirm_no"], state=RegionManagementStates.confirm_add_region)
async def confirm_region_addition(callback: types.CallbackQuery, state: FSMContext):
    """Viloyat qo'shishni tasdiqlash"""
    if callback.data == "confirm_yes":
        data = await state.get_data()
        region_name = data.get('region_name')
        
        try:
            await db.region.create(data={"name": region_name})
            await callback.message.edit_text(
                f"✅ Viloyat muvaffaqiyatli qo'shildi: <b>{region_name}</b>\n\n"
                f"ℹ️ <b>Hurmatli admin!</b> Viloyat bazaga qo'shildi. Unga tuman biriktirishingiz zarur. "
                f"Aks holda bo'sh viloyat yo'lovchilar ro'yxatida ko'rinmaydi!",
                parse_mode="HTML"
            )
            
            notification_text = (f"📢 Yangi viloyat qo'shildi:\n\n"
                               f"🏛️ Viloyat: <b>{region_name}</b>\n"
                               f"👤 Qo'shgan admin: @{callback.from_user.username or callback.from_user.first_name}")
            await notify_admins(notification_text, callback.from_user.id)
            
        except Exception as e:
            logging.error(f"Viloyat qo'shishda xato: {e}")
            await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    else:
        await callback.message.edit_text("❌ Viloyat qo'shish bekor qilindi.")
    
    await state.finish()
    await callback.message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())
    await callback.answer()

# ==================== TUMANLAR BOSHQARUVI ====================

@dp.callback_query_handler(lambda c: c.data.startswith("region_districts_"), state=RegionManagementStates.region_detail)
async def show_region_districts(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatga tegishli tumanlarni ko'rsatish"""
    try:
        region_id = int(callback.data.split("_")[2])
        
        region = await db.region.find_unique(
            where={"id": region_id},
            include={"districts": True}
        )
        
        if not region:
            await callback.answer("❌ Viloyat topilmadi")
            return
        
        districts = region.districts
        total_districts = len(districts)
        
        if not districts:
            await callback.message.edit_text(
                f"🏘️ <b>{region.name} viloyati tumanlari</b>\n\n"
                f"❌ Hozircha hech qanday tuman mavjud emas.\n\n"
                f"➕ Yangi tuman qo'shish uchun 'Tuman qo'shish' tugmasini bosing.",
                reply_markup=back_keyboard(f"back_to_region_{region_id}")
            )
            await callback.answer()
            return
        
        await state.update_data(
            current_region_id=region_id,
            current_region_name=region.name,
            districts=districts,
            current_page=0
        )
        
        keyboard = districts_list_keyboard(districts, region_id)
        
        await callback.message.edit_text(
            f"🏘️ <b>{region.name} viloyati tumanlari</b>\n\n"
            f"Jami: {total_districts} ta tuman\n\n"
            f"Quyidagi tumanlardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await DistrictManagementStates.district_list.set()
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Tumanlar ro'yxatini ko'rsatishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query_handler(lambda c: c.data.startswith("districts_page_"), state=DistrictManagementStates.district_list)
async def districts_pagination(callback: types.CallbackQuery, state: FSMContext):
    """Tumanlar ro'yxati sahifalash"""
    try:
        parts = callback.data.split("_")
        page = int(parts[2])
        region_id = int(parts[3])
        
        data = await state.get_data()
        districts = data.get('districts', [])
        
        keyboard = districts_list_keyboard(districts, region_id, page)
        total_districts = len(districts)
        region_name = data.get('current_region_name', '')
        
        await callback.message.edit_text(
            f"🏘️ <b>{region_name} viloyati tumanlari</b>\n\n"
            f"Jami: {total_districts} ta tuman\n\n"
            f"Quyidagi tumanlardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.update_data(current_page=page)
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Sahifalashda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query_handler(lambda c: c.data.startswith("district_"), state=DistrictManagementStates.district_list)
async def show_district_detail(callback: types.CallbackQuery, state: FSMContext):
    """Tuman tafsilotlarini ko'rsatish"""
    try:
        district_id = int(callback.data.split("_")[1])
        
        district = await db.district.find_unique(
            where={"id": district_id},
            include={
                "region": True,
                "ordersFrom": True,
                "ordersTo": True
            }
        )
        
        if not district:
            await callback.answer("❌ Tuman topilmadi")
            return
        
        total_orders_from = len(district.ordersFrom)
        total_orders_to = len(district.ordersTo)
        
        message_text = (
            f"🏘️ <b>Tuman ma'lumotlari</b>\n\n"
            f"📛 Nomi: <b>{district.name}</b>\n"
            f"🏛️ Viloyat: <b>{district.region.name}</b>\n"
            f"📤 Chiqish buyurtmalari: <b>{total_orders_from} ta</b>\n"
            f"📥 Kirish buyurtmalari: <b>{total_orders_to} ta</b>\n"
            f"📅 Qo'shilgan sana: <b>{district.createdAt.strftime('%Y-%m-%d %H:%M')}</b>"
        )
        
        keyboard = district_actions_keyboard(district_id)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await DistrictManagementStates.district_detail.set()
        await state.update_data(
            current_district_id=district_id,
            current_district_name=district.name,
            current_region_id=district.region.id
        )
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Tuman tafsilotlarini ko'rsatishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

# ==================== TUMAN TAXRIRLASH ====================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_district_"), state=DistrictManagementStates.district_detail)
async def start_edit_district(callback: types.CallbackQuery, state: FSMContext):
    """Tuman nomini tahrirlashni boshlash"""
    district_id = int(callback.data.split("_")[2])
    
    district = await db.district.find_unique(
        where={"id": district_id},
        include={"region": True}
    )
    
    if not district:
        await callback.answer("❌ Tuman topilmadi")
        return
    
    await state.update_data(
        editing_district_id=district_id,
        current_district_name=district.name,
        current_region_id=district.region.id
    )
    
    await callback.message.edit_text(
        f"✏️ <b>Tuman nomini tahrirlash</b>\n\n"
        f"Joriy nom: <b>{district.name}</b>\n"
        f"Viloyat: <b>{district.region.name}</b>\n\n"
        f"Yangi nom kiriting:",
        reply_markup=back_keyboard("back_to_district_detail"),
        parse_mode="HTML"
    )
    await DistrictManagementStates.waiting_for_edit_district_name.set()
    await callback.answer()

@dp.message_handler(state=DistrictManagementStates.waiting_for_edit_district_name)
async def process_edit_district_name(message: types.Message, state: FSMContext):
    """Tuman nomini tahrirlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=admin_main_menu())
        return
    
    new_name = message.text.strip()
    
    if len(new_name) < 2:
        await message.answer("❌ Tuman nomi juda qisqa. Iltimos, qayta kiriting:")
        return
    
    data = await state.get_data()
    district_id = data.get('editing_district_id')
    old_name = data.get('current_district_name')
    region_id = data.get('current_region_id')
    
    try:
        # Check if name already exists in the same region
        existing_district = await db.district.find_first(where={
            "name": new_name,
            "regionId": region_id
        })
        
        if existing_district and existing_district.id != district_id:
            await message.answer("❌ Bu nom bilan tuman allaqachon mavjud. Boshqa nom kiriting:")
            return
        
        # Update district
        await db.district.update(
            where={"id": district_id},
            data={"name": new_name}
        )
        
        region = await db.region.find_unique(where={"id": region_id})
        
        await message.answer(
            f"✅ Tuman muvaffaqiyatli yangilandi:\n\n"
            f"📛 Eski nom: <b>{old_name}</b>\n"
            f"📛 Yangi nom: <b>{new_name}</b>\n"
            f"🏛️ Viloyat: <b>{region.name}</b>",
            parse_mode="HTML"
        )
        
        notification_text = (f"📢 Tuman yangilandi:\n\n"
                           f"🏘️ Eski nom: <b>{old_name}</b>\n"
                           f"🏘️ Yangi nom: <b>{new_name}</b>\n"
                           f"🏛️ Viloyat: <b>{region.name}</b>\n"
                           f"👤 Yangilagan admin: @{message.from_user.username or message.from_user.first_name}")
        await notify_admins(notification_text, message.from_user.id)
        
    except Exception as e:
        logging.error(f"Tuman nomini yangilashda xato: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")
    
    await state.finish()
    await message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())

# ==================== TUMAN O'CHIRISH ====================

@dp.callback_query_handler(lambda c: c.data.startswith("delete_district_"), state=DistrictManagementStates.district_detail)
async def start_delete_district(callback: types.CallbackQuery, state: FSMContext):
    """Tuman ni o'chirishni boshlash"""
    district_id = int(callback.data.split("_")[2])
    
    district = await db.district.find_unique(
        where={"id": district_id},
        include={
            "region": True,
            "ordersFrom": True,
            "ordersTo": True
        }
    )
    
    if not district:
        await callback.answer("❌ Tuman topilmadi")
        return
    
    total_orders = len(district.ordersFrom) + len(district.ordersTo)
    
    warning_text = ""
    if total_orders > 0:
        warning_text = f"⚠️ <b>DIQQAT!</b> Ushbu tumanga bog'liq {total_orders} ta buyurtma mavjud. Tuman ni o'chirish mumkin emas!\n\n"
        
        await callback.message.edit_text(
            f"❌ <b>Tuman ni o'chirib bo'lmaydi</b>\n\n"
            f"{warning_text}"
            f"Tuman nomi: <b>{district.name}</b>\n"
            f"Viloyat: <b>{district.region.name}</b>\n"
            f"Buyurtmalar soni: {total_orders} ta\n\n"
            f"Avval ushbu tumanga bog'liq buyurtmalarni boshqa tumanga ko'chiring yoki ularni o'chiring.",
            reply_markup=back_keyboard("back_to_district_detail"),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"🗑️ <b>Tuman ni o'chirish</b>\n\n"
        f"Tuman nomi: <b>{district.name}</b>\n"
        f"Viloyat: <b>{district.region.name}</b>\n\n"
        f"Rostan ham o'chirmoqchimisiz?",
        reply_markup=confirmation_keyboard(),
        parse_mode="HTML"
    )
    
    await DistrictManagementStates.confirm_delete_district.set()
    await state.update_data(
        deleting_district_id=district_id,
        district_name=district.name,
        region_name=district.region.name
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data in ["confirm_yes", "confirm_no"], state=DistrictManagementStates.confirm_delete_district)
async def confirm_district_deletion(callback: types.CallbackQuery, state: FSMContext):
    """Tuman ni o'chirishni tasdiqlash"""
    if callback.data == "confirm_yes":
        data = await state.get_data()
        district_id = data.get('deleting_district_id')
        district_name = data.get('district_name')
        region_name = data.get('region_name')
        
        try:
            # Avval tekshiramiz, hali ham buyurtmalar bormi
            district = await db.district.find_unique(
                where={"id": district_id},
                include={"ordersFrom": True, "ordersTo": True}
            )
            
            if not district:
                await callback.message.edit_text("❌ Tuman topilmadi")
                await callback.answer()
                return
                
            total_orders = len(district.ordersFrom) + len(district.ordersTo)
            if total_orders > 0:
                await callback.message.edit_text(
                    f"❌ Tuman ni o'chirib bo'lmaydi. Hali ham {total_orders} ta buyurtma mavjud.",
                    reply_markup=back_keyboard("back_to_district_detail")
                )
                await callback.answer()
                return
            
            # Delete district
            await db.district.delete(where={"id": district_id})
            
            await callback.message.edit_text(
                f"✅ Tuman muvaffaqiyatli o'chirildi:\n\n"
                f"🏘️ Tuman: <b>{district_name}</b>\n"
                f"🏛️ Viloyat: <b>{region_name}</b>",
                parse_mode="HTML"
            )
            
            notification_text = (f"📢 Tuman o'chirildi:\n\n"
                               f"🏘️ Tuman: <b>{district_name}</b>\n"
                               f"🏛️ Viloyat: <b>{region_name}</b>\n"
                               f"👤 O'chirgan admin: @{callback.from_user.username or callback.from_user.first_name}")
            await notify_admins(notification_text, callback.from_user.id)
            
        except Exception as e:
            logging.error(f"Tuman ni o'chirishda xato: {e}")
            await callback.message.edit_text(
                f"❌ Xatolik yuz berdi: Tuman ni o'chirish mumkin emas. "
                f"Ushbu tumanga bog'liq buyurtmalar mavjud.",
                reply_markup=back_keyboard("back_to_district_detail")
            )
    else:
        await callback.message.edit_text("❌ Tuman o'chirish bekor qilindi.")
    
    await state.finish()
    await callback.message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())
    await callback.answer()

# ==================== TUMAN QO'SHISH ====================

@dp.callback_query_handler(lambda c: c.data.startswith("add_district_"), state=RegionManagementStates.region_detail)
async def start_add_district(callback: types.CallbackQuery, state: FSMContext):
    """Tuman qo'shishni boshlash"""
    region_id = int(callback.data.split("_")[2])
    
    region = await db.region.find_unique(where={"id": region_id})
    if not region:
        await callback.answer("❌ Viloyat topilmadi")
        return
    
    await state.update_data(
        adding_district_region_id=region_id,
        adding_district_region_name=region.name
    )
    
    await callback.message.edit_text(
        f"➕ <b>Yangi tuman qo'shish</b>\n\n"
        f"🏛️ Viloyat: <b>{region.name}</b>\n\n"
        f"Tuman nomini kiriting:",
        reply_markup=back_keyboard(f"back_to_region_{region_id}"),
        parse_mode="HTML"
    )
    await DistrictManagementStates.waiting_for_new_district_name.set()
    await callback.answer()

@dp.message_handler(state=DistrictManagementStates.waiting_for_new_district_name)
async def process_new_district_name(message: types.Message, state: FSMContext):
    """Yangi tuman nomini qayta ishlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=admin_main_menu())
        return
    
    district_name = message.text.strip()
    
    if len(district_name) < 2:
        await message.answer("❌ Tuman nomi juda qisqa. Iltimos, qayta kiriting:")
        return
    
    data = await state.get_data()
    region_id = data.get('adding_district_region_id')
    region_name = data.get('adding_district_region_name')
    
    try:
        # Check if district already exists in this region
        existing_district = await db.district.find_first(where={
            "name": district_name,
            "regionId": region_id
        })
        
        if existing_district:
            await message.answer("❌ Bu tuman allaqachon mavjud. Boshqa nom kiriting:")
            return
    except Exception as e:
        logging.error(f"Tuman mavjudligini tekshirishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring:")
        return
    
    await state.update_data(district_name=district_name)
    
    await message.answer(
        f"🏛️ Viloyat: <b>{region_name}</b>\n"
        f"🏘️ Tuman: <b>{district_name}</b>\n\n"
        f"Qo'shishni tasdiqlaysizmi?",
        reply_markup=confirmation_keyboard(),
        parse_mode="HTML"
    )
    await DistrictManagementStates.confirm_add_district.set()

@dp.callback_query_handler(lambda c: c.data in ["confirm_yes", "confirm_no"], state=DistrictManagementStates.confirm_add_district)
async def confirm_district_addition(callback: types.CallbackQuery, state: FSMContext):
    """Tuman qo'shishni tasdiqlash"""
    if callback.data == "confirm_yes":
        data = await state.get_data()
        district_name = data.get('district_name')
        region_id = data.get('adding_district_region_id')
        region_name = data.get('adding_district_region_name')
        
        try:
            await db.district.create(data={
                "name": district_name,
                "regionId": region_id
            })
            
            await callback.message.edit_text(
                f"✅ Tuman muvaffaqiyatli qo'shildi:\n\n"
                f"🏛️ Viloyat: <b>{region_name}</b>\n"
                f"🏘️ Tuman: <b>{district_name}</b>",
                parse_mode="HTML"
            )
            
            notification_text = (f"📢 Yangi tuman qo'shildi:\n\n"
                               f"🏛️ Viloyat: <b>{region_name}</b>\n"
                               f"🏘️ Tuman: <b>{district_name}</b>\n"
                               f"👤 Qo'shgan admin: @{callback.from_user.username or callback.from_user.first_name}")
            await notify_admins(notification_text, callback.from_user.id)
            
        except Exception as e:
            logging.error(f"Tuman qo'shishda xato: {e}")
            await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    else:
        await callback.message.edit_text("❌ Tuman qo'shish bekor qilindi.")
    
    await state.finish()
    await callback.message.answer("🔙 Admin paneliga qaytdingiz", reply_markup=admin_main_menu())
    await callback.answer()

# ==================== ORQAGA QAYTISH HANDLERLARI ====================

@dp.callback_query_handler(lambda c: c.data == "back_to_region_menu", state="*")
async def back_to_region_menu(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatlar menyusiga qaytish"""
    await callback.message.edit_text(
        "🏛️ <b>Viloyatlar boshqaruvi</b>\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=region_main_keyboard(),
        parse_mode="HTML"
    )
    await RegionManagementStates.main_menu.set()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "back_to_regions", state="*")
async def back_to_regions_list(callback: types.CallbackQuery, state: FSMContext):
    """Viloyatlar ro'yxatiga qaytish"""
    try:
        regions = await db.region.find_many(include={"districts": True}, order={"name": "asc"})
        
        if not regions:
            await callback.message.edit_text(
                "❌ Hozircha hech qanday viloyat mavjud emas.",
                reply_markup=back_keyboard("back_to_region_menu")
            )
            await callback.answer()
            return
        
        total_regions = len(regions)
        await state.update_data(regions=regions, current_page=0)
        
        keyboard = regions_list_keyboard(regions)
        
        await callback.message.edit_text(
            f"📋 <b>Viloyatlar ro'yxati</b>\n\n"
            f"Jami: {total_regions} ta viloyat\n"
            f"⚠️ Belgisi - tuman biriktirilmagan viloyatlar\n\n"
            f"Quyidagi viloyatlardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await RegionManagementStates.region_list.set()
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Viloyatlar ro'yxatiga qaytishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query_handler(lambda c: c.data.startswith("back_to_region_") and not c.data.endswith('districts'), state="*")
async def back_to_region_from_districts(callback: types.CallbackQuery, state: FSMContext):
    """Viloyat tafsilotlariga qaytish (tumanlar ro'yxatidan)"""
    try:
        # Callback_data format: "back_to_region_123"
        parts = callback.data.split('_')
        if len(parts) >= 4:
            region_id = int(parts[3])
        else:
            await callback.answer("❌ Noto'g'ri format")
            return
        
        region = await db.region.find_unique(
            where={"id": region_id},
            include={
                "districts": True,
                "ordersFrom": True,
                "ordersTo": True
            }
        )
        
        if not region:
            await callback.answer("❌ Viloyat topilmadi")
            return
        
        total_districts = len(region.districts)
        total_orders_from = len(region.ordersFrom)
        total_orders_to = len(region.ordersTo)
        
        message_text = (
            f"🏛️ <b>Viloyat ma'lumotlari</b>\n\n"
            f"📛 Nomi: <b>{region.name}</b>\n"
            f"🏘️ Tumanlar soni: <b>{total_districts} ta</b>\n"
            f"📤 Chiqish buyurtmalari: <b>{total_orders_from} ta</b>\n"
            f"📥 Kirish buyurtmalari: <b>{total_orders_to} ta</b>\n"
            f"📅 Qo'shilgan sana: <b>{region.createdAt.strftime('%Y-%m-%d %H:%M')}</b>"
        )
        
        keyboard = region_actions_keyboard(region_id, total_districts > 0)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await RegionManagementStates.region_detail.set()
        await state.update_data(current_region_id=region_id, current_region_name=region.name)
        await callback.answer()
        
    except ValueError:
        logging.error(f"Noto'g'ri region ID: {callback.data}")
        await callback.answer("❌ Noto'g'ri format")
    except Exception as e:
        logging.error(f"Viloyat tafsilotlariga qaytishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query_handler(lambda c: c.data == "back_to_region_districts", state="*")
async def back_to_region_districts(callback: types.CallbackQuery, state: FSMContext):
    """Viloyat tumanlariga qaytish"""
    try:
        data = await state.get_data()
        region_id = data.get('current_region_id')
        
        if not region_id:
            # Agar region_id state da saqlanmagan bo'lsa, callback_data dan olamiz
            await callback.answer("❌ Viloyat ma'lumotlari topilmadi")
            return
        
        region = await db.region.find_unique(
            where={"id": region_id},
            include={"districts": True}
        )
        
        if not region:
            await callback.answer("❌ Viloyat topilmadi")
            return
        
        districts = region.districts
        total_districts = len(districts)
        
        if not districts:
            await callback.message.edit_text(
                f"🏘️ <b>{region.name} viloyati tumanlari</b>\n\n"
                f"❌ Hozircha hech qanday tuman mavjud emas.\n\n"
                f"➕ Yangi tuman qo'shish uchun 'Tuman qo'shish' tugmasini bosing.",
                reply_markup=back_keyboard(f"back_to_region_{region_id}")
            )
            await callback.answer()
            return
        
        await state.update_data(districts=districts, current_page=0)
        
        keyboard = districts_list_keyboard(districts, region_id)
        
        await callback.message.edit_text(
            f"🏘️ <b>{region.name} viloyati tumanlari</b>\n\n"
            f"Jami: {total_districts} ta tuman\n\n"
            f"Quyidagi tumanlardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await DistrictManagementStates.district_list.set()
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Viloyat tumanlariga qaytishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query_handler(lambda c: c.data == "back_to_district_detail", state="*")
async def back_to_district_detail(callback: types.CallbackQuery, state: FSMContext):
    """Tuman tafsilotlariga qaytish"""
    try:
        data = await state.get_data()
        district_id = data.get('current_district_id')
        
        if not district_id:
            await callback.answer("❌ Tuman ma'lumotlari topilmadi")
            return
        
        district = await db.district.find_unique(
            where={"id": district_id},
            include={
                "region": True,
                "ordersFrom": True,
                "ordersTo": True
            }
        )
        
        if not district:
            await callback.answer("❌ Tuman topilmadi")
            return
        
        total_orders_from = len(district.ordersFrom)
        total_orders_to = len(district.ordersTo)
        
        message_text = (
            f"🏘️ <b>Tuman ma'lumotlari</b>\n\n"
            f"📛 Nomi: <b>{district.name}</b>\n"
            f"🏛️ Viloyat: <b>{district.region.name}</b>\n"
            f"📤 Chiqish buyurtmalari: <b>{total_orders_from} ta</b>\n"
            f"📥 Kirish buyurtmalari: <b>{total_orders_to} ta</b>\n"
            f"📅 Qo'shilgan sana: <b>{district.createdAt.strftime('%Y-%m-%d %H:%M')}</b>"
        )
        
        keyboard = district_actions_keyboard(district_id)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await DistrictManagementStates.district_detail.set()
        await state.update_data(
            current_district_id=district_id,
            current_district_name=district.name,
            current_region_id=district.region.id
        )
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Tuman tafsilotlariga qaytishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query_handler(lambda c: c.data == "back_to_main", state="*")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish"""
    await state.finish()
    await callback.message.edit_text("🔙 Admin paneliga qaytdingiz")
    await callback.message.answer(
        "👨‍💻 Admin paneliga xush kelibsiz!\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=admin_main_menu()
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "back_to_region_detail", state="*")
async def back_to_region_detail_handler(callback: types.CallbackQuery, state: FSMContext):
    """Viloyat tafsilotlariga qaytish"""
    try:
        data = await state.get_data()
        region_id = data.get('current_region_id')
        
        if not region_id:
            await callback.answer("❌ Viloyat ma'lumotlari topilmadi")
            return
        
        region = await db.region.find_unique(
            where={"id": region_id},
            include={
                "districts": True,
                "ordersFrom": True,
                "ordersTo": True
            }
        )
        
        if not region:
            await callback.answer("❌ Viloyat topilmadi")
            return
        
        total_districts = len(region.districts)
        total_orders_from = len(region.ordersFrom)
        total_orders_to = len(region.ordersTo)
        
        message_text = (
            f"🏛️ <b>Viloyat ma'lumotlari</b>\n\n"
            f"📛 Nomi: <b>{region.name}</b>\n"
            f"🏘️ Tumanlar soni: <b>{total_districts} ta</b>\n"
            f"📤 Chiqish buyurtmalari: <b>{total_orders_from} ta</b>\n"
            f"📥 Kirish buyurtmalari: <b>{total_orders_to} ta</b>\n"
            f"📅 Qo'shilgan sana: <b>{region.createdAt.strftime('%Y-%m-%d %H:%M')}</b>"
        )
        
        keyboard = region_actions_keyboard(region_id, total_districts > 0)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await RegionManagementStates.region_detail.set()
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Viloyat tafsilotlariga qaytishda xato: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

# ==================== ADMIN KOMANDALARI ====================

@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    await message.answer(
        "👨‍💻 Admin paneliga xush kelibsiz!\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=admin_main_menu()
    )

@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state="*")
async def cancel_operation(message: types.Message, state: FSMContext):
    """Bekor qilish tugmasi"""
    current_state = await state.get_state()
    if current_state:
        await state.finish()
    
    await message.answer("❌ Amal bekor qilindi.", reply_markup=admin_main_menu())