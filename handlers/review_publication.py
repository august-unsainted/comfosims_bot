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
    data = await select_publication('dynasties', callback)
    await db.execute_query('update dynasties set status = ? where id = ?', 'Принята', data['id'])
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
    data = await select_publication('dynasties', callback)
    kb = get_back_kb(f'{data['id']}_new_pub')
    message = await bot_config.handle_edit_message(callback.message,
                                                   {'text': 'Опишите причину отклонения:', 'reply_markup': kb})
    await state.update_data(message=message.message_id, **data)
    await state.set_state('deny_reason')


@router.message(StateFilter('deny_reason'))
async def set_deny_reason(message: Message, state: FSMContext):
    await state.update_data(deny_reason=message.text)
    data = await state.get_data()
    await message.delete()
    await message.bot.edit_message_text(chat_id=message.chat.id, message_id=data['message'],
                                        text=f'Причина: {message.text}\n\nВсё верно?',
                                        reply_markup=bot_config.keyboards.get('deny_confirm'))


async def edit_message(message: Message, data: dict[str, Any], text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    if data.get('media'):
        await message.edit_media(media=get_photo(data['id'], text), reply_markup=kb)
        return
    await message.edit_text(text=text, parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data == 'deny_send')
async def confirm_deny(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    reason = data['deny_reason']
    await db.execute_query("update dynasties set status = 'Отклонена', deny_reason = ? where id = ?",
                           reason, data['id'])
    text = bot_config.messages.get('denied')['text'].format(data['title'], reason)
    await callback.bot.send_message(chat_id=data['user_id'], text=text, parse_mode='HTML',
                                    reply_markup=bot_config.keyboards.get('denied'))
    comment = f'Отклонено администратором {get_admin(callback)}. Причина: {reason}'
    result_text = format_channel(data, comment)
    await edit_message(callback.message, data, result_text)


@router.callback_query(F.data.endswith('new_pub'))
async def new_pub(callback: CallbackQuery):
    data = await select_publication('dynasties', callback)
    text, args = create_admin_notification(data['id'], data)
    await edit_message(callback.message, data, text, args['reply_markup'])


@router.callback_query(F.data == 'delete_message')
async def delete_message(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        await callback.message.answer_photo(**bot_config.messages.get('cmd_start'))
