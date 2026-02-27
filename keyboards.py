from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔄 С заменой лица"),
        KeyboardButton(text="✨ Просто генерация")
    )
    builder.row(
        KeyboardButton(text="🖼️ Замена лица на своё фото"),  # новая кнопка
        KeyboardButton(text="📊 Моя статистика")
    )
    builder.row(
        KeyboardButton(text="❓ Помощь"),
        KeyboardButton(text="ℹ️ О боте")
    )
    return builder.as_markup(resize_keyboard=True)

def get_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужчина", callback_data="gender_male", style="primary")
    builder.button(text="👩 Женщина", callback_data="gender_female", style="primary")
    builder.adjust(2)
    return builder.as_markup()

def get_style_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    styles = [
        ("⚡ Реализм", "style_realistic"),
        ("🎨 Аниме", "style_anime"),
        ("🖼️ Масло", "style_oil"),
        ("✏️ Скетч", "style_sketch"),
        ("🌌 Киберпанк", "style_cyberpunk"),
        ("🏛️ Барокко", "style_baroque"),
        ("🌀 Сюрреализм", "style_surreal"),
        ("🦸 Комикс", "style_comic"),
        ("📸 Фотореализм", "style_photoreal"),
        ("💧 Акварель", "style_watercolor"),
        ("🖍️ Пастель", "style_pastel"),
        ("🗿 3D-рендер", "style_3d"),
    ]
    for text, callback in styles:
        builder.button(text=text, callback_data=callback)
    builder.button(text="✏️ Свой стиль", callback_data="custom_style")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)
    return builder.as_markup()
