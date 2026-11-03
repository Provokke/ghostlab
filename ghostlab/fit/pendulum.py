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
PIVOT_SIGMAS = 3.0  # a supplied pivot this many circle-fit sigmas from the fitted one is not trusted
PIVOT_MISFIT = 0.05  # ... and a gap above this fraction of the length makes the fit "rough"
PIVOT_PRIOR = 0.02  # a supplied pivot is a guess good to about this fraction of the length


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


def _pivot_and_length(x: np.ndarray, y: np.ndarray,
                      start: tuple[float, float] | None = None) -> tuple[float, float, float, float, float]:
    """Geometric circle fit: pivot x, y, length, length error and pivot error (all metres).

    The length error includes the pivot's uncertainty. `start` seeds the search (e.g. a supplied pivot)."""
    px, py = start if start is not None else _circle_centre(x, y)
    guess = [px, py, float(np.mean(np.hypot(x - px, y - py)))]
    res = least_squares(lambda p: np.hypot(x - p[0], y - p[1]) - p[2], guess)
    s2 = float(np.sum(res.fun**2)) / (len(x) - 3)
    try:
        cov = np.linalg.inv(res.jac.T @ res.jac) * s2
    except np.linalg.LinAlgError as exc:
        raise FitError("the path is too straight to find a pivot") from exc
    if not np.isfinite(cov[2, 2]) or cov[2, 2] < 0 or not np.isfinite(cov[:2, :2]).all():
        raise FitError("the path is too straight to find a pivot")
    sigma_pivot = math.sqrt(max(float(cov[0, 0] + cov[1, 1]), 0.0))
    return float(res.x[0]), float(res.x[1]), float(res.x[2]), math.sqrt(cov[2, 2]), sigma_pivot


def _given_pivot(x: np.ndarray, y: np.ndarray, pivot: tuple[float, float]) -> tuple[float, float, float, float, bool]:
    """Use a supplied pivot as a prior. Returns pivot x, y, length, length error and whether it was kept.

    The pivot is refined by a free circle fit; if the two disagree the free fit wins, and if the supplied
    pivot is kept its uncertainty is added to the length error (the old scatter-only error was ~30 sigma off)."""
    px, py, L, eL, sigma_pivot = _pivot_and_length(x, y, start=pivot)
    gap = math.hypot(px - pivot[0], py - pivot[1])
    if gap > PIVOT_SIGMAS * sigma_pivot or gap > PIVOT_MISFIT * L:
        return px, py, L, eL, gap <= PIVOT_MISFIT * L  # trust the data, not the guess
    r = np.hypot(x - pivot[0], y - pivot[1])
    scatter = float(np.std(r, ddof=1) / math.sqrt(len(r)))
    away = np.column_stack([pivot[0] - x, pivot[1] - y]) / np.maximum(r, 1e-12)[:, None]  # d(radius)/d(pivot) per point
    along = float(np.linalg.norm(away.mean(axis=0)))
    sigma = max(gap, PIVOT_PRIOR * float(np.mean(r)))
    return pivot[0], pivot[1], float(np.mean(r)), math.hypot(scatter, sigma * along), True


def fit(track: Track, pivot: tuple[float, float] | None = None) -> FitResult:
    """Fit the swing. A supplied pivot is a prior: it is refined by the data, never trusted blindly."""
    track.validate()
    t, x, y = track.t, track.x, track.y
    if len(track) < MIN_POINTS:
        raise FitError(f"need at least {MIN_POINTS} tracked frames, got {len(track)}")
    pivot_ok = True
    if pivot is None:
        px, py, L, eL, _ = _pivot_and_length(x, y)
    else:
        px, py, L, eL, pivot_ok = _given_pivot(x, y, pivot)
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
    quality = "rough" if eL / L > MAX_LENGTH_ERROR or not pivot_ok else quality_of(rmse, track)
    return FitResult(MOTION, params, sim, rmse, quality, len(track))
