# Ghostlab Backend Implementation Plan (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python pipeline that turns a phone clip into a JSON result: what the object is, its tracked path in metres, every motion model fitted with error bars, the chosen model, and a student explanation.

**Architecture:** `ingest` normalises the clip with ffmpeg. `identify` (Muse Spark) names the object, its real size and the motion type. `track` (SAM 3.1 on the whole video) gives a box per frame. `scale` converts it to metres. `fit/*` fits each physics model with plain least squares. `explain` (Muse Spark) words the fitted numbers. Every Meta API call is cached on disk by input hash.

**Tech Stack:** Python 3.11+, numpy, scipy, opencv-python-headless, imageio-ffmpeg, openai (OpenAI-compatible client for the Meta Model API), pytest.

**Plan 2** (written after Task 14 has run on real clips, about Oct 28): FastAPI service, web lab screen, ghost replay, predict screen, worksheet export, example gallery, deploy, judging-window billing, and the SAM mask measurements (pendulum string, ramp surface, bounce squash).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-25-ghostlab-design.md`.
- The language model never produces a measurement. Every number comes from SAM boxes plus least squares.
- No number leaves the backend without an error and a fit quality (`"good"` or `"rough"`).
- Every Meta API call goes through `ghostlab.cache.cached`. Re-runs must not spend credits.
- Clips: at most 15 s, scaled to at most 720 px tall.
- Meta Model API: base URL `https://api.meta.ai/v1`, key in env var `MODEL_API_KEY`, models `muse-spark-1.3` and `sam-3.1`.
- Test clips and fixtures: objects and adult hands only. No faces, no minors, no music.
- Commits: no AI attribution trailers.
- Tasks 1-9 need no API key. Task 10 needs the hackathon credits (sent after approval, by Oct 26 9:00 AM ET).
- Run tests quietly: `pytest -q`. Re-run a single failing test with `-x -vv` for detail.

## File structure

```
pyproject.toml
ghostlab/__init__.py
ghostlab/__main__.py        CLI: run, scoreboard
ghostlab/core.py            PixelTrack, Track, Param, FitResult, FitError, rmse_of, quality_of
ghostlab/fit/__init__.py
ghostlab/fit/projectile.py  fit(track), simulate(sim, t)
ghostlab/fit/bounce.py      fit(track), simulate(sim, t)
ghostlab/fit/pendulum.py    fit(track, pivot=None), simulate(sim, t)
ghostlab/fit/ramp.py        fit(track), simulate(sim, t)
ghostlab/fit/select.py      fit_all(track, pivot), better_alternative(chosen, results)
ghostlab/scale.py           to_metres(pixel_track, real_size_m), pivot_to_metres(track, pivot_px)
ghostlab/ingest.py          prepare(src, work) -> Clip
ghostlab/cache.py           cached(kind, key, compute, root=None)
ghostlab/meta_api.py        client(), upload_video(), sam_track(), spark_json()
ghostlab/sam_parse.py       parse(text), pick_object(frames), to_pixel_track(...)
ghostlab/identify.py        identify(client, frames) -> dict
ghostlab/explain.py         explain(client, object_name, fit) -> dict
ghostlab/pipeline.py        run(src, work, client, overrides, cache_root) -> dict
ghostlab/scoreboard.py      load(), score(), render(), write()
scripts/spike.py            Task 10 API probe
tests/...                   one test file per module; tests/synth.py, tests/fakes.py
```

---

### Task 1: Project scaffold and core types

**Files:**
- Create: `pyproject.toml`, `ghostlab/__init__.py`, `ghostlab/fit/__init__.py`, `ghostlab/core.py`, `tests/__init__.py`, `tests/synth.py`, `.gitignore`
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `PixelTrack`, `Track`, `Param`, `FitResult`, `FitError`, `rmse_of(track, x, y) -> float`, `quality_of(rmse, track) -> str`, `tests.synth.noisy(t, x, y, sigma=0.002, drop=0.0, seed=0) -> Track`.
- Convention: `Track.t` starts at 0. `FitResult.sim` holds plain floats that the module's `simulate(sim, t)` turns back into positions; Plan 2's JS simulation uses the same keys.

- [ ] **Step 1: Write the scaffold files**

```toml
# file: pyproject.toml
[project]
name = "ghostlab"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "scipy>=1.11",
    "opencv-python-headless>=4.9",
    "imageio-ffmpeg>=0.5",
    "openai>=1.40",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["ghostlab*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```text
# file: .gitignore
.cache/
work/
*.egg-info/
__pycache__/
.venv/
result.json
```

`ghostlab/__init__.py`, `ghostlab/fit/__init__.py` and `tests/__init__.py` are empty files.

```python
# file: tests/synth.py
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
```

- [ ] **Step 2: Write the failing test**

```python
# file: tests/test_core.py
import json

import numpy as np

from ghostlab.core import FitResult, Param, Track, quality_of, rmse_of


def line_track():
    return Track(t=np.arange(5.0), x=np.linspace(0, 1, 5), y=np.zeros(5), m_per_px=0.001)


def test_quality_good_only_when_rmse_is_small():
    track = line_track()
    assert quality_of(0.01, track) == "good"
    assert quality_of(0.05, track) == "rough"


def test_rmse_ignores_nan_predictions():
    track = line_track()
    x = track.x.copy()
    x[0] = np.nan
    assert rmse_of(track, x, track.y) == 0.0


def test_to_px_inverts_metres():
    track = Track(t=np.zeros(1), x=np.zeros(1), y=np.zeros(1), m_per_px=0.01, origin_px=(100.0, 200.0))
    px, py = track.to_px(np.array([1.0]), np.array([1.0]))
    assert (px[0], py[0]) == (200.0, 100.0)


def test_results_serialise_to_json():
    fit = FitResult("projectile", {"g": Param(9.8, 0.1, "m/s²")}, {"g": 9.8}, 0.001, "good", 18)
    text = json.dumps({"fit": fit.to_json(), "track": line_track().to_json()})
    assert '"g"' in text
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `pip install -e .[dev]` then `pytest -q tests/test_core.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.core'`

- [ ] **Step 4: Write the implementation**

```python
# file: ghostlab/core.py
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
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `pytest -q tests/test_core.py`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore ghostlab tests
git commit -m "Scaffold and core track/fit types"
```

---

### Task 2: Projectile fit

**Files:**
- Create: `ghostlab/fit/projectile.py`
- Test: `tests/test_projectile.py`

**Interfaces:**
- Consumes: `Track`, `FitResult`, `Param`, `FitError`, `rmse_of`, `quality_of` from `ghostlab.core`.
- Produces: `MOTION = "projectile"`, `fit(track) -> FitResult` with params `g`, `launch_speed`, `launch_angle`, `vx`, `vy`; `simulate(sim, t) -> (x, y)` with sim keys `x0, vx, y0, vy, g`.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_projectile.py
import numpy as np
import pytest

from ghostlab.core import FitError, Track
from ghostlab.fit import projectile
from tests.synth import noisy


def make(g=9.81, vx=2.0, vy=3.0, seconds=0.6, fps=30, **kw):
    t = np.arange(0, seconds, 1 / fps)
    x, y = projectile.simulate({"x0": 0.0, "vx": vx, "y0": 0.0, "vy": vy, "g": g}, t)
    return noisy(t, x, y, **kw)


def test_recovers_g_within_its_error_bar():
    result = projectile.fit(make())
    g = result.params["g"]
    assert abs(g.value - 9.81) < 3 * g.error
    assert g.error < 0.5
    assert result.quality == "good"


def test_recovers_launch_angle():
    result = projectile.fit(make(vx=2.0, vy=2.0))
    assert abs(result.params["launch_angle"].value - 45.0) < 3.0


def test_survives_dropped_frames():
    result = projectile.fit(make(drop=0.3, seed=1))
    assert abs(result.params["g"].value - 9.81) < 1.0


def test_too_few_frames_is_an_error():
    with pytest.raises(FitError):
        projectile.fit(make(seconds=0.1))


def test_rising_object_is_not_a_projectile():
    t = np.arange(0, 0.6, 1 / 30)
    track = Track(t=t, x=np.zeros_like(t), y=0.5 * 9.81 * t**2, m_per_px=0.001)
    with pytest.raises(FitError):
        projectile.fit(track)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_projectile.py`
Expected: FAIL, `ImportError: cannot import name 'projectile'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/fit/projectile.py
"""Thrown or dropped object: x = x0 + vx t, y = y0 + vy t - g t^2 / 2."""
from __future__ import annotations

import math

import numpy as np

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "projectile"
MIN_POINTS = 6


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(t, dtype=float)
    return p["x0"] + p["vx"] * t, p["y0"] + p["vy"] * t - 0.5 * p["g"] * t**2


