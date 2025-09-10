from math import ceil
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot_config import entries_on_page
from handlers.add_publication import bot_config, db
from utils.keyboards import get_btn

router = Router()


def get_pagination_kb(key: str, page: int, length: int) -> list[InlineKeyboardButton]:
    pages_count = ceil(length / entries_on_page)
    back_cb = f'{page - 1}_{key}' if page > 1 else 'null'
    next_cb = f'{page + 1}_{key}' if page < pages_count else 'null'
    return [get_btn('◀️', back_cb), get_btn(f'{page}/{pages_count}', 'publications'),
            get_btn('▶️', next_cb)]


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
    page = callback.data.split('_')[0] if '_' in callback.data else 1
    kb = await get_page(callback.from_user.id, int(page))
    await bot_config.handle_edit_message(callback.message, {'text':         bot_config.messages.get('publications')[
                                                                                'text'],
                                                            'reply_markup': kb})


@router.callback_query(F.data == 'null')
async def none_data(callback: CallbackQuery):
    await callback.answer('Значений больше нет 😢')
