# Ghostlab: submission text

Meta Global AI Developer Hackathon, Indie developer track (solo). Draft for the entry form; every claim below is checked against the repo.

## One line

Film something moving on your phone. Ghostlab measures the physics, tests its own model on footage it never saw, and either certifies a twin you can play what-ifs on or refuses to show numbers.

## The problem (Impact)

Physics students and teachers can film a ball bounce or a pendulum swing in seconds, but turning the video into a trustworthy measurement takes tracking software, a ruler in frame and an afternoon. Worse, most "AI from video" tools will happily give a number for a bad clip: a shaking phone, slow motion, the wrong size. For education a confident wrong number is worse than no number.

Ghostlab is a phone-first physics instrument that is honest about when it cannot be trusted. It reads a clip, fits the motion, and then predicts the last 40% of the clip from the first 60%. If the prediction misses, it says so and shows nothing else. If it holds, the "ghost" model replays inside the real video and answers what-ifs: Moon gravity, Mars, a bouncier ball, by typing or by speaking.

## How it uses Meta AI (Meta tooling)

| Tool | Job in Ghostlab | Where |
|---|---|---|
| SAM 3.1 | Tracks the object through the whole clip, one box per frame, from a text prompt. Retries with fallback prompts when the first finds too little. | `ghostlab/meta_api.py`, `pipeline.py`, `sam_parse.py` |
| Muse Spark 1.3 | Looks at six key frames and names the object, its real size and the motion type; writes the plain-language explanation. It never produces a measurement. | `identify.py`, `explain.py` |
| Muse Voice Transcribe | Turns a spoken what-if ("what if this was on the moon?") into text; keywords map it to gravity or bounciness. Checked live on 2026-11-02: it returned "What if this was on the moon?" and the parser gave g = 1.62. | `voice.py` |

Design rule: the language model proposes (what the object is, how big, what kind of motion); numbers come only from tracking plus least squares. A wrong guess from the model is caught by the fit and the held-out check, not trusted.

## Technical depth

- Four motion models fitted by least squares with error bars: projectile, bounce, pendulum (damped, with a geometric circle fit for the pivot), ramp.
- Held-out trust check: fit the first 60%, predict the rest, certify or refuse on the error in centimetres.
- Further refusals: camera moved (background optical-flow drift), fitted g far from 9.81 (slow motion, wrong size), fewer than one full swing, the identified motion cannot fit the data.
- Self-correcting identification: when Muse Spark's motion guess cannot fit at all and another model fits much better, the pipeline switches and says so. An explicit user override is never switched. Found by a live run: Muse Spark called a bouncing ball "a drop".
- Phone web app: five screens, vanilla ES modules, no build step, voice what-ifs, in-browser export of the replay as an H.264 clip.
- Answers are cached per clip, so correcting the size is a cheap local re-fit.
- 83 automated tests plus a headless-browser walk of all five screens at phone width.

## Evidence

Synthetic benchmark (`docs/benchmark.md`, 20 seeds per row): g recovered within about 1% under noise and dropped frames; the trust check refused 100% of clips with an unmodelled late push (0% false certifications).

Rendered clips with known truth, run end to end against the live Meta API (2026-11-02, ball size given as 10 cm):

| Clip | Expected | Result |
|---|---|---|
| bounce (restitution 0.75) | certify | certified: e 0.748, held-out error 0.8 cm |
| pendulum (L 1.0 m, period 2.006 s) | certify | certified: period 2.027 s (1% off), g 10.08 |
| toss | certify | certified: g 8.93 (9% off; motion blur inflates the tracked box) |
| camera shake | refuse | refused: camera moved |
| slow motion (1/3 speed) | refuse | refused: under one swing, g reads 1.13 |

## Honest limits

- The five clips above are rendered, not filmed, so they test the pipeline and are not real footage. Free real clips I tried (pendulum, gym bounce, juggling, tennis, soccer, slow-motion throw) were all refused by the trust check, and none was certified wrongly.
- Toss g is 9% off because of motion blur in the tracked box.
- The ball size has to be confirmed or Muse Spark's guess can be wrong (it guessed a 6.7 cm tennis ball for a 10 cm ball); the app asks before giving a verdict.
- Not yet tested on a real iPhone Safari (camera upload, microphone, export).

## Built during the hackathon

Everything in the repository was written during the building period (first commit 2026-10-25; the design documents under `docs/superpowers/` contain no code). The repo is local git with no public remote yet.
