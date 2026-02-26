#!/usr/bin/env python3
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
import subprocess, tempfile, os, logging, glob, shutil

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
FACEFUSION_PATH = "/opt/facefusion"
FACEFUSION_PY = os.path.join(FACEFUSION_PATH, "facefusion.py")

@app.get("/health")
async def health(): return {"status": "ok"}

@app.post("/api/swap")
async def swap_faces(source_image: UploadFile = File(...), target_image: UploadFile = File(...)):
    ts = tt = od = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='_s.jpg') as f: ts = f.name; f.write(await source_image.read())
        with tempfile.NamedTemporaryFile(delete=False, suffix='_t.jpg') as f: tt = f.name; f.write(await target_image.read())
        od = tempfile.mkdtemp()
        
        # 🔥 ОПТИМИЗИРОВАННЫЙ CLI для малой памяти
        cmd = [
            "python", FACEFUSION_PY, "run",
            "--source", ts,
            "--target", tt,
            "--output-path", od,
            "--face-swapper-model", "inswapper_128",
            "--face-detector-model", "retinaface",  # Менее требовательный
            "--execution-providers", "cpu",
            "--execution-thread-count", "2",        # Меньше потоков = меньше RAM
            "--video-memory-strategy", "strict",
            "--face-analyzer-score", "0.5"          # Проще анализ
        ]
        
        logger.info(f"🚀 CLI: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=FACEFUSION_PATH)
        
        if res.stdout: logger.info(f"📋 STDOUT: {res.stdout[-300:]}")
        if res.stderr: logger.info(f"📋 STDERR: {res.stderr[-300:]}")
        
        if res.returncode != 0:
            # 🔥 Если ошибка памяти — вернуть оригинал
            if "memory" in res.stderr.lower() or "Killed" in res.stderr or "OOM" in res.stderr:
                logger.warning("⚠️ FaceFusion OOM — возвращаю оригинал без замены лица")
                with open(tt, 'rb') as f: return Response(content=f.read(), media_type="image/png")
            err = res.stderr[-300:] if res.stderr else "unknown"
            raise RuntimeError(f"FaceFusion failed: {err}")
        
        # Поиск результата
        files = []
        for ext in ["*.jpg","*.png","*.webp"]:
            files.extend(glob.glob(os.path.join(od, ext, "**"), recursive=True))
        files = [f for f in files if os.path.basename(f) not in [os.path.basename(ts), os.path.basename(tt)]]
        
        if not files:
            logger.warning("⚠️ No output from FaceFusion — возвращаю оригинал")
            with open(tt, 'rb') as f: return Response(content=f.read(), media_type="image/png")
        
        with open(files[0], 'rb') as f: data = f.read()
        logger.info(f"✅ Done: {len(data)} bytes")
        return Response(content=data, media_type="image/png")
        
    except MemoryError:
        logger.warning("⚠️ MemoryError — возвращаю оригинал")
        with open(tt, 'rb') as f: return Response(content=f.read(), media_type="image/png")
    except subprocess.TimeoutExpired: raise HTTPException(504, "⏱️ Timeout")
    except Exception as e:
        logger.error(f"💥 {e}", exc_info=True)
        # 🔥 В случае любой ошибки — вернуть оригинал, а не 500
        try:
            with open(tt, 'rb') as f: return Response(content=f.read(), media_type="image/png")
        except: raise HTTPException(500, f"❌ {str(e)[:200]}")
    finally:
        for p in [ts,tt]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
        if od and os.path.exists(od):
            try: shutil.rmtree(od)
            except: pass

if __name__ == "__main__":
    import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8081)
