# states.py
"""
🎨 AI PhotoStudio — FSM States (COMPLETE)
"""

from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    # 🔹 ОСНОВНОЕ
    idle = State()
    
    # 🔹 РЕЖИМ "🔄 С заменой лица"
    waiting_for_face = State()
    waiting_for_gender = State()
    waiting_for_style = State()
    waiting_for_shot_type = State()
    waiting_for_prompt = State()
    
    # 🔹 РЕЖИМ "✨ Просто генерация"
    waiting_for_prompt_simple = State()
    
    # 🔹 РЕЖИМ "🖼️ Замена на своём фото"
    waiting_for_target_swap = State()
    
    # 🔹 РЕЖИМ "✨ ИИ фотосессия"
    waiting_for_face_photoshoot = State()
    waiting_for_gender_photoshoot = State()
    waiting_for_shot_type_photoshoot = State()
    waiting_for_prompt_photoshoot = State()
    
    # 🔹 ОБЩЕЕ
    generating = State()
