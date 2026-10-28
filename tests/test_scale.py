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
