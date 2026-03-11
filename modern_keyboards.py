# Клавиатуры для AI PhotoStudio 2.0
from aiogram.types import InlineKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    """Главное меню с 3 категориями"""
    builder = InlineKeyboardBuilder()
    
    # Основные функции
    builder.button(text="📸 AI Photoshoot", callback_data="ai_photoshoot")
    builder.button(text="🎨 AI Styles", callback_data="ai_styles")
    builder.button(text="🎯 AIMage", callback_data="ai_image")
    
    # Дополнительные функции
    builder.button(text="📊 Статистика", callback_data="stats")
    
    builder.adjust(3, 1)
    return builder.as_markup()

def get_photoshoot_styles_keyboard():
    """Стили для AI Photoshoot"""
    from prompts import PHOTOSHOOT_REALISM
    
    builder = InlineKeyboardBuilder()
    
    for style_key, style_data in PHOTOSHOOT_REALISM.items():
        builder.button(
            text=f"{style_data['name']}", 
            callback_data=f"photoshoot_style_{style_key}"
        )
    
    builder.adjust(3, 3, 1)
    return builder.as_markup()

def get_ai_styles_keyboard():
    """Стили для AI Styles"""
    from prompts import AI_STYLES
    
    builder = InlineKeyboardBuilder()
    
    for style_key, style_data in AI_STYLES.items():
        builder.button(
            text=f"{style_data['name']}", 
            callback_data=f"ai_style_{style_key}"
        )
    
    builder.adjust(4, 4, 4, 4, 4, 4, 4, 2)
    return builder.as_markup()

def get_photoshoot_formats_keyboard():
    """Форматы для фотосессии"""
    from prompts import PHOTOSHOOT_FORMATS
    
    builder = InlineKeyboardBuilder()
    
    for format_key, format_data in PHOTOSHOOT_FORMATS.items():
        builder.button(
            text=f"{format_data['name']}", 
            callback_data=f"photoshoot_format_{format_key}"
        )
    
    builder.adjust(2)
    return builder.as_markup()

def get_back_menu():
    """Кнопка возврата"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    return builder.as_markup()

# Reply клавиатура для удобства
def get_reply_keyboard():
    """Reply клавиатура с быстрым доступом"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📸 AI Photoshoot"),
                KeyboardButton(text="🎨 AI Styles")
            ],
            [
                KeyboardButton(text="🎯 AIMage"),
                KeyboardButton(text="📊 Статистика")
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard
