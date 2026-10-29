from types import SimpleNamespace

from ghostlab.voice import parse_whatif, transcribe


def test_planet_names_set_gravity():
    assert parse_whatif("what if we did this on the Moon", 9.81, None) == {"g": 1.62}


def test_multiples_of_gravity():
    assert parse_whatif("twice the gravity", 9.81, None) == {"g": 19.62}
    assert parse_whatif("half gravity please", 10.0, None) == {"g": 5.0}


def test_bouncier_only_when_the_motion_bounces():
    assert parse_whatif("make it bouncier", 9.81, 0.7) == {"e": 0.85}
    assert parse_whatif("make it bouncier", 9.81, None) == {}


def test_nothing_recognised():
    assert parse_whatif("hello there", 9.81, 0.7) == {}


def test_transcribe_sends_the_documented_request():
    seen = {}

    def post(url, headers, timeout, files):
        seen.update(url=url, headers=headers, files=files)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"transcript": "on mars"})

    assert transcribe(b"RIFF", "k", post=post) == "on mars"
    assert seen["url"].endswith("/asr/transcribe") and seen["headers"]["Authorization"] == "Bearer k"
    assert "muse-voice-transcribe-1.0" in seen["files"]["request"][1]
