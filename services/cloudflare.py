import aiohttp
import logging
import os
import io
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)

CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def prepare_reference_image(image_bytes: bytes, target_size: int = 512) -> bytes:
    """
    Подготавливает референсное изображение для FLUX.2:
    - Обрезает до квадрата по центру (crop)
    - Масштабирует до target_size (макс. 512)
    - Возвращает JPEG с высоким качеством
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Обрезка до квадрата по центру
        min_side = min(img.size)
        left = (img.width - min_side) // 2
        top = (img.height - min_side) // 2
        img = img.crop((left, top, left + min_side, top + min_side))
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=95, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Image preparation error: {e}")
        return image_bytes

# ================== ГЕНЕРАЦИЯ С FLUX.2 (с референсом) ==================

async def generate_flux_klein(
    prompt: str,
    reference_image: Optional[bytes] = None,
    width: int = 1024,
    height: int = 1024,
    guidance: float = 7.5
) -> Optional[bytes]:
    """
    Генерация с FLUX.2-klein (с референсом).
    Возвращает бинарное изображение или None при ошибке.
    """
    # Подготавливаем изображение, если есть
    image_data = None
    if reference_image:
        image_data = prepare_reference_image(reference_image, target_size=512)

    # Создаём multipart-данные
    data = aiohttp.FormData()
    data.add_field('prompt', prompt)
    data.add_field('width', str(width))
    data.add_field('height', str(height))
    data.add_field('guidance', str(guidance))

    if image_data:
        data.add_field('input_image_0',
                       image_data,
                       filename='reference.jpg',
                       content_type='image/jpeg')

    async with aiohttp.ClientSession() as session:
        async with session.post(CF_WORKER_URL, data=data) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                error_text = await resp.text()
                logger.error(f"❌ FLUX.2 error {resp.status}: {error_text}")
                return None

# ================== ГЕНЕРАЦИЯ С FLUX.1 (без референса) ==================

async def generate_flux_schnell(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance: float = 3.5
) -> Optional[bytes]:
    """
    Генерация с FLUX.1-schnell (без референса).
    Возвращает бинарное изображение или None при ошибке.
    """
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": guidance
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(CF_WORKER_URL, json=payload) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                error_text = await resp.text()
                logger.error(f"❌ FLUX.1 error {resp.status}: {error_text}")
                return None

# ================== ОБЁРТКИ ДЛЯ ТРЁХ РЕЖИМОВ ==================

async def generate_photoshoot(
    prompt: str,
    reference_image: bytes,
    width: int = 768,
    height: int = 1024,
    guidance: float = 7.5
) -> Optional[bytes]:
    """
    Режим AI Photoshoot (фотореализм). Использует FLUX.2-klein.
    """
    return await generate_flux_klein(prompt, reference_image, width, height, guidance)

async def generate_style(
    prompt: str,
    reference_image: bytes,
    width: int = 1024,
    height: int = 576,
    guidance: float = 7.5
) -> Optional[bytes]:
    """
    Режим AI Styles. Использует FLUX.2-klein.
    """
    return await generate_flux_klein(prompt, reference_image, width, height, guidance)

async def generate_ai_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance: float = 3.5
) -> Optional[bytes]:
    """
    Режим AIMage (генерация без референса). Использует FLUX.1-schnell.
    """
    return await generate_flux_schnell(prompt, width, height, steps, guidance)
