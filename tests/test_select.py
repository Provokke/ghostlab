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
