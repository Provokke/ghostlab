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

Needs before recording: real clips, `MODEL_API_KEY`, the scoreboard from `python -m ghostlab scoreboard`.
