# Ghostlab design

- Date: 2026-10-25
- Event: Meta Global AI Developer Hackathon, Indie developer track, solo
- Window: build Oct 26 to Nov 4, 9:00 PM ET (= Thu Nov 5, 1:00 PM AEDT; US DST ends Nov 1)
- Judged on: "creativity, technical ambition, and whether it works"
- Theme: 2, "Push the Frontier" (science education)

## One line

Film anything moving on your phone; Ghostlab finds the object, measures the physics, and lets a student
replay it under different physics with a translucent "ghost" running inside the real footage.

## Why this, and how it differs

Existing tools are manual: Tracker (desktop: autotrack after manual setup, curve fitting, model overlay)
and Vernier Video Physics (iOS: tap-to-track, manual scale, graphs, no physics fit or what-if sim).
Ghostlab needs **no setup**: the AI identifies the object, its real size and the motion type, fits the
physics, and simulates it. Pitch line: "Tracker takes 20 minutes of setup. This takes zero."
Signature visual neither tool has: the ghost replay drawn inside the real video.

Users: high-school physics students and teachers.

## Scope (v1)

Motion types, in build order: projectile (thrown or dropped), bounce, pendulum, ramp/friction.
Ramp is cut if projectile, bounce and pendulum are not solid by Nov 1.

Out of scope for v1: moving camera, motion toward/away from the camera (v1 requires side-on motion),
multiple tracked objects, accounts, saving labs server-side.

## Architecture

```
Browser (phone-first)                     Python backend (FastAPI, small VPS)
Upload/record clip (<=15 s) ───────────►  1 ingest    trim, downscale to 720p, frames + timestamps
                                          2 identify  Muse Spark on 3 frames -> object, real size,
                                                      confidence, motion type, pivot (pendulum)
                                          3 track     SAM 3.1, text prompt -> mask per frame
                                                      -> centre and pixel width per frame
                                          4 scale     real size / pixel width -> metres per pixel
                                          5 fit       fit/<motion>.py -> params +- error, fit quality
                                          6 explain   Muse Spark gets ONLY fitted numbers ->
                                                      3-5 sentence explanation + 1 class question
◄─────────── result JSON ───────────────  {track, params, errors, fit_quality, explanation, masks}
Lab view: video + path + ghost | sliders | graphs | numbers | explanation
```

Principle: **SAM measures, Muse Spark identifies and explains, plain maths fits the physics.**
The language model never produces a measurement.

### Units

| Unit | Job | Depends on |
|---|---|---|
| `ingest.py` | Clip -> frames, timestamps, background-motion check | ffmpeg |
| `identify.py` | Frames -> object, size, motion type, pivot | Meta Model API (Muse Spark) |
| `track.py` | Frames + prompt -> per-frame centre and width | Meta Model API (SAM 3.1) |
| `scale.py` | Track + real size -> track in metres | none |
| `fit/projectile.py`, `fit/bounce.py`, `fit/pendulum.py`, `fit/ramp.py` | `fit(track) -> Params`, `simulate(params, t) -> positions` | SciPy |
| `explain.py` | Params -> explanation text | Meta Model API (Muse Spark) |
| `api.py` | HTTP endpoints, job queue, progress events | all above |
| `web/` | Screens, ghost renderer, client-side simulation | result JSON only |

- `identify.py`, `track.py` and `explain.py` are the only units that call Meta's API. All three save every
  response to disk keyed by input hash, so development re-runs are free and repeatable.
