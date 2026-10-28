"""Disk cache for Meta API answers, so re-runs never spend credits."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable


def cached(kind: str, key: bytes, compute: Callable[[], dict], root: Path | None = None) -> dict:
    root = root or Path(os.environ.get("GHOSTLAB_CACHE", ".cache"))
    path = root / kind / f"{hashlib.sha256(key).hexdigest()}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    value = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return value
