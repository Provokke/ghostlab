"""Clip in, result JSON out: ingest, identify, track, scale, fit, explain."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ghostlab import explain, heldout, identify, ingest, meta_api, sam_parse, scale
from ghostlab.cache import cached
from ghostlab.core import FitError, FitResult
from ghostlab.fit.select import better_alternative, fit_all


FALLBACK_PROMPTS = ("ball", "round object", "small moving object")  # tried in order when the first prompt tracks too little
EARTH_G = 9.81
G_PLAUSIBLE = (0.7, 1.3)  # fitted g outside 70-130% of Earth's: wrong scale or altered playback speed


def speed_warning(chosen) -> str | None:
    g = getattr(chosen, "params", {}).get("g")
    if g is None:
        return None
    lo, hi = G_PLAUSIBLE
    if lo * EARTH_G <= g.value <= hi * EARTH_G:
        return None
    return (f"Fitted gravity is {g.value:.2f} m/s2, far from Earth's 9.81. The clip may be slow motion or "
            "sped up, or the size is wrong. Film at normal speed and check the size.")


@dataclass(frozen=True)
class Overrides:
    object: str | None = None
    size_m: float | None = None
    motion: str | None = None


def identify_clip(c, clip: ingest.Clip, cache_root: Path | None = None) -> dict:
    """Muse Spark's guess at the object, its size and the motion; cached per clip."""
    return cached("identify", identify.PROMPT_VERSION.encode() + b"".join(clip.key_frames),
                  lambda: identify.identify(c, clip.key_frames), cache_root)


def run(src: Path, work: Path, c, overrides: Overrides = Overrides(), cache_root: Path | None = None) -> dict:
    clip = ingest.prepare(src, work)
    warnings = []
    camera_moved = clip.camera_shift > ingest.SHAKE_LIMIT
    if camera_moved:
        warnings.append("The camera moved. Prop your phone against something and film again.")
    ident = identify_clip(c, clip, cache_root)
    if ident["size_confidence"] == "low" and overrides.size_m is None:
        warnings.append(f"Not sure of the {ident['object']}'s size. Check it before trusting the numbers.")
    prompt = overrides.object or ident["sam_prompt"]
    size = overrides.size_m or ident["real_size_m"]
    motion = overrides.motion or ident["motion"]
    video = clip.path.read_bytes()
    file_id = None

    def track_with(prompt: str):
        nonlocal file_id

        def call():
            nonlocal file_id
            file_id = file_id or meta_api.upload_video(c, clip.path)
            return {"text": meta_api.sam_track(c, file_id, prompt)}

        sam = cached("sam", prompt.encode() + b"\0" + video, call, cache_root)
        frames = sam_parse.parse(sam["text"])
        pixels = sam_parse.to_pixel_track(frames, clip.n_frames, clip.fps, clip.width, clip.height)
        return scale.to_metres(pixels, size)

    tried, failure = [], None
    for candidate in dict.fromkeys([prompt, *FALLBACK_PROMPTS]):
        try:
            track, notes = track_with(candidate)
            if tried:
                notes = [*notes, f"SAM found nothing usable for {tried[0]!r}; tracked {candidate!r} instead"]
            break
        except FitError as exc:
            tried.append(candidate)
            failure = exc
    else:
        return {"error": str(failure), "identification": ident, "warnings": warnings, "prompts_tried": tried}
    pivot = scale.pivot_to_metres(track, (ident["pivot_x_px"], ident["pivot_y_px"])) if ident["has_pivot"] else None
    results = fit_all(track, pivot)
    chosen = results[motion]
    explanation = None
    twin = heldout.check(track, motion, pivot)
    if not isinstance(chosen, FitResult) and twin["verdict"] == "certified":
        twin = {**twin, "verdict": "refused", "reason": f"the full-clip fit failed: {chosen}"}
    if camera_moved and twin["verdict"] == "certified":
        twin = {**twin, "verdict": "refused", "reason": "the camera moved, so pixel positions are not real positions"}
    if isinstance(chosen, FitResult):
        if (w := speed_warning(chosen)):
            warnings.append(w)
            if twin["verdict"] == "certified":
                twin = {**twin, "verdict": "refused",
                        "reason": f"g is {chosen.params['g'].value:.1f}, not about 9.8: size or playback speed likely wrong"}
        key = explain.PROMPT_VERSION + ident["object"] + json.dumps(chosen.to_json(), sort_keys=True)
        explanation = cached("explain", key.encode(), lambda: explain.explain(c, ident["object"], chosen), cache_root)
    return {
        "clip": {"fps": clip.fps, "n_frames": clip.n_frames, "width": clip.width, "height": clip.height},
        "identification": ident,
        "track": track.to_json(),
        "fits": {k: v.to_json() if isinstance(v, FitResult) else {"error": v} for k, v in results.items()},
        "chosen": motion,
        "better_alternative": better_alternative(motion, results),
        "twin": twin,
        "notes": notes,
        "warnings": warnings,
        "explanation": explanation,
    }
