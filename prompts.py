# 🎯 Промпты для AI PhotoStudio 2.0 - 3 категории

# AI Photoshoot - фотореализм с лицом пользователя
PHOTOSHOOT_REALISM = {
    "portrait": {
        "name": "📷 Портрет",
        "base_prompt": "professional portrait photography, natural expression, sharp focus on eyes, soft lighting, shallow depth of field, photorealistic, high detail, Canon EOS 5D Mark IV, 85mm f/1.8 lens",
        "negative": "cartoon, anime, painting, drawing, illustration, artificial, plastic, wax figure, uncanny valley, oversaturated",
        "examples": ["в студии", "на нейтральном фоне", "с естественным светом"],
        "description": "Классический портрет с профессиональным качеством"
    },
    "business": {
        "name": "👔 Бизнес",
        "base_prompt": "professional business portrait, confident pose, business attire, office environment, professional lighting, corporate photography style, sharp focus, realistic skin texture, natural expression",
        "negative": "casual, messy, unprofessional, cartoon, anime, artificial lighting",
        "examples": ["в современном офисе", "на фоне города", "с документами"],
        "description": "Идеально для LinkedIn, резюме и корпоративных фото"
    },
    "casual": {
        "name": "🌴 Повседневный",
        "base_prompt": "casual portrait photography, relaxed natural pose, authentic expression, everyday clothing, natural outdoor lighting, lifestyle photography, candid style, warm tones, realistic",
        "negative": "formal, stiff, artificial, studio lighting, cartoon, posed",
        "examples": ["в парке", "в кафе", "на улице", "дома"],
        "description": "Естественный образ для соцсетей и повседневной жизни"
    },
    "sport": {
        "name": "🏃 Спорт",
        "base_prompt": "sport action photography, athletic pose, fitness setting, dynamic movement, professional sports photography, sharp focus, motion blur effects, natural lighting, athletic wear, realistic muscle definition",
        "negative": "static, stiff, artificial, cartoon, studio setting, casual",
        "examples": ["в спортзале", "на стадионе", "на улице", "с инвентарем"],
        "description": "Энергичный и сильный спортивный образ"
    },
    "fashion": {
        "name": "👗 Мода",
        "base_prompt": "high fashion portrait photography, stylish outfit, model pose, dramatic lighting, fashion magazine style, sharp focus, elegant composition, professional fashion photography, realistic textures",
        "negative": "casual, messy, amateur, cartoon, flat lighting",
        "examples": ["на подиуме", "в студии", "на улице моды", "с аксессуарами"],
        "description": "Как в глянцевом модном журнале"
    },
    "luxury": {
        "name": "💎 Роскошь",
        "base_prompt": "luxury portrait photography, elegant expensive outfit, premium setting, sophisticated lighting, high-end photography style, sharp focus, rich colors, realistic textures, exclusive atmosphere",
        "negative": "cheap, casual, ordinary, cartoon, flat lighting",
        "examples": ["в люксовом отеле", "на яхте", "в ресторане", "с дорогими аксессуарами"],
        "description": "Элитный образ премиум-класса"
    },
    "custom": {
        "name": "🎯 Кастомный",
        "base_prompt": "professional portrait photography, realistic, high quality, sharp focus, natural lighting",
        "negative": "cartoon, anime, artificial, low quality",
        "examples": ["любая локация", "любая одежда", "любая поза"],
        "description": "Полностью настраиваемый стиль"
    }
}

