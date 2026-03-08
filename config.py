# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# 🔑 TELEGRAM
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# 🔑 WEBHOOK
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"https://ai-photoface.onrender.com{WEBHOOK_PATH}").strip()

# 🔑 LIMITS
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "50"))

# 🔑 EXTERNAL APIS
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
FACEFUSION_URL = os.getenv("FACEFUSION_URL", "https://Dmitry1313-facefusion-api.hf.space").strip()

# 🔑 BOT INFO
BOT_NAME = "🎨 AI PhotoStudio Pro"

#  ULTRA REALISTIC PROMPTS
ULTRA_REALISTIC_PROMPT = (
    "RAW photo, shot on Sony A7R IV with 85mm f/1.4 GM lens, "
    "natural skin texture with visible pores, subsurface scattering, "
    "realistic lighting, global illumination, professional photography, "
    "8k uhd, dslr quality, soft natural lighting, high quality, film grain, "
    "depth of field, bokeh, studio lighting, sharp focus, "
    "no cgi, no painting, no drawing, no illustration, no anime, "
    "photorealistic, hyperrealistic, ultra detailed"
)

NEGATIVE_PROMPT = (
    "blurry, low quality, distorted face, bad anatomy, deformed, "
    "disfigured, extra limbs, cgi, 3d render, cartoon, anime, drawing, "
    "painting, illustration, plastic skin, wax figure, doll, mannequin, "
    "airbrushed, fake, artificial, oversaturated, watermark, text, signature"
)

# 🎨 STYLE PROMPTS (улучшенные)
STYLE_PROMPTS = {
    "style_photorealistic": "professional photography, photorealistic, natural lighting",
    "style_hyperrealistic": "hyperrealistic, ultra detailed, 8k resolution, sharp focus",
    "style_cinematic": "cinematic shot, movie still, dramatic lighting, film grain",
    "style_art": "artistic interpretation, creative photography",
    "style_oil_painting": "oil painting style, classical art",
    "style_watercolor": "watercolor painting, soft edges",
    "style_sketch": "pencil sketch, black and white drawing",
    "style_cyberpunk": "cyberpunk, neon lights, futuristic city, blade runner style",
    "style_fantasy": "fantasy art, magical, epic atmosphere, mystical",
    "style_scifi": "science fiction, futuristic technology, space age",
    "style_space": "space background, cosmic, stellar, galaxies",
    "style_vintage": "vintage photo, retro style, old photograph, sepia",
    "style_noir": "film noir, black and white, dramatic shadows, detective style",
    "style_popart": "pop art, vibrant colors, warhol style, bold",
    "style_comic": "comic book style, graphic novel, superhero",
    "style_anime": "anime style, manga, japanese animation",
    "style_3d_render": "3D render, CGI, digital art, unreal engine",
    "style_pixel_art": "pixel art, 8-bit, retro game style",
    "style_impressionism": "impressionist painting, monet style, soft brushstrokes",
    "style_classical": "classical art, renaissance style, master painting",
    "style_surrealism": "surrealism, dali style, dreamlike, abstract",
}

# 🎯 SHOT TYPES
SHOT_PROMPTS = {
    "portrait": "portrait, close-up, head and shoulders, professional headshot",
    "fullbody": "full body shot, standing pose, full length portrait"
}

# 👤 GENDER PROMPTS
GENDER_PROMPTS = {
    "male": "professional photo of man, masculine features",
    "female": "professional photo of woman, feminine features"
}
