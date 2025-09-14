from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from handlers.add_publication import bot_config, db
from utils.keyboards import get_content_types, get_back_kb, edit_content_kb, get_sort_kb, get_creators_filters
from utils.publication_utils import split


router = Router()


async def get_filters(data: dict, table: str, user: int) -> str | None:
    filters = data.get(f'{table}_filters')
    if not filters:
        query_res = await db.execute_query(f'select {table} from filters where user_id = ?', user)
        if query_res:
            filters = query_res[0][table]
    return filters


@router.callback_query(F.data.endswith('filters'))
async def receive_filters(callback: CallbackQuery, state: FSMContext):
    table = callback.data.split('_')[0]
    filters = await get_filters(await state.get_data(), table, callback.from_user.id)
    kb = None
    if table == 'creators':
        kb = get_creators_filters(filters) if filters else bot_config.keyboards.get('creators_filters')

    await bot_config.handle_message(callback, {'text': bot_config.texts.get('filters'), 'reply_markup': kb or get_back_kb('start')})


@router.callback_query(F.data.startswith('set_filters_content'))
async def update_filters(callback: CallbackQuery, state: FSMContext):
    kb = edit_content_kb(callback)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await state.update_data(creators_filters=', '.join(get_content_types(kb)))


@router.callback_query(F.data.contains('reset'))
async def reset_filters(callback: CallbackQuery, state: FSMContext):
    table, *_, data_type = split(callback)
    if data_type == 'filters':
        await state.update_data(**{f'{table}_sort': None})
    await state.update_data(**{f'{table}_{data_type}': None})
    sort_kb = await get_sort_kb(table, 0)
    if callback.message.reply_markup.model_dump() == sort_kb.model_dump():
        await callback.answer('Сортировка уже сброшена!')
        return
    try:
        kb = bot_config.keyboards.get('creators_filters') if data_type == 'filters' else sort_kb
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.endswith('sort'))
async def get_sort(callback: CallbackQuery):
    table = callback.data.split('_')[0]
    kb = await get_sort_kb(table, callback.from_user.id)
    await callback.message.edit_text(text=bot_config.texts.get('sort'), reply_markup=kb)


@router.callback_query(F.data.endswith('first'))
async def set_sort(callback: CallbackQuery, state: FSMContext):
    table = split(callback)[0]
    try:
        kb = edit_content_kb(callback, True)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await state.update_data({f'{table}_sort': 'desc' if 'new' in callback.data else ''})
    except TelegramBadRequest:
        await callback.answer('Этот тип сортировки уже выбран!')
