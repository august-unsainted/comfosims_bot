import validators
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot_config import entries_on_page
from config import ADMIN
from handlers.add_publication import bot_config, db
from handlers.filters import save_filters
from utils.keyboards import get_btn, edit_keyboard, get_pagination_kb
from utils.publication_utils import select_publication, format_channel, get_photo, split, get_link

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


@router.callback_query(F.data.endswith('publications'))
async def view_publications(callback: CallbackQuery):
    if '_' in callback.data and not callback.data.startswith('dynasties'):
        page = split(callback)[0]
    else:
        page = 1
    kb = await get_page(callback.from_user.id, int(page))
    text = bot_config.texts.get('publications')
    await bot_config.handle_edit_message(callback.message, {'text': text, 'reply_markup': kb})


@router.callback_query(F.data.endswith('publication'))
async def get_publication(callback: CallbackQuery):
    table, pub_id = split(callback)[:2]
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


@router.callback_query(F.data.endswith(('dynasties', 'creators')))
async def view_dynasties(callback: CallbackQuery, state: FSMContext):
    splited = split(callback)
    table = splited[-1]
    data = await state.get_data()
    entries = data.get(table)
    filters, sort = await save_filters(data, table, callback.from_user.id, state)

    if entries is None or filters:
        query = f'select * from {table} order by date desc'
        if table == 'creators' and filters:
            query = f'''
            SELECT DISTINCT c.*
            FROM creators c JOIN creators_contents cc
            ON c.id = cc.creator
            WHERE cc.content IN ({filters})
            ORDER BY date {sort}
            '''
        entries = await db.execute_query(query)
        await state.update_data(**{table: entries})
    kb = []
    args = {}
    if not entries:
        args['text'] = bot_config.texts.get('no_publications')
    else:
        page = int(splited[0]) if '_' in callback.data else 1
        curr_dynasty = dict(entries[page - 1])
        text = format_channel(curr_dynasty)
        link = get_link(curr_dynasty['link'])
        kb.append([InlineKeyboardButton(text='Подписаться', url=link)])
        if callback.message.chat.id == ADMIN:
            kb.append([get_btn('Удалить', f'{table}_{curr_dynasty['id']}_delete')])
        kb.append(get_pagination_kb(table, page, len(entries), 1))
        if entries and curr_dynasty.get('media'):
            args['media'] = get_photo(curr_dynasty['id'], text)
        else:
            args['text'] = text
    kb.append([get_btn('На главную', 'start'), get_btn('Фильтры', f'{table}_filters')])
    await bot_config.handle_message(callback, {**args, 'reply_markup': InlineKeyboardMarkup(inline_keyboard=kb)})


@router.callback_query(F.data == 'null')
async def none_data(callback: CallbackQuery):
    await callback.answer('Значений больше нет 😢')
