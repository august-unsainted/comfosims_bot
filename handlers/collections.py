from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, FSInputFile, InlineKeyboardMarkup, \
    InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from bot_constructor.bot_config import BotConfig
from copy import deepcopy

bot_config = BotConfig(default_answer='эщкере')
db = bot_config.db
# questions = ['type', 'genre', 'drama_level', 'text_level', 'preset']
questions = ['type']
router = Router()


class Channel(StatesGroup):
    channel_type = State()
    title = State()
    link = State()
    description = State()
    media = State()
    message = State()


states = ['title', 'link', 'description', 'media']
states_groups = [Channel.link, Channel.description, Channel.media]


def edit_keyboard(key: str, template_kb: str):
    kb = deepcopy(bot_config.keyboards.get(template_kb).inline_keyboard)
    for i in range(len(kb)):
        btn_data = kb[i][0].callback_data
        kb[i][0].callback_data = f'{key}_{btn_data}'
    return InlineKeyboardMarkup(inline_keyboard=kb)


def add_back_btn(key: str) -> None:
    kb = bot_config.keyboards.get(key).inline_keyboard
    index = questions.index(key)
    kb.append([InlineKeyboardButton(text='Назад ⬅️', callback_data=questions[index - 1])])


bot_config.keyboards['drama_level'] = edit_keyboard('drama', 'levels')
bot_config.keyboards['text_level'] = edit_keyboard('text', 'levels')
for data in questions[1:]:
    add_back_btn(data)

for state in states:
    bot_config.keyboards[f'set_{state}'] = edit_keyboard(state, 'set_state')

bot_config.load_messages()


@router.callback_query(F.data.in_(('type', 'content')))
async def add_publication(callback: CallbackQuery, state: FSMContext):
    # channel_type = callback.data.split('_')[-1]
    # next_question = 'type' if channel_type == 'dynasty' else 'content'
    await callback.message.edit_text(**bot_config.messages.get(callback.data))
    await state.update_data(message=callback.message.message_id, channel_type='dynasty' if callback.data == 'type' else 'creator')


@router.callback_query(F.data.startswith(tuple(questions)))
async def questions_handler(callback: CallbackQuery, state: FSMContext):
    key, value = callback.data.rsplit('_', 1)
    index = questions.index(key) + 1
    await state.update_data(**{key: int(value)})
    if index < len(questions):
        next_data = questions[index]
    else:
        next_data = 'title'
        await state.set_state(Channel.title)
    await callback.message.edit_text(**bot_config.messages.get(next_data))


async def continue_form(message: Message, state: FSMContext, message_data: str):
    await state.update_data(**{message_data: message.text})
    data = await state.get_data()
    args = {'chat_id': message.chat.id, 'message_id': data['message'], **bot_config.default_args}
    await message.bot.edit_message_text(**args, text=f'{message.text}\n\nВсё верно?',
                                        reply_markup=bot_config.keyboards.get(f'set_{message_data}'))
    await message.delete()


@router.message(StateFilter(Channel.title, Channel.link, Channel.description))
async def get_channel_info(message: Message, state: FSMContext):
    current_state = await state.get_state()
    field_name = current_state.split(':')[-1]
    await continue_form(message, state, field_name)


@router.message(Channel.media)
async def set_media(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    args = {'message_id': data['message'], 'chat_id': message.chat.id}
    if not message.photo:
        await message.bot.edit_message_text(text=bot_config.messages.get('media')['text'] + '\n\n<blockquote>Ошибка! Нет изображения</blockquote>',
                                            **args, **bot_config.default_args)
        return
    caption = bot_config.jsons['messages'].get('channel').format(data['title'], data['link'], data['description'])
    media = InputMediaPhoto(media=message.photo[0].file_id, caption=caption, **bot_config.default_args)
    await message.bot.edit_message_media(media=media, **args)


@router.callback_query(F.data.endswith('update'))
async def set_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    index = states.index(key) + 1
    next_key = states[index] if index < len(states) else 'start'
    await callback.message.edit_text(**bot_config.messages.get(next_key))
    await state.set_state(states_groups[index - 1])


async def get_publications_kb(user_id: int) -> InlineKeyboardMarkup:
    select_query = 'select id, title from {0} where user = {1}'
    queries = []
    for table in ['creators', 'dynasties']:
        queries.append(select_query.format(table, user_id))
    publications = await db.execute_query(' union '.join(queries))
    kb_template = bot_config.keyboards.get('publications').inline_keyboard
    if publications:
        kb = [[InlineKeyboardButton(text=pub['title'], callback_data=f'publication_{pub['id']}')] for pub in publications]
    else:
        kb = []
    kb.extend(kb_template)
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == 'publications')
async def get_publications(callback: CallbackQuery):
    kb = await get_publications_kb(callback.from_user.id)
    await bot_config.handle_edit_message(callback.message, {'text': bot_config.messages.get('publications')['text'],
                                             'reply_markup': kb})
