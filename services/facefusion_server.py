#!/usr/bin/env python3
"""FaceFusion API сервер для Render"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
import subprocess, tempfile, os, logging, glob

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
        with tempfile.NamedTemporaryFile(delete=False, suffix='_s.jpg') as f:
            ts = f.name
            f.write(await source_image.read())
        with tempfile.NamedTemporaryFile(delete=False, suffix='_t.jpg') as f:
            tt = f.name
            f.write(await target_image.read())
        od = tempfile.mkdtemp()
        
        cmd = [
            "python", FACEFUSION_PY, "run",
            "-s", ts, "-t", tt, "-o", od,
            "--face-swapper-model", "inswapper_128",
            "--skip-download"
        ]
        logger.info(f"🚀 FaceFusion CLI: {' '.join(cmd)}")
        
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=FACEFUSION_PATH)
        
        if res.returncode != 0:
            err = res.stderr[-300:] if res.stderr else "unknown"
            raise RuntimeError(f"FaceFusion failed: {err}")
        
        files = []
        for ext in ["*.jpg", "*.png", "*.webp"]:
            files.extend(glob.glob(os.path.join(od, ext)))
        files = [f for f in files if os.path.basename(f) not in [os.path.basename(ts), os.path.basename(tt)]]
        
        if not files:
            raise RuntimeError("No output file")
        
        with open(files[0], 'rb') as f:
            data = f.read()
        logger.info(f"✅ Done: {len(data)} bytes")
        
        return Response(content=data, media_type="image/png")
        
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "⏱️ Timeout")
    except RuntimeError as e:
        raise HTTPException(500, f"❌ {str(e)[:200]}")
    except Exception as e:
        logger.error(f"💥 {e}", exc_info=True)
        raise HTTPException(500, f"❌ {str(e)[:200]}")
    finally:
        for p in [ts, tt]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass
        if od and os.path.exists(od):
            import shutil
            try:
                shutil.rmtree(od)
            except:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)