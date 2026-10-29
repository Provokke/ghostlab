"""Trust check: fit on the first part of a clip, predict the rest, score against the real track."""
from __future__ import annotations

import numpy as np

from ghostlab.core import FitError, Track
from ghostlab.fit.select import MODULES

TRAIN_FRACTION = 0.6
CERTIFY_FRACTION = 0.05  # held-out RMSE must be under 5% of the motion's size
MIN_TEST_POINTS = 3


def _slice(track: Track, keep: np.ndarray) -> Track:
    t = track.t[keep]
    return Track(t=t - t[0], x=track.x[keep], y=track.y[keep], m_per_px=track.m_per_px,
                 origin_px=track.origin_px, t0=track.t0 + float(t[0]))


def check(track: Track, motion: str, pivot=None, train_frac: float = TRAIN_FRACTION) -> dict:
    module = MODULES[motion]
    cut = track.t[0] + train_frac * (track.t[-1] - track.t[0])
    train_mask = track.t <= cut
    test_mask = ~train_mask
    out = {"motion": motion, "train_n": int(train_mask.sum()), "test_n": int(test_mask.sum()),
           "train_frac": train_frac, "verdict": "refused", "reason": None,
           "train_rmse": None, "test_rmse": None, "test_error_cm": None, "sim": None, "t_origin": None}
    if out["test_n"] < MIN_TEST_POINTS:
        out["reason"] = "not enough frames after the fit window"
        return out
    train = _slice(track, train_mask)
    try:
        fit = module.fit(train, pivot=pivot) if motion == "pendulum" else module.fit(train)
    except FitError as exc:
        out["reason"] = str(exc)
        return out
    out.update(sim=fit.sim, t_origin=float(track.t[train_mask][0]))
    px, py = module.simulate(fit.sim, track.t[test_mask] - track.t[train_mask][0])
    err = np.sqrt((track.x[test_mask] - px) ** 2 + (track.y[test_mask] - py) ** 2)
    if not np.isfinite(err).any():
        out["reason"] = "model has no prediction for the unseen part"
        return out
    rmse = float(np.sqrt(np.nanmean(err**2)))
    size = max(float(np.ptp(track.x)), float(np.ptp(track.y)), 1e-9)
    out.update(train_rmse=fit.rmse, test_rmse=rmse, test_error_cm=rmse * 100)
    if rmse <= CERTIFY_FRACTION * size:
        out["verdict"] = "certified"
    else:
        out["reason"] = f"predicted the unseen {int((1 - train_frac) * 100)}% off by {rmse * 100:.1f} cm"
    return out
