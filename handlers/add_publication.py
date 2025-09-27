from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.state import StatesGroup, State

from utils.keyboards import edit_content_kb, get_content_types
from utils.publication_utils import *

router = Router()


class Channel(StatesGroup):
    channel_type = State()
    title = State()
    link = State()
    description = State()
    media = State()
    message = State()


messages, texts, questions, states = config.messages, config.texts, config.questions, config.states


@router.callback_query(F.data.in_(('type', 'content')))
async def add_publication(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(**messages.get(callback.data))
    channel_type = 'dynasties' if callback.data == 'type' else 'creators'
    user = callback.from_user
    await state.update_data(message=callback.message.message_id, channel_type=channel_type,
                            user_id=user.id, user_name=user.username)


async def set_title(callback: CallbackQuery, state: FSMContext, back: str = ''):
    message = messages.get('title')
    if back:
        kb = message['reply_markup'].inline_keyboard
        kb[0][0].callback_data = 'content'
    edited_message = await config.handle_message(callback, message)
    await state.update_data(message=edited_message.message_id)
    await state.set_state(Channel.title)


@router.callback_query(F.data.startswith(tuple(questions)))
async def questions_handler(callback: CallbackQuery, state: FSMContext):
    if callback.data[-1].isdigit():
        key, value = callback.data.rsplit('_', 1)
        await state.update_data(**{key: int(value)})
        index = questions.index(key) + 1
    else:
        key = callback.data
        index = questions.index(key)

    if index >= len(questions):
        await set_title(callback, state)
        return
    next_data = questions[index]
    await callback.message.edit_text(**messages.get(next_data))


@router.callback_query(F.data.startswith('content'))
async def get_content(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=edit_content_kb(callback))


@router.callback_query(F.data == 'set_content')
async def set_content(callback: CallbackQuery, state: FSMContext):
    content_types = get_content_types(callback.message.reply_markup)
    if not content_types:
        await callback.answer('Выберите как минимум 1 тип')
        return
    await state.update_data(content_types=content_types)
    await set_title(callback, state, 'content')


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
        text = texts.get('media') + '\n\n<blockquote>Ошибка! Нет изображения</blockquote>'
        await message.bot.edit_message_text(parse_mode='HTML', text=text, **args)
        return
    photo_id = message.photo[-1].file_id
    await state.update_data(media=photo_id)
    publication = await prepare_message({'media': photo_id, **data})
    await message.bot.edit_message_media(**publication, **args)


@router.callback_query(F.data.endswith('back_state'))
async def get_previous_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    index = states.index(key) - 1
    previous_key = states[index] if 0 <= index < len(states) else questions[-1]
    await callback.message.edit_text(**messages.get(previous_key))
    if index >= 0:
        await state.set_state(Channel.title if index == 0 else getattr(Channel, states[index]))


@router.callback_query(F.data.endswith('update_state'))
async def update_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    index = states.index(key) + 1
    next_key = states[index]
    await callback.message.edit_text(**messages.get(next_key))
    await state.set_state(getattr(Channel, next_key))


@router.callback_query(F.data.endswith('edit_state'))
async def edit_state(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split('_')[0]
    await callback.message.edit_text(**messages.get(key))
    await state.set_state(await state.get_state())


@router.callback_query(F.data == 'set_title')
async def set_title_state(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await set_title(callback, state)


@router.callback_query(F.data == 'send')
async def send_publication(callback: CallbackQuery, state: FSMContext):
    await config.handle_edit_message(callback.message, messages.get('send'))
    data = await state.get_data() or {'message':     callback.message.message_id, 'channel_type': 'dynasties',
                                      'user_id':     callback.from_user.id, 'user_name': callback.from_user.username,
                                      'type':        1,
                                      'title':       'Династия', 'link': 'https://t.me/comfothesimsbot',
                                      'description': 'Род Морено начался с <b>Софии</b> — амбициозной художницы, приехавшей в город без денег и связей. Её упорство позволило построить первый дом, а картины стали приносить стабильный доход. Позже к ней присоединился Даниэль, музыкант со свободным характером. Их союз положил начало династии: дети унаследовали талант к искусству и <u>желание добиться большего</u>.',
                                      'media':       'AgACAgIAAxkBAAIDrmi5nEg-fjxfdNqZ8ATmMy1aB72JAAKPATIbftDRSVuxhA6AvgHQAQADAgADeQADNgQ'}
    await state.clear()
    bot = callback.message.bot
    media, table = data.pop('media'), data.pop('channel_type')
    content_types = data.pop('content_types') if 'content_types' in data else []
    del data['message']
    fields = ', '.join(list(data.keys()))
    info = ', '.join(['?'] * len(data.values()))
    pub_id = await db.execute_query(f"INSERT INTO {table} ({fields}) VALUES ({info})", *data.values())
    if table == 'creators':
        db.cur.executemany("INSERT INTO creators_contents (creator, content) VALUES (?, ?)",
                           [(pub_id, content) for content in content_types])
        db.db.commit()

    photo_file = await bot.get_file(media)
    await bot.download_file(photo_file.file_path, get_photo(pub_id).media.path)
    func, args = prepare_admin_message(table, pub_id, data, 'Новая публикация', bot)
    await func(**args)
