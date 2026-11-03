"""Accuracy scoreboard: run real clips with tape-measured answers and report the errors."""
from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Truth:
    clip: Path
    motion: str
    quantity: str
    value: float


def load(truth_csv: Path) -> list[Truth]:
    with open(truth_csv, newline="", encoding="utf-8") as f:
        return [Truth(truth_csv.parent / r["clip"], r["motion"], r["quantity"], float(r["value"]))
                for r in csv.DictReader(f)]


def _row(t: Truth, run_fn: Callable[[Path, str], dict]) -> dict:
    result = run_fn(t.clip, t.motion)
    row = {"clip": t.clip.name, "motion": t.motion, "quantity": t.quantity, "true": t.value,
           "identified": result.get("identification", {}).get("motion") == t.motion}
    fit = result.get("fits", {}).get(t.motion, {"error": result.get("error", "no result")})
    if "error" in fit:
        return {**row, "error": fit["error"]}
    if t.quantity not in fit.get("params", {}):
        return {**row, "error": f"the {t.motion} fit has no '{t.quantity}'"}
    p = fit["params"][t.quantity]
    diff = p["value"] - t.value
    return {**row, "value": p["value"], "sigma": p["error"], "error_abs": diff,
            "error_pct": 100 * diff / t.value if t.value else None,  # no percentage against a zero truth
            "within_2sigma": abs(diff) <= 2 * p["error"],
            "verdict": (result.get("twin") or {}).get("verdict")}


def score(truths: list[Truth], run_fn: Callable[[Path, str], dict]) -> list[dict]:
    """One row per truth. A clip that errors, or lacks the quantity, becomes a failed row, never a crash."""
    rows = []
    for t in truths:
        try:
            rows.append(_row(t, run_fn))
        except Exception as exc:  # one bad clip must not lose the whole scoreboard
            rows.append({"clip": t.clip.name, "motion": t.motion, "quantity": t.quantity, "true": t.value,
                         "identified": False, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def _error_cell(r: dict) -> str:
    return f"{r['error_pct']:+.1f}%" if r.get("error_pct") is not None else f"{r['error_abs']:+.3g} (abs)"


def render(rows: list[dict]) -> str:
    out = ["# Ghostlab accuracy scoreboard", "",
           "| Clip | Motion | Quantity | True | Measured | Error | Within 2σ | Identified | Verdict |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            out.append(f"| {r['clip']} | {r['motion']} | {r['quantity']} | {r['true']:g} | failed: {r['error']} | | | | |")
        else:
            out.append(f"| {r['clip']} | {r['motion']} | {r['quantity']} | {r['true']:g} | "
                       f"{r['value']:.3g} ± {r['sigma']:.2g} | {_error_cell(r)} | "
                       f"{'yes' if r['within_2sigma'] else 'no'} | {'yes' if r['identified'] else 'no'} | "
                       f"{r.get('verdict') or '-'} |")
    out += ["", "| Quantity | Clips | Median abs error | Within 2σ |", "|---|---|---|---|"]
    ok = [r for r in rows if "error" not in r]
    for q in sorted({r["quantity"] for r in ok}):
        qs = [r for r in ok if r["quantity"] == q]
        pcts = [abs(r["error_pct"]) for r in qs if r.get("error_pct") is not None]
        med = f"{statistics.median(pcts):.1f}%" if pcts else "n/a"
        out.append(f"| {q} | {len(qs)} | {med} | {sum(r['within_2sigma'] for r in qs)}/{len(qs)} |")
    failed = len(rows) - len(ok)
    if failed:
        out += ["", f"{failed} clip(s) failed."]
    wrong = sum(1 for r in ok if r.get("verdict") == "certified" and not r["within_2sigma"])
    if wrong:
        out += ["", f"{wrong} certified clip(s) were off by more than 2σ."]
    return "\n".join(out) + "\n"


def write(truth_csv: Path, out: Path, run_fn: Callable[[Path, str], dict]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(score(load(truth_csv), run_fn)), encoding="utf-8")