- The browser runs `simulate` itself (a JS port of each motion's equations), so sliders respond with no
  server round trip. Python and JS simulations are checked against each other in tests.
- Every fit module runs on every clip. If a non-chosen model fits much better than the chosen one,
  the result says so.

### Fallbacks

- SAM 3.1 API has image segmentation only (no video tracking): segment each frame by text prompt and
  link detections by nearest centre. Costs about a day; nothing else changes.
- SAM 3.1 API too slow or rate-limited: run open-weights SAM on Modal (partner credits offered).
  Last resort: the local GPU.

## Screens

1. **Home**: Film it / Upload, example clip gallery, filming tip.
2. **Working**: stage-by-stage progress; SAM outlines appear on frames as they arrive.
3. **Predict**: "On the Moon, where would it land? Tap the spot." Scored after the reveal.
4. **Lab**: video with tracked path and ghost; sliders (gravity with Earth/Moon/Mars presets, mass,
   launch speed, bounce loss, string length, friction); tabs Graphs (data dots + fitted line for
   position, speed, energy), Numbers (each value +- error, fit quality), Explain; share exports the
   ghost replay as a clip.
5. **Override sheet**: change the object, size or motion type; re-fits instantly.
6. **How it saw it**: per-frame SAM masks and Muse Spark's identification reasoning.

## Errors

| Problem | Detect | Student sees |
|---|---|---|
| Object lost in some frames | Frames with no mask | Gaps up to 3 frames filled; longer gaps: fit the clean section only, and say so |
| Shaky camera | Background motion above threshold | "Prop your phone against something and film again" |
| Unsure of size | Identify confidence low | Pick-list: tennis ball, A4 sheet, 1 m ruler, or type it in |
| Poor fit | Fit quality below threshold | Result labelled "rough", plus filming tips |
| API slow or down | Timeout | Queue with progress; example clips still work from saved results |

Rule: no number is ever shown without its error bar and fit quality.

## Testing and accuracy

1. **Fit modules on synthetic data**: generate each motion with known parameters, add realistic noise
   and dropped frames, assert recovery within the reported error. No API. Runs on every change.
2. **Pipeline on 20 recorded test clips** with saved API responses and tape-measured truths (drops: g;
   pendulums: string length; bounce: measured drop and rebound heights). Output is the accuracy
   scoreboard published in the app and README ("measured g within X% across N clips").
3. **Daily live check**: one real upload to the deployed site.

## Odds improvers (all in scope)

1. Ghost replay inside the real video: the first 10 s of the demo.
2. Predict-then-reveal (predict-observe-explain teaching method).
3. Accuracy scoreboard.
4. "How it saw it" panel showing Meta's models at work.
5. Demo that can't fail: 6 example clips with saved results, alongside live upload.
6. One real physics teacher trying it, with a short quote on camera.
7. Attend workshops; ask one specific question in office hours or Discord.
8. Stay quiet until about Nov 2, then post a short ghost clip.
9. Write the demo video script on day 3 and build toward its shots.
10. Clean public repo: one-command run, passing tests, README with the accuracy table; credit Muse Code
    if used.

## Demo video (2:00)

- 0:00-0:10 Moon ghost inside a real backyard clip
- 0:10-0:30 Problem: video labs need fiddly manual setup, so teachers skip them
- 0:30-1:20 One clip end to end in real time: film, predict, ghost, graphs, explanation
- 1:20-1:40 Bounce, pendulum, ramp cuts; accuracy scoreboard
- 1:40-2:00 Teacher quote; "how it saw it" panel; link

## Schedule

| Day | Work |
|---|---|
| Oct 26 | Kickoff; read the Official Rules and waiver; test the API (SAM 3.1 video vs image, speed, limits, Muse Spark vision); start finding a teacher |
| Oct 27 | Projectile end to end in a rough interface; film the 20 test clips |
| Oct 28 | Scale and identify working; first scoreboard run; write the video script |
| Oct 29 | Lab screen, ghost replay, sliders |
| Oct 30 | Bounce and pendulum fits |
| Oct 31 | Predict screen, graphs, explanation; deploy to the VPS |
| Nov 1 | Ramp fit (cut if the first three are not solid); error handling |
| Nov 2 | Feature freeze. Example gallery, mobile polish, teaser post |
| Nov 3 | Teacher session, record the demo video, README with accuracy table |
| Nov 4 | Buffer; submit Wednesday evening AEDT (hard deadline Thu Nov 5, 1:00 PM AEDT) |

## Open items to settle on Oct 26 (from the Official Rules, unpublished on Oct 25)

- Whether work must be created during the event. This repo holds only this design doc before Oct 26;
  all code starts Oct 26.
- IP and licence terms, repo visibility, submission format (video length, demo, write-up).
- Whether non-Meta coding assistants are allowed.
- Consent rules for filming people, especially minors (students): default to filming objects only,
  with adult hands, and no faces in shared clips.
