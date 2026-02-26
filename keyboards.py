from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

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

def get_style_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора стиля с расширенным списком и кнопкой 'Свой стиль'"""
    builder = InlineKeyboardBuilder()

    # Список предустановленных стилей (можно добавлять сколько угодно)
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

    # Добавляем кнопки стилей по 2 в ряд
    for text, callback in styles:
        builder.button(text=text, callback_data=callback)

    # Добавляем кнопку "Свой стиль"
    builder.button(text="✏️ Свой стиль", callback_data="custom_style")

    # Располагаем: сначала все стили по 2, затем кнопка "Свой стиль" во всю ширину
    builder.adjust(2, 2, 2, 2, 2, 2, 1)  # 7 рядов по 2 + последний ряд из 1 кнопки
    return builder.as_markup()

def get_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужчина", callback_data="gender_male", style="primary")
    builder.button(text="👩 Женщина", callback_data="gender_female", style="primary")
    builder.adjust(2)
    return builder.as_markup()
