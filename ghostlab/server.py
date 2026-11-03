"""Phone web app backend: demos, analyze an uploaded clip, simulate what-ifs."""
from __future__ import annotations

import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Literal

import httpx
import numpy as np
import openai
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from ghostlab import ingest, meta_api, pipeline, voice, whatif

ROOT = Path(__file__).resolve().parent.parent
WEB = Path(os.environ.get("GHOSTLAB_WEB") or ROOT / "web")
DEMOS = WEB / "demos"
app = FastAPI(title="Ghostlab")
log = logging.getLogger("ghostlab")


def _env_num(name: str, default: float) -> float:
    """Numeric tuning knob from the environment, falling back to the default if unset or malformed."""
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


_SLOTS = threading.BoundedSemaphore(int(_env_num("GHOSTLAB_SLOTS", 2)))
SLOT_WAIT = 10.0  # seconds a request queues for a free slot before it is told the app is busy
_HITS: dict[str, deque] = defaultdict(deque)
_HITS_LOCK = threading.Lock()
RATE_LIMIT, RATE_WINDOW = int(_env_num("GHOSTLAB_RATE_LIMIT", 30)), 60.0
BUSY_NOW = "Ghostlab is busy right now. Try again in a moment."


class _Guard:
    """Per-IP rate limit plus a cap on concurrent heavy jobs; protects API credits on a shared network.

    Constructing it spends one rate-limit hit (so do that before reading a body); entering it takes a slot,
    queueing briefly before giving up with 503.
    """

    def __init__(self, request: Request):
        self.ip = request.client.host if request.client else "?"
        self._check_rate()

    def _check_rate(self) -> None:
        now = time.monotonic()
        with _HITS_LOCK:
            q = _HITS[self.ip]
            while q and now - q[0] > RATE_WINDOW:
                q.popleft()
            if len(q) >= RATE_LIMIT:
                raise HTTPException(429, "Too many requests. Wait a minute and try again.")
            q.append(now)

    def __enter__(self):
        if not _SLOTS.acquire(timeout=SLOT_WAIT):
            raise HTTPException(503, BUSY_NOW)
        return self

    def __exit__(self, *exc):
        _SLOTS.release()


