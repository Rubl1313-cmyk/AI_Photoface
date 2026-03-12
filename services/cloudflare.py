# services/cloudflare.py
"""
Сервис для работы с Cloudflare Workers AI.
Поддерживает:
- Dreamshaper-8-LCM (быстрая img2img) для AI Photoshoot и AI Styles
- FLUX.1-schnell (text-to-image) для AIMage
- Возможность выбора модели img2img через переменную окружения IMG2IMG_MODEL
"""
import httpx
import base64
import logging
import os
import io
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Константы
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

# Модель для img2img (можно переопределить через переменную окружения)
# Доступные варианты: "dreamshaper", "sdxl", "lightning"
IMG2IMG_MODEL = os.getenv("IMG2IMG_MODEL", "sdxl").lower()

# Словарь с параметрами моделей
MODEL_CONFIGS = {
    "dreamshaper": {
        "name": "@cf/lykon/dreamshaper-8-lcm",
        "default_steps": 12,
        "default_guidance": 7.5,
        "strength_range": (0.0, 1.0),
        "description": "Быстрая модель, хороша для стилей и фотореализма"
    },
    "sdxl": {
        "name": "@cf/stabilityai/stable-diffusion-xl-base-1.0",
        "default_steps": 20,
        "default_guidance": 7.5,
        "strength_range": (0.0, 1.0),
        "description": "Высокое качество, но медленнее"
    },
    "lightning": {
        "name": "@cf/bytedance/stable-diffusion-xl-lightning",
        "default_steps": 8,
        "default_guidance": 3.5,
        "strength_range": (0.0, 1.0),
        "description": "Очень быстрая, немного уступает в деталях"
    }
}

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def prepare_reference_image(image_bytes: bytes, target_size: int = 1024) -> bytes:
    """
    Подготавливает референсное изображение:
    - Масштабирует с сохранением пропорций, чтобы большая сторона стала target_size
    - Добавляет чёрные полосы (padding) до квадрата target_size x target_size
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        ratio = target_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        new_img = Image.new("RGB", (target_size, target_size), (0, 0, 0))
        left = (target_size - new_size[0]) // 2
        top = (target_size - new_size[1]) // 2
        new_img.paste(img, (left, top))
        
        output = io.BytesIO()
        new_img.save(output, format="JPEG", quality=95, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Image preparation error: {e}")
        return image_bytes

def enhance_image_quality(image_bytes: bytes, mode: str = "auto") -> bytes:
    """Улучшение качества изображения (без изменений)"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        if mode == "photoshoot":
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.15)
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.05)
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.02)
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            img = img.filter(ImageFilter.SMOOTH_MORE)
        elif mode == "styles":
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.15)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.05)
        else:  # auto
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.2)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
        
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=98, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Enhancement error: {e}")
        return image_bytes

