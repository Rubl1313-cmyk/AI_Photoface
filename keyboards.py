from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Константа для новой кнопки (можно вынести в отдельное место, но здесь для наглядности)
PHOTOSHOOT_BUTTON = "✨ ИИ фотосессия"

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔄 С заменой лица"),
        KeyboardButton(text="✨ Просто генерация")
    )
    builder.row(
        KeyboardButton(text=PHOTOSHOOT_BUTTON),  # Новая кнопка
        KeyboardButton(text="📊 Моя статистика")
    )
    builder.row(
        KeyboardButton(text="🖼️ Замена лица на своём изображении"),
        KeyboardButton(text="❓ Помощь")
    )
    builder.row(
        KeyboardButton(text="ℹ️ О боте")
    )
    return builder.as_markup(resize_keyboard=True)

# Остальные клавиатуры (get_gender_keyboard, get_style_keyboard, get_shot_type_keyboard) остаются без изменений
