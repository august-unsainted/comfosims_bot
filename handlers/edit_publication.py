from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import ADMIN
from handlers.add_publication import bot_config, db, continue_form
from utils.keyboards import edit_keyboard, get_back_kb, generate_edition_kb
from utils.publication_utils import select_publication, format_channel, get_photo, create_admin_notification, prepare_admin_message


router = Router()


@router.callback_query(F.data.endswith('edit'))
async def edit_publication(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    pub = await select_publication(table, callback, pub_id)
    edited_pub = await db.execute_query('select * from edition where table_name = ? and id = ?', table, pub_id)
    if edited_pub:
        pub = {**pub, **edited_pub[0]}
    text = bot_config.texts.get('edit').format(pub['title'])
    await bot_config.handle_message(callback, {'text':         text,
                                               'reply_markup': edit_keyboard(f'{table}_{pub_id}', 'edit')})


@router.callback_query(F.data.endswith('edit_data'))
async def edit_data(callback: CallbackQuery, state: FSMContext):
    table, pub_id, field = callback.data.split('_')[:3]
    await state.update_data(field=field, id=pub_id, table=table, message=callback.message.message_id)
    await state.set_state('edit_data')
    await callback.message.edit_text(text=bot_config.texts.get(field),
                                     reply_markup=get_back_kb(f'{table}_{pub_id}_edit'))


@router.message(StateFilter('edit_data'))
async def receive_data(message: Message, state: FSMContext):
    await state.update_data(value=message.text)
    await continue_form(message, state, kb=await generate_edition_kb(state))


@router.callback_query(F.data.startswith('set_data'))
async def set_data(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    table, pub_id = data.get('table'), data.get('id')
    pub = await select_publication(table, pub_id=pub_id)
    fields = ['id', 'user_name', 'user_id', 'title', 'link', 'description', 'media']
    values = [data.get(field) or pub.get(field) for field in fields]
    existing_entry = await db.execute_query('select * from edition where table_name = ? and id = ?', table, pub_id)
    if existing_entry:
        await db.execute_query(f'update edition set {data['field']} = ? where id = ? and table_name = ?',
                               data['value'], pub_id, table)
    else:
        placeholders = ', '.join(['?'] * len(fields))
        fields = ', '.join(fields)
        await db.execute_query(f'insert into edition (table_name, {fields}) values (?, {placeholders})', table, *values)
    await callback.message.edit_text(bot_config.texts.get('send'),
                                     reply_markup=get_back_kb(f'{table}_{pub_id}_publication'))
    text, args = create_admin_notification(table, pub_id, {**pub, **data}, 'Изменение публикации')
    await callback.bot.send_message(chat_id=ADMIN, text=text, **args)
    await state.clear()


@router.callback_query(F.data.endswith('confirm_delete'))
async def confirm_delete(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    kb = edit_keyboard(f'{table}_{pub_id}', 'confirm_delete')
    await bot_config.handle_message(callback,
                                    {'text':         'Вы уверены, что хотите удалить публикацию? Отменить это действие нельзя',
                                     'reply_markup': kb})


@router.callback_query(F.data.endswith('delete'))
async def delete(callback: CallbackQuery):
    table, pub_id = callback.data.split('_')[:2]
    pub = await select_publication(table, pub_id=pub_id)
    await db.execute_query(f'delete from {table} where id = ?', pub_id)
    await callback.message.edit_text('Публикация удалена 😥', reply_markup=get_back_kb('publications'))
    func, args = prepare_admin_message(table, pub_id, pub, 'Удаление публикации', callback.bot)
    del args['reply_markup']
    await func(**args)