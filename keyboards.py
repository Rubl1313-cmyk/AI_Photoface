from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu():
    """Главное меню бота (только генерация)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 AI Photoshoot", callback_data="ai_photoshoot")
    builder.button(text="🎨 AI Styles", callback_data="ai_styles")
    builder.button(text="🎯 AIMage", callback_data="ai_image")
    builder.adjust(3)
    return builder.as_markup()

def get_photoshoot_styles_keyboard():
    """Стили для AI Photoshoot"""
    from prompts import PHOTOSHOOT_REALISM
    builder = InlineKeyboardBuilder()
    for style_key, style_data in PHOTOSHOOT_REALISM.items():
        builder.button(text=style_data['name'], callback_data=f"photoshoot_style_{style_key}")
    builder.adjust(3, 3, 1)
    return builder.as_markup()

def get_ai_styles_keyboard():
    """Стили для AI Styles"""
    from prompts import AI_STYLES
    builder = InlineKeyboardBuilder()
    for style_key, style_data in AI_STYLES.items():
        builder.button(text=style_data['name'], callback_data=f"ai_style_{style_key}")
    builder.adjust(3)  # по 3 кнопки в ряд для лучшей читаемости
    return builder.as_markup()

def get_photoshoot_formats_keyboard():
    """Клавиатура выбора формата"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Вертикаль 4:3", callback_data="photoshoot_format_vertical_4_3"),
        InlineKeyboardButton(text="📸 Горизонтальный 16:9", callback_data="photoshoot_format_horizontal_16_9")
    )
    return builder.as_markup()

def get_back_menu():
    """Кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    return builder.as_markup()

def get_ready_reply_keyboard():
    """Reply-клавиатура с кнопкой '✅ Готово'"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Готово")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_reply_keyboard():
    """Reply клавиатура с быстрым доступом (без статистики)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 AI Photoshoot"), KeyboardButton(text="🎨 AI Styles")],
            [KeyboardButton(text="🎯 AIMage")]
        ],
        resize_keyboard=True
    )
    return keyboard
    
def get_photoshoot_poses_keyboard():
    """Клавиатура выбора базовой позы"""
    from prompts import POSES
    builder = InlineKeyboardBuilder()
    for pose_key, pose_data in POSES.items():
        builder.button(text=pose_data['name'], callback_data=f"photoshoot_pose_{pose_key}")
    builder.adjust(2)  # по 2 кнопки в ряд
    return builder.as_markup()

def get_photoshoot_gaze_keyboard():
    """Клавиатура выбора направления взгляда"""
    from prompts import GAZE
    builder = InlineKeyboardBuilder()
    for gaze_key, gaze_data in GAZE.items():
        builder.button(text=gaze_data['name'], callback_data=f"photoshoot_gaze_{gaze_key}")
    builder.adjust(3)  # все три в ряд
    return builder.as_markup()
