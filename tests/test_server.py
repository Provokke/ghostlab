import re

import httpx

import pytest
from fastapi.testclient import TestClient

from ghostlab import server
from tests.fakes import FakeMeta
from tests.test_pipeline import BALL_M, EXPLAIN, IDENT, sam_text, write_clip


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "x")
    monkeypatch.setenv("GHOSTLAB_CACHE", str(tmp_path / "cache"))
    web = tmp_path / "web"
    web.mkdir()
    monkeypatch.setattr(server, "WEB", web)
    clip = tmp_path / "throw.mp4"
    write_clip(clip)

    def make(chat_replies):
        fake = FakeMeta(chat_replies=chat_replies, sam_text=sam_text())
        monkeypatch.setattr(server.meta_api, "client", lambda: fake)
        return fake

    return TestClient(server.app), clip, make, web


def upload(client, clip):
    with clip.open("rb") as f:
        return client.post("/api/identify", files={"file": ("throw.mp4", f, "video/mp4")})


def test_identify_returns_id_and_guess(env):
    client, clip, make, web = env
    make([IDENT])
    r = upload(client, clip)
    assert r.status_code == 200
    body = r.json()
    assert re.fullmatch(r"[0-9a-f]{32}", body["id"])
    assert body["identification"]["real_size_m"] == BALL_M
    assert body["clip"]["n_frames"] > 2
    assert (web / "uploads" / f"{body['id']}.mp4").exists()
    assert body["video"] == f"/uploads/{body['id']}.mp4"


def test_wrong_size_corrected_changes_verdict(env):
    client, clip, make, _ = env
    fake = make([{**IDENT, "real_size_m": 0.2}, EXPLAIN, EXPLAIN])
    uid = upload(client, clip).json()["id"]
    wrong = client.post("/api/analyze", json={"id": uid, "size_m": None}).json()
    assert wrong["twin"]["verdict"] == "refused"
    right = client.post("/api/analyze", json={"id": uid, "size_m": BALL_M}).json()
    assert right["twin"]["verdict"] == "certified"
    assert right["video"] == f"/uploads/{uid}.mp4"
    kinds = [c[0] for c in fake.calls]
    assert kinds.count("sam") == 1 and kinds.count("file") == 1
    assert sum(1 for k in kinds if k == "chat") == 3  # identify once, explain per fit


def test_unknown_id_404(env):
    client, _, make, _ = env
    make([])
    assert client.post("/api/analyze", json={"id": "0" * 32}).status_code == 404


@pytest.mark.parametrize("bad", ["../x", "abc", "G" * 32, "0" * 31, "0" * 33])
def test_bad_id_rejected(env, bad):
    client, _, make, _ = env
    make([])
    assert 400 <= client.post("/api/analyze", json={"id": bad}).status_code < 500


@pytest.mark.parametrize("size", [0, -1, 11])
def test_size_out_of_range_422(env, size):
    client, _, make, _ = env
    make([])
    assert client.post("/api/analyze", json={"id": "0" * 32, "size_m": size}).status_code == 422


def test_non_video_400(env, tmp_path):
    client, _, make, _ = env
    make([])
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"not a video")
    r = upload(client, junk)
    assert r.status_code == 400
    assert "video" in r.json()["detail"]


def test_no_key_503(env, monkeypatch):
    client, clip, make, _ = env
    make([])
    monkeypatch.delenv("MODEL_API_KEY")
    assert upload(client, clip).status_code == 503
    assert client.post("/api/analyze", json={"id": "0" * 32}).status_code == 503


def test_model_failure_is_502_and_cleans_up(env, monkeypatch):
    client, clip, make, web = env
    make([IDENT])

    def down(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(server.pipeline, "identify_clip", down)
    r = upload(client, clip)
    assert r.status_code == 502
    assert "Try again" in r.json()["detail"]
    assert not list((web / "uploads").iterdir())


def test_code_bug_is_a_500_not_a_busy_502_and_is_logged(env, monkeypatch, caplog):
    client, clip, make, web = env
    make([IDENT])
    monkeypatch.setattr(server.pipeline, "identify_clip", lambda *a, **k: {}["missing"])
    c = TestClient(server.app, raise_server_exceptions=False)
    with caplog.at_level("ERROR", logger="ghostlab"):
        with clip.open("rb") as f:
            r = c.post("/api/identify", files={"file": ("throw.mp4", f, "video/mp4")})
    assert r.status_code == 500
    assert any("identify failed" in m for m in caplog.messages)
    assert not list((web / "uploads").iterdir())


def _identified(client, clip, make):
    make([IDENT, EXPLAIN])
    return upload(client, clip).json()["id"]


def test_analyze_rejects_bad_motion_and_object(env):
    client, clip, make, web = env
    uid = _identified(client, clip, make)
    for bad in ({"motion": "nope"}, {"object": ""}, {"object": "x" * 81}):
        assert client.post("/api/analyze", json={"id": uid, **bad}).status_code == 422


def test_motion_literal_matches_identify_motions():
    from typing import get_args

    from ghostlab import identify
    inner = [a for a in get_args(server.AnalyzeRequest.model_fields["motion"].annotation) if a is not type(None)][0]
    assert list(get_args(inner)) == identify.MOTIONS


def test_analyze_expired_when_mp4_is_gone(env):
    client, clip, make, web = env
    uid = _identified(client, clip, make)
    (web / "uploads" / f"{uid}.mp4").unlink()
    r = client.post("/api/analyze", json={"id": uid})
    assert r.status_code == 404 and "expired" in r.json()["detail"]


def test_analyze_keeps_mp4_and_folder_alive(env):
    import os
    import time
    client, clip, make, web = env
    uid = _identified(client, clip, make)
    stale = time.time() - 23 * 3600
    for path in (web / "uploads" / uid, web / "uploads" / f"{uid}.mp4"):
        os.utime(path, (stale, stale))
    client.post("/api/analyze", json={"id": uid})
    for path in (web / "uploads" / uid, web / "uploads" / f"{uid}.mp4"):
        assert path.stat().st_mtime > stale + 3600


def test_oversize_upload_413_and_cleans_up(env, monkeypatch):
    client, clip, make, web = env
    make([IDENT])
    monkeypatch.setattr(server, "MAX_UPLOAD", 1000)
    assert upload(client, clip).status_code == 413
    assert not list((web / "uploads").iterdir())


def test_old_uploads_are_swept(env):
    import os, time
    client, clip, make, web = env
    make([IDENT])
    up = web / "uploads"
    old_dir, old_mp4 = up / ("a" * 32), up / ("a" * 32 + ".mp4")
    old_dir.mkdir(parents=True); (old_dir / "src.mp4").write_bytes(b"x"); old_mp4.write_bytes(b"x")
    stale = time.time() - 2 * 24 * 3600
    for path in (old_dir, old_mp4):
        os.utime(path, (stale, stale))
    fresh = up / ("b" * 32); fresh.mkdir()
    assert upload(client, clip).status_code == 200
    assert not old_dir.exists() and not old_mp4.exists() and fresh.exists()
