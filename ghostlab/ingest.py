"""Normalise a phone clip for SAM 3.1 and pull the frames Muse Spark looks at."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

MAX_SECONDS = 15
MAX_HEIGHT = 720
SHAKE_LIMIT = 0.02  # background shift above 2% of the width reads as a hand-held camera


@dataclass(frozen=True)
class Clip:
    path: Path
    fps: float
    n_frames: int
    width: int
    height: int
    key_frames: list[bytes]
    camera_shift: float


def _normalise(src: Path, out: Path) -> None:
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src),
        "-t", str(MAX_SECONDS), "-vf", f"scale=-2:'min({MAX_HEIGHT},ih)'",
        "-fps_mode", "cfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out),
    ]
    subprocess.run(cmd, check=True)


def _read_frames(path: Path) -> tuple[float, list[np.ndarray]]:
    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return fps, frames


def _shift(a: np.ndarray, b: np.ndarray) -> float:
    ga = np.float32(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY))
    gb = np.float32(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY))
    (dx, dy), _ = cv2.phaseCorrelate(ga, gb)
    return float(np.hypot(dx, dy) / a.shape[1])


def prepare(src: Path, work: Path) -> Clip:
    work.mkdir(parents=True, exist_ok=True)
    out = work / "clip.mp4"
    _normalise(src, out)
    fps, frames = _read_frames(out)
    if len(frames) < 2:
        raise ValueError("the clip has fewer than two frames")
    n = len(frames)
    keys = [cv2.imencode(".jpg", frames[i])[1].tobytes() for i in (0, n // 2, n - 1)]
    shift = _shift(frames[n // 10], frames[(9 * n) // 10])
    h, w = frames[0].shape[:2]
    return Clip(out, fps, n, w, h, keys, shift)
