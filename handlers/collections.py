from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


from handlers.start import bot_config

router = Router()

class Channel(StatesGroup):
    name = State()
    link = State()
    tags = State()
    description = State()
    media = State()
    message = State()

@router.callback_query(F.data == 'start_form')
async def start_form(callback: CallbackQuery, state: FSMContext):
    media = InputMediaPhoto(media=bot_config.images.get('channel').media, caption=bot_config.jsons['messages'].get('start_form'),
                            **bot_config.default_args)
    await callback.message.edit_media(media=media)
    await state.update_data(message=callback.message.message_id)
    await state.set_state(Channel.name)


async def continue_form(message: Message, state: FSMContext, message_data: str):
    await message.delete()
    await state.update_data(**{message_data: message.text})
    data = await state.get_data()
    text = bot_config.jsons['messages'].get('channel')
    fields = [name.replace('Channel:', '') for name in Channel.__all_states_names__ if name != 'Channel:message']
    for field in fields:
        text = text.replace(field, data.get(field) or '[отсутствует]')

    await message.bot.edit_message_caption(chat_id=message.chat.id, message_id=data['message'],
                                           caption=text.format(bot_config.jsons['messages'].get(f'channel_{message_data}')),
                                           **bot_config.default_args)


@router.message(Channel.name)
async def get_channel_name(message: Message, state: FSMContext):
    await continue_form(message, state, 'name')
    await state.set_state(Channel.link)


@router.message(Channel.link)
async def get_channel_link(message: Message, state: FSMContext):
    await continue_form(message, state, 'link')
    await state.set_state(Channel.tags)
    # await db.broadcast.get_media(message, state, message.bot, '')


@router.message(Channel.description)
async def get_channel_description(message: Message, state: FSMContext):
    await continue_form(message, state, 'description')
    await state.set_state(Channel.media)
