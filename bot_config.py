from bot_constructor.bot_config import BotConfig
from utils.keyboards import get_back, get_back_kb

config = BotConfig(default_answer='эщкере')
db = config.db
config.entries_on_page = 5
config.states = ['title', 'link', 'description', 'media']


def get_previous_question(key: str, questions: list[str]) -> str | None:
    if key in questions:
        index = questions.index(key)
        if index > 0:
            return questions[index - 1]
    return None


def load_questions() -> list[str]:
    data = config.jsons.get('questions')
    questions_order = data.pop('order')
    for key, kb in data.items():
        if key == 'levels_data':
            for callback in kb:
                temp_kb = config.edit_keyboard(callback, 'level')
                prev = get_previous_question(f'{callback}_level', questions_order)
                temp_kb.inline_keyboard[-1] = get_back(prev)
                config.keyboards[f'{callback}_level'] = temp_kb
            continue
        data = {f'{key}_{i + 1}': kb[i] for i in range(len(kb))}
        prev = get_previous_question(key, questions_order) or 'add'
        config.keyboards[key] = config.generate_kb(prev, data)
    return questions_order


def update_states_keyboards():
    for state in config.states:
        config.keyboards[f'set_{state}'] = config.edit_keyboard(state, 'set_state')
        if state != 'media':
            cb = config.questions[-1] if state == 'title' else state + '_back_state'
            config.keyboards[state] = get_back_kb(cb)
    config.keyboards['title_creator'] = get_back_kb('content')
    config.load_messages()


config.questions = load_questions()
update_states_keyboards()

