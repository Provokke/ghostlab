import pytest

from ghostlab.identify import identify
from tests.fakes import FakeMeta

REPLY = {"object": "tennis ball", "sam_prompt": "tennis ball", "real_size_m": 0.067, "size_confidence": "high",
         "motion": "projectile", "has_pivot": False, "pivot_x_px": 0, "pivot_y_px": 0, "reasoning": "thrown"}


def test_sends_three_frames_and_returns_fields():
    fake = FakeMeta(chat_replies=[REPLY])
    result = identify(fake, [b"a", b"b", b"c"])
    assert result["motion"] == "projectile" and result["real_size_m"] == 0.067
    _, messages, fmt = fake.calls[0]
    assert sum(p["type"] == "image_url" for p in messages[0]["content"]) == 3
    assert fmt["json_schema"]["name"] == "identification"


def test_rejects_impossible_size():
    fake = FakeMeta(chat_replies=[{**REPLY, "real_size_m": 0}])
    with pytest.raises(ValueError):
        identify(fake, [b"a", b"b", b"c"])