# AI Styles - популярные стили 2026 года с референсом пользователя
AI_STYLES = {
    "cyberpunk": {
        "name": "🤖 Киберпанк",
        "prompt": "cyberpunk aesthetic, futuristic cityscape, high tech, dystopian future, digital art style, neon accents, advanced technology",
        "description": "Футуристический киберпанк"
    },
    "anime": {
        "name": "� Аниме стиль",
        "prompt": "anime art style, Japanese manga aesthetic, vibrant colors, clean lines, modern anime character design, studio ghibli inspired",
        "description": "Современный аниме стиль"
    },
    "realistic": {
        "name": "📸 Гиперреализм",
        "prompt": "hyperrealistic photography, ultra detailed, professional camera, 8k resolution, perfect lighting, photorealistic, high detail",
        "description": "Максимально реалистичный стиль"
    },
    "cartoon_3d": {
        "name": "� 3D Мультфильм",
        "prompt": "3D cartoon animation style, Pixar style, Disney animation, colorful, friendly, modern 3D rendering, animated movie aesthetic",
        "description": "Стиль современных 3D мультфильмов"
    },
    "vintage": {
        "name": "📷 Ретро",
        "prompt": "vintage photography style, 1970s-1980s aesthetic, film camera, retro colors, grain texture, old photo effect, nostalgic atmosphere",
        "description": "Винтажный стиль 70-80х"
    },
    "fantasy": {
        "name": "🐉 Фэнтези",
        "prompt": "fantasy art style, magical atmosphere, mythical creatures, enchanted forest, epic fantasy, digital painting, mystical lighting",
        "description": "Магический фэнтези мир"
    },
    "sci_fi": {
        "name": "🚀 Научная фантастика",
        "prompt": "science fiction style, space exploration, futuristic technology, alien worlds, sci-fi movie aesthetic, advanced civilization",
        "description": "Космическая научная фантастика"
    },
    "watercolor": {
        "name": "🎨 Акварель",
        "prompt": "watercolor painting style, soft brushstrokes, transparent colors, artistic painting, traditional watercolor technique, gentle washes",
        "description": "Акварельная живопись"
    },
    "oil_painting": {
        "name": "🖼️ Масляная живопись",
        "prompt": "oil painting style, classical art, rich textures, impasto technique, museum quality, traditional oil painting masterpiece",
        "description": "Классическая масляная живопись"
    },
    "comic_book": {
        "name": "💭 Комикс",
        "prompt": "comic book art style, Marvel DC style, bold lines, vibrant colors, superhero aesthetic, modern graphic novel, pop art",
        "description": "Стиль современных комиксов"
    },
    "minimalist": {
        "name": "⚪ Минимализм",
        "prompt": "minimalist art style, clean lines, simple shapes, modern design, aesthetic minimalism, contemporary art, negative space",
        "description": "Современный минимализм"
    },
    "street_art": {
        "name": "� Стрит-арт",
        "prompt": "street art style, graffiti aesthetic, urban art, spray paint, modern street art, bold colors, contemporary urban culture",
        "description": "Городской стрит-арт стиль"
    },
    "glitch": {
        "name": "📺 Глитч-арт",
        "prompt": "glitch art style, digital corruption, RGB color splits, pixelated effects, retro computer graphics, digital artifacts",
        "description": "Цифровой глитч стиль"
    },
    "synthwave": {
        "name": "🌊 Синтвейв",
        "prompt": "synthwave retro 80s aesthetic, neon grid landscape, purple and pink colors, retro futuristic, vaporwave style, electronic music vibes",
        "description": "Ретро-футуризм 80-х"
    },
    "steampunk": {
        "name": "⚙️ Стимпанк",
        "prompt": "steampunk aesthetic, Victorian era technology, brass and copper, mechanical gears, retro futuristic, industrial design",
        "description": "Викторианский стимпанк"
    },
    "gothic": {
        "name": "🦇 Готика",
        "prompt": "gothic art style, dark atmosphere, Victorian gothic, mysterious mood, dramatic lighting, dark fantasy, elegant darkness",
        "description": "Мрачный готический стиль"
    },
    "pop_art": {
        "name": "🎨 Поп-арт",
        "prompt": "pop art style, Andy Warhol aesthetic, bold colors, comic book influence, modern pop art, vibrant, graphic design",
        "description": "Современный поп-арт"
    },
    "impressionist": {
        "name": "🌅 Импрессионизм",
        "prompt": "impressionist painting style, Monet Renoir style, soft brushstrokes, light and color, plein air painting, artistic impressionism",
        "description": "Классический импрессионизм"
    },
    "surreal": {
        "name": "🎭 Сюрреализм",
        "prompt": "surreal art style, dreamlike atmosphere, Salvador Dalí influence, bizarre imagery, subconscious art, fantastical elements",
        "description": "Сюрреалистический стиль"
    },
    "ukiyoe": {
        "name": "🌸 Укиё-э",
        "prompt": "Japanese ukiyo-e woodblock print style, traditional Japanese art, Mount Fuji, cherry blossoms, wave patterns, Edo period aesthetic",
        "description": "Японский традиционный стиль"
    },
    "manga": {
        "name": "� Манга",
        "prompt": "manga art style, Japanese comic aesthetic, black and white manga, dynamic action poses, modern manga illustration, anime influence",
        "description": "Современный манга стиль"
    },
    "tattoo": {
        "name": "💉 Тату",
        "prompt": "tattoo art style, traditional tattoo design, bold lines, tattoo flash, modern tattoo art, body art aesthetic, ink style",
        "description": "Стиль татуировок"
    },
    "pixel_art": {
        "name": "👾 Пиксель-арт",
        "prompt": "pixel art style, 8-bit 16-bit graphics, retro gaming aesthetic, pixelated design, nostalgic video game art, indie game style",
        "description": "Ретро пиксель-арт"
    },
    "low_poly": {
        "name": "� Low Poly",
        "prompt": "low poly art style, geometric shapes, faceted design, modern 3D aesthetic, minimalist geometry, contemporary digital art",
        "description": "Современный low poly стиль"
    },
    "chibi": {
        "name": "🧸 Чиби",
        "prompt": "chibi anime style, cute small characters, adorable aesthetic, kawaii style, cartoonish proportions, sweet and charming",
        "description": "Милый чиби стиль"
    },
    "sketch": {
        "name": "✏️ Эскиз",
        "prompt": "pencil sketch style, charcoal drawing, artistic sketch, rough lines, traditional drawing technique, sketchbook aesthetic",
        "description": "Стиль художественного эскиза"
    }
}

