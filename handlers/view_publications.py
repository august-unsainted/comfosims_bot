from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

from bot_config import entries_on_page
from config import ADMIN
from handlers.add_publication import bot_config, db
from utils.keyboards import get_btn, edit_keyboard, get_pagination_kb
from utils.publication_utils import select_publication, format_channel, get_photo

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


@router.callback_query(F.data.endswith('dynasties'))
async def view_dynasties(callback: CallbackQuery):
    dynasties = await db.execute_query('select * from dynasties order by date desc')
    page = int(callback.data.split('_')[0]) if '_' in callback.data else 1
    curr_dynasty = dict(dynasties[page - 1])

    kb = [[InlineKeyboardButton(text='Подписаться', url=curr_dynasty['link'])]]
    if callback.message.chat.id == ADMIN:
        kb.append([get_btn('Удалить', f'dynasties_{curr_dynasty['id']}_delete')])
    kb.append(get_pagination_kb('dynasties', page, len(dynasties), 1))
    kb.append([get_btn('На главную', 'start'), get_btn('Фильтры', 'filters')])

    text = format_channel(curr_dynasty)
    args = {'reply_markup': InlineKeyboardMarkup(inline_keyboard=kb)}
    if curr_dynasty.get('media'):
        args['media'] = get_photo(curr_dynasty['id'], text)
    else:
        args['text'] = text
    await bot_config.handle_message(callback, args)
