from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню с эмодзи"""
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
    """
    Клавиатура выбора стиля — цветные кнопки с иконками!
    Требуется обновление aiogram до 3.25.0+
    """
    builder = InlineKeyboardBuilder()
    
    # ID кастомных эмодзи (замените на свои, если есть Premium)
    # Если Premium нет — просто уберите параметр icon_custom_emoji_id
    EMOJI_IDS = {
        "realistic": "5285430309720966085",  # ⚡
        "anime": "5310076249404621168",      # 🌸  
        "oil": "5285032475490273112",        # 🎨
        "sketch": "5310169226856644648"      # ✏️
    }
    
    # Формат: (текст, callback_data, цвет, ключ эмодзи)
    styles = [
        ("Реализм", "style_realistic", "primary", "realistic"),
        ("Аниме", "style_anime", "success", "anime"),
        ("Масло", "style_oil", "primary", "oil"),
        ("Скетч", "style_sketch", "success", "sketch"),
    ]
    
    for text, callback, color, emoji_key in styles:
        # Если есть Premium — добавляем иконку, если нет — только текст
        if any(EMOJI_IDS.values()):  # проверка, что ID существуют
            button_text = f"{text}"
            icon_id = EMOJI_IDS.get(emoji_key)
        else:
            button_text = f"{text}"
            icon_id = None
        
        # Создаём кнопку с цветом и опциональной иконкой
        builder.button(
            text=button_text,
            callback_data=callback,
            style=color,  # primary, success или danger
            icon_custom_emoji_id=icon_id
        )
    
    builder.adjust(2)  # по 2 кнопки в ряд
    return builder.as_markup()

def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения с цветными кнопками danger/success
    """
    builder = InlineKeyboardBuilder()
    
    # ID эмодзи для галочки и крестика
    EMOJI_IDS = {
        "yes": "5310076249404621168",  # ✅ зелёная галочка
        "no": "5310169226856644648"     # ❌ красный крестик
    }
    
    # Зелёная кнопка подтверждения (success)
    builder.button(
        text="Да, всё верно",
        callback_data="confirm_yes",
        style="success",
        icon_custom_emoji_id=EMOJI_IDS.get("yes") if any(EMOJI_IDS.values()) else None
    )
    
    # Красная кнопка отмены (danger)
    builder.button(
        text="Начать заново",
        callback_data="confirm_no",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS.get("no") if any(EMOJI_IDS.values()) else None
    )
    
    builder.adjust(1)
    return builder.as_markup()

def get_main_menu_colors() -> ReplyKeyboardMarkup:
    """
    Альтернативное главное меню с цветными reply-кнопками (если нужно)
    Reply-кнопки тоже поддерживают style и icon_custom_emoji_id!
    """
    builder = ReplyKeyboardBuilder()
    
    # Синяя кнопка (primary) для создания фото
    builder.row(
        KeyboardButton(
            text="🎨 Создать фото",
            style="primary",
            icon_custom_emoji_id="5285430309720966085"  # если есть Premium
        )
    )
    
    # Обычные кнопки (без цвета) для остального
    builder.row(
        KeyboardButton(text="📊 Моя статистика"),
        KeyboardButton(text="❓ Помощь"),
        KeyboardButton(text="ℹ️ О боте")
    )
    
    return builder.as_markup(resize_keyboard=True)
