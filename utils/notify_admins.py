from data.config import OWNER_ID


async def on_startup_notify(dp):
    for owner in OWNER_ID:
        try:
            await dp.bot.send_message(owner, "Bot ishga tushdi")
        except Exception as e:
            print(f"[XATO] Admin ID: {owner} uchun xabar yuborilmadi. Sabab: {e}")

