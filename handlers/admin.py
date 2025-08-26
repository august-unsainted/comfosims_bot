from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config import ADMIN

router = Router()

@router.message(F.chat.id == ADMIN)
async def cmd_chat(message: Message):
    await message.answer('тест')
