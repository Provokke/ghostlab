"""Pendulum: the bob moves on a circle round a pivot; its angle is a damped cosine."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import curve_fit, least_squares

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "pendulum"
MIN_POINTS = 12
MIN_CROSSINGS = 3  # at least one full swing
MAX_LENGTH_ERROR = 0.05  # above 5% the fit is "rough": swing wider or give the pivot


def _theta(t, A, gamma, omega, phi, offset):
    return A * np.exp(-gamma * t) * np.cos(omega * t + phi) + offset


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    th = _theta(np.asarray(t, dtype=float), p["A"], p["gamma"], p["omega"], p["phi"], p["offset"])
    return p["px"] + p["L"] * np.sin(th), p["py"] - p["L"] * np.cos(th)


def _circle_centre(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Algebraic (Kasa) circle fit: fast, but biased short on small arcs; only a starting guess."""
    design = np.column_stack([x, y, np.ones_like(x)])
    (c1, c2, _), *_ = np.linalg.lstsq(design, x * x + y * y, rcond=None)
    return float(c1 / 2), float(c2 / 2)


def _pivot_and_length(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """Geometric circle fit. The length error includes the pivot's uncertainty."""
    px, py = _circle_centre(x, y)
    start = [px, py, float(np.mean(np.hypot(x - px, y - py)))]
    res = least_squares(lambda p: np.hypot(x - p[0], y - p[1]) - p[2], start)
    s2 = float(np.sum(res.fun**2)) / (len(x) - 3)
    cov = np.linalg.inv(res.jac.T @ res.jac) * s2
    return float(res.x[0]), float(res.x[1]), float(res.x[2]), math.sqrt(cov[2, 2])


def fit(track: Track, pivot: tuple[float, float] | None = None) -> FitResult:
    t, x, y = track.t, track.x, track.y
    if len(track) < MIN_POINTS:
        raise FitError(f"need at least {MIN_POINTS} tracked frames, got {len(track)}")
    if pivot is None:
        px, py, L, eL = _pivot_and_length(x, y)
    else:
        px, py = pivot
        r = np.hypot(x - px, y - py)
        L, eL = float(np.mean(r)), float(np.std(r, ddof=1) / math.sqrt(len(r)))
    if py <= float(np.mean(y)):
        raise FitError("the path does not hang below a pivot")
    theta = np.arctan2(x - px, py - y)
    crossings = int(np.sum(np.diff(np.sign(theta - theta.mean())) != 0))
    if crossings < MIN_CROSSINGS:
        raise FitError("need at least one full swing")
    w0 = math.pi * crossings / float(t[-1] - t[0])
    design = np.column_stack([np.cos(w0 * t), np.sin(w0 * t), np.ones_like(t)])
    (ca, cb, cc), *_ = np.linalg.lstsq(design, theta, rcond=None)
    p0 = [math.hypot(ca, cb), 0.01, w0, math.atan2(-cb, ca), cc]
    try:
        popt, pcov = curve_fit(
            _theta, t, theta, p0=p0,
            bounds=([0.0, 0.0, 0.2 * w0, -np.inf, -np.pi], [np.pi, 5.0, 5.0 * w0, np.inf, np.pi]),
        )
    except RuntimeError as exc:
        raise FitError(f"swing fit did not converge: {exc}") from exc
    A, gamma, omega, phi, offset = (float(v) for v in popt)
    eA, egamma, eomega = (float(v) for v in np.sqrt(np.diag(pcov))[:3])
    amp = A * float(np.mean(np.exp(-gamma * t)))
    g = (omega**2 + gamma**2) * L * (1 + amp**2 / 16) ** 2
    eg = g * math.hypot(2 * eomega / omega, eL / L)
    period = 2 * math.pi / omega
    sim = {"px": px, "py": py, "L": L, "A": A, "gamma": gamma, "omega": omega, "phi": phi, "offset": offset}
    rmse = rmse_of(track, *simulate(sim, t))
    params = {
        "length": Param(L, eL, "m"),
        "period": Param(period, period * eomega / omega, "s"),
        "g": Param(g, eg, "m/s²"),
        "damping": Param(gamma, egamma, "1/s"),
        "amplitude": Param(math.degrees(amp), math.degrees(eA), "°"),
    }
    quality = "rough" if eL / L > MAX_LENGTH_ERROR else quality_of(rmse, track)
    return FitResult(MOTION, params, sim, rmse, quality, len(track))
