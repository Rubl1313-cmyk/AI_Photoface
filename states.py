from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    idle = State()
    waiting_for_face = State()
    waiting_for_prompt = State()
    choosing_style = State()
    generating = State()
