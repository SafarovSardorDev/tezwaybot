from aiogram import executor
from loader import dp, db
import middlewares, filters, handlers
from utils.notify_admins import on_startup_notify
from utils.set_bot_commands import set_default_commands
from handlers.users.departure import initialize_departure_module


async def on_startup(dispatcher):
    """Bot ishga tushganda Prisma client’ni bog‘lash"""
    await initialize_departure_module()
    await set_default_commands(dispatcher)
    await db.connect()  # **Barcha joylar uchun bitta ulanish!**
    await on_startup_notify(dispatcher)

async def on_shutdown(dispatcher):
    """Bot o‘chirilganda Prisma client’ni uzish"""
    await db.disconnect()  # **Bot o‘chirilganda ulanish uziladi**

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)

