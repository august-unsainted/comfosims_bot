from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from handlers.add_publication import bot_config, db, continue_form
from utils.keyboards import edit_keyboard, get_back_kb, generate_edition_kb
from utils.publication_utils import select_publication, format_channel, get_photo

router = Router()


@router.callback_query(F.data.endswith('publications'))
async def view_publications(callback: CallbackQuery):
    query_template = f'select id, title from table where user_id = ?'
    publications = {}
    for table in ['creators', 'dynasties']:
        query = query_template.replace('table', table)
        publications[table] = await db.execute_query(query, callback.from_user.id)

    kb = []
    for table, pubs in publications.items():
        for pub in pubs:
            btn = InlineKeyboardButton(text=pub['title'], callback_data=f'{table}_{pub['id']}_publication')
            kb.append([btn])
    kb.extend(bot_config.keyboards.get('publications').inline_keyboard)
    await bot_config.handle_edit_message(callback.message, {'text': bot_config.messages.get('publications')['text'],
                                             'reply_markup': InlineKeyboardMarkup(inline_keyboard=kb)})


@router.callback_query(F.data.endswith('publication'))
async def get_publication(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    print(table, pub_id)
    pub = await select_publication(table, callback, pub_id)
    comment = f'Статус: {pub['status'].lower()}.'
    if pub['deny_reason']:
        comment += f'\nПричина: {pub['deny_reason']}.'

    kb = edit_keyboard(f'{table}_{pub_id}', 'my_publication')
    if pub.get('media'):
        await callback.message.edit_media(media=get_photo(pub_id, format_channel(pub, comment)), reply_markup=kb)
    else:
        await callback.message.edit_text(format_channel(pub, comment), parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.endswith('edit'))
async def edit_publication(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    pub = await select_publication(table, callback, pub_id)
    text = bot_config.texts.get('edit').format(pub['title'])
    await bot_config.handle_message(callback, {'text': text,
                                               'reply_markup': edit_keyboard(f'{table}_{pub_id}', 'edit')})


@router.callback_query(F.data.endswith('edit_data'))
async def edit_data(callback: CallbackQuery, state: FSMContext):
    table, pub_id, field = callback.data.split('_')[:3]
    await state.update_data(field=field, id=pub_id, table=table, message=callback.message.message_id)
    await state.set_state('edit_data')
    await callback.message.edit_text(text=bot_config.texts.get(field), reply_markup=get_back_kb(f'{table}_{pub_id}_edit'))


@router.message(StateFilter('edit_data'))
async def receive_data(message: Message, state: FSMContext):
    await state.update_data(value=message.text)
    await continue_form(message, state, kb=await generate_edition_kb(state))


@router.callback_query(F.data.startswith('set_data'))
async def set_data(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    table, pub_id = data.get('table'), data.get('id')
    await db.execute_query(f"update {table} set {data.get('field')} = ?, status = 'На рассмотрении', deny_reason = NULL WHERE id = ?",
                           data.get('value'), pub_id)
    text = bot_config.texts.get('send')
    await callback.message.edit_text(text, reply_markup=get_back_kb(f'{table}_{pub_id}_publication'))
    await state.clear()


@router.callback_query(F.data.endswith('confirm_delete'))
async def confirm_delete(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    kb = edit_keyboard(f'{table}_{pub_id}', 'confirm_delete')
    await bot_config.handle_message(callback, {'text': 'Вы уверены, что хотите удалить династию?',
                                         'reply_markup': kb})


@router.callback_query(F.data.endswith('delete'))
async def delete(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    await db.execute_query(f'delete from {table} where id = ?', pub_id)
    await callback.message.edit_text('Династия удалена(((', reply_markup=get_back_kb('publications'))
