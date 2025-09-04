import sqlite3
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, \
    FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.text_decorations import html_decoration
from bot_constructor.bot_config import BotConfig
from copy import deepcopy

from config import ADMIN

bot_config = BotConfig(default_answer='эщкере')
db = bot_config.db
# questions = ['type', 'genre', 'drama_level', 'text_level', 'preset']
questions = ['type']
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


def edit_keyboard(key: str, template_kb: str):
    kb = deepcopy(bot_config.keyboards.get(template_kb).inline_keyboard)
    for i in range(len(kb)):
        for j in range(len(kb[i])):
            btn_data = kb[i][j].callback_data
            kb[i][j].callback_data = f'{key}_{btn_data}'
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_back(callback: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text='Назад ⬅️', callback_data=callback)]


def add_back_btn(key: str) -> None:
    kb = bot_config.keyboards.get(key).inline_keyboard
    index = questions.index(key)
    kb.append(get_back(questions[index - 1]))


bot_config.keyboards['drama_level'] = edit_keyboard('drama', 'levels')
bot_config.keyboards['text_level'] = edit_keyboard('text', 'levels')
for data in questions[1:]:
    add_back_btn(data)

for state in states:
    bot_config.keyboards[f'set_{state}'] = edit_keyboard(state, 'set_state')
    if state != 'media':
        cb = questions[-1] if state == 'title' else state + '_back'
        bot_config.keyboards[state] = InlineKeyboardMarkup(inline_keyboard=[get_back(cb)])

bot_config.keyboards['title_creator'] = InlineKeyboardMarkup(inline_keyboard=[get_back('content')])
bot_config.load_messages()


@router.callback_query(F.data.in_(('type', 'content')))
async def add_publication(callback: CallbackQuery, state: FSMContext):
    message = callback.message
    await message.edit_text(**bot_config.messages.get(callback.data))
    channel_type = 'dynasty' if callback.data == 'type' else 'creator'
    await state.update_data(message=message.message_id, channel_type=channel_type, user_id=callback.from_user.id,
                            user_name=callback.from_user.username)


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
    await callback.message.edit_text(**bot_config.messages.get(next_data))


async def continue_form(message: Message, state: FSMContext, message_data: str):
    await state.update_data(**{message_data: message.html_text})
    data = await state.get_data()
    args = {'chat_id': message.chat.id, 'message_id': data['message'], **bot_config.default_args}
    header = bot_config.messages.get(message_data)['text'].replace('Введите ', '').replace('ссылку',
                                                                                           'ссылка').capitalize()
    await message.bot.edit_message_text(**args, text=f'<b>{header}:</b>\n{message.html_text}\n\nВсё верно?',
                                        reply_markup=bot_config.keyboards.get(f'set_{message_data}'))
    await message.delete()


@router.message(StateFilter(Channel.title, Channel.link, Channel.description))
async def get_channel_info(message: Message, state: FSMContext):
    current_state = await state.get_state()
    field_name = current_state.split(':')[-1]
    await continue_form(message, state, field_name)


def get_channel(data: dict[str, str]) -> str:
    return bot_config.jsons['messages'].get('channel').format(data['title'], data['link'], data['description'])


async def get_publication(data: dict[str, str]) -> dict[str, str | InlineKeyboardMarkup]:
    text = get_channel(data)
    kb = bot_config.keyboards.get('check_publication')
    if data.get('media'):
        media = InputMediaPhoto(media=data.get('media'), caption=text, **bot_config.default_args)
        return {"media": media, "reply_markup": kb}
    return {"text": text, "reply_markup": kb, **bot_config.default_args}


