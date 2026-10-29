"""Synthetic accuracy and trust benchmark: how well g is recovered, and does the held-out check catch bad physics?"""
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

sys.path.insert(0, ".")
from ghostlab.core import FitError, Track
from ghostlab.fit import bounce, pendulum, projectile
from ghostlab.fit.select import MODULES
from ghostlab.heldout import check

SEEDS = range(20)
FPS = 30


def noisy(t, x, y, sigma, drop, seed):
    rng = np.random.default_rng(seed)
    keep = rng.random(len(t)) >= drop
    keep[0] = keep[-1] = True
    n = int(keep.sum())
    return Track(t=t[keep], x=x[keep] + rng.normal(0, sigma, n), y=y[keep] + rng.normal(0, sigma, n), m_per_px=0.001)


def clean(motion):
    if motion == "projectile":
        t = np.arange(0, 1.0, 1 / FPS)
        return (t, *projectile.simulate({"x0": 0, "vx": 2.0, "y0": 0.1, "vy": 4.0, "g": 9.81}, t)), None
    if motion == "bounce":
        t = np.arange(0, 1.6, 1 / FPS)
        return (t, *bounce.simulate({"x0": 0.0, "vx": 0.3, "y0": 2.0, "vy": 0.0, "g": 9.81, "e": 0.72, "floor": 0.0, "t_start": 0.0}, t)), None
    L, g, th0, gam, T = 0.8, 9.81, 0.5, 0.05, 6.0
    t = np.arange(0, T, 1 / FPS)
    th = solve_ivp(lambda _t, s: [s[1], -(g / L) * np.sin(s[0]) - 2 * gam * s[1]], (0, T), [th0, 0.0], t_eval=t, rtol=1e-10, atol=1e-12).y[0]
    return (t, L * np.sin(th), 1.0 - L * np.cos(th)), (0.0, 1.0)


def kick(t, x, y):
    k = np.clip(t - 0.7 * t[-1], 0, None)
    return x + 0.6 * k, y + 1.8 * k


def run(motion, sigma, drop, bad):
    errs, cert = [], 0
    for seed in SEEDS:
        (t, x, y), pivot = clean(motion)
        if bad:
            x, y = kick(t, x, y)
        tr = noisy(t, x, y, sigma, drop, seed)
        verdict = check(tr, motion, pivot)["verdict"]
        cert += verdict == "certified"
        if not bad:
            try:
                f = MODULES[motion].fit(tr, pivot=pivot) if motion == "pendulum" else MODULES[motion].fit(tr)
                errs.append(abs(f.params["g"].value - 9.81) / 9.81 * 100)
            except FitError:
                pass
    return (float(np.median(errs)) if errs else None), cert / len(SEEDS)


rows = ["| Motion | Noise (mm) | Dropped frames | Median g error | Certified (good physics) | Certified (bad physics) |", "|---|---|---|---|---|---|"]
for motion in ("projectile", "bounce", "pendulum"):
    for sigma, drop in ((0.002, 0.0), (0.005, 0.0), (0.005, 0.2), (0.010, 0.2)):
        e, good = run(motion, sigma, drop, False)
        _, bad = run(motion, sigma, drop, True)
        rows.append(f"| {motion} | {sigma * 1000:.0f} | {int(drop * 100)}% | {'-' if e is None else f'{e:.1f}%'} | {good * 100:.0f}% | {bad * 100:.0f}% |")
out = "# Synthetic benchmark\n\n20 seeds per row. Bad physics = a late unmodelled push the early frames cannot predict.\n\n" + "\n".join(rows) + "\n"
Path("docs/benchmark.md").write_text(out, encoding="utf-8")
print(out)
