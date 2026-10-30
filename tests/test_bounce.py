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


def test_ball_settling_after_last_bounce_does_not_break_the_fit():
    result = bounce.fit(make(seconds=6.0, fps=30, sigma=0.003))
    assert abs(result.params["e"].value - 0.8) < 0.05
    assert abs(result.params["g"].value - 9.81) < 0.5
