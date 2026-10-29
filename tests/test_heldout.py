import numpy as np

from ghostlab.core import Track
from ghostlab.fit import projectile
from ghostlab.heldout import check
from tests.synth import noisy


def make(seconds=1.0, fps=30, **kw):
    t = np.arange(0, seconds, 1 / fps)
    x, y = projectile.simulate({"x0": 0.0, "vx": 2.0, "y0": 0.0, "vy": 4.0, "g": 9.81}, t)
    return noisy(t, x, y, **kw)


def test_true_physics_predicts_the_unseen_part():
    r = check(make(), "projectile")
    assert r["verdict"] == "certified"
    assert r["test_n"] > 0 and r["train_n"] > r["test_n"]
    assert r["test_error_cm"] < 3.0


def test_physics_that_changes_midway_is_refused():
    tr = make()
    y = tr.y.copy()
    y[int(0.7 * len(y)):] += 0.5  # something knocks it upward after the fit window
    bad = Track(t=tr.t, x=tr.x, y=y, m_per_px=tr.m_per_px)
    assert check(bad, "projectile")["verdict"] == "refused"


def test_unfittable_data_is_refused_not_raised():
    t = np.arange(0, 0.1, 1 / 30)
    tiny = Track(t=t, x=t, y=t, m_per_px=0.001)
    assert check(tiny, "projectile")["verdict"] == "refused"


def test_result_carries_the_blind_prediction_model():
    from ghostlab.fit import projectile as pj
    tr = make()
    r = check(tr, "projectile")
    x, y = pj.simulate(r["sim"], tr.t - r["t_origin"])
    assert np.nanmax(np.hypot(x - tr.x, y - tr.y)) < 0.05
