# Ghostlab design

- Date: 2026-10-25
- Event: Meta Global AI Developer Hackathon, Indie developer track, solo
- Window: build Oct 26 to Nov 4, 9:00 PM ET (= Thu Nov 5, 1:00 PM AEDT; US DST ends Nov 1)
- Judged on (Official Rules): Impact 30%, Use of Meta AI Tooling 25%, Technical Depth & Execution 20%,
  Demo 25% (working live, holds up, video quality)
- Indie prizes: $150k / $100k / $75k / $50k / $25k, plus bonus prizes up to $50k total (community vote,
  most viral, others) announced about Nov 10
- Credits: $150 Meta Model API credits, valid for the 10-day development window only
- Theme: 2, "Push the Frontier" (SAM 3.1 as a scientific measuring instrument), applied to physics
  education for impact. Re-check against the problem statements published at kickoff.

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

## Scoring against the judging weights

**Impact (30%)**
- Pitch: a phone replaces a few hundred dollars of lab sensors (photogates, motion detectors), so any
  school can run real kinematics labs.
- Printable lab worksheet export: the student's prediction, data table, fitted values with errors,
  graph, and the class question. A teacher can use it in a lesson the next day.
- A real teacher's verdict on camera (odds improver 6).

**Use of Meta AI Tooling (25%): go beyond "SAM tracks a ball"**
- SAM 3.1 as a measuring instrument, not just a tracker:
  - pendulum: segment the string itself to get pivot and length, so nothing is typed in;
  - ramp: segment the ramp surface to get the slope angle;
  - bounce: mask shape change (squash) at impact gives contact time.
- Muse Spark vision: object identity and real size (the scale), pivot location, motion type, and the
  check "does this fit match what you see in the frames?"
- Muse Image (stretch, Nov 2 only if ahead): repaint the share clip's background as the Moon or Mars
  while the ghost moves under that gravity. Built for the most-viral bonus.
- Write-up section "What we found SAM 3.1 can measure": accuracy per quantity from the scoreboard.
  This is the "surfaced unexpected capabilities" the criterion asks for.
- Use Muse Code for part of the build and say so.

**Technical Depth & Execution (20%)**: error bars on every number, the cross-check between motion
models, synthetic-data tests, the accuracy scoreboard.

**Demo (25%)**: ghost replay, example gallery that cannot fail, live upload, a 2:00 video.

## Credits and the judging window

- $150 must cover development and judges' live uploads. On Oct 26, measure the cost of one clip.
  Budget: about $60 development, $60 judge traffic, $30 reserve.
- Every API response is cached by input hash; development re-runs cost nothing.
- Public uploads: clips capped at 15 s and 720p, per-visitor daily cap.
- **Risk: credits expire after the 10-day window, but judging runs Nov 4-8.** Live upload during
  judging needs one of: paid billing on the Meta Model API account, or open-weights SAM on Modal
  (partner credits). The example gallery works with no API at all. Settle this by Oct 31.

## Odds improvers (all in scope)

1. Ghost replay inside the real video: the first 10 s of the demo.
2. Predict-then-reveal (predict-observe-explain teaching method).
3. Accuracy scoreboard.
4. "How it saw it" panel showing Meta's models at work.
5. Demo that can't fail: 6 example clips with saved results, alongside live upload.
6. One real physics teacher trying it, with a short quote on camera.
7. Attend workshops; ask one specific question in office hours or Discord.
8. Post a short ghost clip from about Oct 31 (once the ghost looks good), then progress clips daily.
   The rules give no confidentiality anyway, and community-vote and most-viral bonus prizes reward
   reach built before judging.
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
| Oct 31 | Predict screen, graphs, explanation; deploy to the VPS; settle judging-window credits; first teaser post |
| Nov 1 | Ramp fit (cut if the first three are not solid); string and ramp segmentation; error handling |
| Nov 2 | Feature freeze. Example gallery, worksheet export, mobile polish; Muse Image backdrop only if ahead |
| Nov 3 | Teacher session, record the demo video, README with accuracy table and "what SAM 3.1 can measure" |
| Nov 4 | Buffer; submit Wednesday evening AEDT (hard deadline Thu Nov 5, 1:00 PM AEDT) |

## Rules that shape the build (Official Rules, read Oct 25)

- The Submission must be original work that you own and that infringes no one's IP or privacy.
  Contracted technical help is allowed if you own the result; open source is allowed if its licences
  are followed. No rule requires work to start during the event. Before Oct 26 the repo holds only
  the design doc and the Plan 1 implementation plan (which includes code drafts); the package itself
  is built from Oct 26.
- You keep ownership. Meta and Cerebral Valley get a perpetual, royalty-free, non-exclusive licence to
  the Submission, and anything shared during the event is not confidential.
- Example and demo clips: objects and adult hands only, no faces, no minors, no music, so there are no
  privacy or copyright claims.
- Indie track allows teams of up to 4; this plan is solo.
- Submit at https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit

## Open items to settle on Oct 26

- The problem statements (Impact checks fit with one), and the submission form fields and video length.
- What Glimmer and Muse Wonder do, and whether either beats Muse Spark for identify or explain.
- SAM 3.1 API: video tracking or images only; speed; price per clip.
- Whether credits or paid billing continue through judging (Nov 4-8).
