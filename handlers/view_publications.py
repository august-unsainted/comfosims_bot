import sqlite3

import validators
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

from bot_config import entries_on_page
from config import ADMIN
from handlers.add_publication import bot_config, db
from utils.keyboards import get_btn, edit_keyboard, get_pagination_kb, get_content_types, get_back_kb, \
    edit_content_kb, get_sort_kb
from utils.publication_utils import select_publication, format_channel, get_photo, split

router = Router()


async def get_page(user_id: int, page: int) -> InlineKeyboardMarkup:
    query_template = f"select id, title, date, 'table' as type from table where user_id = ?"
    queries = []
    for table in ['creators', 'dynasties']:
        queries.append(query_template.replace('table', table))
    query = f'''select el.id as id, coalesce(edit.title, el.title) as title, coalesce(edit.date, el.date) as date,
        el.type as type
        from ({queries[0]} union {queries[1]})
        el left join edition edit on el.id = edit.id and el.type = edit.table_name
        order by date desc
        '''
    publications = await db.execute_query(query, user_id, user_id)
    kb = []
    i = page - 1
    start = i * entries_on_page
    end = start + entries_on_page
    for pub in publications[start:end]:
        btn = InlineKeyboardButton(text=pub['title'], callback_data=f'{pub['type']}_{pub['id']}_publication')
        kb.append([btn])
    kb.append(get_pagination_kb('publications', page, len(publications)))
    kb.extend(bot_config.keyboards.get('publications').inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_creators_filters(selected: str = None):
    kb_markup = edit_keyboard('set_filters', 'content')
    kb = kb_markup.inline_keyboard
    del kb[-1]
    has_filters = bool(selected)
    if has_filters:
        selected = selected.split(', ')
    for i in range(len(kb)):
        for j in range(len(kb[i])):
            if (has_filters and kb[i][j].callback_data.endswith(tuple(selected))) or not has_filters:
                kb[i][j].text = '✅ ' + kb[i][j].text
    kb.insert(-1, [get_btn('Сортировка', f'creators_sort')])
    kb[-1] = [get_btn('Назад', 'creators'), get_btn('Сбросить всё', 'creators_reset_filters')]
    return kb_markup


creators_filters_kb = get_creators_filters()


@router.callback_query(F.data.endswith('publications'))
async def view_publications(callback: CallbackQuery):
    if '_' in callback.data and not callback.data.startswith('dynasties'):
        page = callback.data.split('_')[0]
    else:
        page = 1
    kb = await get_page(callback.from_user.id, int(page))
    await bot_config.handle_edit_message(callback.message, {'text':         bot_config.messages.get('publications')[
                                                                                'text'],
                                                            'reply_markup': kb})


@router.callback_query(F.data == 'null')
async def none_data(callback: CallbackQuery):
    await callback.answer('Значений больше нет 😢')


@router.callback_query(F.data.endswith('publication'))
async def get_publication(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    pub = await select_publication(table, callback, pub_id)
    edited_pub = await db.execute_query('select * from edition where table_name = ? and id = ?', table, pub_id)
    if edited_pub:
        pub = {**pub, **edited_pub[0]}
    comment = f'Статус: {pub['status'].lower()}.'
    if pub.get('deny_reason'):
        comment += f'\nПричина: {pub['deny_reason']}.'
    kb = edit_keyboard(f'{table}_{pub_id}', 'my_publication')

    if pub.get('media'):
        await callback.message.edit_media(media=get_photo(pub_id, format_channel(pub, comment)), reply_markup=kb)
    else:
        await callback.message.edit_text(format_channel(pub, comment), parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.contains('reset'))
async def reset_filters(callback: CallbackQuery, state: FSMContext):
    table, *_, data_type = split(callback)
    if data_type == 'filters':
        await state.update_data(**{f'{table}_sort': None})
    await state.update_data(**{f'{table}_{data_type}': None})
    try:
        await callback.message.edit_reply_markup(reply_markup=creators_filters_kb if data_type == 'filters' else get_sort_kb(table))
    except TelegramBadRequest:
        if callback.message.reply_markup == get_sort_kb(table):
            await callback.answer('Сортировка уже сброшена!')


@router.callback_query(F.data.endswith(('dynasties', 'creators')))
async def view_dynasties(callback: CallbackQuery, state: FSMContext):
    splited = callback.data.split('_')
    table = splited[-1]
    data = await state.get_data()
    filters = data.get(f'{table}_filters')
    if filters:
        filters = ', '.join(filters)
        sort = data.get(f'{table}_sort') or ''
        await db.execute_query(f'''
            INSERT INTO filters (user_id, {table}, {table}_sort)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            {table} = excluded.{table},
            {table}_sort = excluded.{table}_sort;
        ''', callback.from_user.id, filters, sort)
        data_dict = {f'{table}_filters': None}
        if table == 'creators':
            data_dict['creators'] = await db.execute_query(f'''
            SELECT DISTINCT c.*
            FROM creators c JOIN creators_contents cc
            ON c.id = cc.creator
            WHERE cc.content IN ({filters})
            ORDER BY date {sort}
            ''')
        await state.update_data(**data_dict)

    entries = data.get(table)
    if not entries:
        entries = await db.execute_query(f'select * from {table} order by date desc')
        await state.update_data(**{table: entries})
    page = int(splited[0]) if '_' in callback.data else 1
    curr_dynasty = dict(entries[page - 1])

    link = curr_dynasty['link']
    if not validators.url(link):
        if link.startswith('@'):
            link = link.replace('@', 'https://t.me/', 1)
        else:
            link = 'https://t.me/comfosims'
    kb = [[InlineKeyboardButton(text='Подписаться', url=link)]]
    if callback.message.chat.id == ADMIN:
        kb.append([get_btn('Удалить', f'{table}_{curr_dynasty['id']}_delete')])
    kb.append(get_pagination_kb(table, page, len(entries), 1))
    kb.append([get_btn('На главную', 'start'), get_btn('Фильтры', f'{table}_filters')])

    text = format_channel(curr_dynasty)
    args = {'reply_markup': InlineKeyboardMarkup(inline_keyboard=kb)}
    if curr_dynasty.get('media'):
        args['media'] = get_photo(curr_dynasty['id'], text)
    else:
        args['text'] = text
    await bot_config.handle_message(callback, args)


@router.callback_query(F.data.endswith('filters'))
async def get_filters(callback: CallbackQuery, state: FSMContext):
    table = callback.data.split('_')[0]
    data = await state.get_data()
    filters = data.get(f'{table}_filters')
    if not filters:
        query_res = await db.execute_query(f'select {table} from filters where user_id = ?', callback.from_user.id)
        if query_res:
            filters = query_res[0][table]

    kb = None
    if table == 'creators':
        kb = get_creators_filters(filters) if filters else creators_filters_kb

    await bot_config.handle_message(callback, {'text': bot_config.texts.get('filters'), 'reply_markup': kb or get_back_kb('start')})


@router.callback_query(F.data.startswith('set_filters_content'))
async def update_filters(callback: CallbackQuery, state: FSMContext):
    kb = edit_content_kb(callback)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await state.update_data(creators_filters=get_content_types(kb))


@router.callback_query(F.data.endswith('sort'))
async def get_sort(callback: CallbackQuery):
    table = callback.data.split('_')[0]
    await callback.message.edit_text(text=bot_config.texts.get('sort'), reply_markup=get_sort_kb(table))


@router.callback_query(F.data.endswith('first'))
async def set_sort(callback: CallbackQuery, state: FSMContext):
    table = split(callback)[0]
    try:
        kb = edit_content_kb(callback, True)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await state.update_data({f'{table}_sort': 'desc' if 'new' in callback.data else ''})
    except TelegramBadRequest:
        await callback.answer('Этот тип сортировки уже выбран!')
    # await state.update_data({f'{table}_sort': })

