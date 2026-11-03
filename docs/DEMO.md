# Demo video plan (3:00 max)

Rubric: Impact 30, Meta tooling 25, Demo 25, Technical depth 20. Disclosure: all clips shown are rendered with known physics, not filmed footage; say so on screen at least once.

| Time | Shot | Line |
|---|---|---|
| 0:00-0:12 | Rendered clip with known physics (a bouncing ball), ghost appears inside it | "This ghost is a physics model fitted from one video. Watch it predict the future." |
| 0:12-0:35 | Phone: Capture -> Analysing (orange real path, then the cyan ghost) | "SAM 3.1 tracks the ball. Muse Spark names it and its size. No model ever produces a measurement." |
| 0:35-1:10 | Confirm the size (10 cm), then Verdict: CERTIFIED, off by 0.8 cm; drag up the prediction-test chart | "Ghostlab tests itself on frames it never saw. Certified or refused." |
| 1:10-1:35 | camera_shake clip: REFUSED, the camera moved | "When it cannot back up a number, it says so." |
| 1:35-2:10 | Playground: hold to talk, "what if this was on the Moon" (Muse Voice Transcribe), ghost rises; Export clip | "Ask a what-if out loud. The twin answers under new physics." |
| 2:10-2:35 | Results: bounce e 0.748 vs 0.75, pendulum period 2.027 vs 2.006 s, 2 refusals | "Rendered clips with known truth: certified where it should be, refused where it should be." |
| 2:35-3:00 | Stack: SAM 3.1, Muse Spark, Muse Voice Transcribe; repo URL | "Video in, trusted physics out." |

Notes: pass ball size 10 cm or the model guesses 6.7 cm and the g check refuses. Results are cached, so do one run before recording. Regenerate the rendered clips with `scripts/render_clips.py` (output in `work/render/`; the bundled sample clips are tagged 6.7 cm, the rendered test clips are 10 cm); `scripts/ui_check.py` saves per-screen screenshots.
