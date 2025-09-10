from datetime import datetime
from typing import Any
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.keyboards import get_back_kb
from utils.publication_utils import *

router = Router()


def get_admin(callback: CallbackQuery) -> str:
    admin = callback.from_user
    return f'<a href="tg://user?id={admin.id}">@{admin.username}</a>'


@router.callback_query(F.data.endswith('accept'))
async def accept_publication(callback: CallbackQuery):
    is_editing = 'edit' in callback.data
    table, pub_id = callback.data.split('_')[:2]
    data = await select_publication(table, pub_id=pub_id)
    if is_editing:
        del data['status']
        table_name = data.pop('table_name')
        query = ', '.join([f"{key} = ?" for key in data.keys()])
        await db.execute_query(f'update {table_name} set status = ?, date = ?, {query} where id = ?', 'Принята',
                               datetime.now().timestamp(), *data.values(), pub_id)
        await db.execute_query('delete from edition where id = ? and table_name = ?', pub_id, table_name)
    else:
        await db.execute_query(f'update {table} set status = ?, date = ? where id = ?', 'Принята',
                               datetime.now().timestamp(), pub_id)
    message = callback.message
    accepted_args = bot_config.messages.get('accepted')
    accepted_args['text'] = accepted_args['text'].format(data['title'])
    await message.bot.send_message(chat_id=data['user_id'], **accepted_args)
    text = format_channel(data, f'Принято администратором {get_admin(callback)}')
    if message.photo:
        await message.edit_caption(caption=text, parse_mode='HTML')
        return
    await message.edit_text(text=text, parse_mode='HTML')


@router.callback_query(F.data.endswith('deny'))
async def deny_publication(callback: CallbackQuery, state: FSMContext):
    table, pub_id = callback.data.split('_')[:2]
    editing = 'edit' in callback.data
    data = await select_publication(table, pub_id=pub_id)
    kb = get_back_kb(f'{callback.data.replace('_deny', '')}_new_pub')
    message = await bot_config.handle_edit_message(callback.message,
                                                   {'text': 'Опишите причину отклонения:', 'reply_markup': kb})
    await state.update_data(message=message.message_id, table=table, editing=editing, **data)
    await state.set_state('deny_reason')


@router.message(StateFilter('deny_reason'))
async def set_deny_reason(message: Message, state: FSMContext):
    await state.update_data(deny_reason=message.text)
    data = await state.get_data()
    await message.delete()
    await message.bot.edit_message_text(chat_id=message.chat.id, message_id=data['message'],
                                        text=f'Причина: {message.text}\n\nВсё верно?',
                                        reply_markup=bot_config.keyboards.get('deny_confirm'))


async def edit_message(message: Message, data: dict[str, Any], text: str,
                       kb: InlineKeyboardMarkup | None = None) -> None:
    if data.get('media'):
        await message.edit_media(media=get_photo(data['id'], text), reply_markup=kb)
        return
    await message.edit_text(text=text, parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data == 'deny_send')
async def confirm_deny(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    reason = data['deny_reason']
    query = "update {0} set status = 'Отклонена', deny_reason = ?, date = ? where id = ?"
    date = datetime.now().timestamp()
    if data['editing']:
        await db.execute_query(query.format('edition') + " and table_name = ?", reason, date, data['id'], data['table'])
        edited_data = await db.execute_query('select * from edition where id = ? and table_name = ?',
                                             data['id'], data['table'])
        data = {**data, **edited_data[0]}
    else:
        await db.execute_query(query.format(data['table']), reason, date, data['id'])
    text = bot_config.messages.get('denied')['text'].format(data['title'], reason)
    await callback.bot.send_message(chat_id=data['user_id'], text=text, parse_mode='HTML',
                                    reply_markup=bot_config.keyboards.get('denied'))
    comment = f'Отклонено администратором {get_admin(callback)}. Причина: {reason}'
    result_text = format_channel(data, comment)
    await edit_message(callback.message, data, result_text)


@router.callback_query(F.data.endswith('new_pub'))
async def new_pub(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    data = await select_publication(table, pub_id=pub_id)
    header = 'Изменение публикации' if 'edit' in callback.data else 'Новая публикация'
    text, args = create_admin_notification(table, data['id'], data, header)
    await edit_message(callback.message, data, text, args['reply_markup'])


@router.callback_query(F.data == 'delete_message')
async def delete_message(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        await callback.message.answer_photo(**bot_config.messages.get('cmd_start'))