def fit(track: Track) -> FitResult:
    if len(track) < MIN_POINTS:
        raise FitError(f"need at least {MIN_POINTS} tracked frames, got {len(track)}")
    (vx, x0), cov_x = np.polyfit(track.t, track.x, 1, cov=True)
    (a, vy, y0), cov_y = np.polyfit(track.t, track.y, 2, cov=True)
    g = -2.0 * a
    if g <= 0:
        raise FitError("the object is not falling")
    evx = math.sqrt(cov_x[0, 0])
    eg, evy = 2.0 * math.sqrt(cov_y[0, 0]), math.sqrt(cov_y[1, 1])
    speed = math.hypot(vx, vy)
    espeed = math.hypot(vx * evx, vy * evy) / speed if speed else math.hypot(evx, evy)
    angle = math.degrees(math.atan2(vy, vx))
    eangle = math.degrees(math.hypot(vx * evy, vy * evx) / speed**2) if speed else 180.0
    sim = {"x0": float(x0), "vx": float(vx), "y0": float(y0), "vy": float(vy), "g": float(g)}
    rmse = rmse_of(track, *simulate(sim, track.t))
    params = {
        "g": Param(float(g), eg, "m/s²"),
        "launch_speed": Param(float(speed), float(espeed), "m/s"),
        "launch_angle": Param(angle, eangle, "°"),
        "vx": Param(float(vx), evx, "m/s"),
        "vy": Param(float(vy), evy, "m/s"),
    }
    return FitResult(MOTION, params, sim, rmse, quality_of(rmse, track), len(track))
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_projectile.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/fit/projectile.py tests/test_projectile.py
git commit -m "Projectile fit with error bars"
```

---

### Task 3: Bounce fit

**Files:**
- Create: `ghostlab/fit/bounce.py`
- Test: `tests/test_bounce.py`

**Interfaces:**
- Consumes: `ghostlab.core` as in Task 2.
- Produces: `MOTION = "bounce"`, `fit(track) -> FitResult` with params `e` (restitution), `g`, `bounces`; `simulate(sim, t)` with sim keys `x0, vx, y0, vy, g, e, floor, t_start`. Times before `t_start` simulate to NaN.

How it works: the low points of `y` split the track into arcs. Each arc gets its own parabola. The floor is where consecutive parabolas meet, the apex heights above the floor give `e = sqrt(h_next / h)` per bounce, and the results are combined by inverse-variance weighting.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_bounce.py
import numpy as np
import pytest

from ghostlab.core import FitError
from ghostlab.fit import bounce, projectile
from tests.synth import noisy

TRUE = {"x0": 0.0, "vx": 0.4, "y0": 1.0, "vy": 0.0, "g": 9.81, "e": 0.8, "floor": 0.0, "t_start": 0.0}


def make(seconds=2.5, fps=60, **kw):
    t = np.arange(0, seconds, 1 / fps)
    x, y = bounce.simulate(TRUE, t)
    return noisy(t, x, y, **kw)


def test_simulate_hits_floor_at_free_fall_time():
    t_hit = np.sqrt(2 * 1.0 / 9.81)
    _, y = bounce.simulate(TRUE, np.array([t_hit]))
    assert abs(y[0]) < 1e-6


@pytest.mark.parametrize("fps", [30, 60])
def test_recovers_restitution_within_its_error_bar(fps):
    result = bounce.fit(make(fps=fps))
    e = result.params["e"]
    assert abs(e.value - 0.8) < 3 * e.error
    assert e.error < 0.03
    assert abs(result.params["g"].value - 9.81) < 0.3
    assert result.params["bounces"].value >= 3
    assert result.quality == "good"


def test_single_arc_is_not_a_bounce():
    t = np.arange(0, 0.6, 1 / 30)
    x, y = projectile.simulate({"x0": 0.0, "vx": 2.0, "y0": 0.0, "vy": 3.0, "g": 9.81}, t)
    with pytest.raises(FitError):
        bounce.fit(noisy(t, x, y))
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_bounce.py`
Expected: FAIL, `ImportError: cannot import name 'bounce'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/fit/bounce.py
"""Bouncing ball: projectile arcs; each bounce keeps a fraction e of the vertical speed."""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import find_peaks

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "bounce"
MIN_ARC_POINTS = 5
MAX_BOUNCES = 50


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(t, dtype=float)
    x = p["x0"] + p["vx"] * t
    s_all = t - p["t_start"]
    y = np.where(s_all >= 0, p["floor"], np.nan)
    g, e, floor = p["g"], p["e"], p["floor"]
    start, y_start, vy = 0.0, p["y0"], p["vy"]
    for _ in range(MAX_BOUNCES):
        flight = (vy + math.sqrt(vy * vy + 2.0 * g * max(y_start - floor, 0.0))) / g
        if flight < 1e-4:
            break
        seg = (s_all >= start) & (s_all < start + flight)
        s = s_all[seg] - start
        y[seg] = y_start + vy * s - 0.5 * g * s * s
        vy = -e * (vy - g * flight)
        start, y_start = start + flight, floor
    return x, y


def _arc(t: np.ndarray, y: np.ndarray):
    """Parabola through one arc: g, its error, apex height, its error, coefficients."""
    (a, b, c), cov = np.polyfit(t, y, 2, cov=True)
    if a >= 0:
        raise FitError("an arc is not curving downward")
    apex = c - b * b / (4 * a)
    jac = np.array([b * b / (4 * a * a), -b / (2 * a), 1.0])
    return -2 * a, 2 * math.sqrt(cov[0, 0]), apex, math.sqrt(jac @ cov @ jac), (a, b, c)


def _meet(pa, pb, near: float, fallback: float) -> float:
    """Height where two consecutive parabolas meet, nearest the bounce time."""
    roots = np.roots(np.subtract(pa, pb))
    real = roots[np.isreal(roots)].real
    if len(real) == 0:
        return fallback
    t_hit = real[np.argmin(np.abs(real - near))]
    return float(np.polyval(pa, t_hit))


def _wmean(values, errors) -> tuple[float, float]:
    w = 1.0 / np.square(errors)
    return float(np.sum(w * np.asarray(values)) / np.sum(w)), float(math.sqrt(1.0 / np.sum(w)))


def fit(track: Track) -> FitResult:
    t, y = track.t, track.y
    span = float(np.ptp(y))
    if len(track) < 2 * MIN_ARC_POINTS or span == 0:
        raise FitError("too few frames for a bounce")
    lows, _ = find_peaks(-y, prominence=0.1 * span)
    if len(lows) == 0:
        raise FitError("no bounce found")
    bounds = [-1, *lows.tolist(), len(t)]
    arcs = [np.arange(a + 1, b) for a, b in zip(bounds[:-1], bounds[1:])]
    fits = [_arc(t[i], y[i]) if len(i) >= MIN_ARC_POINTS else None for i in arcs]
    pairs = [(k, fits[k], fits[k + 1]) for k in range(len(fits) - 1) if fits[k] and fits[k + 1]]
    if not pairs:
        raise FitError("need at least two full arcs between bounces")
    floor = float(np.median([_meet(fa[4], fb[4], t[lows[k]], y[lows[k]]) for k, fa, fb in pairs]))
    ratios, ratio_errors = [], []
    for _, fa, fb in pairs:
        ha, hb = fa[2] - floor, fb[2] - floor
        if ha <= 0 or hb <= 0:
            raise FitError("an arc peaks below the floor")
        e = math.sqrt(hb / ha)
        ratios.append(e)
        ratio_errors.append(e * 0.5 * math.hypot(fa[3] / ha, fb[3] / hb))
    e, ee = _wmean(ratios, ratio_errors)
    good = [f for f in fits if f]
    g, eg = _wmean([f[0] for f in good], [f[1] for f in good])
    first = next(k for k, f in enumerate(fits) if f)
    t_start = float(t[arcs[first][0]])
    a, b, c = fits[first][4]
    (vx, x0), cov_x = np.polyfit(t, track.x, 1, cov=True)
    sim = {
        "x0": float(x0), "vx": float(vx),
        "y0": float(np.polyval((a, b, c), t_start)), "vy": float(2 * a * t_start + b),
        "g": g, "e": e, "floor": floor, "t_start": t_start,
    }
    rmse = rmse_of(track, *simulate(sim, t))
    params = {
        "e": Param(e, ee, ""),
        "g": Param(g, eg, "m/s²"),
        "bounces": Param(float(len(pairs)), 0.0, ""),
    }
    return FitResult(MOTION, params, sim, rmse, quality_of(rmse, track), len(track))
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_bounce.py`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/fit/bounce.py tests/test_bounce.py
git commit -m "Bounce fit: restitution from consecutive arcs"
```

---

### Task 4: Pendulum fit

**Files:**
- Create: `ghostlab/fit/pendulum.py`
- Test: `tests/test_pendulum.py`

**Interfaces:**
- Consumes: `ghostlab.core` as in Task 2.
- Produces: `MOTION = "pendulum"`, `fit(track, pivot=None) -> FitResult` with params `length`, `period`, `g`, `damping`, `amplitude`; `simulate(sim, t)` with sim keys `px, py, L, A, gamma, omega, phi, offset`. `pivot` is `(x, y)` in metres in track coordinates. When it is `None`, the pivot comes from a circle fit.

How it works: a geometric circle fit gives the pivot and length, with an error that includes the pivot's uncertainty (a quick algebraic fit is only the starting guess; on small arcs it comes out about 6% short). Then convert to the angle `theta(t)` and fit a damped cosine. A small swing can't pin the length from its shape alone, so the fit reports a wide error and marks itself "rough". Plan 2 supplies the pivot from SAM's outline of the string. Then `g = (omega^2 + gamma^2) L (1 + amp^2/16)^2`, which includes the finite-amplitude period correction. The test data comes from the full nonlinear pendulum equation, so the correction is genuinely tested.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_pendulum.py
import numpy as np
import pytest
from scipy.integrate import solve_ivp

from ghostlab.core import FitError
from ghostlab.fit import pendulum, projectile
from tests.synth import noisy


def swing(L=0.8, g=9.81, theta0=0.25, gamma=0.05, seconds=6.0, fps=30, pivot=(0.0, 1.0)):
    t = np.arange(0, seconds, 1 / fps)
    rhs = lambda _t, s: [s[1], -(g / L) * np.sin(s[0]) - 2 * gamma * s[1]]
    th = solve_ivp(rhs, (0, seconds), [theta0, 0.0], t_eval=t, rtol=1e-10, atol=1e-12).y[0]
    return noisy(t, pivot[0] + L * np.sin(th), pivot[1] - L * np.cos(th))


def test_small_swing_gives_honest_error_bars():
    result = pendulum.fit(swing())
    g, L = result.params["g"], result.params["length"]
    assert abs(g.value - 9.81) < 3 * g.error
    assert abs(L.value - 0.8) < 3 * L.error
    assert abs(result.params["period"].value - 2 * np.pi * np.sqrt(0.8 / 9.81)) < 0.02


def test_tiny_swing_without_pivot_is_rough():
    assert pendulum.fit(swing(theta0=0.15)).quality == "rough"


def test_big_swing_pins_length_and_uses_amplitude_correction():
    result = pendulum.fit(swing(theta0=0.6))
    assert abs(result.params["length"].value - 0.8) < 0.01
    assert abs(result.params["g"].value - 9.81) < 0.15
    assert result.quality == "good"


def test_known_pivot_gives_the_same_answer():
    result = pendulum.fit(swing(), pivot=(0.0, 1.0))
    assert abs(result.params["g"].value - 9.81) < 0.1


def test_projectile_arc_is_not_a_pendulum():
    t = np.arange(0, 0.6, 1 / 30)
    x, y = projectile.simulate({"x0": 0.0, "vx": 2.0, "y0": 0.0, "vy": 3.0, "g": 9.81}, t)
    with pytest.raises(FitError):
        pendulum.fit(noisy(t, x, y))
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_pendulum.py`
Expected: FAIL, `ImportError: cannot import name 'pendulum'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/fit/pendulum.py
"""Pendulum: the bob moves on a circle round a pivot; its angle is a damped cosine."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import curve_fit, least_squares

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "pendulum"
MIN_POINTS = 12
MIN_CROSSINGS = 3  # at least one full swing
MAX_LENGTH_ERROR = 0.05  # above 5% the fit is "rough": swing wider or give the pivot


def _theta(t, A, gamma, omega, phi, offset):
    return A * np.exp(-gamma * t) * np.cos(omega * t + phi) + offset


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    th = _theta(np.asarray(t, dtype=float), p["A"], p["gamma"], p["omega"], p["phi"], p["offset"])
    return p["px"] + p["L"] * np.sin(th), p["py"] - p["L"] * np.cos(th)


def _circle_centre(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Algebraic (Kasa) circle fit: fast, but biased short on small arcs; only a starting guess."""
    design = np.column_stack([x, y, np.ones_like(x)])
    (c1, c2, _), *_ = np.linalg.lstsq(design, x * x + y * y, rcond=None)
    return float(c1 / 2), float(c2 / 2)


def _pivot_and_length(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """Geometric circle fit. The length error includes the pivot's uncertainty."""
    px, py = _circle_centre(x, y)
    start = [px, py, float(np.mean(np.hypot(x - px, y - py)))]
    res = least_squares(lambda p: np.hypot(x - p[0], y - p[1]) - p[2], start)
    s2 = float(np.sum(res.fun**2)) / (len(x) - 3)
    cov = np.linalg.inv(res.jac.T @ res.jac) * s2
    return float(res.x[0]), float(res.x[1]), float(res.x[2]), math.sqrt(cov[2, 2])


def fit(track: Track, pivot: tuple[float, float] | None = None) -> FitResult:
    t, x, y = track.t, track.x, track.y
    if len(track) < MIN_POINTS:
        raise FitError(f"need at least {MIN_POINTS} tracked frames, got {len(track)}")
    if pivot is None:
        px, py, L, eL = _pivot_and_length(x, y)
    else:
        px, py = pivot
        r = np.hypot(x - px, y - py)
        L, eL = float(np.mean(r)), float(np.std(r, ddof=1) / math.sqrt(len(r)))
    if py <= float(np.mean(y)):
        raise FitError("the path does not hang below a pivot")
    theta = np.arctan2(x - px, py - y)
    crossings = int(np.sum(np.diff(np.sign(theta - theta.mean())) != 0))
    if crossings < MIN_CROSSINGS:
        raise FitError("need at least one full swing")
    w0 = math.pi * crossings / float(t[-1] - t[0])
    design = np.column_stack([np.cos(w0 * t), np.sin(w0 * t), np.ones_like(t)])
    (ca, cb, cc), *_ = np.linalg.lstsq(design, theta, rcond=None)
    p0 = [math.hypot(ca, cb), 0.01, w0, math.atan2(-cb, ca), cc]
    try:
        popt, pcov = curve_fit(
            _theta, t, theta, p0=p0,
            bounds=([0.0, 0.0, 0.2 * w0, -np.inf, -np.pi], [np.pi, 5.0, 5.0 * w0, np.inf, np.pi]),
        )
    except RuntimeError as exc:
        raise FitError(f"swing fit did not converge: {exc}") from exc
    A, gamma, omega, phi, offset = (float(v) for v in popt)
    eA, egamma, eomega = (float(v) for v in np.sqrt(np.diag(pcov))[:3])
    amp = A * float(np.mean(np.exp(-gamma * t)))
    g = (omega**2 + gamma**2) * L * (1 + amp**2 / 16) ** 2
    eg = g * math.hypot(2 * eomega / omega, eL / L)
    period = 2 * math.pi / omega
    sim = {"px": px, "py": py, "L": L, "A": A, "gamma": gamma, "omega": omega, "phi": phi, "offset": offset}
    rmse = rmse_of(track, *simulate(sim, t))
    params = {
        "length": Param(L, eL, "m"),
        "period": Param(period, period * eomega / omega, "s"),
        "g": Param(g, eg, "m/s²"),
        "damping": Param(gamma, egamma, "1/s"),
        "amplitude": Param(math.degrees(amp), math.degrees(eA), "°"),
    }
    quality = "rough" if eL / L > MAX_LENGTH_ERROR else quality_of(rmse, track)
    return FitResult(MOTION, params, sim, rmse, quality, len(track))
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_pendulum.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/fit/pendulum.py tests/test_pendulum.py
git commit -m "Pendulum fit with amplitude correction"
```

