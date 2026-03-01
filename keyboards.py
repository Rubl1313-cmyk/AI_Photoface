# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu():
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 С заменой лица", callback_data="mode_generate")
    builder.button(text="✨ Просто генерация", callback_data="mode_simple")
    builder.button(text="🖼️ Замена лица на своём изображении", callback_data="mode_swap_own")
    builder.button(text="✨ ИИ фотосессия", callback_data="mode_photoshoot")
    builder.button(text="📊 Моя статистика", callback_data="stats")
    builder.button(text="❓ Помощь", callback_data="help")
    builder.adjust(1, 1, 1, 1, 2)
    return builder.as_markup()


def get_gender_keyboard():
    """Выбор пола"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужчина", callback_data="gender_male")
    builder.button(text="👩 Женщина", callback_data="gender_female")
    builder.adjust(2)
    return builder.as_markup()


def get_style_keyboard():
    """Выбор стиля — 22 варианта"""
    builder = InlineKeyboardBuilder()
    
    # Реализм
    builder.button(text="📸 Фотореализм", callback_data="style_photorealistic")
    builder.button(text="🎯 Гиперреализм", callback_data="style_hyperrealistic")
    builder.button(text="🎬 Кино кадр", callback_data="style_cinematic")
    
    # Художественные
    builder.button(text="🎨 Арт", callback_data="style_art")
    builder.button(text="🖼️ Масло", callback_data="style_oil_painting")
    builder.button(text="💧 Акварель", callback_data="style_watercolor")
    builder.button(text="✏️ Скетч", callback_data="style_sketch")
    
    # Фантастика
    builder.button(text="🔥 Киберпанк", callback_data="style_cyberpunk")
    builder.button(text="🧙 Фэнтези", callback_data="style_fantasy")
    builder.button(text="🚀 Sci-Fi", callback_data="style_scifi")
    builder.button(text="🌌 Космос", callback_data="style_space")
    
    # Стилизации
    builder.button(text="✨ Винтаж", callback_data="style_vintage")
    builder.button(text="🎭 Нуар", callback_data="style_noir")
    builder.button(text="🎪 Поп-арт", callback_data="style_popart")
    builder.button(text="📰 Комикс", callback_data="style_comic")
    
    # Аниме/Игры
    builder.button(text="🌸 Аниме", callback_data="style_anime")
    builder.button(text="🎮 3D Render", callback_data="style_3d_render")
    builder.button(text="👾 Пиксель-арт", callback_data="style_pixel_art")
    
    # Другие
    builder.button(text="🌅 Импрессионизм", callback_data="style_impressionism")
    builder.button(text="🏛️ Классика", callback_data="style_classical")
    builder.button(text="🎲 Сюрреализм", callback_data="style_surrealism")
    
    builder.adjust(2, 2, 2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def get_shot_type_keyboard():
    """Выбор типа кадра"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Портрет", callback_data="shot_portrait")
    builder.button(text="🚶 В полный рост", callback_data="shot_fullbody")
    builder.adjust(2)
    return builder.as_markup()
