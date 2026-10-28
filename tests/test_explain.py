from ghostlab.core import FitResult, Param
from ghostlab.explain import explain
from tests.fakes import FakeMeta


def test_sends_numbers_only():
    fit = FitResult("projectile", {"g": Param(9.74, 0.21, "m/s²")}, {}, 0.004, "good", 18)
    fake = FakeMeta(chat_replies=[{"explanation": "It fell.", "class_question": "Why?"}])
    out = explain(fake, "tennis ball", fit)
    assert out == {"explanation": "It fell.", "class_question": "Why?"}
    _, messages, _ = fake.calls[0]
    parts = messages[0]["content"]
    assert [p["type"] for p in parts] == ["text"]
    assert "9.74" in parts[0]["text"] and "0.21" in parts[0]["text"] and "tennis ball" in parts[0]["text"]