@app.exception_handler(Exception)
async def _catch_all(request: Request, exc: Exception):
    log.error("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse({"detail": "Something went wrong on our side. Try again."}, status_code=500)


SIM_LIMIT = 1e6  # no real clip has a fitted parameter this large; anything bigger overflows the maths


class SimRequest(BaseModel):
    motion: str
    sim: dict[str, float]
    t: list[Annotated[float, Field(ge=0, le=60)]] = Field(min_length=1, max_length=2000)
    m_per_px: float = Field(gt=0)
    origin_px: list[float] = Field(min_length=2, max_length=2)
    g: float | None = Field(None, ge=0, le=50)
    e: float | None = Field(None, ge=0, le=1)

    @field_validator("sim")
    @classmethod
    def _finite(cls, sim: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(v) or abs(v) > SIM_LIMIT for v in sim.values()):
            raise ValueError("simulation parameters out of range")
        return sim


@app.get("/api/demos")
def demos():
    return sorted(p.stem for p in DEMOS.glob("*.json"))


@app.get("/api/demo/{name}")
def demo(name: str):
    path = DEMOS / f"{Path(name).name}.json"
    if not path.exists():
        raise HTTPException(404, "no such demo")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(500, "That demo could not be loaded.")


@app.get("/api/status")
def status():
    return {"live": bool(os.environ.get("MODEL_API_KEY"))}


@app.post("/api/simulate")
def simulate(req: SimRequest):
    if req.motion not in whatif.MODULES:
        raise HTTPException(400, "unknown motion")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x, y = whatif.simulate(req.motion, req.sim, req.t, req.g, req.e)
    except KeyError:
        raise HTTPException(422, "missing parameter in the fitted motion")
    except (ValueError, FloatingPointError, OverflowError):
        raise HTTPException(422, "Those numbers are out of range for this motion.")
    px = req.origin_px[0] + x / req.m_per_px
    py = req.origin_px[1] - y / req.m_per_px
    clean = lambda a: [None if not np.isfinite(v) else round(float(v), 2) for v in a]
    return {"px": clean(px), "py": clean(py)}


class WhatIfText(BaseModel):
    text: str = Field(max_length=500)
    g: float = Field(gt=0, le=100)
    e: float | None = Field(None, ge=0, le=1)


@app.post("/api/whatif")
def whatif_text(req: WhatIfText):
    return {"transcript": req.text, "whatif": voice.parse_whatif(req.text, req.g, req.e)}


MAX_AUDIO = 5 * 1024 * 1024


@app.post("/api/voice")
def voice_whatif(request: Request, audio: UploadFile = File(...), g: float = Form(..., gt=0, le=100), e: float | None = Form(None)):
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        raise HTTPException(503, "Voice needs MODEL_API_KEY. Type your what-if instead.")
    too_long = HTTPException(413, "That recording is too long. Keep it short.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_AUDIO + 64 * 1024:  # multipart framing adds a little
        raise too_long
    guard = _Guard(request)  # rate limit first: a client must not get free buffered reads
    data = audio.file.read(MAX_AUDIO + 1)
    if len(data) > MAX_AUDIO:
        raise too_long
    with guard:
        try:
            text = voice.transcribe(voice.to_wav(data), key)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            raise HTTPException(400, "That recording could not be read. Try again or type your what-if.")
        except (httpx.HTTPError, KeyError, ValueError):
            log.exception("voice transcription failed")
            raise HTTPException(502, "Voice is unavailable right now. Type your what-if instead.")
    return {"transcript": text, "whatif": voice.parse_whatif(text, g, e)}


UPLOAD_ID = re.compile(r"^[0-9a-f]{32}$")
NEEDS_KEY = "Live analysis needs MODEL_API_KEY. Try a demo clip."


class AnalyzeRequest(BaseModel):
    id: str
    size_m: float | None = Field(None, gt=0, lt=10)
    object: str | None = Field(None, min_length=1, max_length=80)
    motion: Literal["projectile", "bounce", "pendulum", "ramp"] | None = None  # mirrors identify.MOTIONS (asserted in tests)


def _require_key() -> None:
    if not os.environ.get("MODEL_API_KEY"):
        raise HTTPException(503, NEEDS_KEY)


MAX_UPLOAD = int(_env_num("GHOSTLAB_MAX_UPLOAD_MB", 150)) * 1024 * 1024
BUSY = "The analysis service is busy or unavailable. Try again, or use a sample clip."


UPLOAD_TTL = int(_env_num("GHOSTLAB_UPLOAD_TTL", 24 * 3600))


def _sweep_uploads() -> None:
    """Delete uploads older than a day so the disk does not fill; runs before each new upload."""
    root = WEB / "uploads"
    if not root.is_dir():
        return
    cutoff = time.time() - UPLOAD_TTL
    for item in root.iterdir():
        try:
            if item.stat().st_mtime < cutoff and (item.is_dir() or UPLOAD_ID.fullmatch(item.stem)):
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
        except OSError:
            pass


def _save_capped(file: UploadFile, dest: Path) -> None:
    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, f"That clip is too large. Keep it under {MAX_UPLOAD // (1024 * 1024)} MB.")
            out.write(chunk)


@app.post("/api/identify")
def identify_upload(request: Request, file: UploadFile = File(...)):  # plain def: FastAPI runs it in a worker thread, ffmpeg and the model call must not block the loop
    _require_key()
    return _identify(file, _Guard(request))


def _is_service_error(exc: Exception) -> bool:
    """True for failures of the network or the Meta API (worth a "busy" message), False for our own bugs."""
    return isinstance(exc, (httpx.HTTPError, openai.OpenAIError))


def _identify(file: UploadFile, guard: _Guard):
    _sweep_uploads()
    uid = uuid.uuid4().hex
    folder = WEB / "uploads" / uid
    folder.mkdir(parents=True)
    try:
        suffix = re.sub(r"[^A-Za-z0-9.]", "", Path(file.filename or "clip.mp4").suffix)[:8]
        src = folder / f"src{suffix}"
        _save_capped(file, src)  # before taking a slot: a slow upload must not hold one
        try:
            with guard, tempfile.TemporaryDirectory() as tmp:
                clip = ingest.prepare(src, Path(tmp))
                ident = pipeline.identify_clip(meta_api.client(), clip)
                (WEB / "uploads" / f"{uid}.mp4").write_bytes(clip.path.read_bytes())
        except HTTPException:
            raise
        except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            log.exception("identify: clip rejected")
            raise HTTPException(400, "That file could not be read as a video.")
        except Exception as exc:
            log.exception("identify failed")
            if _is_service_error(exc):
                raise HTTPException(502, BUSY)
            raise
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        (WEB / "uploads" / f"{uid}.mp4").unlink(missing_ok=True)
        raise
    return {"id": uid, "identification": ident, "video": f"/uploads/{uid}.mp4",
            "clip": {"fps": clip.fps, "n_frames": clip.n_frames, "width": clip.width, "height": clip.height}}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, request: Request):
    _require_key()
    if not UPLOAD_ID.fullmatch(req.id):
        raise HTTPException(400, "bad clip id")
    sources = list((WEB / "uploads" / req.id).glob("src*"))
    mp4 = WEB / "uploads" / f"{req.id}.mp4"
    if not sources or not mp4.exists():
        raise HTTPException(404, "That upload expired. Please upload the clip again.")
    for keep in (mp4, sources[0].parent):  # the sweeper ages each by its own mtime: keep both alive together
        try:
            keep.touch()
        except OSError:
            pass
    with _Guard(request), tempfile.TemporaryDirectory() as tmp:
        try:
            result = pipeline.run(sources[0], Path(tmp) / "work", meta_api.client(),
                                  pipeline.Overrides(object=req.object, size_m=req.size_m, motion=req.motion))
        except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            log.exception("analyze: clip rejected")
            raise HTTPException(400, "That file could not be read as a video.")
        except Exception as exc:
            log.exception("analyze failed")
            if _is_service_error(exc):
                raise HTTPException(502, BUSY)
            raise
    if "error" not in result:  # SAM found nothing: the error dict has no clip to point at
        result["video"] = f"/uploads/{req.id}.mp4"
    return result


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
