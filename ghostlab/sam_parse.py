"""Parse SAM 3.1's special-token output (one line per frame) into a pixel track."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

from ghostlab.core import PixelTrack

MASK = re.compile(r"<\|mask;[^|]*\|>")
FRAME_TAG = re.compile(r"<(\d+)f>")
OBJECT = re.compile(r"(\d+)<\|box;([^|]*)\|>")


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float | None


def _box(fields: str) -> Box | None:
    """One box from its `key=value;...` fields, or None when it is malformed, non-finite or inverted."""
    kv = dict(f.split("=", 1) for f in fields.split(";") if "=" in f)
    try:
        x1, y1, x2, y2 = (float(kv[k]) for k in ("x1", "y1", "x2", "y2"))
        conf = float(kv["c"]) if "c" in kv else None
    except (KeyError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)) or (conf is not None and not math.isfinite(conf)):
        return None
    if x2 < x1 or y2 < y1:
        return None
    return Box(x1, y1, x2, y2, conf)


def parse(text: str) -> dict[int, dict[int, Box]]:
    """Frame number to {object id: box}. Malformed boxes are skipped; a frame with none left stays, empty."""
    parts = FRAME_TAG.split(MASK.sub("", text))
    frames: dict[int, dict[int, Box]] = {}
    for number, body in zip(parts[1::2], parts[2::2]):
        objects = {}
        for oid, fields in OBJECT.findall(body):
            if (box := _box(fields)) is not None:
                objects[int(oid)] = box
        frames[int(number)] = objects
    return frames


def pick_object(frames: dict[int, dict[int, Box]]) -> int | None:
    counts = Counter(oid for objects in frames.values() for oid in objects)
    return counts.most_common(1)[0][0] if counts else None


def to_pixel_track(frames: dict[int, dict[int, Box]], n_frames: int, fps: float,
                   frame_w: int, frame_h: int, object_id: int | None = None) -> PixelTrack:
    oid = object_id if object_id is not None else pick_object(frames)
    cx, cy, w, h = (np.full(n_frames, np.nan) for _ in range(4))
    for f, objects in frames.items():
        if f < n_frames and oid in objects:
            b = objects[oid]
            cx[f], cy[f] = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
            w[f], h[f] = b.x2 - b.x1, b.y2 - b.y1
    return PixelTrack(t=np.arange(n_frames) / fps, cx=cx, cy=cy, w=w, h=h, frame_w=frame_w, frame_h=frame_h)
