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


def score(truths: list[Truth], run_fn: Callable[[Path, str], dict]) -> list[dict]:
    rows = []
    for t in truths:
        result = run_fn(t.clip, t.motion)
        row = {"clip": t.clip.name, "motion": t.motion, "quantity": t.quantity, "true": t.value,
               "identified": result.get("identification", {}).get("motion") == t.motion}
        fit = result.get("fits", {}).get(t.motion, {"error": result.get("error", "no result")})
        if "error" in fit:
            rows.append({**row, "error": fit["error"]})
            continue
        p = fit["params"][t.quantity]
        rows.append({**row, "value": p["value"], "sigma": p["error"],
                     "error_pct": 100 * (p["value"] - t.value) / t.value,
                     "within_2sigma": abs(p["value"] - t.value) <= 2 * p["error"]})
    return rows


def render(rows: list[dict]) -> str:
    out = ["# Ghostlab accuracy scoreboard", "",
           "| Clip | Motion | Quantity | True | Measured | Error | Within 2σ | Identified |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            out.append(f"| {r['clip']} | {r['motion']} | {r['quantity']} | {r['true']:g} | failed: {r['error']} | | | |")
        else:
            out.append(f"| {r['clip']} | {r['motion']} | {r['quantity']} | {r['true']:g} | "
                       f"{r['value']:.3g} ± {r['sigma']:.2g} | {r['error_pct']:+.1f}% | "
                       f"{'yes' if r['within_2sigma'] else 'no'} | {'yes' if r['identified'] else 'no'} |")
    out += ["", "| Quantity | Clips | Median abs error | Within 2σ |", "|---|---|---|---|"]
    ok = [r for r in rows if "error" not in r]
    for q in sorted({r["quantity"] for r in ok}):
        qs = [r for r in ok if r["quantity"] == q]
        med = statistics.median(abs(r["error_pct"]) for r in qs)
        out.append(f"| {q} | {len(qs)} | {med:.1f}% | {sum(r['within_2sigma'] for r in qs)}/{len(qs)} |")
    failed = len(rows) - len(ok)
    if failed:
        out += ["", f"{failed} clip(s) failed."]
    return "\n".join(out) + "\n"


def write(truth_csv: Path, out: Path, run_fn: Callable[[Path, str], dict]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(score(load(truth_csv), run_fn)), encoding="utf-8")
