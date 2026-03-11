# 🚀 Современные клавиатуры для AI PhotoStudio 2.0
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_modern_main_menu():
    """Современное главное меню"""
    builder = InlineKeyboardBuilder()
    
    # Основные функции
    builder.button(text="📸 AI Фотосессия", callback_data="photoshoot")
    builder.button(text="🎨 Генерация по промпту", callback_data="generate")
    builder.button(text="🔄 Замена лица", callback_data="swap")
    
    # Дополнительно
    builder.button(text="📊 Статистика", callback_data="stats")
    builder.button(text="❓ Помощь", callback_data="help")
    
    builder.adjust(3, 2)
    return builder.as_markup()

def get_photoshoot_styles_keyboard():
    """Клавиатура стилей фотосессий"""
    from main import ULTRA_PHOTOSHOOT_STYLES
    
    builder = InlineKeyboardBuilder()
    
    # Ultra стили в 2 колонки
    for style_key, style_data in ULTRA_PHOTOSHOOT_STYLES.items():
        builder.button(
            text=f"{style_data['name']}", 
            callback_data=f"ultra_style_{style_key}"
        )
    
    builder.adjust(2, 2, 2)
    return builder.as_markup()

def get_reply_keyboard():
    """Нижнее меню с быстрым доступом"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📸 AI Фотосессия"),
                KeyboardButton(text="🎨 Генерация")
            ],
            [
                KeyboardButton(text="🔄 Замена лица"),
                KeyboardButton(text="📊 Статистика")
            ],
            [
                KeyboardButton(text="❓ Помощь"),
                KeyboardButton(text="🏠 Главное меню")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выбери действие 👇"
    )

def get_back_menu():
    """Кнопка возврата"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    return builder.as_markup()

# Старые функции для совместимости
def get_main_menu():
    return get_modern_main_menu()

def get_gender_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужчина", callback_data="gender_male")
    builder.button(text="👩 Женщина", callback_data="gender_female")
    builder.adjust(2)
    return builder.as_markup()

def get_style_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Фотореализм", callback_data="style_photorealistic")
    builder.button(text="🎯 Гиперреализм", callback_data="style_hyperrealistic")
    builder.button(text="🎬 Кино", callback_data="style_cinematic")
    builder.button(text="🎨 Арт", callback_data="style_art")
    builder.adjust(2, 2)
    return builder.as_markup()
