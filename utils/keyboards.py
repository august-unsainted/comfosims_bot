from math import ceil
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery


def get_btn(text: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback)


def get_back(callback: str) -> list[InlineKeyboardButton]:
    return [get_btn('Назад ⬅️', callback)]


def get_back_kb(callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[get_back(callback)])


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


def get_pagination_kb(key: str, page: int, length: int, on_page: int) -> list[InlineKeyboardButton]:
    pages_count = ceil(length / on_page)
    back_cb = f'{page - 1}_{key}' if page > 1 else 'null'
    next_cb = f'{page + 1}_{key}' if page < pages_count else 'null'
    return [get_btn('◀️', back_cb), get_btn(f'{page}/{pages_count}', 'publications'),
            get_btn('▶️', next_cb)]
