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
    assert result["explanation"] == EXPLAIN
    assert [c[0] for c in fake.calls] == ["chat", "file", "sam", "chat"]


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
