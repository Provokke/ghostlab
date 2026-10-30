# Phone UI overhaul: design

## Intent
Ghostlab is a phone-first web app judged mainly on a 3-minute demo video (Demo 25, Impact 30, Meta tooling 25, Technical depth 20). The overhaul exists for demo wow factor: the ghost, the trust verdict (certified or refused) and the what-if playground are the show. The current UI is one scrolling stack of cards that reads as a dev tool and has no way to correct the object's size, which the rendered-clip runs showed decides most results.

Owner decisions (2026-10-31): dark "lab scope" look (full-bleed video, glowing cyan ghost, orange real path); stepped screens; confirm the size before the verdict; playground with planet presets plus live slider, voice what-if, ghost replay animation and an exportable clip; vanilla JS modules with no build step; export in the browser.

## Screens (390 px wide first, scales up)
1. Capture: wordmark, Film (camera) and Upload buttons, sample clips as small chips, a one-line hint (prop the phone, film at normal speed).
2. Analysing: clip plays full-bleed; tracking dots appear, the real path draws in orange, then the cyan ghost draws and extends past it.
3. Confirm: detected object circled with its guessed size as preset chips (tennis ball, football, basketball, custom cm); one tap confirms or corrects. Shown before any verdict.
4. Verdict: full-bleed ghost replay under a bottom card with a CERTIFIED (green) or REFUSED (red) badge and "off by N cm". A drag-up sheet holds the prediction-test chart and measured numbers. A refusal shows the reason in plain words, a "film again" tip and withholds numbers (with "Show anyway", as today).
5. Playground: Moon, Mars, Jupiter chips, live gravity slider (bounciness for bounces), hold-to-talk mic, export button. The ghost re-arcs as physics changes.

## Code structure (vanilla ES modules, no build step)
`web/app.js` is replaced by modules: `screens.js` (state machine over the five screens), `ghost.js` (canvas overlay, replay animation, trails), `capture.js`, `confirm.js`, `verdict.js`, `playground.js`, `voice.js` (MediaRecorder to `/api/voice`), `export.js` (canvas + MediaRecorder to a downloadable clip), `api.js`. `style.css` defines design tokens on `:root` (colours, glow, type scale, spacing). The existing light theme is dropped.

## Backend changes (small)
- `POST /api/identify`: takes the upload, stores it under an upload id, returns `{id, identification, video}`.
- `POST /api/analyze`: takes `{id, size_m?, object?, motion?}` and runs `pipeline.run` with `Overrides`. Identify and SAM results are cached per clip, so a size correction is a cheap local re-fit.
- Unchanged: demo clips, `/api/simulate`, `/api/whatif`, `/api/voice`, `/api/status`.
- Demo clips (bump, drop, throw) skip the Confirm screen and are tagged "Sample clip (synthetic)".

## Out of scope
Accounts, history, saved sessions, any change to the physics fits or trust gates, a server-side export render (added only if Safari recording fails in testing).

## Testing
- Extend `scripts/ui_check.py` to walk all five screens in a phone viewport: no console errors, no horizontal overflow, ghost ink drawn on Analysing, Verdict and Playground.
- Backend tests for the two-step identify/analyze flow, including a wrong-size correction that changes the verdict.
- A headless-Edge test that export produces a non-empty video blob. Real iPhone Safari is untested and will be reported as such.

## Risks
- Safari `MediaRecorder` support is patchy (may emit WebM or fail); fallback is the server-side render.
- Microphone capture needs HTTPS or localhost on phones; a tunnel or Modal deploy is needed for real-device voice and camera.
- Live analysis needs `MODEL_API_KEY` and costs credit per run (~$0.1-0.5).
