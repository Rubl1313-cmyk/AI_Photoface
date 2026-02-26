from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🎨 Создать фото"),
        KeyboardButton(text="📊 Моя статистика")
    )
    builder.row(KeyboardButton(text="❓ Помощь"))
    return builder.as_markup(resize_keyboard=True)

def get_style_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    styles = [
        ("🎬 Кинематографичный", "style_cinematic"),
        ("🌟 Портрет", "style_portrait"),
        ("🎨 Арт", "style_art"),
        ("📸 Реализм", "style_realistic"),
        ("🌃 Киберпанк", "style_cyberpunk"),
        ("✨ Фэнтези", "style_fantasy"),
    ]
    for text, callback in styles:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    builder.button(text="⏭️ Пропустить стиль", callback_data="style_skip")
    return builder.as_markup()

def get_result_keyboard(gen_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Ещё раз", callback_data=f"retry_{gen_id}"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")
    )
    return builder.as_markup()