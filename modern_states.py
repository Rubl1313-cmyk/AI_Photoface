# 🚀 Современные состояния для AI PhotoStudio 2.0
from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    # Основное состояние
    idle = State()
    
    # AI Фотосессия
    waiting_for_face_photoshoot = State()
    selecting_photoshoot_style = State()
    waiting_for_custom_prompt = State()
    generating_photoshoot = State()
    
    # Генерация по промпту
    waiting_for_prompt_generate = State()
    generating = State()
    
    # Замена лица
    waiting_for_target_swap = State()
    
    # Общие состояния
    processing = State()