---

### Task 5: Ramp fit

**Files:**
- Create: `ghostlab/fit/ramp.py`
- Test: `tests/test_ramp.py`

**Interfaces:**
- Consumes: `ghostlab.core` as in Task 2.
- Produces: `MOTION = "ramp"`, `G = 9.81`, `fit(track) -> FitResult` with params `angle`, `acceleration`, `friction`, `start_speed`; `simulate(sim, t)` with sim keys `xs, ys, dx, dy, s0, v0, a`.

How it works: the path's main direction (from an SVD) gives the slope angle. The distance along it is fitted as `s0 + v0 t + a t^2/2`, and `mu = tan(angle) - a / (g cos(angle))`. The angle error comes from the scatter perpendicular to the line.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_ramp.py
import math

import numpy as np
import pytest

from ghostlab.core import FitError
from ghostlab.fit import ramp
from tests.synth import noisy


def slide(angle_deg=20.0, mu=0.15, seconds=1.2, fps=30, **kw):
    ang = math.radians(angle_deg)
    a = ramp.G * (math.sin(ang) - mu * math.cos(ang))
    t = np.arange(0, seconds, 1 / fps)
    s = 0.5 * a * t**2
    return noisy(t, s * math.cos(ang), -s * math.sin(ang), **kw)


def test_recovers_friction_and_angle():
    result = ramp.fit(slide())
    mu = result.params["friction"]
    assert abs(mu.value - 0.15) < 3 * mu.error
    assert mu.error < 0.05
    assert abs(result.params["angle"].value - 20.0) < 1.0
    assert result.quality == "good"


def test_flat_surface_is_not_a_ramp():
    with pytest.raises(FitError):
        ramp.fit(slide(angle_deg=1.0, mu=0.0))


def test_straight_drop_is_not_a_ramp():
    t = np.arange(0, 0.6, 1 / 30)
    with pytest.raises(FitError):
        ramp.fit(noisy(t, np.zeros_like(t), -0.5 * 9.81 * t**2))
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_ramp.py`
Expected: FAIL, `ImportError: cannot import name 'ramp'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/fit/ramp.py
"""Sliding down a ramp: constant acceleration along a straight line; friction from the slope."""
from __future__ import annotations

import math

import numpy as np

from ghostlab.core import FitError, FitResult, Param, Track, quality_of, rmse_of

MOTION = "ramp"
G = 9.81
MIN_POINTS = 8
MIN_SLOPE_DEG = 3.0
MAX_SLOPE_DEG = 85.0


def simulate(p: dict[str, float], t) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(t, dtype=float)
    s = p["s0"] + p["v0"] * t + 0.5 * p["a"] * t * t
    return p["xs"] + p["dx"] * s, p["ys"] + p["dy"] * s


