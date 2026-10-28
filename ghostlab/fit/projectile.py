"""Thrown or dropped object: x = x0 + vx t, y = y0 + vy t - g t^2 / 2."""
from __future__ import annotations

import math

import numpy as np

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "projectile"
MIN_POINTS = 6


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(t, dtype=float)
    return p["x0"] + p["vx"] * t, p["y0"] + p["vy"] * t - 0.5 * p["g"] * t**2


def fit(track: Track) -> FitResult:
    if len(track) < MIN_POINTS:
        raise FitError(f"need at least {MIN_POINTS} tracked frames, got {len(track)}")
    (vx, x0), cov_x = np.polyfit(track.t, track.x, 1, cov=True)
    (a, vy, y0), cov_y = np.polyfit(track.t, track.y, 2, cov=True)
    g = -2.0 * a
    if g <= 0:
        raise FitError("the object is not falling")
    evx = math.sqrt(cov_x[0, 0])
    eg, evy = 2.0 * math.sqrt(cov_y[0, 0]), math.sqrt(cov_y[1, 1])
    speed = math.hypot(vx, vy)
    espeed = math.hypot(vx * evx, vy * evy) / speed if speed else math.hypot(evx, evy)
    angle = math.degrees(math.atan2(vy, vx))
    eangle = math.degrees(math.hypot(vx * evy, vy * evx) / speed**2) if speed else 180.0
    sim = {"x0": float(x0), "vx": float(vx), "y0": float(y0), "vy": float(vy), "g": float(g)}
    rmse = rmse_of(track, *simulate(sim, track.t))
    params = {
        "g": Param(float(g), eg, "m/s²"),
        "launch_speed": Param(float(speed), float(espeed), "m/s"),
        "launch_angle": Param(angle, eangle, "°"),
        "vx": Param(float(vx), evx, "m/s"),
        "vy": Param(float(vy), evy, "m/s"),
    }
    return FitResult(MOTION, params, sim, rmse, quality_of(rmse, track), len(track))
