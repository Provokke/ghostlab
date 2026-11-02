import json

import cv2
import numpy as np

from ghostlab.pipeline import Overrides, run
from tests.fakes import FakeMeta

FPS, N, BALL_PX, BALL_M = 30, 18, 30, 0.067
G_PX = 9.81 / (BALL_M / BALL_PX)  # g in px/s²


def centres():
    t = np.arange(N) / FPS
    return 200 + 300 * t, 150 - 800 * t + 0.5 * G_PX * t**2


def write_clip(path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (1280, 720))
    for cx, cy in zip(*centres()):
        frame = np.full((720, 1280, 3), 40, np.uint8)
        cv2.circle(frame, (int(cx), int(cy)), BALL_PX // 2, (0, 255, 255), -1)
        writer.write(frame)
    writer.release()


def sam_text():
    h = BALL_PX / 2
    return "\n".join(f"<{i}f>0<|box;x1={cx - h:.2f};y1={cy - h:.2f};x2={cx + h:.2f};y2={cy + h:.2f};w=1280;h=720|>"
                     for i, (cx, cy) in enumerate(zip(*centres())))


IDENT = {"object": "tennis ball", "sam_prompt": "tennis ball", "real_size_m": BALL_M, "size_confidence": "high",
         "motion": "projectile", "has_pivot": False, "pivot_x_px": 0, "pivot_y_px": 0, "reasoning": "thrown"}
EXPLAIN = {"explanation": "It fell at about 9.8 m/s².", "class_question": "Why not exactly 9.81?"}


def test_end_to_end_recovers_g(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, cache_root=tmp_path / "cache")
    json.dumps(result)
    assert result["chosen"] == "projectile"
    g = result["fits"]["projectile"]["params"]["g"]
    assert abs(g["value"] - 9.81) < 0.2
    assert result["better_alternative"] is None
    assert result["twin"]["verdict"] == "certified"
    assert result["explanation"] == EXPLAIN
    assert [c[0] for c in fake.calls] == ["chat", "file", "sam", "chat"]


def test_wrong_size_cannot_be_certified(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, Overrides(size_m=BALL_M * 3), cache_root=tmp_path / "cache")
    assert result["warnings"]
    assert result["twin"]["verdict"] == "refused"
    assert "not about 9.8" in result["twin"]["reason"]


def test_moving_camera_cannot_be_certified(tmp_path, monkeypatch):
    from ghostlab import ingest
    monkeypatch.setattr(ingest, "SHAKE_LIMIT", -1.0)
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, cache_root=tmp_path / "cache")
    assert result["twin"]["verdict"] == "refused" and "camera moved" in result["twin"]["reason"]


def test_failed_full_fit_cannot_be_certified(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, Overrides(motion="bounce"), cache_root=tmp_path / "cache")
    assert result["twin"]["verdict"] != "certified"


def test_second_run_is_served_from_cache(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    first = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    run(src, tmp_path / "work", first, cache_root=tmp_path / "cache")
    second = FakeMeta()
    run(src, tmp_path / "work", second, cache_root=tmp_path / "cache")
    assert second.calls == []


def test_override_changes_motion(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, Overrides(motion="ramp"), cache_root=tmp_path / "cache")
    assert result["chosen"] == "ramp"
    assert result["better_alternative"] == "projectile"


def test_speed_warning_flags_slow_motion_g():
    from ghostlab.core import Param
    from ghostlab.pipeline import speed_warning

    class Fit:
        def __init__(self, g):
            self.params = {"g": Param(g, 0.01, "m/s2")}

    assert speed_warning(Fit(0.83)) and "slow motion" in speed_warning(Fit(0.83))
    assert speed_warning(Fit(9.6)) is None
    assert speed_warning(type("F", (), {"params": {}})()) is None


class PromptAwareMeta(FakeMeta):
    """SAM finds the ball only for the prompt 'ball'; any other prompt tracks nothing."""

    def _responses_create(self, model, input):
        prompt = input[0]["content"][0]["text"]
        self.sam_text = sam_text() if prompt == "ball" else ""
        return super()._responses_create(model, input)


def test_falls_back_to_generic_prompt_when_sam_finds_nothing(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = PromptAwareMeta(chat_replies=[IDENT, EXPLAIN])
    result = run(src, tmp_path / "work", fake, cache_root=tmp_path / "cache")
    assert "error" not in result
    assert result["twin"]["verdict"] == "certified"
    assert any("'tennis ball'" in n and "'ball'" in n for n in result["notes"])
    assert [c[0] for c in fake.calls].count("file") == 1  # video uploaded once, not per prompt


def test_reports_every_prompt_tried_when_all_fail(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    result = run(src, tmp_path / "work", FakeMeta(chat_replies=[IDENT], sam_text=""), cache_root=tmp_path / "cache")
    assert result["error"] and result["prompts_tried"][0] == "tennis ball" and len(result["prompts_tried"]) == 4

def test_wrong_motion_guess_that_cannot_fit_falls_back_to_the_better_fit(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    wrong = json.dumps({**json.loads(IDENT), "motion": "bounce"}) if isinstance(IDENT, str) else {**IDENT, "motion": "bounce"}
    fake = FakeMeta(chat_replies=[wrong, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, cache_root=tmp_path / "cache")
    assert result["chosen"] == "projectile"
    assert any("bounce model could not fit" in n for n in result["notes"])


def test_explicit_motion_override_is_never_switched(tmp_path):
    src = tmp_path / "throw.mp4"
    write_clip(src)
    fake = FakeMeta(chat_replies=[IDENT, EXPLAIN], sam_text=sam_text())
    result = run(src, tmp_path / "work", fake, Overrides(motion="bounce"), cache_root=tmp_path / "cache")
    assert result["chosen"] == "bounce"
