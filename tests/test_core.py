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
