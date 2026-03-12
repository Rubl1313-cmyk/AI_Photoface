# services/cloudflare.py
"""
🔥 Обновленный сервис Cloudflare Workers AI для AI PhotoStudio 2.0
Поддержка FLUX.2-klein с корректным референсом (input_image) и подготовкой изображения
Учтены режимы: AI Photoshoot (фотореализм) и AI Styles (различные стили)
"""
import httpx
import base64
import logging
import os
import io
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Модели Cloudflare Workers AI
CF_MODELS = {
    "flux_klein": "@cf/black-forest-labs/flux-2-klein-4b",  # Для фотореализма и стилей с референсами
    "flux_schnell": "@cf/black-forest-labs/flux-1-schnell",  # Для быстрой генерации без референса
}

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def prepare_reference_image(image_bytes: bytes, target_size: int = 1024) -> bytes:
    """
    Подготавливает референсное изображение для FLUX.2-klein:
    - Обрезает до квадрата по центру
    - Изменяет размер до target_size (кратно 16, оптимально 1024)
    - Возвращает JPEG с высоким качеством
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Обрезка до квадрата по центру
        min_side = min(img.size)
        left = (img.width - min_side) / 2
        top = (img.height - min_side) / 2
        right = (img.width + min_side) / 2
        bottom = (img.height + min_side) / 2
        img = img.crop((left, top, right, bottom))
        # Ресайз до target_size
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=95, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Image preparation error: {e}")
        return image_bytes  # fallback – возвращаем оригинал

def enhance_image_quality(image_bytes: bytes, mode: str = "auto") -> bytes:
    """
    Улучшение качества изображения
    mode: 
        'auto' - автоматически (для AIMage)
        'photoshoot' - для фотосессии (усиленная резкость, контраст, гладкость кожи)
        'styles' - для стилей (меньше обработки, сохраняется арт-стиль)
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        if mode == "photoshoot":
            # Улучшения для фотореализма
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
            # Для стилей - меньше обработки, сохраняем арт-стиль
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
    """Сжатие изображения (используется для уменьшения размера перед отправкой)"""
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

# ================== ГЕНЕРАЦИЯ С FLUX.2-KLEIN (С РЕФЕРЕНСОМ) ==================

async def generate_with_flux_klein(
    prompt: str,
    reference_image: bytes = None,
    width: int = 1024,
    height: int = 1024,
    steps: int = 28,
    guidance: float = 7.5,
    negative_prompt: str = "",  # теперь передаётся извне
    enhance_mode: str = "photoshoot"
) -> Optional[bytes]:
    """
    Генерация с FLUX.2-klein для AI Photoshoot и AI Styles.
    Поддерживает референсное изображение через поле input_image.
    """
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # Подготавливаем данные для JSON
    data = {
        "prompt": prompt.strip(),
        "model": CF_MODELS["flux_klein"],
        "width": min(1024, width),
        "height": min(1024, height),
        "num_steps": min(50, max(20, int(steps))),
        "guidance_scale": guidance,
        "num_outputs": 1
    }
    
    # Если передан негативный промпт, добавляем его
    if negative_prompt:
        data["negative_prompt"] = negative_prompt.strip()
    
    # Добавляем референсное изображение (если есть)
    if reference_image:
        # Шаг 1: подготавливаем изображение (обрезаем до квадрата 1024x1024)
        prepared_ref = prepare_reference_image(reference_image, target_size=1024)
        # Шаг 2: сжимаем до разумного размера (опционально, но улучшает скорость)
        compressed_ref = compress_image(prepared_ref)
        # Шаг 3: кодируем в base64
        ref_b64 = base64.b64encode(compressed_ref).decode()
        # Шаг 4: используем правильное поле: input_image
        data["input_image"] = ref_b64
        logger.info(f"📎 Reference image added as input_image: {len(ref_b64)} chars")
    
    logger.info(f"🎯 FLUX.2-klein ({enhance_mode} mode): {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            # Отправляем JSON с полем input_image
            resp = await client.post(
                url,
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
                # Улучшаем качество в соответствии с режимом
                enhanced = enhance_image_quality(image_bytes, mode=enhance_mode)
                logger.info(f"✅ FLUX.2-klein success: {len(enhanced)} bytes")
                return enhanced
            else:
                logger.error(f"❌ FLUX.2-klein error: {result}")
                return None
                
        except Exception as e:
            logger.error(f"❌ FLUX.2-klein error: {e}")
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
    """
    Быстрая генерация с FLUX.1-schnell для AIMage.
    """
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = {
        "prompt": prompt.strip(),
        "model": CF_MODELS["flux_schnell"],
        "width": min(1024, width),
        "height": min(1024, height),
        "num_steps": steps,
        "guidance_scale": guidance,
        "num_outputs": 1
    }
    
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt.strip()
    
    logger.info(f"⚡ FLUX.1-schnell: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
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

# ================== АВТОВЫБОР МОДЕЛИ ==================

async def generate_best_quality(
    prompt: str,
    category: str = "photoshoot",
    reference_image: bytes = None,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""  # добавили возможность передать негативный промпт
) -> Optional[bytes]:
    """
    Автоматический выбор модели в зависимости от категории
    """
    if category in ["photoshoot", "ai_styles"]:
        enhance_mode = "photoshoot" if category == "photoshoot" else "styles"
        return await generate_with_flux_klein(
            prompt=prompt,
            reference_image=reference_image,
            width=width,
            height=height,
            steps=28,
            guidance=7.5,
            negative_prompt=negative_prompt,
            enhance_mode=enhance_mode
        )
    else:
        return await generate_with_flux_schnell(
            prompt=prompt,
            width=width,
            height=height,
            negative_prompt=negative_prompt
        )
