from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from bot_constructor.bot_config import BotConfig

router = Router()
bot_config = BotConfig(default_answer='эщкере')
db = bot_config.db


@router.message(CommandStart())
async def cmd_start(message: Message):
    # await message.answer(str(message.chat.id))
    await message.answer_photo(**bot_config.messages.get('cmd_start'))
    await db.add_user(message.from_user.id)
