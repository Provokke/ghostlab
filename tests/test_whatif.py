import numpy as np

from ghostlab.fit import projectile
from ghostlab.whatif import simulate

SIM = {"x0": 0.0, "vx": 1.0, "y0": 0.0, "vy": 3.0, "g": 9.81}


def test_no_override_matches_the_fit():
    t = np.linspace(0, 0.5, 6)
    x, y = simulate("projectile", SIM, t)
    px, py = projectile.simulate(SIM, t)
    assert np.allclose(x, px) and np.allclose(y, py)


def test_moon_gravity_flies_higher():
    t = np.linspace(0, 0.5, 6)
    _, earth = simulate("projectile", SIM, t)
    _, moon = simulate("projectile", SIM, t, g=1.62)
    assert moon[-1] > earth[-1]


def test_zero_gravity_does_not_crash_a_bounce():
    from ghostlab.fit import bounce
    sim = {"x0": 0.0, "vx": 0.5, "y0": 1.0, "vy": 0.0, "g": 9.81, "e": 0.7, "floor": 0.0, "t_start": 0.0}
    x, y = simulate("bounce", sim, [0, 0.5, 1.0], g=0.0)
    assert np.all(np.isfinite(x)) and len(y) == 3
    x, y = simulate("projectile", SIM, [0, 0.5, 1.0], g=0.0)
    assert np.all(np.isfinite(y))


def test_pendulum_scales_the_undamped_frequency():
    import math
    sim = {"px": 0.0, "py": 1.0, "L": 0.8, "A": 0.3, "gamma": 0.4, "omega": 3.4, "phi": 0.0, "offset": 0.0}
    t = np.linspace(0, 2, 5)
    x0, _ = simulate("pendulum", sim, t, g=9.81)
    assert np.allclose(x0, simulate("pendulum", sim, t)[0])
    x1, _ = simulate("pendulum", sim, t, g=9.81 / 4)
    omega0 = math.hypot(3.4, 0.4)
    expect = math.sqrt((omega0 / 2) ** 2 - 0.4**2)
    th = 0.3 * np.exp(-0.4 * t) * np.cos(expect * t)
    assert np.allclose(x1, 0.8 * np.sin(th))
