import asyncio
from aiogram import Bot, Dispatcher
from handlers import admin, add_publication

from config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()


async def main():
    dp.include_routers(admin.router, add_publication.router)
    add_publication.bot_config.include_routers(dp)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот выключен')
