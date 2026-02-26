from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🎨 Создать фото"),
        KeyboardButton(text="📊 Моя статистика")
    )
    builder.row(
        KeyboardButton(text="❓ Помощь"),
        KeyboardButton(text="ℹ️ О боте")
    )
    return builder.as_markup(resize_keyboard=True)

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
