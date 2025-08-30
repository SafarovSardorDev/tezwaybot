from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

def get_role_keyboard():
    """Rol tanlash uchun klaviatura"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Haydovchi"), KeyboardButton("Yo'lovchi"))
    return keyboard

def get_phone_keyboard():
    """Telefon raqamni jo'natish uchun klaviatura"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Telefon raqamni jo'natish", request_contact=True))
    return keyboard

def get_driver_keyboard():
    """Haydovchi uchun asosiy klaviatura"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton("Profilim"))
    # keyboard.add(KeyboardButton("Foydalanish qo'llanmasi"))
    return keyboard

def get_passenger_keyboard():
    """Yo'lovchi uchun asosiy klaviatura"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton("Yo'lga otlanish"))
    keyboard.add(KeyboardButton("Profilim"), KeyboardButton("Buyurtma tarixi"))
    # keyboard.add(KeyboardButton("Foydalanish qo'llanmasi"))
    return keyboard