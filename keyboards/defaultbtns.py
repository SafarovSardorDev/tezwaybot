from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Klaviaturalar
def get_role_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Haydovchi"), KeyboardButton("Yo'lovchi"))
    return keyboard

def get_phone_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(text="Telefon raqamni yuborish", request_contact=True))
    return keyboard

def get_passenger_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["Yo'lga otlanish", "Profilim", "Buyurtma tarixi", "Foydalanish qo'llanmasi"]
    keyboard.add(*[KeyboardButton(text) for text in buttons])
    return keyboard

def get_driver_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["Profilim", "Foydalanish qo'llanmasi"]
    keyboard.add(*[KeyboardButton(text) for text in buttons])
    return keyboard