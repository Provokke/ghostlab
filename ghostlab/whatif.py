"""What-if physics: change gravity or bounciness and re-run a fitted motion model."""
from __future__ import annotations

import math

import numpy as np

from ghostlab.fit.select import MODULES

G_EARTH = 9.81


MIN_G = 1e-6  # zero gravity would divide by zero in the bounce flight time; this is a straight line in practice


def simulate(motion: str, sim: dict, t, g: float | None = None, e: float | None = None):
    """Positions in metres at times t. g and e override the fitted gravity and restitution.

    Projectile and bounce take g as an absolute value. The pendulum and ramp fits carry no g, so g is
    relative to Earth's 9.81 there (9.81 reproduces the clip)."""
    p = dict(sim)
    t = np.asarray(t, dtype=float)
    if g is not None:
        g = max(float(g), MIN_G)
    if motion in ("projectile", "bounce"):
        if g is not None:
            p["g"] = g
        if e is not None and "e" in p:
            p["e"] = e
    elif motion == "pendulum" and g is not None:
        omega0_sq = p["omega"] ** 2 + p["gamma"] ** 2  # the fitted omega is the damped frequency
        p["omega"] = math.sqrt(max(omega0_sq * g / G_EARTH - p["gamma"] ** 2, 0.0))
    elif motion == "ramp" and g is not None:
        p["a"] = p["a"] * g / G_EARTH
    x, y = MODULES[motion].simulate(p, t)
    return x, y
