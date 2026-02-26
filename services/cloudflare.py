import httpx
import logging
from config import CF_WORKER_URL, CF_API_KEY

logger = logging.getLogger(__name__)

# 🔥 Хэши известных "test/placeholder" изображений (если Cloudflare возвращает заглушку)
TEST_IMAGE_HASHES = [
    "d41d8cd98f00b204e9800998ecf8427e",  # пустой файл
    # Добавь хэши если узнаешь что Cloudflare возвращает конкретную заглушку
]

def _is_test_image(data: bytes) -> bool:
    """Проверяет не является ли изображение тестовой заглушкой"""
    if len(data) < 1000:  # Слишком маленькое
        return True
    # Можно добавить проверку по хэшу если нужно:
    # import hashlib
    # h = hashlib.md5(data).hexdigest()
    # return h in TEST_IMAGE_HASHES
    return False

async def generate_with_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4
) -> bytes:
    """Генерация через Cloudflare Worker с проверкой на заглушку"""
    
    # 🔥 Усиливаем промпт если он слишком короткий
    if len(prompt.split()) < 5:
        prompt = f"detailed portrait, {prompt}, professional photography"
        logger.info(f"🔧 Усилен короткий промпт: {prompt}")
    
    async with httpx.AsyncClient(timeout=90.0) as client:
        data = {
            "prompt": prompt,
            "width": str(width),
            "height": str(height),
            "steps": str(steps),
        }
        logger.info(f"📡 Cloudflare request: prompt='{prompt[:100]}...', size={width}x{height}")
        
        response = await client.post(
            CF_WORKER_URL.strip(),
            headers={"Authorization": f"Bearer {CF_API_KEY}"},
            data=data,
            timeout=90
        )
        response.raise_for_status()
        
        content = response.content
        
        # 🔥 Проверка на заглушку
        if _is_test_image(content):
            logger.warning(f"⚠️ Cloudflare вернул подозрительное изображение ({len(content)} bytes)")
            # Не выбрасываем ошибку — пусть бот отправит что есть, но с предупреждением в логе
        
        if len(content) < 1000:
            raise ValueError(f"Пустой ответ от генератора ({len(content)} bytes)")
        
        logger.info(f"✅ Cloudflare: {len(content)} bytes")
        return content
