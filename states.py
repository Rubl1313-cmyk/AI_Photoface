from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    idle = State()
    waiting_for_face = State()
    waiting_for_gender = State()
    waiting_for_prompt = State()
    waiting_for_prompt_simple = State()
    waiting_for_target_image = State()  # новое состояние для загрузки целевого изображения
    choosing_style = State()
    waiting_for_custom_style = State()
    generating = State()
