from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    idle = State()
    
    # AI Photoshoot - фотореализм с лицом
    waiting_for_photoshoot_face = State()
    selecting_photoshoot_style = State()
    selecting_photoshoot_format = State()
    selecting_photoshoot_pose = State()      # выбор позы
    selecting_photoshoot_gaze = State()      # выбор взгляда  <-- новое
    waiting_for_photoshoot_prompt = State()
    generating_photoshoot = State()
    
    # AI Styles - референс + стили
    waiting_for_ai_styles_face = State()
    selecting_ai_styles_style = State()
    waiting_for_ai_styles_prompt = State()
    generating_ai_styles = State()
    
    # AIMage - простая генерация
    waiting_for_ai_image_prompt = State()
    generating_ai_image = State()
    
    # Общие состояния
    processing = State()
