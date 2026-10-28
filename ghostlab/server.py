"""Phone web app backend: demos, analyze an uploaded clip, simulate what-ifs."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ghostlab import meta_api, pipeline, whatif

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DEMOS = WEB / "demos"
app = FastAPI(title="Ghostlab")


class SimRequest(BaseModel):
    motion: str
    sim: dict[str, float]
    t: list[float]
    m_per_px: float
    origin_px: list[float]
    g: float | None = None
    e: float | None = None


@app.get("/api/demos")
def demos():
    return sorted(p.stem for p in DEMOS.glob("*.json"))


@app.get("/api/demo/{name}")
def demo(name: str):
    path = DEMOS / f"{Path(name).name}.json"
    if not path.exists():
        raise HTTPException(404, "no such demo")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/status")
def status():
    return {"live": bool(os.environ.get("MODEL_API_KEY"))}


@app.post("/api/simulate")
def simulate(req: SimRequest):
    try:
        x, y = whatif.simulate(req.motion, req.sim, req.t, req.g, req.e)
    except KeyError:
        raise HTTPException(400, "unknown motion")
    px = req.origin_px[0] + x / req.m_per_px
    py = req.origin_px[1] - y / req.m_per_px
    clean = lambda a: [None if not np.isfinite(v) else round(float(v), 2) for v in a]
    return {"px": clean(px), "py": clean(py)}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    if not os.environ.get("MODEL_API_KEY"):
        raise HTTPException(503, "Live analysis needs MODEL_API_KEY. Try a demo clip.")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / (Path(file.filename or "clip.mp4").name)
        src.write_bytes(await file.read())
        result = pipeline.run(src, Path(tmp) / "work", meta_api.client())
        name = f"upload-{abs(hash(src.name)) % 10**8}.mp4"
        (WEB / "uploads").mkdir(exist_ok=True)
        (WEB / "uploads" / name).write_bytes(src.read_bytes())
    result["video"] = f"/uploads/{name}"
    return result


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
