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
