"""What-if physics: change gravity or bounciness and re-run a fitted motion model."""
from __future__ import annotations

import math

import numpy as np

from ghostlab.fit.select import MODULES

G_EARTH = 9.81


def simulate(motion: str, sim: dict, t, g: float | None = None, e: float | None = None):
    """Positions in metres at times t. g and e override the fitted gravity and restitution."""
    p = dict(sim)
    t = np.asarray(t, dtype=float)
    if motion in ("projectile", "bounce"):
        if g is not None:
            p["g"] = g
        if e is not None and "e" in p:
            p["e"] = e
    elif motion == "pendulum" and g is not None:
        p["omega"] = p["omega"] * math.sqrt(g / G_EARTH)
    elif motion == "ramp" and g is not None:
        p["a"] = p["a"] * g / G_EARTH
    x, y = MODULES[motion].simulate(p, t)
    return x, y
