# services/enhancement.py
"""
🎨 Image Enhancement Services
Post-processing for better quality
"""
import io
import logging
from PIL import Image, ImageEnhance, ImageFilter
from typing import Optional

logger = logging.getLogger(__name__)

def enhance_image_quality(
    image_bytes: bytes,
    sharpness: float = 1.3,
    contrast: float = 1.1,
    brightness: float = 1.05,
    quality: int = 95
) -> bytes:
    """Улучшение качества изображения"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Увеличение резкости
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
        
        # Увеличение контраста
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(contrast)
        
        # Увеличение яркости
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(brightness)
        
        # Сохранение с высоким качеством
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue()
    
    except Exception as e:
        logger.error(f"❌ Enhancement error: {e}")
        return image_bytes

def reduce_noise(image_bytes: bytes, radius: float = 1.0) -> bytes:
    """Уменьшение шума"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))
        
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=95, optimize=True)
        return out.getvalue()
    
    except Exception as e:
        logger.error(f"❌ Noise reduction error: {e}")
        return image_bytes

def upscale_image(image_bytes: bytes, scale: int = 2) -> bytes:
    """Увеличение разрешения изображения"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        new_width = width * scale
        new_height = height * scale
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=95, optimize=True)
        return out.getvalue()
    
    except Exception as e:
        logger.error(f"❌ Upscale error: {e}")
        return image_bytes

def validate_image_quality(image_bytes: bytes) -> tuple[bool, str]:
    """Проверка качества изображения"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        
        # Минимальный размер
        if w < 512 or h < 512:
            return False, "❌ Изображение слишком маленькое (минимум 512x512)"
        
        # Проверка на артефакты
        pixels = list(img.convert("RGB").getdata())
        avg_brightness = sum(sum(p[:3]) for p in pixels) / (len(pixels) * 3)
        
        if avg_brightness < 20:
            return False, "❌ Изображение слишком тёмное"
        if avg_brightness > 240:
            return False, "❌ Изображение слишком светлое"
        
        return True, ""
    
    except Exception as e:
        logger.error(f"❌ Validation error: {e}")
        return False, f"❌ Ошибка проверки: {str(e)}"
