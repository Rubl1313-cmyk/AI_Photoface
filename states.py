from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    idle = State()
    waiting_for_face = State()
    waiting_for_gender = State()          # новое состояние для выбора пола
    waiting_for_prompt = State()           # для генерации с лицом
    waiting_for_prompt_simple = State()    # для простой генерации
    choosing_style = State()
    generating = State()
