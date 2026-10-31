import re

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
