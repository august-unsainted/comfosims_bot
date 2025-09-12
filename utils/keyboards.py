from copy import deepcopy
from math import ceil

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from bot_config import bot_config, entries_on_page
from config import ADMIN


def get_btn(text: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback)


def edit_keyboard(key: str, template_kb: str):
    kb = deepcopy(bot_config.keyboards.get(template_kb).inline_keyboard)
    for i in range(len(kb)):
        for j in range(len(kb[i])):
            btn_data = kb[i][j].callback_data
            kb[i][j].callback_data = f'{key}_{btn_data}'
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_back(callback: str) -> list[InlineKeyboardButton]:
    return [get_btn('Назад ⬅️', callback)]


def get_back_kb(callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[get_back(callback)])


def get_previous_question(key: str, questions: list[str]) -> str | None:
    if key in questions:
        index = questions.index(key)
        if index > 0:
            return questions[index - 1]
    return None


async def generate_edition_kb(state: FSMContext) -> InlineKeyboardMarkup:
    data = await state.get_data()
    pub_info = f'{data.get('table')}_{data.get('id')}'
    kb = [
        [get_btn('Изменить ✏\uFE0F', f'{pub_info}_{data.get('field')}_edit_data')],
        [get_btn('Всё верно ✅', 'set_data')],
        [get_btn('Назад ⬅\uFE0F', f'{pub_info}_edit')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
    # "set_pub": {
    #     "set":     "Изменить ✏\uFE0F",
    #     "set_pub": "Всё верно ✅",
    #     "edit":    "Назад ⬅\uFE0F"
    # },


def edit_content_kb(callback: CallbackQuery) -> InlineKeyboardMarkup:
    callback, keyboard = callback.data, callback.message.reply_markup.inline_keyboard
    for i in range(len(keyboard)):
        for j in range(len(keyboard[i])):
            if keyboard[i][j].callback_data == callback:
                btn = keyboard[i][j].text
                new_text = btn.replace('✅ ', '') if btn.startswith('✅') else f'✅ {btn}'
                keyboard[i][j].text = new_text
                break
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_content_types(kb: InlineKeyboardMarkup) -> list[str]:
    result = []
    for row in kb.inline_keyboard:
        for btn in row:
            if btn.text.startswith('✅'):
                result.append(btn.callback_data.replace('content_', ''))
    return result


def load_questions():
    data = bot_config.jsons.get('questions')
    questions = data.pop('order')
    for key, kb in data.items():
        if key == 'levels_data':
            for callback in kb:
                temp_kb = edit_keyboard(callback, 'levels')
                prev = get_previous_question(callback, questions)
                temp_kb.inline_keyboard.append(get_back(prev))
                bot_config.keyboards[f'{callback}_level'] = temp_kb
            continue
        data = {f'{key}_{i + 1}': kb[i] for i in range(len(kb))}
        prev = get_previous_question(key, questions) or 'start_form'
        bot_config.keyboards[key] = bot_config.generate_kb(prev, data)
    return questions


def get_pagination_kb(key: str, page: int, length: int, on_page: int = 0) -> list[InlineKeyboardButton]:
    if on_page == 0:
        on_page = entries_on_page
    pages_count = ceil(length / on_page)
    back_cb = f'{page - 1}_{key}' if page > 1 else 'null'
    next_cb = f'{page + 1}_{key}' if page < pages_count else 'null'
    return [get_btn('◀️', back_cb), get_btn(f'{page}/{pages_count}', 'publications'),
            get_btn('▶️', next_cb)]
