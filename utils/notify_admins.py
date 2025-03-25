import logging

from aiogram import Dispatcher

from data.config import OWNER_ID


async def on_startup_notify(dp: Dispatcher):
    for owner in OWNER_ID:
        try:
            await dp.bot.send_message(owner, "Bot ishga tushdi")

        except Exception as err:
            logging.exception(err)
