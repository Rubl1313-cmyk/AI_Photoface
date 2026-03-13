import aiohttp
import logging
import os
import io
from typing import Optional, List
from PIL import Image

logger = logging.getLogger(__name__)

CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

def prepare_reference_images(image_bytes_list: List[bytes], target_size: int = 512) -> List[Optional[bytes]]:
    """
    Подготавливает список референсных изображений для FLUX.2.
    - Каждое изображение обрезается до квадрата по центру.
    - Масштабируется до target_size (макс. 512, требование модели).
    - Конвертируется в RGB и сохраняется как JPEG с высоким качеством.
    - При ошибке возвращает None для этого элемента (не добавляем в запрос).
    
    Args:
        image_bytes_list: Список байтов исходных изображений
        target_size: Целевой размер (должен быть ≤ 512)
    
    Returns:
        Список подготовленных байтов или None для каждого
    """
    prepared = []
    for i, image_bytes in enumerate(image_bytes_list):
        if not image_bytes:
            prepared.append(None)
            continue
            
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
            prepared.append(output.getvalue())
            logger.info(f"✅ Референс {i} подготовлен: {target_size}x{target_size}")
        except Exception as e:
            logger.error(f"❌ Image preparation error for reference {i}: {e}")
            prepared.append(None)  # Не добавляем повреждённое изображение
    return prepared

async def generate_flux_klein(
    prompt: str,
    reference_images: Optional[List[bytes]] = None,
    width: int = 1024,
    height: int = 1024,
    guidance: float = 7.5
) -> Optional[bytes]:
    """
    Генерация с FLUX.2-klein (поддержка до 4 референсов).
    
    Args:
        prompt: Текстовое описание
        reference_images: Список байтов референсных изображений (максимум 4)
        width: Ширина выходного изображения
        height: Высота выходного изображения
        guidance: Guidance scale (по умолч. 7.5)
    
    Returns:
        Бинарные данные изображения (PNG) или None при ошибке
    """
    # Подготавливаем изображения (максимум 4)
    prepared_images = []
    if reference_images:
        prepared_images = prepare_reference_images(reference_images[:4])
    else:
        prepared_images = []

    # Создаём multipart/form-data
    data = aiohttp.FormData()
    data.add_field('prompt', prompt)
    data.add_field('width', str(width))
    data.add_field('height', str(height))
    data.add_field('guidance', str(guidance))

    # Добавляем все подготовленные референсы (до 4)
    for i, img_bytes in enumerate(prepared_images):
        if img_bytes is not None:  # Добавляем только успешно подготовленные
            data.add_field(
                f'input_image_{i}',
                img_bytes,
                filename=f'reference_{i}.jpg',
                content_type='image/jpeg'
            )
            logger.info(f"📎 Добавлен референс {i}")
        else:
            logger.warning(f"⚠️ Пропущен референс {i} (ошибка подготовки)")

    # Отправляем запрос
    async with aiohttp.ClientSession() as session:
        async with session.post(CF_WORKER_URL, data=data) as resp:
            if resp.status == 200:
                content_type = resp.headers.get('content-type', '')
                if 'image' in content_type:
                    image_data = await resp.read()
                    logger.info(f"✅ Получено изображение: {len(image_data)} байт, content-type: {content_type}")
                    return image_data
                else:
                    # Сервер вернул не изображение (JSON ошибки)
                    error_text = await resp.text()
                    logger.error(f"❌ Worker вернул не изображение (статус 200, content-type: {content_type}): {error_text[:200]}")
                    return None
            else:
                error_text = await resp.text()
                logger.error(f"❌ FLUX.2 error {resp.status}: {error_text}")
                return None

# Удобные обёртки для конкретных режимов (могут быть расширены для нескольких референсов)
async def generate_photoshoot(
    prompt: str,
    reference_image: bytes,
    width: int = 768,
    height: int = 1024,
    guidance: float = 7.5
) -> Optional[bytes]:
    """
    Режим AI Photoshoot (принимает один референс, но внутренняя функция поддерживает до 4).
    """
    return await generate_flux_klein(prompt, [reference_image], width, height, guidance)

async def generate_style(
    prompt: str,
    reference_image: bytes,
    width: int = 1024,
    height: int = 576,
    guidance: float = 7.5
) -> Optional[bytes]:
    """
    Режим AI Styles (принимает один референс, но внутренняя функция поддерживает до 4).
    """
    return await generate_flux_klein(prompt, [reference_image], width, height, guidance)

# FLUX.1-schnell (без референса)
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
