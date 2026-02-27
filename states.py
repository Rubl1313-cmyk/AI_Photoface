from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    idle = State()
    waiting_for_face = State()
    waiting_for_gender = State()
    waiting_for_prompt = State()
    waiting_for_prompt_simple = State()
    choosing_style = State()
    choosing_shot_type = State()          # новое состояние
    waiting_for_custom_style = State()
    waiting_for_target_image = State()
    generating = State()
