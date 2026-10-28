"""Noisy synthetic tracks with known physics."""
import numpy as np

from ghostlab.core import Track


def noisy(t, x, y, sigma=0.002, drop=0.0, seed=0) -> Track:
    rng = np.random.default_rng(seed)
    keep = rng.random(len(t)) >= drop
    keep[0] = keep[-1] = True
    n = int(keep.sum())
    return Track(
        t=np.asarray(t, float)[keep],
        x=np.asarray(x, float)[keep] + rng.normal(0, sigma, n),
        y=np.asarray(y, float)[keep] + rng.normal(0, sigma, n),
        m_per_px=0.001,
    )
