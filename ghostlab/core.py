"""Shared types: pixel tracks from SAM, metric tracks, and fit results."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GOOD_RMSE_FRACTION = 0.03  # a fit is "good" when its RMSE is under 3% of the motion's size


class FitError(ValueError):
    """The data cannot support this motion model."""


@dataclass(frozen=True)
class PixelTrack:
    t: np.ndarray  # seconds since clip start
    cx: np.ndarray  # box centre x, px; NaN where the object is missing
    cy: np.ndarray  # box centre y, px, y points down
    w: np.ndarray  # box width, px
    h: np.ndarray  # box height, px
    frame_w: int
    frame_h: int


@dataclass(frozen=True)
class Track:
    t: np.ndarray  # seconds, starts at 0
    x: np.ndarray  # metres, right is positive
    y: np.ndarray  # metres, up is positive
    m_per_px: float
    origin_px: tuple[float, float] = (0.0, 0.0)  # pixel position of x=0, y=0
    t0: float = 0.0  # clip time of t=0

    def __len__(self) -> int:
        return len(self.t)

    def to_px(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.origin_px[0] + x / self.m_per_px, self.origin_px[1] - y / self.m_per_px

    def to_json(self) -> dict:
        return {
            "t": self.t.tolist(),
            "x": self.x.tolist(),
            "y": self.y.tolist(),
            "m_per_px": self.m_per_px,
            "origin_px": list(self.origin_px),
            "t0": self.t0,
        }


@dataclass(frozen=True)
class Param:
    value: float
    error: float
    unit: str


@dataclass(frozen=True)
class FitResult:
    motion: str
    params: dict[str, Param]
    sim: dict[str, float]  # inputs for the module's simulate()
    rmse: float  # metres
    quality: str  # "good" or "rough"
    n_points: int

    def to_json(self) -> dict:
        return {
            "motion": self.motion,
            "params": {k: {"value": p.value, "error": p.error, "unit": p.unit} for k, p in self.params.items()},
            "sim": self.sim,
            "rmse": self.rmse,
            "quality": self.quality,
            "n_points": self.n_points,
        }


def rmse_of(track: Track, x: np.ndarray, y: np.ndarray) -> float:
    return float(np.sqrt(np.nanmean((track.x - x) ** 2 + (track.y - y) ** 2)))


def quality_of(rmse: float, track: Track) -> str:
    size = max(np.ptp(track.x), np.ptp(track.y))
    return "good" if rmse <= GOOD_RMSE_FRACTION * size else "rough"
