"""Phone web app backend: demos, analyze an uploaded clip, simulate what-ifs."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ghostlab import ingest, meta_api, pipeline, voice, whatif

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


class WhatIfText(BaseModel):
    text: str
    g: float
    e: float | None = None


@app.post("/api/whatif")
def whatif_text(req: WhatIfText):
    return {"transcript": req.text, "whatif": voice.parse_whatif(req.text, req.g, req.e)}


@app.post("/api/voice")
async def voice_whatif(audio: UploadFile = File(...), g: float = Form(...), e: float | None = Form(None)):
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        raise HTTPException(503, "Voice needs MODEL_API_KEY. Type your what-if instead.")
    text = voice.transcribe(voice.to_wav(await audio.read()), key)
    return {"transcript": text, "whatif": voice.parse_whatif(text, g, e)}


UPLOAD_ID = re.compile(r"^[0-9a-f]{32}$")
NEEDS_KEY = "Live analysis needs MODEL_API_KEY. Try a demo clip."


class AnalyzeRequest(BaseModel):
    id: str
    size_m: float | None = Field(None, gt=0, lt=10)
    object: str | None = None
    motion: str | None = None


def _require_key() -> None:
    if not os.environ.get("MODEL_API_KEY"):
        raise HTTPException(503, NEEDS_KEY)


MAX_UPLOAD = 150 * 1024 * 1024
BUSY = "The analysis service is busy or unavailable. Try again, or use a sample clip."


def _save_capped(file: UploadFile, dest: Path) -> None:
    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, "That clip is too large. Keep it under 150 MB.")
            out.write(chunk)


@app.post("/api/identify")
def identify(file: UploadFile = File(...)):  # plain def: FastAPI runs it in a worker thread, ffmpeg and the model call must not block the loop
    _require_key()
    uid = uuid.uuid4().hex
    folder = WEB / "uploads" / uid
    folder.mkdir(parents=True)
    try:
        src = folder / f"src{Path(file.filename or 'clip.mp4').suffix[:8]}"
        _save_capped(file, src)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                clip = ingest.prepare(src, Path(tmp))
                ident = pipeline.identify_clip(meta_api.client(), clip)
                (WEB / "uploads" / f"{uid}.mp4").write_bytes(clip.path.read_bytes())
        except (ValueError, subprocess.CalledProcessError):
            raise HTTPException(400, "That file could not be read as a video.")
        except Exception:
            raise HTTPException(502, BUSY)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        (WEB / "uploads" / f"{uid}.mp4").unlink(missing_ok=True)
        raise
    return {"id": uid, "identification": ident, "video": f"/uploads/{uid}.mp4",
            "clip": {"fps": clip.fps, "n_frames": clip.n_frames, "width": clip.width, "height": clip.height}}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    _require_key()
    if not UPLOAD_ID.fullmatch(req.id):
        raise HTTPException(400, "bad clip id")
    sources = list((WEB / "uploads" / req.id).glob("src*"))
    if not sources:
        raise HTTPException(404, "no such clip")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            result = pipeline.run(sources[0], Path(tmp) / "work", meta_api.client(),
                                  pipeline.Overrides(object=req.object, size_m=req.size_m, motion=req.motion))
        except (ValueError, subprocess.CalledProcessError):
            raise HTTPException(400, "That file could not be read as a video.")
        except Exception:
            raise HTTPException(502, BUSY)
    result["video"] = f"/uploads/{req.id}.mp4"
    return result


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
