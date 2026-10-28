"""Sliding down a ramp: constant acceleration along a straight line; friction from the slope."""
from __future__ import annotations

import math

import numpy as np

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "ramp"
G = 9.81
MIN_POINTS = 8
MIN_SLOPE_DEG = 3.0
MAX_SLOPE_DEG = 85.0


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(t, dtype=float)
    s = p["s0"] + p["v0"] * t + 0.5 * p["a"] * t * t
    return p["xs"] + p["dx"] * s, p["ys"] + p["dy"] * s


def fit(track: Track) -> FitResult:
    if len(track) < MIN_POINTS:
        raise FitError(f"need at least {MIN_POINTS} tracked frames, got {len(track)}")
    pts = np.column_stack([track.x, track.y])
    centre = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centre)
    d = vt[0] if vt[0][1] <= 0 else -vt[0]  # point downhill
    angle = math.atan2(-d[1], abs(d[0]))
    if math.degrees(angle) < MIN_SLOPE_DEG:
        raise FitError("too flat to be a ramp")
    if math.degrees(angle) > MAX_SLOPE_DEG:
        raise FitError("that is a fall, not a slide")
    s = (pts - centre) @ d
    n = (pts - centre) @ np.array([-d[1], d[0]])
    eangle = float(np.std(n, ddof=2) / math.sqrt(np.sum((s - s.mean()) ** 2)))
    (half_a, v0, s0), cov = np.polyfit(track.t, s, 2, cov=True)
    a, ea = 2 * float(half_a), 2 * math.sqrt(cov[0, 0])
    if a <= 0:
        raise FitError("the object is not speeding up downhill")
    cos, sin = math.cos(angle), math.sin(angle)
    mu = math.tan(angle) - a / (G * cos)
    dmu_dangle = 1 / cos**2 - a * sin / (G * cos**2)
    emu = math.hypot(dmu_dangle * eangle, ea / (G * cos))
    sim = {"xs": float(centre[0]), "ys": float(centre[1]), "dx": float(d[0]), "dy": float(d[1]),
           "s0": float(s0), "v0": float(v0), "a": a}
    rmse = rmse_of(track, *simulate(sim, track.t))
    params = {
        "angle": Param(math.degrees(angle), math.degrees(eangle), "°"),
        "acceleration": Param(a, ea, "m/s²"),
        "friction": Param(mu, emu, ""),
        "start_speed": Param(float(v0), math.sqrt(cov[1, 1]), "m/s"),
    }
    return FitResult(MOTION, params, sim, rmse, quality_of(rmse, track), len(track))
