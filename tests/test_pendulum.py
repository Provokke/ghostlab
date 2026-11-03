from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from ghostlab.core import FitError, Track
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

def test_straight_vertical_path_is_refused_not_a_crash():
    # Real tracked bounce clip (x moves 1 mm): the circle fit's variance came out negative and crashed.
    d = np.load(Path(__file__).parent / "data" / "straight_fall_track.npz")
    track = Track(t=d["t"], x=d["x"], y=d["y"], m_per_px=float(d["m"]))
    with pytest.raises(FitError):
        pendulum.fit(track)


def test_wrong_pivot_is_corrected_not_trusted():
    # swing() has the true pivot at (0, 1.0); a pivot guess 0.1 m off must not give a confident wrong g
    for bad in [(0.0, 1.1), (0.03, 1.02)]:
        result = pendulum.fit(swing(theta0=0.5), pivot=bad)
        g = result.params["g"]
        assert abs(g.value - 9.81) < 3 * g.error + 0.3, (bad, g)
        assert abs(result.params["length"].value - 0.8) < 3 * result.params["length"].error + 0.01


def test_small_pivot_error_widens_the_length_bar():
    exact = pendulum.fit(swing(theta0=0.5), pivot=(0.0, 1.0)).params["length"]
    off = pendulum.fit(swing(theta0=0.5), pivot=(0.0, 1.01)).params["length"]
    assert off.error >= exact.error


def test_nan_track_is_a_fit_error():
    track = swing()
    x = track.x.copy()
    x[5] = np.nan
    with pytest.raises(FitError):
        pendulum.fit(Track(t=track.t, x=x, y=track.y, m_per_px=track.m_per_px))
