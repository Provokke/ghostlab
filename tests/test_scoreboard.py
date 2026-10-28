from pathlib import Path

from ghostlab.scoreboard import load, render, score

MEASURED = {"drop1": (9.70, 0.10), "drop2": (9.95, 0.05), "swing1": (0.81, 0.01)}


def fake_run(calls):
    def run(clip: Path, motion: str) -> dict:
        calls.append((clip.name, motion))
        if clip.stem == "broken":
            return {"error": "object not found", "identification": {"motion": motion}}
        value, error = MEASURED[clip.stem]
        quantity = "length" if motion == "pendulum" else "g"
        return {"identification": {"motion": motion},
                "fits": {motion: {"params": {quantity: {"value": value, "error": error, "unit": ""}}}}}
    return run


def test_scores_each_clip(tmp_path):
    csv = tmp_path / "truth.csv"
    csv.write_text("clip,motion,quantity,value\n"
                   "drop1.mp4,projectile,g,9.81\ndrop2.mp4,projectile,g,9.81\n"
                   "swing1.mp4,pendulum,length,0.80\nbroken.mp4,projectile,g,9.81\n")
    calls = []
    rows = score(load(csv), fake_run(calls))
    assert calls == [("drop1.mp4", "projectile"), ("drop2.mp4", "projectile"),
                     ("swing1.mp4", "pendulum"), ("broken.mp4", "projectile")]
    assert rows[0]["within_2sigma"] is True   # 9.70 ± 0.10 vs 9.81
    assert rows[1]["within_2sigma"] is False  # 9.95 ± 0.05 vs 9.81
    assert rows[3]["error"] == "object not found"
    table = render(rows)
    assert "| g | 2 | 1.3% | 1/2 |" in table
    assert "| length | 1 | 1.3% | 1/1 |" in table
    assert "1 clip(s) failed" in table
