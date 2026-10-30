# Demo video plan (3:00 max, judges watch this first)

Rubric: Impact 30, Meta tooling 25, Demo 25, Technical depth 20. Show only what was built during the event.

| Time | Shot | Line |
|---|---|---|
| 0:00-0:12 | Real clip of a ball bouncing, ghost appears inside it | "This ghost is a physics model fitted from one phone video. Watch it predict the future." |
| 0:12-0:35 | Phone: film a throw, upload, SAM 3.1 tracking overlay | "SAM 3.1 tracks the ball. Muse Spark names it and its size. No model ever produces a measurement." |
| 0:35-1:10 | Trust card: fit on first 60%, predicted last 40%, off by N cm | "Ghostlab tests itself on frames it never saw. Certified or refused." |
| 1:10-1:35 | Bad clip (camera moving or two objects): twin refused | "When it cannot back up a number, it says so." |
| 1:35-2:10 | Say "what if this was on the Moon" (Muse Voice Transcribe), ghost rises | "Ask a what-if out loud. The twin answers under new physics." |
| 2:10-2:35 | Scoreboard table: measured g vs 9.81 across all clips | "Across N clips, g is within X%, with error bars." |
| 2:35-3:00 | Stack slide: SAM 3.1, Muse Spark, Voice Transcribe, Muse Code; public repo URL | "Video in, trusted physics out. Built this week." |

Status (2026-10-30):
- Ready: rendered clips with known truth in `work/render/` (bounce, pendulum, toss certify; camera_shake and slowmo refuse). Results are in `docs/benchmark.md`. Label them "rendered" on screen; nothing here is filmed footage.
- Shots 1-2 and 1:10-1:35 can use these clips: the certify/refuse contrast is real, run live. Say plainly that the clips are rendered with known physics, and that free real clips were mostly refused, which is the trust check working.
- Pass the ball size (`--size 0.10`) or the model will guess a 6.7 cm tennis ball and the g-plausibility gate will refuse the clip.
- Owner only: screen and voice recording, the Moon what-if with live Voice Transcribe, public repo URL (no GitHub remote yet).
- The scoreboard command is for tape-measured real clips; use the benchmark table until there are some.

