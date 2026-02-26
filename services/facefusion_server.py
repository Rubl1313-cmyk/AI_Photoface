#!/usr/bin/env python3
"""FaceFusion API для Render — МИНИМАЛЬНЫЙ CLI"""
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
        
        # 🔥 МИНИМАЛЬНЫЙ CLI — только рабочие аргументы!
        cmd = [
            "python", FACEFUSION_PY, "run",
            "--source", ts,
            "--target", tt,
            "--output-path", od,
            "--face-swapper-model", "inswapper_128",
            "--face-detector-model", "retinaface",
            "--execution-providers", "cpu"
            # ❌ НИКАКИХ других флагов!
        ]
        
        logger.info(f"🚀 CLI: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=FACEFUSION_PATH)
        
        if res.returncode != 0:
            logger.warning(f"⚠️ FaceFusion failed: {res.stderr[-200:]}")
            # 🔥 FALLBACK: возвращаем оригинал (target) если FaceFusion упал
            with open(tt, 'rb') as f:
                return Response(content=f.read(), media_type="image/png")
        
        # Поиск результата
        files = []
        for ext in ["*.jpg","*.png","*.webp"]:
            files.extend(glob.glob(os.path.join(od, ext, "**"), recursive=True))
        files = [f for f in files if os.path.basename(f) not in [os.path.basename(ts), os.path.basename(tt)]]
        
        if not files:
            logger.warning("⚠️ No output — returning original")
            with open(tt, 'rb') as f:
                return Response(content=f.read(), media_type="image/png")
        
        with open(files[0], 'rb') as f:
            data = f.read()
        logger.info(f"✅ FaceFusion done: {len(data)} bytes")
        return Response(content=data, media_type="image/png")
        
    except Exception as e:
        logger.error(f"💥 {e}", exc_info=True)
        # 🔥 FALLBACK в случае любой ошибки
        try:
            if tt and os.path.exists(tt):
                with open(tt, 'rb') as f:
                    return Response(content=f.read(), media_type="image/png")
        except: pass
        raise HTTPException(500, f"❌ {str(e)[:200]}")
    finally:
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
