from copy import deepcopy
from math import ceil

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from bot_config import bot_config, entries_on_page


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


def edit_content_kb(callback: CallbackQuery, single_select: bool = False) -> InlineKeyboardMarkup:
    callback, keyboard = callback.data, callback.message.reply_markup.inline_keyboard
    for i in range(len(keyboard)):
        for j in range(len(keyboard[i])):
            btn = keyboard[i][j]
            text = btn.text
            selected = text.startswith('✅')
            unselect = text.replace('✅ ', '')
            if keyboard[i][j].callback_data == callback:
                if single_select:
                    btn.text = f'✅ {unselect}'
                else:
                    btn.text = unselect if selected else f'✅ {text}'
                    break
            elif single_select and selected:
                btn.text = unselect
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_content_types(kb: InlineKeyboardMarkup) -> list[str]:
    result = []
    for row in kb.inline_keyboard:
        for btn in row:
            if btn.text.startswith('✅'):
                result.append(btn.callback_data.split('_')[-1])
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


async def get_sort_kb(table: str, user: int) -> InlineKeyboardMarkup:
    kb = edit_keyboard(table, 'sort')
    query_res = await bot_config.db.execute_query(f'select {table}_sort from filters where user_id = ?', user)
    sort = query_res[0][f'{table}_sort'] if query_res else 'desc'
    index = int(not sort)
    selected_option = kb.inline_keyboard[index][0]
    selected_option.text = '✅ ' + selected_option.text
    return kb


def get_creators_filters(selected: str = None):
    kb_markup = edit_keyboard('set_filters', 'content')
    kb = kb_markup.inline_keyboard
    del kb[-1]
    has_filters = bool(selected)
    if has_filters:
        selected = selected.split(', ')
    for i in range(len(kb)):
        for j in range(len(kb[i])):
            if (has_filters and kb[i][j].callback_data.endswith(tuple(selected))) or not has_filters:
                kb[i][j].text = '✅ ' + kb[i][j].text
    kb.insert(-1, [get_btn('Сортировка', f'creators_sort')])
    kb[-1] = [get_btn('Назад', 'creators'), get_btn('Сбросить всё', 'creators_reset_filters')]
    return kb_markup


bot_config.keyboards['creators_filters'] = get_creators_filters()
