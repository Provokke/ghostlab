import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

from ghostlab import server, voice


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    server._HITS.clear()
    return TestClient(server.app, raise_server_exceptions=False)


SIM = {"motion": "projectile", "sim": {"x0": 0, "y0": 0, "vx": 1, "vy": 1, "g": 9.8}, "t": [0, 0.1],
       "m_per_px": 0.01, "origin_px": [0, 0]}


def test_status_and_demos_without_key(client):
    assert client.get("/api/status").json() == {"live": False}
    assert {"bump", "drop", "throw"} <= set(client.get("/api/demos").json())
    assert client.get("/api/demo/bump").status_code == 200
    assert client.get("/api/demo/..%2Fx").status_code == 404
    assert client.get("/api/demo/nope").json()["detail"]


def test_analyze_missing_key_is_plain_words(client):
    r = client.post("/api/identify", files={"file": ("a.mp4", b"x")})
    assert r.status_code == 503 and "MODEL_API_KEY" in r.json()["detail"]


def test_simulate_validation(client):
    assert client.post("/api/simulate", json={**SIM, "m_per_px": 0}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "origin_px": [0]}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "t": [0.0] * 2001}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "g": -1}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "e": 2}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "motion": "nope"}).status_code == 400
    r = client.post("/api/simulate", json={**SIM, "motion": "pendulum", "sim": {}, "g": 1})
    assert r.status_code == 422


def test_whatif_limits(client):
    base = {"text": "moon", "g": 9.81}
    assert client.post("/api/whatif", json=base).status_code == 200
    assert client.post("/api/whatif", json={**base, "text": "x" * 501}).status_code == 422
    assert client.post("/api/whatif", json={**base, "g": -1}).status_code == 422
    assert client.post("/api/whatif", json={**base, "g": 1000}).status_code == 422


def _voice(client):
    return client.post("/api/voice", files={"audio": ("a.webm", b"junk")}, data={"g": "9.81"})


def test_voice_errors(client, monkeypatch):
    assert _voice(client).status_code == 503
    monkeypatch.setenv("MODEL_API_KEY", "x")
    r = _voice(client)
    assert r.status_code == 400 and "recording" in r.json()["detail"]
    monkeypatch.setattr(voice, "to_wav", lambda d: b"wav")

    def boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(voice, "transcribe", boom)
    r = _voice(client)
    assert r.status_code == 502 and "Voice" in r.json()["detail"]
    monkeypatch.setattr(server, "MAX_AUDIO", 3)
    assert _voice(client).status_code == 413


def test_catch_all_is_json(client, monkeypatch):
    monkeypatch.setattr(server.whatif, "simulate", lambda *a, **k: 1 / 0)
    r = client.post("/api/simulate", json=SIM)
    assert r.status_code == 500 and "went wrong" in r.json()["detail"]


def test_rate_limit(client, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "x")
    monkeypatch.setattr(server, "RATE_LIMIT", 2)
    monkeypatch.setattr(voice, "to_wav", lambda d: b"wav")
    monkeypatch.setattr(voice, "transcribe", lambda *a, **k: "moon")
    codes = [_voice(client).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_busy_503_and_slot_release(client, monkeypatch):
    import threading
    monkeypatch.setenv("MODEL_API_KEY", "x")
    monkeypatch.setattr(voice, "to_wav", lambda d: b"wav")
    monkeypatch.setattr(voice, "transcribe", lambda *a, **k: "moon")
    monkeypatch.setattr(server, "_SLOTS", threading.BoundedSemaphore(0))
    r = _voice(client)
    assert r.status_code == 503 and r.json()["detail"] == server.BUSY_NOW
    monkeypatch.setattr(server, "_SLOTS", threading.BoundedSemaphore(1))
    server._HITS.clear()
    assert _voice(client).status_code == 200
    assert _voice(client).status_code == 200  # slot was released after the first call


def test_slot_released_after_failure(client, monkeypatch):
    import threading
    monkeypatch.setenv("MODEL_API_KEY", "x")
    monkeypatch.setattr(voice, "to_wav", lambda d: b"wav")
    monkeypatch.setattr(voice, "transcribe", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_SLOTS", slots)
    assert _voice(client).status_code == 502
    assert slots.acquire(blocking=False)


def test_simulate_rejects_absurd_numbers(client):
    assert client.post("/api/simulate", json={**SIM, "t": []}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "t": [-1e9]}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "t": [61]}).status_code == 422
    assert client.post("/api/simulate", json={**SIM, "sim": {**SIM["sim"], "vx": 1e308}}).status_code == 422


def test_typed_whatif_e_is_bounded(client):
    base = {"text": "bouncier", "g": 9.81}
    assert client.post("/api/whatif", json={**base, "e": 5}).status_code == 422
    assert client.post("/api/whatif", json={**base, "e": 0.5}).status_code == 200


def test_whatif_gravity_is_capped_with_a_note(client):
    r = client.post("/api/whatif", json={"text": "1000 times gravity", "g": 9.81}).json()["whatif"]
    assert r["g"] == 50.0 and "note" in r
    assert client.post("/api/simulate", json={**SIM, "g": r["g"]}).status_code == 200


def test_voice_ffmpeg_missing_or_hung_is_a_400(client, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "x")
    for exc in (FileNotFoundError("ffmpeg"), subprocess.TimeoutExpired("ffmpeg", 30)):
        def bad(d, exc=exc):
            raise exc
        monkeypatch.setattr(voice, "to_wav", bad)
        assert _voice(client).status_code == 400


def test_voice_content_length_is_checked_before_reading(client, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "x")
    monkeypatch.setattr(server, "MAX_AUDIO", 10)
    r = client.post("/api/voice", files={"audio": ("a.webm", b"x" * (70 * 1024))}, data={"g": "9.81"})
    assert r.status_code == 413


def test_guard_queues_then_503(client, monkeypatch):
    monkeypatch.setattr(server, "SLOT_WAIT", 0.05)
    held = [server._SLOTS.acquire() for _ in range(2)]
    try:
        request = type("R", (), {"client": type("C", (), {"host": "9.9.9.9"})()})()
        with pytest.raises(server.HTTPException) as e:
            with server._Guard(request):
                pass
        assert e.value.status_code == 503
    finally:
        for _ in held:
            server._SLOTS.release()


def test_sweep_removes_old_and_keeps_fresh(tmp_path, monkeypatch):
    import os
    import time
    monkeypatch.setattr(server, "WEB", tmp_path)
    up = tmp_path / "uploads"
    up.mkdir()
    old, fresh = "a" * 32, "b" * 32
    for uid in (old, fresh):
        (up / uid).mkdir()
        (up / f"{uid}.mp4").write_bytes(b"x")
    (up / "notes.txt").write_text("keep")
    stale = time.time() - 2 * 24 * 3600
    for path in (up / old, up / f"{old}.mp4", up / "notes.txt"):
        os.utime(path, (stale, stale))
    server._sweep_uploads()
    assert not (up / old).exists() and not (up / f"{old}.mp4").exists()
    assert (up / fresh).exists() and (up / f"{fresh}.mp4").exists() and (up / "notes.txt").exists()
