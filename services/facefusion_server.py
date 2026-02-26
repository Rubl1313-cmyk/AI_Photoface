#!/usr/bin/env python3
"""
FaceFusion API сервер для Render.com
✅ ИСПРАВЛЕНО: --source --target --output (не -s -t -o)
✅ Увеличен таймаут до 300 сек для CPU
✅ Рекурсивный поиск результата
✅ Подробное логирование для отладки
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
import subprocess, tempfile, os, logging, glob, shutil

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="FaceFusion API")
FACEFUSION_PATH = "/opt/facefusion"
FACEFUSION_PY = os.path.join(FACEFUSION_PATH, "facefusion.py")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "facefusion-api"}

@app.post("/api/swap")
async def swap_faces(source_image: UploadFile = File(...), target_image: UploadFile = File(...)):
    ts = tt = od = None
    try:
        # Сохраняем временные файлы
        with tempfile.NamedTemporaryFile(delete=False, suffix='_source.jpg') as f:
            ts = f.name
            f.write(await source_image.read())
        with tempfile.NamedTemporaryFile(delete=False, suffix='_target.jpg') as f:
            tt = f.name
            f.write(await target_image.read())
        od = tempfile.mkdtemp()
        
        # 🔥 ИСПРАВЛЕННЫЙ CLI: --source --target --output
        cmd = [
            "python", FACEFUSION_PY, "run",
            "--source", ts,
            "--target", tt,
            "--output", od,
            "--face-swapper-model", "inswapper_128",
            "--face-detector-model", "yoloface_8n",
            "--skip-download",
            "--execution-providers", "cpu"
        ]
        
        logger.info(f"🚀 FaceFusion CLI: {' '.join(cmd)}")
        
        # Запускаем с увеличенным таймаутом (CPU медленный)
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 минут
            cwd=FACEFUSION_PATH
        )
        
        # Логируем вывод для отладки
        if res.stdout:
            logger.info(f"📋 STDOUT: {res.stdout[-500:]}")
        if res.stderr:
            logger.info(f"📋 STDERR: {res.stderr[-500:]}")
        
        if res.returncode != 0:
            err = res.stderr[-500:] if res.stderr else "unknown error"
            raise RuntimeError(f"FaceFusion failed: {err}")
        
        # Ищем результат (рекурсивно в подпапках)
        result_files = []
        for ext in ["*.jpg", "*.png", "*.webp"]:
            result_files.extend(glob.glob(os.path.join(od, ext, "**"), recursive=True))
        
        # Исключаем исходные файлы
        result_files = [
            f for f in result_files 
            if os.path.basename(f) not in [os.path.basename(ts), os.path.basename(tt)]
        ]
        
        # Если не нашли — пробуем os.walk
        if not result_files:
            for root, dirs, files in os.walk(od):
                for f in files:
                    if f.lower().endswith(('.jpg', '.png', '.webp')):
                        if f not in [os.path.basename(ts), os.path.basename(tt)]:
                            result_files.append(os.path.join(root, f))
        
        if not result_files:
            raise RuntimeError(f"No output file. STDOUT: {res.stdout[-200:]}, STDERR: {res.stderr[-200:]}")
        
        result_path = result_files[0]
        logger.info(f"✅ Found result: {result_path}")
        
        with open(result_path, 'rb') as f:
            data = f.read()
        
        logger.info(f"✅ Done: {len(data)} bytes")
        return Response(content=data, media_type="image/png")
        
    except subprocess.TimeoutExpired:
        logger.error("⏱️ FaceFusion timeout (300 sec)")
        raise HTTPException(504, "⏱️ Timeout: замена лица заняла больше 5 минут")
    except RuntimeError as e:
        logger.error(f"❌ FaceFusion error: {e}")
        raise HTTPException(500, f"❌ {str(e)[:300]}")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}", exc_info=True)
        raise HTTPException(500, f"❌ {str(e)[:300]}")
    finally:
        # Очистка временных файлов
        for p in [ts, tt]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
        if od and os.path.exists(od):
            try: shutil.rmtree(od)
            except: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
