import aiohttp
import logging
import os
import io
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)

CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

def prepare_reference_image(image_bytes: bytes, target_size: int = 512) -> bytes:
    """Обрезает до квадрата по центру и масштабирует"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
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

async def generate_flux_klein(
    prompt: str,
    reference_image: Optional[bytes] = None,
    width: int = 1024,
    height: int = 1024,
    guidance: float = 7.5
) -> Optional[bytes]:
    """Генерация с FLUX.2-klein. Возвращает JPEG bytes."""
    image_data = None
    if reference_image:
        image_data = prepare_reference_image(reference_image, target_size=512)

    data = aiohttp.FormData()
    data.add_field('prompt', prompt)
    data.add_field('width', str(width))
    data.add_field('height', str(height))
    data.add_field('guidance', str(guidance))
    if image_data:
        data.add_field('input_image_0', image_data, filename='ref.jpg', content_type='image/jpeg')

    async with aiohttp.ClientSession() as session:
        async with session.post(CF_WORKER_URL, data=data) as resp:
            if resp.status == 200:
                content_type = resp.headers.get('Content-Type', '')
                image_bytes = await resp.read()
                logger.info(f"✅ Worker вернул {len(image_bytes)} байт, Content-Type: {content_type}")

                # Проверяем, не вернул ли Worker ошибку в виде текста
                if not content_type.startswith('image/'):
                    # Возможно, это текст ошибки
                    try:
                        error_text = image_bytes.decode('utf-8')
                        logger.error(f"❌ Worker вернул текст вместо изображения: {error_text[:200]}")
                    except:
                        logger.error("❌ Worker вернул неизвестный тип данных")
                    return None

                # Конвертируем в JPEG для надёжности
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    output = io.BytesIO()
                    img.save(output, format='JPEG', quality=95)
                    return output.getvalue()
                except Exception as e:
                    logger.error(f"❌ Ошибка конвертации изображения: {e}")
                    return None
            else:
                error_text = await resp.text()
                logger.error(f"❌ FLUX.2 error {resp.status}: {error_text}")
                return None

async def generate_flux_schnell(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance: float = 3.5
) -> Optional[bytes]:
    """Генерация с FLUX.1-schnell. Возвращает JPEG bytes."""
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
                content_type = resp.headers.get('Content-Type', '')
                image_bytes = await resp.read()
                logger.info(f"✅ Worker вернул {len(image_bytes)} байт, Content-Type: {content_type}")

                if not content_type.startswith('image/'):
                    try:
                        error_text = image_bytes.decode('utf-8')
                        logger.error(f"❌ Worker вернул текст вместо изображения: {error_text[:200]}")
                    except:
                        logger.error("❌ Worker вернул неизвестный тип данных")
                    return None

                # Конвертируем в JPEG
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    output = io.BytesIO()
                    img.save(output, format='JPEG', quality=95)
                    return output.getvalue()
                except Exception as e:
                    logger.error(f"❌ Ошибка конвертации изображения: {e}")
                    return None
            else:
                error_text = await resp.text()
                logger.error(f"❌ FLUX.1 error {resp.status}: {error_text}")
                return None

# Обёртки для трёх режимов
async def generate_photoshoot(prompt: str, reference_image: bytes, width: int = 768, height: int = 1024, guidance: float = 7.5) -> Optional[bytes]:
    return await generate_flux_klein(prompt, reference_image, width, height, guidance)

async def generate_style(prompt: str, reference_image: bytes, width: int = 1024, height: int = 576, guidance: float = 7.5) -> Optional[bytes]:
    return await generate_flux_klein(prompt, reference_image, width, height, guidance)

async def generate_ai_image(prompt: str, width: int = 1024, height: int = 1024, steps: int = 4, guidance: float = 3.5) -> Optional[bytes]:
    return await generate_flux_schnell(prompt, width, height, steps, guidance)
