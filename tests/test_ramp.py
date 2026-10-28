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
