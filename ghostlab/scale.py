"""Pixel track to metres: known object size sets the scale; short gaps are filled."""
from __future__ import annotations

import numpy as np

from ghostlab.core import FitError, PixelTrack, Track

MAX_GAP = 3  # missing frames filled by interpolation
MIN_FRAMES = 6


def _segments(present: np.ndarray) -> list[tuple[int, int]]:
    idx = np.flatnonzero(present)
    if len(idx) == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > MAX_GAP + 1)
    starts = [int(idx[0]), *(int(i) for i in idx[breaks + 1])]
    ends = [*(int(i) for i in idx[breaks]), int(idx[-1])]
    return list(zip(starts, ends))


def to_metres(px: PixelTrack, real_size_m: float) -> tuple[Track, list[str]]:
    present = ~np.isnan(px.cx)
    segments = _segments(present)
    if not segments:
        raise FitError("the object was not found in any frame")
    a, b = max(segments, key=lambda s: int(present[s[0]:s[1] + 1].sum()))
    sl = slice(a, b + 1)
    keep = present[sl]
    if keep.sum() < MIN_FRAMES:
        raise FitError(f"the object was tracked in only {int(keep.sum())} frames in a row")
    t = px.t[sl]
    cx = np.interp(t, t[keep], px.cx[sl][keep])
    cy = np.interp(t, t[keep], px.cy[sl][keep])
    m = real_size_m / float(np.nanmedian(np.maximum(px.w[sl], px.h[sl])))
    notes = []
    if (filled := int((~keep).sum())):
        notes.append(f"filled {filled} missing frame(s)")
    if a > 0 or b < len(px.t) - 1:
        notes.append(f"used frames {a}-{b} only; the object was lost elsewhere")
    origin = (float(cx[0]), float(cy[0]))
    track = Track(t=t - t[0], x=(cx - origin[0]) * m, y=-(cy - origin[1]) * m,
                  m_per_px=m, origin_px=origin, t0=float(t[0]))
    return track, notes


def pivot_to_metres(track: Track, pivot_px: tuple[float, float]) -> tuple[float, float]:
    return ((pivot_px[0] - track.origin_px[0]) * track.m_per_px,
            -(pivot_px[1] - track.origin_px[1]) * track.m_per_px)
