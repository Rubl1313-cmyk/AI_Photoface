# services/cloudflare.py
"""
🔥 Обновленный сервис Cloudflare Workers AI для AI PhotoStudio 2.0
Поддержка FLUX.2-klein и FLUX.1-schnell для 3 категорий
"""
import httpx
import base64
import logging
import os
import io
from typing import Optional, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Модели Cloudflare Workers AI
CF_MODELS = {
    "flux_klein": "@cf/black-forest-labs/flux-2-klein-4b",  # Для фотореализма с референсами
    "flux_schnell": "@cf/black-forest-labs/flux-1-schnell",  # Для быстрой генерации
}

def enhance_image_quality(image_bytes: bytes) -> bytes:
    """Улучшение качества изображения"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Улучшение резкости
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.2)
        
        # Улучшение контрастности
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.1)
        
        # Unsharp mask
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

def create_face_mask(image_bytes: bytes) -> str:
    """Создание маски для лица"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        
        # Создаем маску для лица (центральная область)
        mask = Image.new("L", (w, h), 255)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        
        # Область лица
        face_x = int(w * 0.25)
        face_y = int(h * 0.15)
        face_w = int(w * 0.5)
        face_h = int(h * 0.5)
        
        draw.ellipse([face_x, face_y, face_x + face_w, face_y + face_h], fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=20))
        
        mask_bytes = io.BytesIO()
        mask.save(mask_bytes, format="PNG")
        mask_b64 = base64.b64encode(mask_bytes.getvalue()).decode()
        return mask_b64
        
    except Exception as e:
        logger.error(f"❌ Mask creation error: {e}")
        return ""

async def generate_with_flux_klein(
    prompt: str,
    reference_image: bytes = None,
    width: int = 1024,
    height: int = 1024,
    steps: int = 28,
    guidance: float = 7.5,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    Генерация с FLUX.2-klein для AI Photoshoot и AI Styles
    Поддержка референсных изображений для сохранения лица
    """
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = {
        "prompt": prompt.strip(),
        "model": CF_MODELS["flux_klein"],
        "width": min(1024, width),
        "height": min(1024, height),
        "num_steps": min(50, max(20, int(steps))),
        "guidance_scale": guidance,
        "num_outputs": 1
    }
    
    # Добавляем референсное изображение если есть
    if reference_image:
        compressed_ref = compress_image(reference_image)
        ref_b64 = base64.b64encode(compressed_ref).decode()
        payload["image_b64"] = ref_b64
        
        # Создаем маску для лица
        mask_b64 = create_face_mask(compressed_ref)
        if mask_b64:
            payload["mask_b64"] = mask_b64
    
    # Улучшенный негативный промпт для фотореализма
    enhanced_negative = "cartoon, anime, painting, drawing, illustration, 3d, render, blurry, low quality, distorted face, artificial, plastic, wax figure, uncanny valley, oversaturated, unnatural colors, artifacts, noise, compression artifacts, watermark, signature, text, multiple faces, extra limbs, deformed hands, bad anatomy"
    full_negative = f"{enhanced_negative}, {negative_prompt}" if negative_prompt else enhanced_negative
    
    if full_negative:
        payload["negative_prompt"] = full_negative.strip()
    
    model_type = "с референсом" if reference_image else "без референса"
    logger.info(f"🎯 FLUX.2-klein ({model_type}): {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=300) as client:
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
                
                # Улучшение качества
                enhanced = enhance_image_quality(image_bytes)
                
                logger.info(f"✅ FLUX.2-klein success: {len(enhanced)} bytes")
                return enhanced
            else:
                logger.error(f"❌ FLUX.2-klein error: {result}")
                return None
                
        except Exception as e:
            logger.error(f"❌ FLUX.2-klein error: {e}")
            return None

async def generate_with_flux_schnell(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance: float = 3.5,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    Быстрая генерация с FLUX.1-schnell для AIMage
    Оптимизирована для скорости без референсов
    """
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = {
        "prompt": prompt.strip(),
        "model": CF_MODELS["flux_schnell"],
        "width": min(1024, width),
        "height": min(1024, height),
        "num_steps": steps,  # Мало шагов для скорости
        "guidance_scale": guidance,
        "num_outputs": 1
    }
    
    # Базовый негативный промпт
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
                
                # Легкое улучшение качества
                enhanced = enhance_image_quality(image_bytes)
                
                logger.info(f"✅ FLUX.1-schnell success: {len(enhanced)} bytes")
                return enhanced
            else:
                logger.error(f"❌ FLUX.1-schnell error: {result}")
                return None
                
        except Exception as e:
            logger.error(f"❌ FLUX.1-schnell error: {e}")
            return None

async def generate_best_quality(
    prompt: str,
    category: str = "photoshoot",
    reference_image: bytes = None,
    width: int = 1024,
    height: int = 1024
) -> Optional[bytes]:
    """
    Автоматический выбор модели в зависимости от категории
    """
    if category in ["photoshoot", "ai_styles"]:
        # FLUX.2-klein для категорий с референсами
        return await generate_with_flux_klein(
            prompt=prompt,
            reference_image=reference_image,
            width=width,
            height=height,
            steps=28,
            guidance=7.5
        )
    else:
        # FLUX.1-schnell для AIMage
        return await generate_with_flux_schnell(
            prompt=prompt,
            width=width,
            height=height
        )
