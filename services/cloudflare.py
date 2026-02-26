import httpx, logging
from config import CF_WORKER_URL, CF_API_KEY
logger = logging.getLogger(__name__)

async def generate_with_cloudflare(prompt: str, width: int = 1024, height: int = 1024, steps: int = 4) -> bytes:
    logger.info(f"📡 Cloudflare request:")
    logger.info(f"   URL: {CF_WORKER_URL}")
    logger.info(f"   Prompt: {prompt[:100]}...")
    logger.info(f"   Size: {width}x{height}")
    
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            r = await client.post(
                CF_WORKER_URL.strip(),
                headers={"Authorization": f"Bearer {CF_API_KEY}"},
                data={"prompt": prompt, "width": str(width), "height": str(height), "steps": str(steps)},
                timeout=90
            )
            
            logger.info(f"📥 Cloudflare response:")
            logger.info(f"   Status: {r.status_code}")
            logger.info(f"   Size: {len(r.content)} bytes")
            logger.info(f"   Content-Type: {r.headers.get('content-type', 'unknown')}")
            
            # 🔥 Проверка на тестовое изображение
            if len(r.content) < 5000:
                logger.warning(f"⚠️ Слишком маленький ответ ({len(r.content)} bytes) - возможно тестовая заглушка!")
            
            # Проверка что это действительно изображение
            if not r.content.startswith(b'\xff\xd8') and not r.content.startswith(b'\x89PNG'):
                logger.error(f"❌ Ответ не является изображением!")
                logger.error(f"   Первые байты: {r.content[:50]}")
                raise ValueError(f"Cloudflare вернул не изображение (статус {r.status_code})")
            
            if r.status_code != 200:
                raise ValueError(f"HTTP {r.status_code}: {r.text[:200]}")
            
            if len(r.content) < 1000:
                raise ValueError(f"Пустой ответ ({len(r.content)} bytes)")
            
            logger.info(f"✅ Cloudflare: {len(r.content)} bytes - OK")
            return r.content
            
        except httpx.ConnectError as e:
            logger.error(f"❌ Не удалось подключиться к Cloudflare: {e}")
            raise ValueError("Cloudflare Worker недоступен")
        except httpx.TimeoutException as e:
            logger.error(f"⏱️ Timeout при запросе к Cloudflare: {e}")
            raise ValueError("Cloudflare не ответил за 90 секунд")
        except Exception as e:
            logger.error(f"❌ Ошибка Cloudflare: {e}")
            raise