def fit(track: Track) -> FitResult:
    if len(track) < MIN_POINTS:
        raise FitError(f"need at least {MIN_POINTS} tracked frames, got {len(track)}")
    pts = np.column_stack([track.x, track.y])
    centre = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centre)
    d = vt[0] if vt[0][1] <= 0 else -vt[0]  # point downhill
    angle = math.atan2(-d[1], abs(d[0]))
    if math.degrees(angle) < MIN_SLOPE_DEG:
        raise FitError("too flat to be a ramp")
    if math.degrees(angle) > MAX_SLOPE_DEG:
        raise FitError("that is a fall, not a slide")
    s = (pts - centre) @ d
    n = (pts - centre) @ np.array([-d[1], d[0]])
    eangle = float(np.std(n, ddof=2) / math.sqrt(np.sum((s - s.mean()) ** 2)))
    (half_a, v0, s0), cov = np.polyfit(track.t, s, 2, cov=True)
    a, ea = 2 * float(half_a), 2 * math.sqrt(cov[0, 0])
    if a <= 0:
        raise FitError("the object is not speeding up downhill")
    cos, sin = math.cos(angle), math.sin(angle)
    mu = math.tan(angle) - a / (G * cos)
    dmu_dangle = 1 / cos**2 - a * sin / (G * cos**2)
    emu = math.hypot(dmu_dangle * eangle, ea / (G * cos))
    sim = {"xs": float(centre[0]), "ys": float(centre[1]), "dx": float(d[0]), "dy": float(d[1]),
           "s0": float(s0), "v0": float(v0), "a": a}
    rmse = rmse_of(track, *simulate(sim, track.t))
    params = {
        "angle": Param(math.degrees(angle), math.degrees(eangle), "°"),
        "acceleration": Param(a, ea, "m/s²"),
        "friction": Param(mu, emu, ""),
        "start_speed": Param(float(v0), math.sqrt(cov[1, 1]), "m/s"),
    }
    return FitResult(MOTION, params, sim, rmse, quality_of(rmse, track), len(track))
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_ramp.py`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/fit/ramp.py tests/test_ramp.py
git commit -m "Ramp fit: slope angle and friction"
```

---

### Task 6: Fit every model and flag a better one

**Files:**
- Create: `ghostlab/fit/select.py`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: the four fit modules.
- Produces: `MODULES: dict[str, module]`, `fit_all(track, pivot=None) -> dict[str, FitResult | str]` (a string is the FitError message), `better_alternative(chosen, results) -> str | None`, `MUCH_BETTER = 0.5`.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_select.py
import numpy as np

from ghostlab.core import FitResult
from ghostlab.fit import bounce, projectile
from ghostlab.fit.select import better_alternative, fit_all
from tests.synth import noisy


def throw():
    t = np.arange(0, 0.6, 1 / 30)
    return noisy(t, *projectile.simulate({"x0": 0.0, "vx": 2.0, "y0": 0.0, "vy": 3.0, "g": 9.81}, t))


def bouncing():
    p = {"x0": 0.0, "vx": 0.4, "y0": 1.0, "vy": 0.0, "g": 9.81, "e": 0.8, "floor": 0.0, "t_start": 0.0}
    t = np.arange(0, 2.5, 1 / 30)
    return noisy(t, *bounce.simulate(p, t))


def test_fit_all_returns_every_model():
    results = fit_all(throw())
    assert set(results) == {"projectile", "bounce", "pendulum", "ramp"}
    assert isinstance(results["projectile"], FitResult)
    assert isinstance(results["bounce"], str)


def test_no_alternative_when_choice_is_best():
    assert better_alternative("projectile", fit_all(throw())) is None


def test_flags_projectile_when_ramp_was_chosen():
    assert better_alternative("ramp", fit_all(throw())) == "projectile"


def test_flags_bounce_when_projectile_was_chosen():
    assert better_alternative("projectile", fit_all(bouncing())) == "bounce"
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_select.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.fit.select'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/fit/select.py
"""Run every motion model; say when another model fits much better than the chosen one."""
from __future__ import annotations

from ghostlab.core import FitError, FitResult, Track
from ghostlab.fit import bounce, pendulum, projectile, ramp

MODULES = {m.MOTION: m for m in (projectile, bounce, pendulum, ramp)}
MUCH_BETTER = 0.5  # another model must halve the RMSE to be suggested


def fit_all(track: Track, pivot: tuple[float, float] | None = None) -> dict[str, FitResult | str]:
    results: dict[str, FitResult | str] = {}
    for name, module in MODULES.items():
        try:
            results[name] = module.fit(track, pivot=pivot) if name == "pendulum" else module.fit(track)
        except FitError as exc:
            results[name] = str(exc)
    return results


def better_alternative(chosen: str, results: dict[str, FitResult | str]) -> str | None:
    fitted = {k: v for k, v in results.items() if isinstance(v, FitResult)}
    if not fitted:
        return None
    best = min(fitted.values(), key=lambda r: r.rmse)
    if best.motion == chosen:
        return None
    mine = fitted.get(chosen)
    if mine is None or best.rmse < MUCH_BETTER * mine.rmse:
        return best.motion
    return None
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_select.py`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/fit/select.py tests/test_select.py
git commit -m "Fit all models and flag a better one"
```

---

### Task 7: Pixels to metres, with gap handling

**Files:**
- Create: `ghostlab/scale.py`
- Test: `tests/test_scale.py`

**Interfaces:**
- Consumes: `PixelTrack`, `Track`, `FitError`.
- Produces: `to_metres(px: PixelTrack, real_size_m: float) -> tuple[Track, list[str]]`, `pivot_to_metres(track, pivot_px) -> tuple[float, float]`, `MAX_GAP = 3`, `MIN_FRAMES = 6`.
- `real_size_m` is the object's longest side, matched to the median of `max(box w, box h)`. Gaps of up to `MAX_GAP` frames are interpolated. A longer gap splits the track, and the segment with the most real detections is kept. Each choice adds a note for the student.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_scale.py
import numpy as np
import pytest

from ghostlab.core import FitError, PixelTrack
from ghostlab.scale import pivot_to_metres, to_metres


def pixel_track(n=20, missing=()):
    cx = 100.0 + 10.0 * np.arange(n)
    cy = 500.0 - 5.0 * np.arange(n)
    cx[list(missing)] = np.nan
    cy[list(missing)] = np.nan
    w = np.full(n, 50.0)
    return PixelTrack(t=np.arange(n) / 30, cx=cx, cy=cy, w=w, h=w, frame_w=1280, frame_h=720)


def test_scale_and_axes():
    track, notes = to_metres(pixel_track(), 0.05)
    assert track.m_per_px == pytest.approx(0.001)
    assert track.x[1] == pytest.approx(0.010)
    assert track.y[1] == pytest.approx(0.005)  # image y down becomes y up
    assert track.t[0] == 0 and notes == []


def test_short_gap_is_filled():
    track, notes = to_metres(pixel_track(missing=(5, 6)), 0.05)
    assert len(track) == 20
    assert track.x[5] == pytest.approx(0.050)
    assert notes == ["filled 2 missing frame(s)"]


def test_long_gap_keeps_longest_segment():
    track, notes = to_metres(pixel_track(missing=range(4, 9)), 0.05)
    assert len(track) == 11
    assert track.t0 == pytest.approx(9 / 30)
    assert any("used frames 9-19" in n for n in notes)


def test_too_few_frames():
    with pytest.raises(FitError):
        to_metres(pixel_track(missing=range(3, 20)), 0.05)


def test_pivot_to_metres():
    track, _ = to_metres(pixel_track(), 0.05)
    assert pivot_to_metres(track, (200.0, 400.0)) == pytest.approx((0.1, 0.1))
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_scale.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.scale'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/scale.py
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
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_scale.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/scale.py tests/test_scale.py
git commit -m "Scale pixel tracks to metres with gap handling"
```

---

### Task 8: Ingest a clip

**Files:**
- Create: `ghostlab/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Produces: `Clip` (fields `path: Path, fps: float, n_frames: int, width: int, height: int, key_frames: list[bytes]` (3 JPEGs: first, middle, last), `camera_shift: float` (background shift as a fraction of width)), `prepare(src: Path, work: Path) -> Clip`, `MAX_SECONDS = 15`, `MAX_HEIGHT = 720`, `SHAKE_LIMIT = 0.02`.
- The normalised clip is H.264 MP4, constant frame rate, no audio. SAM 3.1 accepts this, and it rejects VP9/WebM, which some phones produce.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_ingest.py
import cv2
import numpy as np

from ghostlab.ingest import SHAKE_LIMIT, prepare


def write_clip(path, shake_px=0, n=60, fps=30):
    rng = np.random.default_rng(0)
    background = rng.integers(0, 255, (760, 1280 + n * 2, 3), dtype=np.uint8)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1280, 720))
    for i in range(n):
        dx = i * shake_px
        frame = background[20:740, dx:dx + 1280].copy()
        cv2.circle(frame, (100 + 15 * i, 300), 25, (0, 255, 255), -1)
        writer.write(frame)
    writer.release()


def test_prepare_normalises_and_grabs_key_frames(tmp_path):
    src = tmp_path / "raw.mp4"
    write_clip(src)
    clip = prepare(src, tmp_path / "work")
    assert clip.path.exists() and clip.path.suffix == ".mp4"
    assert abs(clip.fps - 30) < 0.5
    assert 58 <= clip.n_frames <= 61
    assert clip.height == 720
    assert len(clip.key_frames) == 3 and all(f[:2] == b"\xff\xd8" for f in clip.key_frames)
    assert clip.camera_shift < SHAKE_LIMIT


