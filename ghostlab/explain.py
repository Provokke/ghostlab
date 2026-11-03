"""Muse Spark explains the fitted numbers to a student. It sees numbers only, never frames."""
from __future__ import annotations

from ghostlab import meta_api
from ghostlab.core import FitResult

PROMPT_VERSION = "explain-v2"
MAX_NAME = 60
SCHEMA = {
    "type": "object",
    "properties": {"explanation": {"type": "string"}, "class_question": {"type": "string"}},
    "required": ["explanation", "class_question"],
    "additionalProperties": False,
}


def _clean_name(name: str) -> str:
    """The object name is user-editable text going into a prompt: one short printable line."""
    cleaned = " ".join("".join(ch if ch.isprintable() else " " for ch in str(name)).split())[:MAX_NAME]
    return cleaned or "object"


def _prompt(object_name: str, fit: FitResult, verdict: str | None = None, reason: str | None = None) -> str:
    lines = [f"- {k}: {p.value:.3g} ± {p.error:.2g} {p.unit}".rstrip() for k, p in fit.params.items()]
    caveat = ""
    if verdict == "refused":
        caveat = (" The app REFUSED to certify this result"
                  + (f" ({reason})" if reason else "")
                  + ": its prediction test on unseen frames failed. Say plainly that these numbers are not "
                  "trustworthy, do not praise them, and say what the student should film again.")
    return (f"A high-school student filmed a {_clean_name(object_name)} ({fit.motion} motion). "
            f"These values were measured from the video (fit quality: {fit.quality}):\n" + "\n".join(lines) +
            "\nIn 3 to 5 plain sentences, explain what these numbers show about the physics, comparing with "
            "textbook values where one applies (Earth's g is 9.81 m/s²). Use only the numbers given." + caveat +
            " Then write one question a teacher could ask the class about this result.")


def explain(c, object_name: str, fit: FitResult, verdict: str | None = None, reason: str | None = None) -> dict:
    """Plain-language explanation and a class question. Pass the held-out verdict so a refused fit is caveated."""
    return meta_api.spark_json(c, _prompt(object_name, fit, verdict, reason), [], "explanation", SCHEMA)
