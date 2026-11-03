"""Render synthetic demo clips and run the real pipeline over them with a stand-in Meta API.

These are deliberate synthetic sample clips with known physics (ball tagged 6.7 cm), not filmed footage.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, ".")
from ghostlab.fit import bounce, pendulum, projectile
from ghostlab.pipeline import run
from tests.fakes import FakeMeta

FPS, SECONDS, W, H = 30, 1.6, 1280, 720
OUT = Path("web/demos")
BALL_M, BALL_PX = 0.067, 34
M_PER_PX = BALL_M / BALL_PX
ORIGIN = (140.0, 600.0)  # pixel of x=0,y=0

CASES = {
    "throw": ("projectile", projectile, {"x0": 0.0, "vx": 2.6, "y0": 0.1, "vy": 4.4, "g": 9.81}),
    "drop": ("bounce", bounce, {"x0": 0.5, "vx": 0.3, "y0": 2.0, "vy": 0.0, "g": 9.81, "e": 0.72, "floor": 0.0, "t_start": 0.0}),
}


def px(x, y):
    return ORIGIN[0] + np.asarray(x) / M_PER_PX, ORIGIN[1] - np.asarray(y) / M_PER_PX


def render(path, xs, ys, extra=None):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for cx, cy in zip(xs, ys):
        f = np.full((H, W, 3), 38, np.uint8)
        cv2.line(f, (0, int(ORIGIN[1] + BALL_PX / 2)), (W, int(ORIGIN[1] + BALL_PX / 2)), (90, 90, 90), 3)
        if extra:
            extra(f)
        if np.isfinite(cx):
            cv2.circle(f, (int(cx), int(cy)), BALL_PX // 2, (60, 220, 255), -1)
        w.write(f)
    w.release()


def sam_text(xs, ys):
    h = BALL_PX / 2
    return "\n".join(f"<{i}f>0<|box;x1={cx - h:.2f};y1={cy - h:.2f};x2={cx + h:.2f};y2={cy + h:.2f};w={W};h={H}|>"
                     for i, (cx, cy) in enumerate(zip(xs, ys)) if np.isfinite(cx))


def make(name, motion, module, sim, ident_extra=None, extra=None, warp=None):
    t = np.arange(0, SECONDS, 1 / FPS)
    x, y = module.simulate(sim, t)
    if warp:
        x, y = warp(t, x, y)
    cx, cy = px(x, y)
    rng = np.random.default_rng(3)
    cx, cy = cx + rng.normal(0, 0.8, len(t)), cy + rng.normal(0, 0.8, len(t))
    clip = OUT / f"{name}.mp4"
    render(clip, cx, cy, extra)
    ident = {"object": "tennis ball", "sam_prompt": "tennis ball", "real_size_m": BALL_M, "size_confidence": "high",
             "motion": motion, "has_pivot": False, "pivot_x_px": 0, "pivot_y_px": 0, "reasoning": "synthetic demo"}
    ident.update(ident_extra or {})
    explain = {"explanation": f"Fitted {motion} motion to the tracked ball.", "class_question": "What would change on the Moon?"}
    fake = FakeMeta(chat_replies=[ident, explain], sam_text=sam_text(cx, cy))
    result = run(clip, Path("work") / name, fake, cache_root=Path("work") / "cache-demo")
    result["video"] = f"/demos/{name}.mp4"
    result["demo"] = True
    (OUT / f"{name}.json").write_text(json.dumps(result), encoding="utf-8")
    print(name, result["chosen"], result["twin"]["verdict"], result["twin"]["test_error_cm"])


OUT.mkdir(parents=True, exist_ok=True)
for name, (motion, module, sim) in CASES.items():
    make(name, motion, module, sim)


def kicked(t, x, y):
    """Something nudges the ball upward late in the clip: physics the early frames cannot predict."""
    k = np.clip(t - 1.0, 0, None)
    return x + 0.8 * k, y + 2.2 * k


make("bump", "projectile", projectile, {"x0": 0.0, "vx": 1.6, "y0": 0.1, "vy": 3.2, "g": 9.81}, warp=kicked)


# Browsers cannot play OpenCV's mpeg4: re-encode every demo clip to H.264 after the pipeline has read it.
import shutil, subprocess, tempfile
for mp4 in sorted(OUT.glob("*.mp4")):
    tmp = Path(tempfile.gettempdir()) / f"{mp4.stem}.h264.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(tmp)], check=True)
    shutil.move(str(tmp), str(mp4))
