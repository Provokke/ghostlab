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