def test_moving_background_reads_as_shaky(tmp_path):
    src = tmp_path / "shaky.mp4"
    write_clip(src, shake_px=1)  # frames 6 and 54 differ by 48 px, 3.75% of the width
    assert prepare(src, tmp_path / "work").camera_shift > SHAKE_LIMIT
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_ingest.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.ingest'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/ingest.py
"""Normalise a phone clip for SAM 3.1 and pull the frames Muse Spark looks at."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

MAX_SECONDS = 15
MAX_HEIGHT = 720
SHAKE_LIMIT = 0.02  # background shift above 2% of the width reads as a hand-held camera


@dataclass(frozen=True)
class Clip:
    path: Path
    fps: float
    n_frames: int
    width: int
    height: int
    key_frames: list[bytes]
    camera_shift: float


def _normalise(src: Path, out: Path) -> None:
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src),
        "-t", str(MAX_SECONDS), "-vf", f"scale=-2:'min({MAX_HEIGHT},ih)'",
        "-fps_mode", "cfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out),
    ]
    subprocess.run(cmd, check=True)


def _read_frames(path: Path) -> tuple[float, list[np.ndarray]]:
    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return fps, frames


def _shift(a: np.ndarray, b: np.ndarray) -> float:
    ga = np.float32(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY))
    gb = np.float32(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY))
    (dx, dy), _ = cv2.phaseCorrelate(ga, gb)
    return float(np.hypot(dx, dy) / a.shape[1])


def prepare(src: Path, work: Path) -> Clip:
    work.mkdir(parents=True, exist_ok=True)
    out = work / "clip.mp4"
    _normalise(src, out)
    fps, frames = _read_frames(out)
    if len(frames) < 2:
        raise ValueError("the clip has fewer than two frames")
    n = len(frames)
    keys = [cv2.imencode(".jpg", frames[i])[1].tobytes() for i in (0, n // 2, n - 1)]
    shift = _shift(frames[n // 10], frames[(9 * n) // 10])
    h, w = frames[0].shape[:2]
    return Clip(out, fps, n, w, h, keys, shift)
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_ingest.py`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/ingest.py tests/test_ingest.py
git commit -m "Ingest: normalise clip, key frames, shake check"
```

---

### Task 9: Cache and Meta API client

**Files:**
- Create: `ghostlab/cache.py`, `ghostlab/meta_api.py`, `tests/fakes.py`
- Test: `tests/test_cache.py`, `tests/test_meta_api.py`

**Interfaces:**
- Produces: `cached(kind: str, key: bytes, compute: Callable[[], dict], root: Path | None = None) -> dict` (JSON on disk at `<root>/<kind>/<sha256>.json`; root defaults to env `GHOSTLAB_CACHE` or `.cache`).
- Produces: `meta_api.client() -> OpenAI`, `upload_video(c, path) -> str` (file id), `sam_track(c, file_id, prompt) -> str` (raw `output_text`), `spark_json(c, prompt, images: list[bytes], name, schema) -> dict`, constants `BASE_URL`, `SPARK = "muse-spark-1.3"`, `SAM = "sam-3.1"`.
- Produces: `tests.fakes.FakeMeta(chat_replies: list[dict], sam_text: str)`. It records every call, refuses unexpected models, and answers `files.create`, `responses.create` and `chat.completions.create`.

- [ ] **Step 1: Write the fake and the failing tests**

```python
# file: tests/fakes.py
"""A Meta Model API stand-in that records calls and refuses wrong models."""
import json
from types import SimpleNamespace


class FakeMeta:
    def __init__(self, chat_replies=(), sam_text=""):
        self.chat_replies = list(chat_replies)
        self.sam_text = sam_text
        self.calls = []
        self.files = SimpleNamespace(create=self._file_create)
        self.responses = SimpleNamespace(create=self._responses_create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))

    def _file_create(self, file, purpose):
        assert purpose == "user_data"
        self.calls.append(("file", file.name))
        return SimpleNamespace(id=f"file-{len(self.calls)}")

    def _responses_create(self, model, input):
        assert model == "sam-3.1", model
        self.calls.append(("sam", input))
        return SimpleNamespace(output_text=self.sam_text)

    def _chat_create(self, model, messages, response_format):
        assert model == "muse-spark-1.3", model
        assert response_format["type"] == "json_schema"
        self.calls.append(("chat", messages, response_format))
        reply = self.chat_replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))])
```

```python
# file: tests/test_cache.py
from ghostlab.cache import cached


def test_computes_once_per_key(tmp_path):
    calls = []

    def compute():
        calls.append(1)
        return {"n": len(calls)}

    assert cached("sam", b"a", compute, tmp_path) == {"n": 1}
    assert cached("sam", b"a", compute, tmp_path) == {"n": 1}
    assert cached("sam", b"b", compute, tmp_path) == {"n": 2}
    assert len(list((tmp_path / "sam").glob("*.json"))) == 2


def test_kinds_do_not_collide(tmp_path):
    assert cached("a", b"k", lambda: {"v": "a"}, tmp_path) == {"v": "a"}
    assert cached("b", b"k", lambda: {"v": "b"}, tmp_path) == {"v": "b"}
```

```python
# file: tests/test_meta_api.py
import base64

from ghostlab import meta_api
from tests.fakes import FakeMeta


def test_sam_track_sends_prompt_and_video(tmp_path):
    fake = FakeMeta(sam_text="<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    file_id = meta_api.upload_video(fake, clip)
    text = meta_api.sam_track(fake, file_id, "tennis ball")
    assert text.startswith("<0f>")
    content = fake.calls[1][1][0]["content"]
    assert content[0] == {"type": "input_text", "text": "tennis ball"}
    assert content[1] == {"type": "input_video", "file_id": file_id}


def test_spark_json_sends_images_and_schema():
    fake = FakeMeta(chat_replies=[{"object": "ball"}])
    schema = {"type": "object", "properties": {"object": {"type": "string"}},
              "required": ["object"], "additionalProperties": False}
    reply = meta_api.spark_json(fake, "what is it?", [b"img1", b"img2"], "probe", schema)
    assert reply == {"object": "ball"}
    _, messages, fmt = fake.calls[0]
    parts = messages[0]["content"]
    assert parts[0] == {"type": "text", "text": "what is it?"}
    assert parts[2]["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(b"img2").decode()
    assert fmt["json_schema"]["name"] == "probe" and fmt["json_schema"]["schema"] == schema
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `pytest -q tests/test_cache.py tests/test_meta_api.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.cache'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/cache.py
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
```

```python
# file: ghostlab/meta_api.py
"""Thin wrappers over the Meta Model API (OpenAI-compatible)."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"
SPARK = "muse-spark-1.3"
SAM = "sam-3.1"


def client() -> OpenAI:
    return OpenAI(api_key=os.environ["MODEL_API_KEY"], base_url=BASE_URL)


def upload_video(c, path: Path) -> str:
    with open(path, "rb") as f:
        return c.files.create(file=f, purpose="user_data").id


def sam_track(c, file_id: str, prompt: str) -> str:
    content = [{"type": "input_text", "text": prompt}, {"type": "input_video", "file_id": file_id}]
    response = c.responses.create(model=SAM, input=[{"type": "message", "role": "user", "content": content}])
    return response.output_text


def spark_json(c, prompt: str, images: list[bytes], name: str, schema: dict) -> dict:
    parts = [{"type": "text", "text": prompt}]
    for img in images:
        url = "data:image/jpeg;base64," + base64.b64encode(img).decode()
        parts.append({"type": "image_url", "image_url": {"url": url}})
    response = c.chat.completions.create(
        model=SPARK,
        messages=[{"role": "user", "content": parts}],
        response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
    )
    return json.loads(response.choices[0].message.content)
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_cache.py tests/test_meta_api.py`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/cache.py ghostlab/meta_api.py tests/fakes.py tests/test_cache.py tests/test_meta_api.py
git commit -m "Disk cache and Meta Model API wrappers"
```

---

### Task 10: API spike (needs the hackathon credits)

**Files:**
- Create: `scripts/spike.py`, `docs/spike.md`, `tests/fixtures/sam_real.txt` (written by the script)

**Interfaces:**
- Consumes: `meta_api` from Task 9.
- Produces: `tests/fixtures/sam_real.txt` (one real SAM 3.1 response for a thrown-ball clip) and `docs/spike.md` (the answers below). Task 11 tests against the fixture.

- [ ] **Step 1: Film the probe clip.** On a phone propped against something, film a tennis ball thrown across the frame, side-on, for about 3 s. Save it as `clips/probe_throw.mp4`. In `.gitignore` add `clips/*.mp4` and `!clips/probe_throw.mp4`, so only this clip is committed.

- [ ] **Step 2: Write the probe script**

