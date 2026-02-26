import httpx
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class FaceFusionClient:
    def __init__(self, api_url: str = "http://localhost:8081"):
        self.api_url = api_url
        self.client = httpx.Client(timeout=180.0)
        logger.info(f"🔌 FaceFusion Client: {api_url}")
    
    def swap(self, user_face: bytes, generated: bytes) -> Tuple[bytes, Optional[str]]:
        if not user_face or not generated:
            return generated, "❌ Пустое изображение"
        try:
            logger.info(f"🔄 Замена лица ({len(user_face)}b → {len(generated)}b)")
            source_path = "/tmp/ff_source.jpg"
            target_path = "/tmp/ff_target.jpg"
            
            with open(source_path, "wb") as f:
                f.write(user_face)
            with open(target_path, "wb") as f:
                f.write(generated)
            
            with open(source_path, "rb") as src:
                with open(target_path, "rb") as tgt:
                    files = {
                        "source_image": ("source.jpg", src, "image/jpeg"),
                        "target_image": ("target.jpg", tgt, "image/jpeg")
                    }
                    response = self.client.post(
                        f"{self.api_url}/api/swap",
                        files=files,
                        timeout=180
                    )
            
            for path in [source_path, target_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            if response.status_code == 200:
                logger.info(f"✅ Замена выполнена: {len(response.content)} bytes")
                return response.content, None
            else:
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"❌ {error}")
                return generated, f"⚠️ Ошибка API: {response.status_code}"
                
        except httpx.ConnectError:
            logger.error("❌ FaceFusion API недоступен")
            return generated, "❌ FaceFusion не отвечает"
        except httpx.TimeoutException:
            logger.error("⏱️ FaceFusion timeout")
            return generated, "⏱️ Превышено время ожидания (180 сек)"
        except Exception as e:
            logger.error(f"💥 Ошибка: {e}", exc_info=True)
            return generated, f"❌ {str(e)[:100]}"