@router.message(Channel.media)
async def set_media(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    args = {'message_id': data['message'], 'chat_id': message.chat.id}
    if not message.photo:
        await message.bot.edit_message_text(
            text=bot_config.messages.get('media')['text'] + '\n\n<blockquote>Ошибка! Нет изображения</blockquote>',
            **args, **bot_config.default_args)
        return
    photo_id = message.photo[-1].file_id
    await state.update_data(media=photo_id)
    publication = await get_publication({'media': photo_id, **data})
    await message.bot.edit_message_media(**publication, **args)


@router.callback_query(F.data == 'skip_media')
async def skip_message(callback: CallbackQuery, state: FSMContext):
    await state.update_data(media=None)
    data = await state.get_data()
    await callback.message.edit_text(**(await get_publication(data)))


@router.callback_query(F.data.endswith('back'))
async def get_previous_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    index = states.index(key) - 1
    previous_key = states[index] if 0 <= index < len(states) else questions[-1]
    await callback.message.edit_text(**bot_config.messages.get(previous_key))
    if index >= 0:
        await state.set_state(Channel.title if index == 0 else states_groups[index])


@router.callback_query(F.data.endswith('update'))
async def update_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    index = states.index(key) + 1
    next_key = states[index]
    await callback.message.edit_text(**bot_config.messages.get(next_key))
    await state.set_state(states_groups[index])


@router.callback_query(F.data.endswith('edit'))
async def edit_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    await callback.message.edit_text(**bot_config.messages.get(key))
    await state.set_state(await state.get_state())


@router.callback_query(F.data == 'set_title')
async def set_title(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Channel.title)
    await callback.message.edit_text(**bot_config.messages.get('title'))


def get_new_dynasty(pub_id: int | str, data: dict[str, str]) -> tuple[str, dict]:
    text = f'<b>Новая династия</b>\n\n{get_channel(data)}\n\nАвтор: @{data['user_name']}'
    kb = edit_keyboard(pub_id, 'new_publication')
    return text, {'chat_id': ADMIN, 'reply_markup': kb, 'parse_mode': 'HTML'}


@router.callback_query(F.data == 'send')
async def send_publication(callback: CallbackQuery, state: FSMContext):
    await bot_config.handle_edit_message(callback.message, bot_config.messages.get('send'))
    data = await state.get_data() or {'message': callback.message.message_id, 'channel_type': 'dynasty', 'user_id': callback.from_user.id, 'user_name': callback.from_user.username, 'type': 1,
            'title': 'Династия', 'link': 'https://t.me/comfothesimsbot', 'description': 'Род Морено начался с <b>Софии</b> — амбициозной художницы, приехавшей в город без денег и связей. Её упорство позволило построить первый дом, а картины стали приносить стабильный доход. Позже к ней присоединился Даниэль, музыкант со свободным характером. Их союз положил начало династии: дети унаследовали талант к искусству и <u>желание добиться большего</u>.', 'media': 'AgACAgIAAxkBAAIDrmi5nEg-fjxfdNqZ8ATmMy1aB72JAAKPATIbftDRSVuxhA6AvgHQAQADAgADeQADNgQ'}
    await state.clear()
    bot = callback.message.bot
    media = data.get('media')
    del data['message'], data['channel_type']
    data['media'] = 1 if data.get('media') else 0
    fields = ', '.join(list(data.keys()))
    info = ', '.join([str(value) if key in questions else f"'{value}'" for key, value in data.items()])
    pub_id = await db.execute_query(f"INSERT INTO dynasties ({fields}) VALUES ({info})")
    # pub_id = 6
    text, args = get_new_dynasty(pub_id, data)
    if not media:
        await bot.send_message(text=text, **args)
        return
    await bot.send_photo(photo=media, caption=text, **args)
    photo_file = await bot.get_file(media)
    photo_path = Path().cwd() / 'data/images' / f'{pub_id}.jpg'
    await bot.download_file(photo_file.file_path, photo_path)


@router.callback_query(F.data.endswith('accept'))
async def accept_publication(callback: CallbackQuery):
    pub_id = callback.data.split('_')[0]
    await db.execute_query('update dynasties set status = ? where id = ?', 'Принята', int(pub_id))
    data = await db.execute_query('select * from dynasties where id = ?', pub_id)
    message = callback.message
    accept_alert = f'\n\nПринято администратором {callback.from_user.first_name}'
    accepted_args = bot_config.messages.get('accepted')
    accepted_args['text'] = accepted_args['text'].format(data['title'])
    await message.bot.send_message(chat_id=data['user_id'], **accepted_args)
    text = get_channel(data) + accept_alert
    if message.photo:
        await message.edit_caption(caption=text, parse_mode='HTML')
        return
    await message.edit_text(text=text, parse_mode='HTML')


@router.callback_query(F.data.endswith('deny'))
async def deny_publication(callback: CallbackQuery, state: FSMContext):
    pub_id = callback.data.split('_')[0] if callback.data != 'deny' else (await state.get_data()).get('id')
    data = await db.execute_query('select * from dynasties where id = ?', int(pub_id))
    # pub = await get_publication(data)
    message = callback.message
    admin = callback.from_user.first_name
    deny_text = f'Вы ({admin}) отклонили «{data['title']}» от @{data['user_name']}.\n\nОпишите причину'
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Назад', callback_data=f'{pub_id}_new_pub')]])
    res = await bot_config.handle_edit_message(message, {'text': deny_text, 'reply_markup': kb})
    await state.update_data(deny_text=deny_text, message=res.message_id, **data)
    await state.set_state('deny_reason')


@router.message(StateFilter('deny_reason'))
async def set_deny_reason(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(deny_reason=message.text)
    data = await state.get_data()
    text = data['deny_text'].replace('Опишите причину', f'Причина: {message.text}')
    await message.bot.edit_message_text(chat_id=message.chat.id, message_id=data['message'], text=text,
                                        reply_markup=bot_config.keyboards.get('deny_confirm'))


@router.callback_query(F.data == 'deny_send')
async def confirm_deny(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.execute_query("update dynasties set status = 'Отклонена', deny_reason = ? where id = ?", data['deny_reason'],
                           data['id'])
    admin = callback.from_user.first_name
    text = bot_config.messages.get('denied')['text'].format(data['title'], data['deny_reason'])
    await callback.bot.send_message(data['user_id'], text, parse_mode='HTML')
    result_text = get_channel(data) + f'\n\nОтклонено администратором {admin}. Причина: {data['deny_reason']}'
    if data.get('media'):
        media = FSInputFile(Path().cwd() / f'data/images/{data['id']}.jpg')
        await callback.message.edit_media(media=InputMediaPhoto(media=media, caption=result_text, parse_mode='HTML'))
        return
    await callback.message.edit_text(text=result_text, parse_mode='HTML')


@router.callback_query(F.data.endswith('new_pub'))
async def new_pub(callback: CallbackQuery):
    pub_id = callback.data.split('_')[0]
    data = await db.execute_query('select * from dynasties where id = ?', pub_id)
    text, args = get_new_dynasty(pub_id, data)
    del args['chat_id']
    if data.get('media'):
        photo_path = Path().cwd() / f'data/images/{data['media']}.jpg'
        photo = InputMediaPhoto(media=FSInputFile(photo_path), caption=text, parse_mode='HTML')
        await callback.message.edit_media(media=photo, reply_markup=args['reply_markup'])
        return
    await callback.message.edit_text(text, **args)


@router.callback_query(F.data == 'delete_message')
async def delete_message(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
