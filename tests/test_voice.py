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


def test_planet_needs_a_whole_word():
    for text in ("marshmallow gravity", "smarts", "earthquake", "behalf of gravity"):
        assert parse_whatif(text, 9.81, None) == {}, text


def test_factor_applies_to_the_named_planet():
    assert parse_whatif("half the gravity of mars", 9.81, None) == {"g": 1.85}


def test_earliest_planet_wins():
    assert parse_whatif("on mars, not the moon", 9.81, None) == {"g": 3.71}
    assert parse_whatif("on the moon not mars", 9.81, None) == {"g": 1.62}


def test_gravity_is_clamped_to_what_the_simulator_accepts():
    out = parse_whatif("1000 times gravity", 9.81, None)
    assert out["g"] == 50.0 and "50" in out["note"]
    assert parse_whatif("0.001 times gravity", 9.81, None)["g"] == 0.1
    assert "note" not in parse_whatif("twice the gravity", 9.81, None)
    assert parse_whatif("jupiter", 9.81, None) == {"g": 24.8}


def test_to_wav_has_a_timeout(monkeypatch):
    from ghostlab import voice
    seen = {}

    def run(cmd, **kw):
        seen.update(kw)
        raise OSError("stop")
    monkeypatch.setattr(voice.subprocess, "run", run)
    try:
        voice.to_wav(b"x")
    except OSError:
        pass
    assert seen["timeout"] == voice.FFMPEG_TIMEOUT
