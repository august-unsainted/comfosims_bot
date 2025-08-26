from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


from handlers.start import bot_config

router = Router()

class Channel(StatesGroup):
    name = State()
    tags = State()
    description = State()
    media = State()
    message = State()

@router.callback_query(F.data == 'start_form')
async def start_form(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('Введите название канала')
    await state.update_data(message=callback.message.message_id)
    await state.set_state(Channel.name)


async def continue_form(message: Message, state: FSMContext, message_data: str):
    data = await state.get_data()
    await message.bot.edit_message_text(chat_id=message.chat.id, message_id=data['message'],
                                        text=bot_config.jsons['messages'].get('channel_' + message_data).format(message.text))
    await message.delete()
    await state.update_data(**{message_data: message.text})


@router.message(Channel.name)
async def get_channel_name(message: Message, state: FSMContext):
    await continue_form(message, state, 'name')
    await state.set_state(Channel.tags)


@router.message(Channel.tags)
async def get_channel_name(message: Message, state: FSMContext):
    await continue_form(message, state, 'tags')
    await state.set_state(Channel.description)
    # await db.broadcast.get_media(message, state, message.bot, '')
