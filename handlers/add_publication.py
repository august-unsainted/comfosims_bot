from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot_config import bot_config, db
from config import ADMIN
from utils.keyboards import edit_keyboard, add_back_btn, get_back_kb
from utils.publication_utils import *

router = Router()


class Channel(StatesGroup):
    channel_type = State()
    title = State()
    link = State()
    description = State()
    media = State()
    message = State()


states = ['title', 'link', 'description', 'media']
states_groups = [Channel.title, Channel.link, Channel.description, Channel.media]
# questions = ['type', 'genre', 'drama_level', 'text_level', 'preset']
questions = ['type']


def update_keyboards():
    for level_key in ['drama', 'text']:
        bot_config.keyboards[f'{level_key}_level'] = edit_keyboard(level_key, 'levels')
    for data in questions[1:]:
        add_back_btn(data, questions)
    for state in states:
        bot_config.keyboards[f'set_{state}'] = edit_keyboard(state, 'set_state')
        if state != 'media':
            cb = questions[-1] if state == 'title' else state + '_back_state'
            bot_config.keyboards[state] = get_back_kb(cb)
    bot_config.keyboards['title_creator'] = get_back_kb('content')
    bot_config.load_messages()


update_keyboards()
messages = bot_config.messages


@router.callback_query(F.data.in_(('type', 'content')))
async def add_publication(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(**messages.get(callback.data))
    channel_type = 'dynasty' if callback.data == 'type' else 'creator'
    await state.update_data(message=callback.message.message_id, channel_type=channel_type,
                            user_id=callback.from_user.id, user_name=callback.from_user.username)


@router.callback_query(F.data.startswith(tuple(questions)))
async def questions_handler(callback: CallbackQuery, state: FSMContext):
    key, value = callback.data.rsplit('_', 1)
    index = questions.index(key) + 1
    await state.update_data(**{key: int(value)})
    if index < len(questions):
        next_data = questions[index]
    else:
        next_data = 'title'
        await state.set_state(Channel.title)
    await callback.message.edit_text(**messages.get(next_data))


async def continue_form(message: Message, state: FSMContext, field_name: str = '', kb: InlineKeyboardMarkup = None):
    data = await state.get_data()
    if field_name == '':
        field_name = data['field']
    await state.update_data(**{field_name: message.html_text})
    args = {'chat_id': message.chat.id, 'message_id': data.get('message'), 'parse_mode': 'HTML'}
    header = messages.get(field_name)['text'].replace('Введите ', '').replace('ссылку', 'ссылка').capitalize()
    await message.delete()
    kb = kb or bot_config.keyboards.get(f'set_{field_name}')
    await message.bot.edit_message_text(text=f'<b>{header}:</b>\n{message.html_text}\n\nВсё верно?', reply_markup=kb,
                                        **args)


@router.message(StateFilter(Channel.title, Channel.link, Channel.description))
async def get_channel_info(message: Message, state: FSMContext):
    current_state = await state.get_state()
    field_name = current_state.split(':')[-1]
    await continue_form(message, state, field_name)


@router.message(Channel.media)
async def set_media(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    args = {'message_id': data['message'], 'chat_id': message.chat.id}
    if not message.photo:
        await message.bot.edit_message_text(parse_mode='HTML',
                                            text=messages.get('media')[
                                                     'text'] + '\n\n<blockquote>Ошибка! Нет изображения</blockquote>',
                                            **args)
        return
    photo_id = message.photo[-1].file_id
    await state.update_data(media=photo_id)
    publication = await prepare_message({'media': photo_id, **data})
    await message.bot.edit_message_media(**publication, **args)


@router.callback_query(F.data == 'skip_media')
async def skip_message(callback: CallbackQuery, state: FSMContext):
    await state.update_data(media=None)
    data = await state.get_data()
    await callback.message.edit_text(**(await prepare_message(data)))


@router.callback_query(F.data.endswith('back_state'))
async def get_previous_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    index = states.index(key) - 1
    previous_key = states[index] if 0 <= index < len(states) else questions[-1]
    await callback.message.edit_text(**messages.get(previous_key))
    if index >= 0:
        await state.set_state(Channel.title if index == 0 else states_groups[index])


@router.callback_query(F.data.endswith('update_state'))
async def update_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    index = states.index(key) + 1
    next_key = states[index]
    await callback.message.edit_text(**messages.get(next_key))
    await state.set_state(states_groups[index])


@router.callback_query(F.data.endswith('edit_state'))
async def edit_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    await callback.message.edit_text(**messages.get(key))
    await state.set_state(await state.get_state())


@router.callback_query(F.data == 'set_title')
async def set_title(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    message = await bot_config.handle_message(callback, messages.get('title'))
    await state.update_data(message=message.message_id)
    await state.set_state(Channel.title)


@router.callback_query(F.data == 'send')
async def send_publication(callback: CallbackQuery, state: FSMContext):
    await bot_config.handle_edit_message(callback.message, messages.get('send'))
    data = await state.get_data() or {'message':     callback.message.message_id, 'channel_type': 'dynasty',
                                      'user_id':     callback.from_user.id, 'user_name': callback.from_user.username,
                                      'type':        1,
                                      'title':       'Династия', 'link': 'https://t.me/comfothesimsbot',
                                      'description': 'Род Морено начался с <b>Софии</b> — амбициозной художницы, приехавшей в город без денег и связей. Её упорство позволило построить первый дом, а картины стали приносить стабильный доход. Позже к ней присоединился Даниэль, музыкант со свободным характером. Их союз положил начало династии: дети унаследовали талант к искусству и <u>желание добиться большего</u>.',
                                      'media':       'AgACAgIAAxkBAAIDrmi5nEg-fjxfdNqZ8ATmMy1aB72JAAKPATIbftDRSVuxhA6AvgHQAQADAgADeQADNgQ'}
    await state.clear()
    bot = callback.message.bot
    media = data.pop('media')
    del data['message'], data['channel_type']
    data['media'] = int(media is not None)
    fields = ', '.join(list(data.keys()))
    info = ', '.join(['?'] * len(data.values()))
    pub_id = await db.execute_query(f"INSERT INTO dynasties ({fields}) VALUES ({info})", *data.values())
    text, args = create_admin_notification(pub_id, data)
    args['chat_id'] = ADMIN
    if media:
        await bot.send_photo(caption=text, photo=media, **args)
        photo_file = await bot.get_file(media)
        await bot.download_file(photo_file.file_path, get_photo(pub_id).media.path)
    else:
        await bot.send_message(text=text, **args)
