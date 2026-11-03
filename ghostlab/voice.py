"""Spoken what-ifs: Muse Voice Transcribe turns speech into text, then keywords turn text into physics."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
import imageio_ffmpeg

ASR_URL = "https://api.meta.ai/v1/asr/transcribe"
ASR_MODEL = "muse-voice-transcribe-1.0"
PLANETS = {"moon": 1.62, "mars": 3.71, "jupiter": 24.8, "venus": 8.87, "earth": 9.81, "mercury": 3.7, "pluto": 0.62}
G_MIN, G_MAX = 0.1, 50.0  # the range /api/simulate accepts
FFMPEG_TIMEOUT = 30
KEYWORDS = list(PLANETS) + ["gravity", "bouncier", "bounciness", "heavier", "lighter"]


def to_wav(data: bytes) -> bytes:
    """Any browser recording to mono 16-bit 24 kHz WAV, the one format the API accepts."""
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in.bin", Path(tmp) / "out.wav"
        src.write_bytes(data)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(src), "-ac", "1", "-ar", "24000",
                        "-c:a", "pcm_s16le", "-map_metadata", "-1", str(dst)], check=True, capture_output=True, timeout=FFMPEG_TIMEOUT)
        return dst.read_bytes()


def transcribe(wav: bytes, key: str, post=httpx.post) -> str:
    request = json.dumps({"mode": "PUSH_TO_TALK", "model": ASR_MODEL, "audioEncoding": "WAV", "keywords": KEYWORDS})
    r = post(ASR_URL, headers={"Authorization": f"Bearer {key}"}, timeout=60,
             files={"request": (None, request, "application/json"), "audio": ("clip.wav", wav, "audio/wav")})
    r.raise_for_status()
    return r.json()["transcript"]


_FACTOR = r"(twice|double|half|(\d+(?:\.\d+)?)\s*(?:x|times))"
_GRAVITY_FACTOR = re.compile(rf"\b{_FACTOR}\b.*gravity|gravity.*\b{_FACTOR}\b")
_PLANET_RES = {name: re.compile(rf"\b{name}\b") for name in PLANETS}


def parse_whatif(text: str, g: float, e: float | None) -> dict:
    """Pull a gravity or bounciness change out of a spoken sentence. Empty dict if there is none.

    A planet sets gravity (the earliest one mentioned wins); a multiplier scales the planet's gravity if
    one was named, else the current g. Gravity is clamped to what the simulator accepts and a "note" says so.
    """
    t = text.lower()
    out: dict = {}
    hits = [(m.start(), name) for name, rx in _PLANET_RES.items() if (m := rx.search(t))]
    planet = PLANETS[min(hits)[1]] if hits else None
    if planet is not None:
        out["g"] = planet
    m = _GRAVITY_FACTOR.search(t)
    if m:
        word = next(v for v in m.groups() if v)
        factor = {"twice": 2.0, "double": 2.0, "half": 0.5}.get(word)
        if factor is None:
            nums = [v for v in m.groups() if v and re.fullmatch(r"\d+(?:\.\d+)?", v)]
            factor = float(nums[0]) if nums else 1.0
        raw = (planet if planet is not None else g) * factor
        out["g"] = round(min(G_MAX, max(G_MIN, raw)), 2)
        if out["g"] != round(raw, 2):
            out["note"] = f"Gravity limited to {out['g']:g} m/s2"
    if e is not None:
        if "bouncier" in t or "more bounce" in t:
            out["e"] = min(0.98, round(e + 0.15, 2))
        elif "less bounc" in t or "deader" in t:
            out["e"] = max(0.1, round(e - 0.15, 2))
    return out