```python
# file: scripts/spike.py
"""Day-1 probe: one SAM 3.1 video call and one Muse Spark image call; saves the raw SAM output."""
import json
import re
import sys
import time
from pathlib import Path

import cv2

from ghostlab import meta_api

SCHEMA = {"type": "object", "properties": {"object": {"type": "string"}, "size_m": {"type": "number"}},
          "required": ["object", "size_m"], "additionalProperties": False}


def main(clip: Path, prompt: str) -> None:
    c = meta_api.client()
    cap = cv2.VideoCapture(str(clip))
    fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    _, frame = cap.read()
    cap.release()
    t0 = time.time()
    file_id = meta_api.upload_video(c, clip)
    t1 = time.time()
    text = meta_api.sam_track(c, file_id, prompt)
    t2 = time.time()
    out = Path("tests/fixtures/sam_real.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    tags = [int(m) for m in re.findall(r"<(\d+)f>", text)]
    print(json.dumps({"fps": fps, "frames": n, "frame_tags": len(tags), "first_tags": tags[:5],
                      "upload_s": round(t1 - t0, 1), "sam_s": round(t2 - t1, 1), "chars": len(text)}, indent=2))
    jpg = cv2.imencode(".jpg", frame)[1].tobytes()
    t3 = time.time()
    reply = meta_api.spark_json(c, "Name the moving object and its real longest side in metres.", [jpg], "probe", SCHEMA)
    print(json.dumps({"spark": reply, "spark_s": round(time.time() - t3, 1)}, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "tennis ball")
```

- [ ] **Step 3: Run it**

Run: `MODEL_API_KEY=<key> python scripts/spike.py clips/probe_throw.mp4 "tennis ball"`
Expected: two JSON blocks printed, and `tests/fixtures/sam_real.txt` written.

- [ ] **Step 4: Write `docs/spike.md`** with the measured answers, then apply the matching rule:

| Question | Rule if the answer differs from the plan's assumption |
|---|---|
| Does `frame_tags` equal `frames`, numbered 0, 1, 2, ...? | If the tags step by k (0, k, 2k), no change: `to_pixel_track` maps tag n to `n / fps`. If they run 0, 1, 2 but there are fewer of them than frames, change Task 11's `t = np.arange(n_frames) / fps` to `t = np.arange(n_frames) * (clip_frames / tag_count) / fps` and add a test for it. |
| Does each frame look like `<Nf>id<\|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..\|>`? | If not, change `FRAME_TAG` / `OBJECT` in Task 11 until `test_real_fixture` passes. The doc-example test stays as well. |
| SAM time for a 3 s clip | If over 20 s, set `ingest.MAX_SECONDS = 8` and say so in the spec. |
| Cost of the run (from the dashboard) | Record it. If more than $0.50 per clip, revisit the budget section of the spec. |
| Did Muse Spark give a plausible size (tennis ball about 0.067 m)? | If it is wrong by more than 30%, Task 12's prompt must list common reference sizes. |
| Does `upload_video` reject `purpose="user_data"`? | If yes, fall back to sending `{"type": "input_video", "video_url": "data:video/mp4;base64,..."}` in `sam_track` and update `test_sam_track_sends_prompt_and_video` to match. |

- [ ] **Step 5: Commit**

```bash
git add scripts/spike.py docs/spike.md tests/fixtures/sam_real.txt clips/probe_throw.mp4 .gitignore
git commit -m "API spike: real SAM 3.1 fixture and findings"
```

---

### Task 11: Parse SAM 3.1 output into a pixel track

**Files:**
- Create: `ghostlab/sam_parse.py`
- Test: `tests/test_sam_parse.py`

**Interfaces:**
- Consumes: `PixelTrack`; `tests/fixtures/sam_real.txt` from Task 10.
- Produces: `Box(x1, y1, x2, y2, conf)`, `parse(text) -> dict[int, dict[int, Box]]` (frame -> object id -> box), `pick_object(frames) -> int | None` (the id seen in the most frames), `to_pixel_track(frames, n_frames, fps, frame_w, frame_h, object_id=None) -> PixelTrack`.
- Mask blocks are stripped before parsing, because their payload can contain text that looks like a frame tag. v1 uses box centres; mask centroids come in Plan 2.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_sam_parse.py
from pathlib import Path

import numpy as np

from ghostlab.sam_parse import parse, pick_object, to_pixel_track

DOC_EXAMPLE = ("<0f>0<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334|><|mask;x=0;y=0;data=27,60,~!!<3f>!M|>,"
               "1<|box;x1=10;y1=10;x2=20;y2=20;w=320;h=334;c=0.4|>\n"
               "<1f>0<|box;x1=221;y1=238;x2=280;y2=264;w=320;h=334|>\n"
               "<3f>0<|box;x1=241;y1=258;x2=300;y2=284;w=320;h=334|>\n")


def test_parse_doc_example():
    frames = parse(DOC_EXAMPLE)
    assert sorted(frames) == [0, 1, 3]  # the "<3f>" inside the mask is not a frame
    assert frames[0][0].x1 == 211 and frames[0][1].conf == 0.4
    assert frames[1][0].conf is None


def test_pick_object_prefers_most_frames():
    assert pick_object(parse(DOC_EXAMPLE)) == 0
    assert pick_object({}) is None


def test_pixel_track_marks_missing_frames():
    track = to_pixel_track(parse(DOC_EXAMPLE), n_frames=4, fps=2.0, frame_w=320, frame_h=334)
    assert track.cx[0] == 240.5 and track.cy[0] == 241.0 and track.w[0] == 59
    assert np.isnan(track.cx[2])
    assert track.t[3] == 1.5


def test_real_fixture():
    text = Path("tests/fixtures/sam_real.txt").read_text(encoding="utf-8")
    frames = parse(text)
    assert len(frames) >= 10
    oid = pick_object(frames)
    assert oid is not None
    hits = sum(oid in objs for objs in frames.values())
    assert hits >= 0.8 * len(frames)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_sam_parse.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.sam_parse'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/sam_parse.py
"""Parse SAM 3.1's special-token output (one line per frame) into a pixel track."""
from __future__ import annotations

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


def parse(text: str) -> dict[int, dict[int, Box]]:
    parts = FRAME_TAG.split(MASK.sub("", text))
    frames: dict[int, dict[int, Box]] = {}
    for number, body in zip(parts[1::2], parts[2::2]):
        objects = {}
        for oid, fields in OBJECT.findall(body):
            kv = dict(f.split("=", 1) for f in fields.split(";") if "=" in f)
            objects[int(oid)] = Box(float(kv["x1"]), float(kv["y1"]), float(kv["x2"]), float(kv["y2"]),
                                    float(kv["c"]) if "c" in kv else None)
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
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_sam_parse.py`
Expected: `4 passed`. If `test_real_fixture` fails, apply the Task 10 rule for the output format. Don't weaken the test.

- [ ] **Step 5: Commit**

```bash
git add ghostlab/sam_parse.py tests/test_sam_parse.py
git commit -m "Parse SAM 3.1 boxes into a pixel track"
```

---

### Task 12: Identify and explain (Muse Spark)

**Files:**
- Create: `ghostlab/identify.py`, `ghostlab/explain.py`
- Test: `tests/test_identify.py`, `tests/test_explain.py`

**Interfaces:**
- Consumes: `meta_api.spark_json`, `FitResult`, `tests.fakes.FakeMeta`.
- Produces: `identify.identify(c, frames: list[bytes]) -> dict` with keys `object, sam_prompt, real_size_m, size_confidence ("high"|"medium"|"low"), motion ("projectile"|"bounce"|"pendulum"|"ramp"), has_pivot, pivot_x_px, pivot_y_px, reasoning`; `identify.PROMPT_VERSION`.
- Produces: `explain.explain(c, object_name, fit: FitResult) -> dict` with keys `explanation, class_question`; `explain.PROMPT_VERSION`. Only numbers go in; no images.

- [ ] **Step 1: Write the failing tests**

```python
# file: tests/test_identify.py
import pytest

from ghostlab.identify import identify
from tests.fakes import FakeMeta

REPLY = {"object": "tennis ball", "sam_prompt": "tennis ball", "real_size_m": 0.067, "size_confidence": "high",
         "motion": "projectile", "has_pivot": False, "pivot_x_px": 0, "pivot_y_px": 0, "reasoning": "thrown"}


def test_sends_three_frames_and_returns_fields():
    fake = FakeMeta(chat_replies=[REPLY])
    result = identify(fake, [b"a", b"b", b"c"])
    assert result["motion"] == "projectile" and result["real_size_m"] == 0.067
    _, messages, fmt = fake.calls[0]
    assert sum(p["type"] == "image_url" for p in messages[0]["content"]) == 3
    assert fmt["json_schema"]["name"] == "identification"


def test_rejects_impossible_size():
    fake = FakeMeta(chat_replies=[{**REPLY, "real_size_m": 0}])
    with pytest.raises(ValueError):
        identify(fake, [b"a", b"b", b"c"])
```

```python
# file: tests/test_explain.py
from ghostlab.core import FitResult, Param
from ghostlab.explain import explain
from tests.fakes import FakeMeta


