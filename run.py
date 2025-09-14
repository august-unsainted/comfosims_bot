import asyncio
from aiogram import Bot, Dispatcher
from handlers import filters, admin, add_publication, view_publications, consider_publication, edit_publication

from config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()


async def main():
    dp.include_routers(filters.router, view_publications.router, edit_publication.router, add_publication.router, consider_publication.router, admin.router)
    add_publication.bot_config.include_routers(dp)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот выключен')
