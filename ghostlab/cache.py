"""Disk cache for Meta API answers, so re-runs never spend credits."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Callable

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def key_of(*parts: bytes | str) -> bytes:
    """Collision-safe cache key: each part is length-prefixed, so ('ab','c') != ('a','bc')."""
    out = bytearray()
    for part in parts:
        data = part.encode() if isinstance(part, str) else part
        out += len(data).to_bytes(8, "big") + data
    return bytes(out)


def _lock_for(name: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(name, threading.Lock())


def _read(path: Path) -> dict | None:
    """Cached value, or None when missing or unreadable (a corrupt entry is a miss, never an error)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def cached(kind: str, key: bytes, compute: Callable[[], dict], root: Path | None = None) -> dict:
    """Return the stored answer for (kind, key) or compute, store (atomically) and return it.

    A per-key lock makes concurrent callers share one computation instead of each spending API credits.
    """
    root = root or Path(os.environ.get("GHOSTLAB_CACHE", ".cache"))
    path = root / kind / f"{hashlib.sha256(key).hexdigest()}.json"
    if (hit := _read(path)) is not None:
        return hit
    with _lock_for(str(path)):
        if (hit := _read(path)) is not None:
            return hit
        value = compute()
        _write_atomic(path, value)
        return value