def test_sends_numbers_only():
    fit = FitResult("projectile", {"g": Param(9.74, 0.21, "m/s²")}, {}, 0.004, "good", 18)
    fake = FakeMeta(chat_replies=[{"explanation": "It fell.", "class_question": "Why?"}])
    out = explain(fake, "tennis ball", fit)
    assert out == {"explanation": "It fell.", "class_question": "Why?"}
    _, messages, _ = fake.calls[0]
    parts = messages[0]["content"]
    assert [p["type"] for p in parts] == ["text"]
    assert "9.74" in parts[0]["text"] and "0.21" in parts[0]["text"] and "tennis ball" in parts[0]["text"]
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `pytest -q tests/test_identify.py tests/test_explain.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.identify'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/identify.py
"""Muse Spark looks at three frames: what is moving, how big it really is, what kind of motion."""
from __future__ import annotations

from ghostlab import meta_api

PROMPT_VERSION = "identify-v1"
MOTIONS = ["projectile", "bounce", "pendulum", "ramp"]
PROMPT = """These are the first, middle and last frames of a short video a physics student filmed.
Find the single object whose motion the student wants to measure.
- object: a short name, e.g. "tennis ball".
- sam_prompt: ONE short noun phrase a segmentation model can find in every frame, e.g. "tennis ball".
- real_size_m: the object's real longest side in metres (tennis ball 0.067, basketball 0.24, A4 sheet 0.297).
- size_confidence: high if it is a standard object, low if you are guessing.
- motion: projectile (thrown or dropped, no bounce), bounce (hits the floor and rebounds),
  pendulum (swings on a string or rod), ramp (slides or rolls down a slope).
- has_pivot / pivot_x_px / pivot_y_px: for a pendulum, the pivot's pixel position in the FIRST frame; otherwise false, 0, 0.
- reasoning: one sentence."""
SCHEMA = {
    "type": "object",
    "properties": {
        "object": {"type": "string"},
        "sam_prompt": {"type": "string"},
        "real_size_m": {"type": "number"},
        "size_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "motion": {"type": "string", "enum": MOTIONS},
        "has_pivot": {"type": "boolean"},
        "pivot_x_px": {"type": "number"},
        "pivot_y_px": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["object", "sam_prompt", "real_size_m", "size_confidence", "motion",
                 "has_pivot", "pivot_x_px", "pivot_y_px", "reasoning"],
    "additionalProperties": False,
}


def identify(c, frames: list[bytes]) -> dict:
    result = meta_api.spark_json(c, PROMPT, frames, "identification", SCHEMA)
    if not 0 < result["real_size_m"] < 10:
        raise ValueError(f"implausible object size {result['real_size_m']} m")
    return result
```

```python
# file: ghostlab/explain.py
"""Muse Spark explains the fitted numbers to a student. It sees numbers only, never frames."""
from __future__ import annotations

from ghostlab import meta_api
from ghostlab.core import FitResult

PROMPT_VERSION = "explain-v1"
SCHEMA = {
    "type": "object",
    "properties": {"explanation": {"type": "string"}, "class_question": {"type": "string"}},
    "required": ["explanation", "class_question"],
    "additionalProperties": False,
}


def _prompt(object_name: str, fit: FitResult) -> str:
    lines = [f"- {k}: {p.value:.3g} ± {p.error:.2g} {p.unit}".rstrip() for k, p in fit.params.items()]
    return (f"A high-school student filmed a {object_name} ({fit.motion} motion). "
            f"These values were measured from the video (fit quality: {fit.quality}):\n" + "\n".join(lines) +
            "\nIn 3 to 5 plain sentences, explain what these numbers show about the physics, comparing with "
            "textbook values where one applies (Earth's g is 9.81 m/s²). Use only the numbers given. "
            "Then write one question a teacher could ask the class about this result.")


def explain(c, object_name: str, fit: FitResult) -> dict:
    return meta_api.spark_json(c, _prompt(object_name, fit), [], "explanation", SCHEMA)
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_identify.py tests/test_explain.py`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add ghostlab/identify.py ghostlab/explain.py tests/test_identify.py tests/test_explain.py
git commit -m "Identify and explain with Muse Spark"
```

---

### Task 13: Pipeline and CLI

**Files:**
- Create: `ghostlab/pipeline.py`, `ghostlab/__main__.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `Overrides(object=None, size_m=None, motion=None)`, `run(src, work, c, overrides=Overrides(), cache_root=None) -> dict`. Result keys: `clip` (`fps, n_frames, width, height`), `identification`, `track` (`Track.to_json()`), `fits` (motion -> `FitResult.to_json()` or `{"error": str}`), `chosen`, `better_alternative`, `notes`, `warnings`, `explanation`. On a scaling failure the result is `{"error": str, "identification": ..., "warnings": ...}`.
- CLI: `python -m ghostlab run <clip> [--out result.json] [--work work] [--object ..] [--size ..] [--motion ..]` and `python -m ghostlab scoreboard <truth.csv> [--out docs/scoreboard.md]` (the scoreboard module comes in Task 14).

- [ ] **Step 1: Write the failing test**

The test draws a synthetic clip of a thrown ball and builds the matching SAM text from the same physics. It then checks the whole chain recovers g.

```python
# file: tests/test_pipeline.py
import json

import cv2
import numpy as np

from ghostlab.pipeline import Overrides, run
from tests.fakes import FakeMeta

FPS, N, BALL_PX, BALL_M = 30, 18, 30, 0.067
G_PX = 9.81 / (BALL_M / BALL_PX)  # g in px/s²


def centres():
    t = np.arange(N) / FPS
    return 200 + 300 * t, 150 - 800 * t + 0.5 * G_PX * t**2


def write_clip(path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (1280, 720))
    for cx, cy in zip(*centres()):
        frame = np.full((720, 1280, 3), 40, np.uint8)
        cv2.circle(frame, (int(cx), int(cy)), BALL_PX // 2, (0, 255, 255), -1)
        writer.write(frame)
    writer.release()


def sam_text():
    h = BALL_PX / 2
    return "\n".join(f"<{i}f>0<|box;x1={cx - h:.2f};y1={cy - h:.2f};x2={cx + h:.2f};y2={cy + h:.2f};w=1280;h=720|>"
                     for i, (cx, cy) in enumerate(zip(*centres())))


IDENT = {"object": "tennis ball", "sam_prompt": "tennis ball", "real_size_m": BALL_M, "size_confidence": "high",
         "motion": "projectile", "has_pivot": False, "pivot_x_px": 0, "pivot_y_px": 0, "reasoning": "thrown"}
EXPLAIN = {"explanation": "It fell at about 9.8 m/s².", "class_question": "Why not exactly 9.81?"}


def test_end_to_end_recovers_g(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, cache_root=tmp_path / "cache")
    json.dumps(result)
    assert result["chosen"] == "projectile"
    g = result["fits"]["projectile"]["params"]["g"]
    assert abs(g["value"] - 9.81) < 0.2
    assert result["better_alternative"] is None
    assert result["explanation"] == EXPLAIN
    assert [c[0] for c in fake.calls] == ["chat", "file", "sam", "chat"]


def test_second_run_is_served_from_cache(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    first = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    run(src, tmp_path / "work", first, cache_root=tmp_path / "cache")
    second = FakeMeta()
    run(src, tmp_path / "work", second, cache_root=tmp_path / "cache")
    assert second.calls == []


def test_override_changes_motion(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, Overrides(motion="ramp"), cache_root=tmp_path / "cache")
    assert result["chosen"] == "ramp"
    assert result["better_alternative"] == "projectile"
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_pipeline.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.pipeline'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/pipeline.py
"""Clip in, result JSON out: ingest, identify, track, scale, fit, explain."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ghostlab import explain, identify, ingest, meta_api, sam_parse, scale
from ghostlab.cache import cached
from ghostlab.core import FitError, FitResult
from ghostlab.fit.select import better_alternative, fit_all


@dataclass(frozen=True)
class Overrides:
    object: str | None = None
    size_m: float | None = None
    motion: str | None = None


def run(src: Path, work: Path, c, overrides: Overrides = Overrides(), cache_root: Path | None = None) -> dict:
    clip = ingest.prepare(src, work)
    warnings = []
    if clip.camera_shift > ingest.SHAKE_LIMIT:
        warnings.append("The camera moved. Prop your phone against something and film again.")
    ident = cached("identify", identify.PROMPT_VERSION.encode() + b"".join(clip.key_frames),
                   lambda: identify.identify(c, clip.key_frames), cache_root)
    if ident["size_confidence"] == "low" and overrides.size_m is None:
        warnings.append(f"Not sure of the {ident['object']}'s size. Check it before trusting the numbers.")
    prompt = overrides.object or ident["sam_prompt"]
    size = overrides.size_m or ident["real_size_m"]
    motion = overrides.motion or ident["motion"]
    video = clip.path.read_bytes()
    sam = cached("sam", prompt.encode() + b"\0" + video,
                 lambda: {"text": meta_api.sam_track(c, meta_api.upload_video(c, clip.path), prompt)}, cache_root)
    frames = sam_parse.parse(sam["text"])
    pixels = sam_parse.to_pixel_track(frames, clip.n_frames, clip.fps, clip.width, clip.height)
    try:
        track, notes = scale.to_metres(pixels, size)
    except FitError as exc:
        return {"error": str(exc), "identification": ident, "warnings": warnings}
    pivot = scale.pivot_to_metres(track, (ident["pivot_x_px"], ident["pivot_y_px"])) if ident["has_pivot"] else None
    results = fit_all(track, pivot)
    chosen = results[motion]
    explanation = None
    if isinstance(chosen, FitResult):
        key = explain.PROMPT_VERSION + ident["object"] + json.dumps(chosen.to_json(), sort_keys=True)
        explanation = cached("explain", key.encode(), lambda: explain.explain(c, ident["object"], chosen), cache_root)
    return {
        "clip": {"fps": clip.fps, "n_frames": clip.n_frames, "width": clip.width, "height": clip.height},
        "identification": ident,
        "track": track.to_json(),
        "fits": {k: v.to_json() if isinstance(v, FitResult) else {"error": v} for k, v in results.items()},
        "chosen": motion,
        "better_alternative": better_alternative(motion, results),
        "notes": notes,
        "warnings": warnings,
        "explanation": explanation,
    }
```

