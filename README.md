# Ghostlab

Film something moving on your phone. Ghostlab tracks it, fits the physics, and then **tests its own
model on footage it never saw**. If the prediction holds, you get a certified physics twin you can play
what-ifs on (Moon gravity, a bouncier ball). If it does not hold, Ghostlab refuses to show numbers.

Built for the Meta Global AI Developer Hackathon, Push the Frontier track.

## How it works

1. **Muse Spark** reads key frames and names the object, its real size and the motion type. It never produces a measurement.
2. **SAM 3.1** tracks the object through the whole clip (one box per frame).
3. Pixels become metres from the object's real size; least squares fits projectile, bounce, pendulum and ramp models, each with error bars.
4. **Held-out check:** fit on the first 60% of the clip, predict the last 40%, score against the real track. Certified or refused.
5. The phone web app draws the twin as a ghost over the real video and re-simulates under what-if physics.

## Run it

```
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]" fastapi uvicorn python-multipart
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/make_demos.py      # synthetic dev demos (placeholders, not real footage)
.venv/Scripts/python -m uvicorn ghostlab.server:app --port 8791
```

Live analysis needs `MODEL_API_KEY` (Meta Model API). Without it the app serves the bundled demos.

## What was built during the hackathon

Everything in this repository was written during the building period (the design docs under
`docs/superpowers/` were drafted on Oct 25 and contain no code).

## Accuracy (synthetic)

`docs/benchmark.md`: g is recovered within about 1% under noise and dropped frames, and the held-out check refused 100% of clips with an unmodelled late push (0% false certifications). This is synthetic data; the real-clip scoreboard comes from `python -m ghostlab scoreboard`.
