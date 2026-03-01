# services/face_fusion_api.py
import httpx, logging
from typing import Optional

logger = logging.getLogger(__name__)

class FaceFusionClient:
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")
        logger.info(f"🔗 FaceFusionClient initialized: {self.api_url}")
    
    async def swap_face(self, source_face_bytes: bytes, target_image_bytes: bytes) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                files = {
                    "target": ("target.jpg", target_image_bytes, "image/jpeg"),
                    "source": ("source.jpg", source_face_bytes, "image/jpeg")
                }
                logger.info(f"🔄 FaceFusion request (timeout=300s): {len(target_image_bytes)}B target, {len(source_face_bytes)}B source")
                response = await client.post(f"{self.api_url}/swap", files=files)
                if response.status_code == 200:
                    logger.info(f"✅ Face swap success: {len(response.content)} bytes")
                    return response.content
                else:
                    logger.error(f"❌ FaceFusion error {response.status_code}: {response.text[:200]}")
                    return None
        except httpx.TimeoutException:
            logger.error("❌ FaceFusion timeout after 300s")
            return None
        except Exception as e:
            logger.error(f"❌ Face swap error: {type(e).__name__}: {e}")
            return None
