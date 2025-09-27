from bot_constructor.bot_config import BotConfig
from utils.keyboards import get_back, get_back_kb

config = BotConfig(default_answer='эщкере')
db = config.db
config.entries_on_page = 5
config.states = ['title', 'link', 'description', 'media']
config.questions = ["type", "genre", "drama_level", "text_level", "preset"]


def get_previous_question(key: str, questions: list[str]) -> str | None:
    if key in questions:
        index = questions.index(key)
        if index > 0:
            return questions[index - 1]
    return None


def load_questions():
    data = config.jsons.get('questions')
    for key, kb in data.items():
        data = {f'{key}_{i + 1}': kb[i] for i in range(len(kb))}
        prev = get_previous_question(key, config.questions) or 'add'
        config.keyboards[key] = config.generate_kb(prev, data)

    for question in config.questions:
        if not question.endswith('level'):
            continue
        key = question.split('_')[0]
        temp_kb = config.edit_keyboard(key, 'level')
        prev = get_previous_question(question, config.questions)
        temp_kb.inline_keyboard[-1] = get_back(prev)
        config.keyboards[question] = temp_kb


def update_states_keyboards():
    for state in config.states:
        config.keyboards[f'set_{state}'] = config.edit_keyboard(state, 'set_state')
        if state != 'media':
            cb = config.questions[-1] if state == 'title' else state + '_back_state'
            config.keyboards[state] = get_back_kb(cb)
    config.keyboards['title_creator'] = get_back_kb('content')
    config.load_messages()


load_questions()
update_states_keyboards()

