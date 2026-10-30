"""Muse Spark looks at three frames: what is moving, how big it really is, what kind of motion."""
from __future__ import annotations

from ghostlab import meta_api

PROMPT_VERSION = "identify-v2"
MOTIONS = ["projectile", "bounce", "pendulum", "ramp"]
PROMPT = """These are evenly spaced frames, in time order, from a short video a physics student filmed.
Find the single object whose motion the student wants to measure.
- object: a short name, e.g. "tennis ball".
- sam_prompt: ONE short noun phrase a segmentation model can find in every frame, e.g. "tennis ball".
- real_size_m: the object's real longest side in metres (tennis ball 0.067, basketball 0.24, A4 sheet 0.297).
- size_confidence: high if it is a standard object, low if you are guessing.
- motion: projectile (thrown or dropped, no bounce), bounce (hits the floor and rebounds: the object is high, then low, then high again),
  pendulum (swings on a string or rod), ramp (slides or rolls down a slope).
- has_pivot / pivot_x_px / pivot_y_px: for a pendulum, the pivot's pixel position in the FIRST frame; otherwise false, 0, 0.
- reasoning: one sentence."""
SCHEMA = {
    "type": "object",
    "properties": {
        "object": {"type": "string"},
        "sam_prompt": {"type": "string"},
        "real_size_m": {"type": "number"},
        "size_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "motion": {"type": "string", "enum": MOTIONS},
        "has_pivot": {"type": "boolean"},
        "pivot_x_px": {"type": "number"},
        "pivot_y_px": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["object", "sam_prompt", "real_size_m", "size_confidence", "motion",
                 "has_pivot", "pivot_x_px", "pivot_y_px", "reasoning"],
    "additionalProperties": False,
}


def identify(c, frames: list[bytes]) -> dict:
    result = meta_api.spark_json(c, PROMPT, frames, "identification", SCHEMA)
    if not 0 < result["real_size_m"] < 10:
        raise ValueError(f"implausible object size {result['real_size_m']} m")
    return result
