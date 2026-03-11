# services/phoenix_cloudflare.py
"""
🔥 Phoenix & Lucid Origin - Лучшие модели Cloudflare Workers AI
Phoenix 1.0: лучший для текста и промптов
Lucid Origin: лучший для фотореализма
"""
import httpx
import base64
import logging
import os
import io
from typing import Optional, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Лучшие модели Cloudflare 2024
CF_MODELS = {
    "phoenix": "@cf/leonardo/phoenix-1.0",      # Лучший для промптов и текста
    "lucid": "@cf/leonardo/lucid-origin",       # Лучший для фотореализма
    "sdxl_lightning": "@cf/stabilityai/stable-diffusion-xl-base-1.0",
    "sdxl_turbo": "@cf/stabilityai/stable-diffusion-xl-turbo"
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

async def generate_with_phoenix(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    guidance: float = 4.0,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Генерация с Phoenix 1.0 - лучшая модель для промптов"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = {
        "prompt": prompt.strip(),
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": guidance,
        "model": CF_MODELS["phoenix"]
    }
    
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt.strip()
    
    logger.info(f"🔥 Phoenix generation: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            
            enhanced = enhance_image_quality(resp.content)
            logger.info(f"✅ Phoenix success: {len(enhanced)} bytes")
            return enhanced
            
        except Exception as e:
            logger.error(f"❌ Phoenix error: {e}")
            return None

async def generate_with_lucid(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    guidance: float = 4.0,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Генерация с Lucid Origin - лучшая модель для фотореализма"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = {
        "prompt": prompt.strip(),
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": guidance,
        "model": CF_MODELS["lucid"]
    }
    
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt.strip()
    
    logger.info(f"🎨 Lucid generation: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            
            enhanced = enhance_image_quality(resp.content)
            logger.info(f"✅ Lucid success: {len(enhanced)} bytes")
            return enhanced
            
        except Exception as e:
            logger.error(f"❌ Lucid error: {e}")
            return None

async def generate_photoshoot_with_face(
    prompt: str,
    source_image_bytes: bytes,
    model: str = "lucid",  # lucid лучше для фотореализма
    width: int = 1024,
    height: int = 1024,
    strength: float = 0.8,
    guidance: float = 6.0,
    steps: int = 25
) -> Optional[bytes]:
    """Фотосессия с заменой лица"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # Сжимаем исходное изображение
    compressed = compress_image(source_image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    
    # Создаем маску для лица
    img = Image.open(io.BytesIO(compressed))
    w, h = img.size
    
    mask = Image.new("L", (w, h), 255)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    
    # Область лица
    face_x = int(w * 0.3)
    face_y = int(h * 0.1)
    face_w = int(w * 0.4)
    face_h = int(h * 0.4)
    
    draw.ellipse([face_x, face_y, face_x + face_w, face_y + face_h], fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=15))
    
    mask_bytes = io.BytesIO()
    mask.save(mask_bytes, format="PNG")
    mask_b64 = base64.b64encode(mask_bytes.getvalue()).decode()
    
    payload = {
        "prompt": f"{prompt}, professional photography, ultra realistic, sharp focus, natural lighting",
        "image_b64": image_b64,
        "mask_b64": mask_b64,
        "width": width,
        "height": height,
        "strength": strength,
        "guidance_scale": guidance,
        "num_steps": steps,
        "model": CF_MODELS.get(model, CF_MODELS["lucid"]),
        "negative_prompt": "cartoon, anime, artificial, ugly, deformed, blurry, low quality"
    }
    
    logger.info(f"📸 Photoshoot with {model}: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            
            enhanced = enhance_image_quality(resp.content)
            logger.info(f"✅ Photoshoot success: {len(enhanced)} bytes")
            return enhanced
            
        except Exception as e:
            logger.error(f"❌ Photoshoot error: {e}")
            return None

async def generate_best_quality(
    prompt: str,
    style: str = "realistic",
    width: int = 1024,
    height: int = 1024
) -> Optional[bytes]:
    """Автоматический выбор лучшей модели"""
    
    if style == "realistic":
        # Lucid лучше для фотореализма
        return await generate_with_lucid(
            prompt=f"{prompt}, photorealistic, professional photography, sharp focus",
            width=width,
            height=height,
            steps=25,
            guidance=4.0
        )
    else:
        # Phoenix лучше для креативных стилей
        return await generate_with_phoenix(
            prompt=prompt,
            width=width,
            height=height,
            steps=25,
            guidance=4.0
        )