def compress_image(image_bytes: bytes, max_kb: int = 400) -> bytes:
    """Сжатие изображения"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > 1024:
            ratio = 1024 / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        for quality in range(95, 70, -5):
            output.seek(0)
            output.truncate(0)
            img.save(output, format="JPEG", quality=quality, optimize=True)
            if len(output.getvalue()) / 1024 <= max_kb:
                return output.getvalue()
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Compression error: {e}")
        return image_bytes

# ================== УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ IMG2IMG ==================

async def generate_img2img(
    prompt: str,
    reference_image: Optional[bytes] = None,
    width: int = 768,
    height: int = 768,
    steps: Optional[int] = None,
    guidance: Optional[float] = None,
    strength: float = 0.7,
    negative_prompt: str = "",
    enhance_mode: str = "photoshoot"
) -> Optional[bytes]:
    """
    Универсальная генерация с выбранной img2img моделью.
    Параметры steps и guidance берутся из конфига модели, если не указаны явно.
    """
    config = MODEL_CONFIGS.get(IMG2IMG_MODEL, MODEL_CONFIGS["sdxl"])
    model_name = config["name"]
    
    data = {
        "prompt": prompt.strip(),
        "model": model_name,
        "width": min(768, width),
        "height": min(768, height),
        "num_steps": steps if steps is not None else config["default_steps"],
        "guidance": guidance if guidance is not None else config["default_guidance"],
        "strength": strength,
    }
    
    if negative_prompt:
        data["negative_prompt"] = negative_prompt.strip()
    
    if reference_image:
        prepared = prepare_reference_image(reference_image, target_size=1024)
        compressed = compress_image(prepared)
        data["image_b64"] = base64.b64encode(compressed).decode()
        logger.info(f"📎 Reference image added (image_b64): {len(data['image_b64'])} chars")
    
    logger.info(f"🎨 {model_name} ({enhance_mode}, strength={strength}, steps={data['num_steps']}): {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            resp = await client.post(
                CF_WORKER_URL,
                json=data,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("success") and result.get("images"):
                image_b64 = result["images"][0]
                if len(image_b64) < 1000:
                    logger.error(f"❌ Invalid base64 image (len={len(image_b64)})")
                    return None
                image_bytes = base64.b64decode(image_b64)
                enhanced = enhance_image_quality(image_bytes, mode=enhance_mode)
                logger.info(f"✅ {model_name} success: {len(enhanced)} bytes")
                return enhanced
            else:
                logger.error(f"❌ {model_name} error: {result}")
                return None
        except Exception as e:
            logger.error(f"❌ {model_name} error: {e}")
            return None

# ================== ГЕНЕРАЦИЯ С FLUX.1-SCHNELL (БЕЗ РЕФЕРЕНСА) ==================

async def generate_with_flux_schnell(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance: float = 3.5,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Быстрая генерация для AIMage (без референса)"""
    data = {
        "prompt": prompt.strip(),
        "model": "@cf/black-forest-labs/flux-1-schnell",
        "width": min(1024, width),
        "height": min(1024, height),
        "num_steps": steps,
        "guidance_scale": guidance,
        "num_outputs": 1
    }
    if negative_prompt:
        data["negative_prompt"] = negative_prompt.strip()
    
    logger.info(f"⚡ FLUX.1-schnell: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(CF_WORKER_URL, json=data, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            result = resp.json()
            if result.get("success") and result.get("images"):
                image_b64 = result["images"][0]
                image_bytes = base64.b64decode(image_b64)
                enhanced = enhance_image_quality(image_bytes, mode="auto")
                logger.info(f"✅ FLUX.1-schnell success: {len(enhanced)} bytes")
                return enhanced
            else:
                logger.error(f"❌ FLUX.1-schnell error: {result}")
                return None
        except Exception as e:
            logger.error(f"❌ FLUX.1-schnell error: {e}")
            return None

# ================== УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ==================

async def generate_best_quality(
    prompt: str,
    category: str = "photoshoot",
    reference_image: Optional[bytes] = None,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = "",
    strength: float = 0.7
) -> Optional[bytes]:
    """
    Автоматический выбор модели в зависимости от категории:
    - "photoshoot", "ai_styles" → img2img модель (настраиваемая через IMG2IMG_MODEL)
    - иначе → FLUX.1-schnell
    """
    if category in ["photoshoot", "ai_styles"]:
        enhance_mode = "photoshoot" if category == "photoshoot" else "styles"
        # Для стилей можно увеличить strength
        if category == "ai_styles":
            strength = max(strength, 0.8)  # чуть выше для стилизации
        return await generate_img2img(
            prompt=prompt,
            reference_image=reference_image,
            width=width,
            height=height,
            strength=strength,
            negative_prompt=negative_prompt,
            enhance_mode=enhance_mode
        )
    else:
        return await generate_with_flux_schnell(
            prompt=prompt,
            width=width,
            height=height,
            steps=4,
            guidance=3.5,
            negative_prompt=negative_prompt
        )