# Позы для фотосессии
# Базовые позы (без указания взгляда)
POSES = {
    "standing": {
        "name": "🧍 Стоя",
        "prompt_addition": "standing pose, full body",
        "description": "В полный рост"
    },
    "sitting": {
        "name": "🪑 Сидя",
        "prompt_addition": "sitting pose, relaxed",
        "description": "Сидячая поза"
    },
    "walking": {
        "name": "🏃 В движении",
        "prompt_addition": "walking pose, motion, dynamic movement, natural stride",
        "description": "Динамичная поза в движении"
    },
    "model": {
        "name": "💃 Поза модели",
        "prompt_addition": "professional model pose, elegant posture, fashion pose",
        "description": "Профессиональная модельная поза"
    },
    "half_body": {
        "name": "👔 Поясной портрет",
        "prompt_addition": "half body portrait, waist up",
        "description": "По пояс"
    },
    "closeup": {
        "name": "🔍 Крупный план",
        "prompt_addition": "close-up portrait, face only",
        "description": "Только лицо, крупно"
    }
}

# Направление взгляда
GAZE = {
    "to_camera": {
        "name": "📷 В камеру",
        "prompt_addition": "looking directly at camera, making eye contact",
        "description": "Смотрит прямо в объектив"
    },
    "away": {
        "name": "👀 В сторону",
        "prompt_addition": "looking away from camera, candid style, gaze averted",
        "description": "Взгляд отведён в сторону"
    },
    "profile": {
        "name": "↪️ Профиль",
        "prompt_addition": "profile shot, looking to the side, silhouette view",
        "description": "Чистый профиль"
    }
}
# Форматы для фотосессии
PHOTOSHOOT_FORMATS = {
    "vertical_4_3": {
        "name": "📱 Вертикаль 4:3",
        "width": 768,
        "height": 1024,
        "description": "Вертикальный формат для Instagram, TikTok"
    },
    "horizontal_16_9": {
        "name": "📸 Горизонтальный 16:9",
        "width": 1024,
        "height": 576,
        "description": "Горизонтальный формат для YouTube, Facebook"
    }
}

def build_photoshoot_prompt(style_key: str, pose_key: str = None, gaze_key: str = None, user_prompt: str = "") -> str:
    """Собирает полный промпт для AI Photoshoot с учётом позы и взгляда"""
    style = PHOTOSHOOT_REALISM.get(style_key, PHOTOSHOOT_REALISM["portrait"])
    base_prompt = style["base_prompt"]
    
    # Добавляем позу
    if pose_key and pose_key in POSES:
        base_prompt = f"{base_prompt}, {POSES[pose_key]['prompt_addition']}"
    
    # Добавляем взгляд
    if gaze_key and gaze_key in GAZE:
        base_prompt = f"{base_prompt}, {GAZE[gaze_key]['prompt_addition']}"
    
    # Добавляем пользовательский промпт
    if user_prompt:
        base_prompt = f"{base_prompt}, {user_prompt}"
    
    # Финальные улучшения для фотореализма
    base_prompt = f"{base_prompt}, photorealistic, professional photography, natural lighting, save face like on reference"
    
    return base_prompt

def get_photoshoot_negative_prompt(style_key: str) -> str:
    """Возвращает негативный промпт для фотосессии"""
    style = PHOTOSHOOT_REALISM.get(style_key, PHOTOSHOOT_REALISM["portrait"])
    return style["negative"]

def build_ai_styles_prompt(style_key: str, user_prompt: str = "") -> str:
    """Собирает промпт для AI Styles"""
    if style_key in AI_STYLES:
        base_style = AI_STYLES[style_key]["prompt"]
        if user_prompt:
            return f"{base_style}, {user_prompt}"
        return base_style
    return user_prompt