```python
# file: ghostlab/__main__.py
"""CLI: python -m ghostlab run <clip> | scoreboard <truth.csv>"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ghostlab import meta_api, pipeline
from ghostlab.fit.select import MODULES


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="ghostlab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("clip", type=Path)
    r.add_argument("--out", type=Path, default=Path("result.json"))
    r.add_argument("--work", type=Path, default=Path("work"))
    r.add_argument("--object")
    r.add_argument("--size", type=float)
    r.add_argument("--motion", choices=sorted(MODULES))
    s = sub.add_parser("scoreboard")
    s.add_argument("truth", type=Path)
    s.add_argument("--out", type=Path, default=Path("docs/scoreboard.md"))
    args = ap.parse_args(argv)
    c = meta_api.client()
    if args.cmd == "run":
        overrides = pipeline.Overrides(args.object, args.size, args.motion)
        result = pipeline.run(args.clip, args.work, c, overrides)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        fit = result.get("fits", {}).get(result.get("chosen"), result)
        print(json.dumps({"chosen": result.get("chosen"), "fit": fit, "warnings": result.get("warnings")}, indent=2))
    else:
        from ghostlab import scoreboard

        def run_one(clip: Path, motion: str) -> dict:
            return pipeline.run(clip, Path("work") / clip.stem, c, pipeline.Overrides(motion=motion))

        scoreboard.write(args.truth, args.out, run_one)
        print(args.out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_pipeline.py`
Expected: `3 passed`

- [ ] **Step 5: Run it once for real on the probe clip**

Run: `MODEL_API_KEY=<key> python -m ghostlab run clips/probe_throw.mp4`
Expected: `"chosen": "projectile"` and a `g` value. Write the value and its error in `docs/spike.md` under "First real run". A value far from 9.81 is a finding to record, not a reason to edit thresholds.

- [ ] **Step 6: Commit**

```bash
git add ghostlab/pipeline.py ghostlab/__main__.py tests/test_pipeline.py docs/spike.md
git commit -m "Pipeline and CLI, end to end"
```

---

### Task 14: Test clips and the accuracy scoreboard

**Files:**
- Create: `ghostlab/scoreboard.py`, `clips/truth.csv`
- Test: `tests/test_scoreboard.py`

**Interfaces:**
- Consumes: `pipeline.run` through a `run_fn(clip: Path, motion: str) -> dict` callable.
- Produces: `Truth(clip, motion, quantity, value)`, `load(csv) -> list[Truth]`, `score(truths, run_fn) -> list[dict]`, `render(rows) -> str`, `write(truth_csv, out, run_fn)`.

- [ ] **Step 1: Write the failing test**

```python
# file: tests/test_scoreboard.py
from pathlib import Path

from ghostlab.scoreboard import load, render, score

MEASURED = {"drop1": (9.70, 0.10), "drop2": (9.95, 0.05), "swing1": (0.81, 0.01)}


def fake_run(calls):
    def run(clip: Path, motion: str) -> dict:
        calls.append((clip.name, motion))
        if clip.stem == "broken":
            return {"error": "object not found", "identification": {"motion": motion}}
        value, error = MEASURED[clip.stem]
        quantity = "length" if motion == "pendulum" else "g"
        return {"identification": {"motion": motion},
                "fits": {motion: {"params": {quantity: {"value": value, "error": error, "unit": ""}}}}}
    return run


def test_scores_each_clip(tmp_path):
    csv = tmp_path / "truth.csv"
    csv.write_text("clip,motion,quantity,value\n"
                   "drop1.mp4,projectile,g,9.81\ndrop2.mp4,projectile,g,9.81\n"
                   "swing1.mp4,pendulum,length,0.80\nbroken.mp4,projectile,g,9.81\n")
    calls = []
    rows = score(load(csv), fake_run(calls))
    assert calls == [("drop1.mp4", "projectile"), ("drop2.mp4", "projectile"),
                     ("swing1.mp4", "pendulum"), ("broken.mp4", "projectile")]
    assert rows[0]["within_2sigma"] is True   # 9.70 ± 0.10 vs 9.81
    assert rows[1]["within_2sigma"] is False  # 9.95 ± 0.05 vs 9.81
    assert rows[3]["error"] == "object not found"
    table = render(rows)
    assert "| g | 2 | 1.3% | 1/2 |" in table
    assert "| length | 1 | 1.3% | 1/1 |" in table
    assert "1 clip(s) failed" in table
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest -q tests/test_scoreboard.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'ghostlab.scoreboard'`

- [ ] **Step 3: Write the implementation**

```python
# file: ghostlab/scoreboard.py
"""Accuracy scoreboard: run real clips with tape-measured answers and report the errors."""
from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Truth:
    clip: Path
    motion: str
    quantity: str
    value: float


def load(truth_csv: Path) -> list[Truth]:
    with open(truth_csv, newline="", encoding="utf-8") as f:
        return [Truth(truth_csv.parent / r["clip"], r["motion"], r["quantity"], float(r["value"]))
                for r in csv.DictReader(f)]


def score(truths: list[Truth], run_fn: Callable[[Path, str], dict]) -> list[dict]:
    rows = []
    for t in truths:
        result = run_fn(t.clip, t.motion)
        row = {"clip": t.clip.name, "motion": t.motion, "quantity": t.quantity, "true": t.value,
               "identified": result.get("identification", {}).get("motion") == t.motion}
        fit = result.get("fits", {}).get(t.motion, {"error": result.get("error", "no result")})
        if "error" in fit:
            rows.append({**row, "error": fit["error"]})
            continue
        p = fit["params"][t.quantity]
        rows.append({**row, "value": p["value"], "sigma": p["error"],
                     "error_pct": 100 * (p["value"] - t.value) / t.value,
                     "within_2sigma": abs(p["value"] - t.value) <= 2 * p["error"]})
    return rows


def render(rows: list[dict]) -> str:
    out = ["# Ghostlab accuracy scoreboard", "",
           "| Clip | Motion | Quantity | True | Measured | Error | Within 2σ | Identified |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            out.append(f"| {r['clip']} | {r['motion']} | {r['quantity']} | {r['true']:g} | failed: {r['error']} | | | |")
        else:
            out.append(f"| {r['clip']} | {r['motion']} | {r['quantity']} | {r['true']:g} | "
                       f"{r['value']:.3g} ± {r['sigma']:.2g} | {r['error_pct']:+.1f}% | "
                       f"{'yes' if r['within_2sigma'] else 'no'} | {'yes' if r['identified'] else 'no'} |")
    out += ["", "| Quantity | Clips | Median abs error | Within 2σ |", "|---|---|---|---|"]
    ok = [r for r in rows if "error" not in r]
    for q in sorted({r["quantity"] for r in ok}):
        qs = [r for r in ok if r["quantity"] == q]
        med = statistics.median(abs(r["error_pct"]) for r in qs)
        out.append(f"| {q} | {len(qs)} | {med:.1f}% | {sum(r['within_2sigma'] for r in qs)}/{len(qs)} |")
    failed = len(rows) - len(ok)
    if failed:
        out += ["", f"{failed} clip(s) failed."]
    return "\n".join(out) + "\n"


def write(truth_csv: Path, out: Path, run_fn: Callable[[Path, str], dict]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(score(load(truth_csv), run_fn)), encoding="utf-8")
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest -q tests/test_scoreboard.py`
Expected: `1 passed`

- [ ] **Step 5: Film the 20 clips (owner task, about 1 hour)**

Phone propped still, side-on, plain background, good light, objects and hands only. Measure each true value with a tape before filming.

| Clips | Motion | Quantity | True value |
|---|---|---|---|
| 6 drops or throws of a tennis ball | projectile | g | 9.81 |
| 5 bounces of a tennis ball on a hard floor | bounce | e | sqrt(rebound height / drop height), from a still frame against a tape on the wall |
| 5 pendulums (2 string lengths) | pendulum | length | taped length, pivot to ball centre |
| 4 slides of a book on a board at a taped angle | ramp | angle | atan(rise / run), from the tape |

Save them as `clips/<name>.mp4` and list them in `clips/truth.csv` with the columns `clip,motion,quantity,value`.

- [ ] **Step 6: Run the scoreboard**

Run: `MODEL_API_KEY=<key> python -m ghostlab scoreboard clips/truth.csv`
Expected: `docs/scoreboard.md` is written. These numbers go in the README and the demo video. Failures and misses are inputs to Plan 2, so don't tune thresholds to make them pass.

- [ ] **Step 7: Commit**

```bash
git add ghostlab/scoreboard.py tests/test_scoreboard.py clips/truth.csv docs/scoreboard.md
git commit -m "Accuracy scoreboard on 20 real clips"
```

(Clip videos stay out of git through `.gitignore`. Back up `clips/` separately.)

---

## Done when

- `pytest -q` passes with every test above.
- `python -m ghostlab run clips/probe_throw.mp4` prints a projectile fit with g and its error.
- `docs/scoreboard.md` exists from the 20 real clips.
- Then write Plan 2 (web app, ghost, predict, worksheet, gallery, deploy, judging-window billing, SAM mask measurements).
