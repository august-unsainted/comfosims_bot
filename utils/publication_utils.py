from pathlib import Path
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto, CallbackQuery, FSInputFile

from handlers.add_publication import db, bot_config, edit_keyboard


async def select_publication(table: str, callback: CallbackQuery, pub_id: str = None) -> dict[str, str]:
    pub_id = pub_id or callback.data.split('_')[0]
    data = await db.execute_query(f'select * from {table} where id = ?', pub_id)
    return dict(data[0])


def get_photo(pub_id: int | str, text: str = '') -> InputMediaPhoto:
    input_file = FSInputFile(Path().cwd() / f'data/images/{pub_id}.jpg')
    return InputMediaPhoto(media=input_file, caption=text, parse_mode='HTML')


def format_channel(data: dict[str, str], comment: str = '') -> str:
    text = bot_config.jsons['messages'].get('channel').format(data['title'], data['link'], data['description'])
    return text + '\n\n' + comment


async def prepare_message(data: dict[str, str]) -> dict[str, str | InlineKeyboardMarkup]:
    text = format_channel(data)
    kb = bot_config.keyboards.get('check_publication')
    if data.get('media'):
        media = InputMediaPhoto(media=data.get('media'), caption=text, **bot_config.default_args)
        return {"media": media, "reply_markup": kb}
    return {"text": text, "reply_markup": kb, **bot_config.default_args}


def create_admin_notification(pub_id: int | str, data: dict[str, str]) -> tuple[str, dict]:
    channel = format_channel(data, f'Автор: @{data['user_name']}')
    text = f'<b>Новая династия</b>\n\n{channel}'
    kb = edit_keyboard(pub_id, 'new_publication')
    return text, {'reply_markup': kb, 'parse_mode': 'HTML'}
