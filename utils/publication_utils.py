from pathlib import Path

import validators
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto, CallbackQuery, FSInputFile, Message

from config import ADMIN
from bot_config import db, config


async def select_publication(table: str, callback: CallbackQuery = None, pub_id: str = None) -> dict[str, str]:
    pub_id = pub_id or callback.data.split('_')[0]
    data = await db.execute_query(f'select * from {table} where id = ?', pub_id)
    return dict(data[0])


def get_photo(pub_id: int | str, text: str = '') -> InputMediaPhoto:
    input_file = FSInputFile(Path().cwd() / f'data/images/{pub_id}.jpg')
    return InputMediaPhoto(media=input_file, caption=text, parse_mode='HTML')


def format_channel(data: dict[str, str], comment: str = '') -> str:
    link = get_link(data['link'])
    text = config.jsons['messages'].get('channel').format(data['title'], link, data['description'])
    return text + '\n\n' + comment


async def prepare_message(data: dict[str, str]) -> dict[str, str | InlineKeyboardMarkup]:
    text = format_channel(data)
    kb = config.keyboards.get('check_publication')
    if data.get('media'):
        media = InputMediaPhoto(media=data.get('media'), caption=text, **config.default_args)
        return {"media": media, "reply_markup": kb}
    return {"text": text, "reply_markup": kb, **config.default_args}


def create_admin_notification(table: str, pub_id: int | str, data: dict[str, str], header: str) -> tuple[str, dict]:
    channel = format_channel(data, f'Автор: @{data['user_name']}')
    channel_type = 'династия' if table == 'dynasties' else 'креатор'
    text = f'<b>{header} ({channel_type})</b>\n\n{channel}'
    if header == 'Изменение публикации':
        pub_id = f'{pub_id}_edit'
    kb = config.edit_keyboard(f"{table}_{pub_id}", 'new_publication')
    return text, {'reply_markup': kb, 'parse_mode': 'HTML'}


def prepare_admin_message(table: str, pub_id: str | int, data: dict[str, any], header: str, bot: Bot):
    text, args = create_admin_notification(table, pub_id, data, header)
    args['chat_id'] = ADMIN
    if data.get('media'):
        return bot.send_photo, {'caption': text, 'photo': get_photo(pub_id, '').media, **args}
        # await bot.send_photo(caption=text, photo=get_photo(pub_id, '').media, **args)
    return bot.send_message, {'text': text, **args}


async def continue_form(message: Message, state: FSMContext, field_name: str = '', kb: InlineKeyboardMarkup = None):
    data = await state.get_data()
    if field_name == '':
        field_name = data['field']
    await state.update_data(**{field_name: message.html_text})
    args = {'chat_id': message.chat.id, 'message_id': data.get('message'), 'parse_mode': 'HTML'}
    header = config.texts.get(field_name).replace('Введите ', '').replace('ссылку', 'ссылка').capitalize()
    await message.delete()
    kb = kb or config.keyboards.get(f'set_{field_name}')
    if data.get('channel_type') == 'creators':
        kb.inline_keyboard[-1][0].callback_data = 'content'
    text = f'<b>{header}:</b>\n{message.html_text}\n\nВсё верно?'
    await message.bot.edit_message_text(text=text, reply_markup=kb, **args)


def split(callback: CallbackQuery) -> list[str]:
    return callback.data.split('_')


def get_link(link: str) -> str:
    if not validators.url(link):
        if link.startswith('@'):
            link = link.replace('@', 'https://t.me/', 1)
        else:
            link = 'https://t.me/comfosims'
    return link
