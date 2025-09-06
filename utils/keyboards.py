from copy import deepcopy

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot_config import bot_config


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


def add_back_btn(key: str, questions: list[str]) -> None:
    kb = bot_config.keyboards.get(key).inline_keyboard
    index = questions.index(key)
    kb.append(get_back(questions[index - 1]))


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


def load_questions():
    data = bot_config.jsons.get('questions')
    questions = data.pop('order')
    for key, kb in data.items():
        if key == 'levels_data':
            bot_config.keyboards[f'{key}_level'] = edit_keyboard(key, 'levels')
            continue
        data = {f'{key}_{i + 1}': kb[i] for i in range(len(kb))}
        question_index = questions.index(key)
        if question_index > 0:
            back = questions[question_index - 1]
        else:
            back = None
        bot_config.keyboards[key] = bot_config.generate_kb(back, data)
    return questions
