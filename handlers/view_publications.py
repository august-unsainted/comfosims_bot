from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from handlers.add_publication import bot_config, db

router = Router()


@router.callback_query(F.data == 'publications')
async def view_publications(callback: CallbackQuery):
    select_query = f'select id, title from table where user_id = {callback.from_user.id}'
    queries = [select_query.replace('table', table) for table in ['creators', 'dynasties']]
    publications = await db.execute_query(' union '.join(queries))
    kb_template = bot_config.keyboards.get('publications').inline_keyboard
    if publications:
        if isinstance(publications, dict):
            publications = [publications]
        kb = [[InlineKeyboardButton(text=pub['title'], callback_data=f'publication_{pub['id']}')] for pub in
              publications]
    else:
        kb = []
    kb.extend(kb_template)
    await bot_config.handle_edit_message(callback.message, {'text': bot_config.messages.get('publications')['text'],
                                             'reply_markup': InlineKeyboardMarkup(inline_keyboard=kb)})


@router.callback_query(F.data.startswith('publication'))
async def get_publication(callback: CallbackQuery):
    pub_id = callback.data.split('_')[-1]
    await callback.message.edit_text(bot_config.messages.get(''))
