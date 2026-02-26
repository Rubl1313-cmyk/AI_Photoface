from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔄 С заменой лица"),
        KeyboardButton(text="✨ Просто генерация")
    )
    builder.row(
        KeyboardButton(text="📊 Моя статистика"),
        KeyboardButton(text="❓ Помощь")
    )
    builder.row(KeyboardButton(text="ℹ️ О боте"))
    return builder.as_markup(resize_keyboard=True)

def get_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="👨 Мужчина",
        callback_data="gender_male",
        style="primary"  # если поддерживаются цветные кнопки
    )
    builder.button(
        text="👩 Женщина",
        callback_data="gender_female",
        style="primary"
    )
    builder.adjust(2)
    return builder.as_markup()

def get_style_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    styles = [
        ("⚡ Реализм", "style_realistic"),
        ("🎨 Аниме", "style_anime"),
        ("🖼️ Масло", "style_oil"),
        ("✏️ Скетч", "style_sketch"),
    ]
    for text, callback in styles:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()
