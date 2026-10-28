"""Bouncing ball: projectile arcs; each bounce keeps a fraction e of the vertical speed."""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import find_peaks

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "bounce"
MIN_ARC_POINTS = 5
MAX_BOUNCES = 50


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(t, dtype=float)
    x = p["x0"] + p["vx"] * t
    s_all = t - p["t_start"]
    y = np.where(s_all >= 0, p["floor"], np.nan)
    g, e, floor = p["g"], p["e"], p["floor"]
    start, y_start, vy = 0.0, p["y0"], p["vy"]
    for _ in range(MAX_BOUNCES):
        flight = (vy + math.sqrt(vy * vy + 2.0 * g * max(y_start - floor, 0.0))) / g
        if flight < 1e-4:
            break
        seg = (s_all >= start) & (s_all < start + flight)
        s = s_all[seg] - start
        y[seg] = y_start + vy * s - 0.5 * g * s * s
        vy = -e * (vy - g * flight)
        start, y_start = start + flight, floor
    return x, y


def _arc(t: np.ndarray, y: np.ndarray):
    """Parabola through one arc: g, its error, apex height, its error, coefficients."""
    (a, b, c), cov = np.polyfit(t, y, 2, cov=True)
    if a >= 0:
        raise FitError("an arc is not curving downward")
    apex = c - b * b / (4 * a)
    jac = np.array([b * b / (4 * a * a), -b / (2 * a), 1.0])
    return -2 * a, 2 * math.sqrt(cov[0, 0]), apex, math.sqrt(jac @ cov @ jac), (a, b, c)


def _meet(pa, pb, near: float, fallback: float) -> float:
    """Height where two consecutive parabolas meet, nearest the bounce time."""
    roots = np.roots(np.subtract(pa, pb))
    real = roots[np.isreal(roots)].real
    if len(real) == 0:
        return fallback
    t_hit = real[np.argmin(np.abs(real - near))]
    return float(np.polyval(pa, t_hit))


def _wmean(values, errors) -> tuple[float, float]:
    w = 1.0 / np.square(errors)
    return float(np.sum(w * np.asarray(values)) / np.sum(w)), float(math.sqrt(1.0 / np.sum(w)))


def fit(track: Track) -> FitResult:
    t, y = track.t, track.y
    span = float(np.ptp(y))
    if len(track) < 2 * MIN_ARC_POINTS or span == 0:
        raise FitError("too few frames for a bounce")
    lows, _ = find_peaks(-y, prominence=0.1 * span)
    if len(lows) == 0:
        raise FitError("no bounce found")
    bounds = [-1, *lows.tolist(), len(t)]
    arcs = [np.arange(a + 1, b) for a, b in zip(bounds[:-1], bounds[1:])]
    fits = [_arc(t[i], y[i]) if len(i) >= MIN_ARC_POINTS else None for i in arcs]
    pairs = [(k, fits[k], fits[k + 1]) for k in range(len(fits) - 1) if fits[k] and fits[k + 1]]
    if not pairs:
        raise FitError("need at least two full arcs between bounces")
    floor = float(np.median([_meet(fa[4], fb[4], t[lows[k]], y[lows[k]]) for k, fa, fb in pairs]))
    ratios, ratio_errors = [], []
    for _, fa, fb in pairs:
        ha, hb = fa[2] - floor, fb[2] - floor
        if ha <= 0 or hb <= 0:
            raise FitError("an arc peaks below the floor")
        e = math.sqrt(hb / ha)
        ratios.append(e)
        ratio_errors.append(e * 0.5 * math.hypot(fa[3] / ha, fb[3] / hb))
    e, ee = _wmean(ratios, ratio_errors)
    good = [f for f in fits if f]
    g, eg = _wmean([f[0] for f in good], [f[1] for f in good])
    first = next(k for k, f in enumerate(fits) if f)
    t_start = float(t[arcs[first][0]])
    a, b, c = fits[first][4]
    (vx, x0), cov_x = np.polyfit(t, track.x, 1, cov=True)
    sim = {
        "x0": float(x0), "vx": float(vx),
        "y0": float(np.polyval((a, b, c), t_start)), "vy": float(2 * a * t_start + b),
        "g": g, "e": e, "floor": floor, "t_start": t_start,
    }
    rmse = rmse_of(track, *simulate(sim, t))
    params = {
        "e": Param(e, ee, ""),
        "g": Param(g, eg, "m/s²"),
        "bounces": Param(float(len(pairs)), 0.0, ""),
    }
    return FitResult(MOTION, params, sim, rmse, quality_of(rmse, track), len(track))
