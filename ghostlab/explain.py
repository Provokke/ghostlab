"""Muse Spark explains the fitted numbers to a student. It sees numbers only, never frames."""
from __future__ import annotations

from ghostlab import meta_api
from ghostlab.core import FitResult

PROMPT_VERSION = "explain-v1"
SCHEMA = {
    "type": "object",
    "properties": {"explanation": {"type": "string"}, "class_question": {"type": "string"}},
    "required": ["explanation", "class_question"],
    "additionalProperties": False,
}


def _prompt(object_name: str, fit: FitResult) -> str:
    lines = [f"- {k}: {p.value:.3g} ± {p.error:.2g} {p.unit}".rstrip() for k, p in fit.params.items()]
    return (f"A high-school student filmed a {object_name} ({fit.motion} motion). "
            f"These values were measured from the video (fit quality: {fit.quality}):\n" + "\n".join(lines) +
            "\nIn 3 to 5 plain sentences, explain what these numbers show about the physics, comparing with "
            "textbook values where one applies (Earth's g is 9.81 m/s²). Use only the numbers given. "
            "Then write one question a teacher could ask the class about this result.")


def explain(c, object_name: str, fit: FitResult) -> dict:
    return meta_api.spark_json(c, _prompt(object_name, fit), [], "explanation", SCHEMA)
