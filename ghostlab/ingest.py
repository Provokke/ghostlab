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
KEY_FRAMES = 6  # evenly spaced stills for the identification step; three cannot show a rebound
SHAKE_LIMIT = 0.01  # background shift above 1% of the width (75th percentile over the clip) reads as a hand-held camera


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


MIN_FEATURES = 15  # fewer background corners than this and the drift cannot be measured


def camera_shift(frames: list[np.ndarray]) -> float:
    """Typical background drift against the first frame as a fraction of the width.

    Tracks corners and takes the median motion, so a ball moving through a textured scene does not count;
    a featureless wall gives 0 because there is nothing to measure."""
    gray = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    pts = cv2.goodFeaturesToTrack(gray[0], maxCorners=300, qualityLevel=0.01, minDistance=10)
    if pts is None or len(pts) < MIN_FEATURES:
        return 0.0
    shifts = []
    for g in gray[:: max(1, len(gray) // 20)][1:]:
        nxt, ok, _ = cv2.calcOpticalFlowPyrLK(gray[0], g, pts, None)
        good = ok.ravel() == 1
        if good.sum() < MIN_FEATURES:
            continue
        d = np.median((nxt - pts)[good].reshape(-1, 2), axis=0)
        shifts.append(float(np.hypot(*d) / g.shape[1]))
    return float(np.percentile(shifts, 75)) if shifts else 0.0


def prepare(src: Path, work: Path) -> Clip:
    work.mkdir(parents=True, exist_ok=True)
    out = work / "clip.mp4"
    _normalise(src, out)
    fps, frames = _read_frames(out)
    if len(frames) < 2:
        raise ValueError("the clip has fewer than two frames")
    n = len(frames)
    keys = [cv2.imencode(".jpg", frames[i])[1].tobytes() for i in sorted({round(k * (n - 1) / (KEY_FRAMES - 1)) for k in range(KEY_FRAMES)})]
    shift = camera_shift(frames)
    h, w = frames[0].shape[:2]
    return Clip(out, fps, n, w, h, keys, shift)
