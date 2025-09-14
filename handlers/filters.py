from typing import Any, Coroutine

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from handlers.add_publication import bot_config, db
from utils.keyboards import get_content_types, get_back_kb, edit_content_kb, get_creators_filters, \
    edit_keyboard
from utils.publication_utils import split

router = Router()


async def get_filters(data: dict, table: str, user: int, data_type: str = 'filters') -> str | None:
    filters = data.get(f'{table}_{data_type}')
    is_filters = data_type == 'filters'
    col = table if is_filters else table + '_sort'
    if filters is None:
        query_res = await db.execute_query(f'select {col} from filters where user_id = ?', user)
        if query_res:
            filters = query_res[0][col]
    if filters is None and not is_filters:
        filters = 'desc'
    return filters


async def save_filters(data: dict, table: str, user: id, state: FSMContext) -> tuple[str | None, str | None]:
    filters = data.get(f'{table}_filters')
    sort = await get_filters(data, table, user, 'sort')
    if filters:
        sort_col = table + '_sort'
        await db.execute_query(
            f'''
                INSERT INTO filters (user_id, {table}, {sort_col})
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                {table} = excluded.{table},
                {sort_col} = excluded.{sort_col};
            ''', user, filters, sort)
        await state.update_data(**{f'{table}_filters': None})
    else:
        filters = await get_filters(data, table, user)
    return filters, sort


async def get_sort_kb(table: str, user: int, state: FSMContext) -> InlineKeyboardMarkup:
    kb = edit_keyboard(table, 'sort')
    data = await state.get_data()
    sort = await get_filters(data, table, user, 'sort')
    index = int(not sort)
    selected_option = kb.inline_keyboard[index][0]
    selected_option.text = '✅ ' + selected_option.text
    return kb


@router.callback_query(F.data.contains('reset'))
async def reset_filters(callback: CallbackQuery, state: FSMContext):
    table, *_, data_type = split(callback)
    is_filters = data_type == 'filters'
    if is_filters:
        await state.update_data(**{f'{table}_sort': 'desc'})
    await state.update_data(**{f'{table}_{data_type}': '1, 2, 3, 4'})
    kb = bot_config.keyboards.get('creators_filters') if is_filters else await get_sort_kb(table, 0, state)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest:
        answer_text = 'Фильтры успешно сброшены!' if is_filters else 'Сортировка уже сброшена!'
        await callback.answer(answer_text)


@router.callback_query(F.data.endswith('filters'))
async def receive_filters(callback: CallbackQuery, state: FSMContext):
    table = callback.data.split('_')[0]
    filters = await get_filters(await state.get_data(), table, callback.from_user.id)
    kb = None
    if table == 'creators':
        kb = get_creators_filters(filters) if filters else bot_config.keyboards.get('creators_filters')

    await bot_config.handle_message(callback, {'text':         bot_config.texts.get('filters'),
                                               'reply_markup': kb or get_back_kb('start')})


@router.callback_query(F.data.startswith('set_filters_content'))
async def update_filters(callback: CallbackQuery, state: FSMContext):
    kb = edit_content_kb(callback)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await state.update_data(creators_filters=', '.join(get_content_types(kb)))


@router.callback_query(F.data.endswith('sort'))
async def get_sort(callback: CallbackQuery, state: FSMContext):
    table = callback.data.split('_')[0]
    user = callback.from_user.id
    # await save_filters({}, table, user, state)
    kb = await get_sort_kb(table, user, state)
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
