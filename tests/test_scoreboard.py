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


def test_zero_truth_and_missing_quantity_do_not_crash(tmp_path):
    csv = tmp_path / "truth.csv"
    csv.write_text("clip,motion,quantity,value\ndrop1.mp4,projectile,g,0\ndrop2.mp4,projectile,e,0.5\nboom.mp4,projectile,g,9.81\n")
    def run(clip, motion):
        if clip.stem == "boom":
            raise RuntimeError("kaput")
        return fake_run([])(clip, motion)
    rows = score(load(csv), run)
    assert "error" not in rows[0] and rows[0]["error_pct"] is None and rows[0]["error_abs"] == 9.70
    assert "error" in rows[1] and "error" in rows[2] and "kaput" in rows[2]["error"]
    assert "2 clip(s) failed" in render(rows)


def test_verdict_column_and_certified_but_wrong_count(tmp_path):
    rows = [{"clip": "a.mp4", "motion": "projectile", "quantity": "g", "true": 9.81, "identified": True,
             "value": 8.0, "sigma": 0.1, "error_pct": -18.5, "error_abs": -1.81, "within_2sigma": False,
             "verdict": "certified"}]
    table = render(rows)
    assert "certified" in table and "1 certified clip(s) were off by more than 2σ" in table
