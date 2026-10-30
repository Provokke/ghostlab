# Phone UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-scroll light UI with five dark "lab scope" phone screens (Capture, Analysing, Confirm, Verdict, Playground) and a two-step identify/analyze backend so the object size can be confirmed before the verdict.

**Architecture:** FastAPI gains `/api/identify` (store clip, run Muse Spark, return id) and a JSON `/api/analyze` (id + overrides, re-fit from the disk cache). The front end becomes vanilla ES modules: `screens.js` is a state machine, `ghost.js` owns the canvas overlay and replay, one module per screen. No build step.

**Tech Stack:** Python 3.11, FastAPI, pytest + `fastapi.testclient`, vanilla JS ES modules, Playwright (Edge, headless) via `scripts/ui_check.py`.

**Spec:** `docs/superpowers/specs/2026-10-31-phone-ui-overhaul-design.md`

## Global Constraints

- Phone first: 390 px wide, scales up; no horizontal overflow at 390 px.
- Dark look only: full-bleed video, glowing cyan ghost (`--ghost`), orange real path (`--real`); the light `prefers-color-scheme` theme is deleted.
- Design tokens (colours, glow, type scale, spacing) live on `:root` in `web/style.css`.
- Vanilla ES modules, no bundler, no npm; `web/app.js` is deleted.
- Demo clips (`bump`, `drop`, `throw`) skip Confirm and show the tag "Sample clip (synthetic)".
- No change to physics fits, trust gates, `/api/simulate`, `/api/whatif`, `/api/voice`, `/api/status`, `/api/demos`, `/api/demo/{name}`.
- Export happens in the browser (canvas + MediaRecorder); server-side render only if Safari recording fails in testing (not in this plan).
- Run tests quietly: `.venv/Scripts/python -m pytest -q 2>&1 | tail -n 30`.
- Real iPhone Safari is untested; say so in the final report.

## Review Focus

- Upload id taken from the URL/body is untrusted: `../x` or a wrong-length id must give 4xx, never read outside `web/uploads`.
- Analyze for an unknown id gives 404; without `MODEL_API_KEY` gives 503 with the existing "Try a demo clip" wording.
- A non-video or one-frame upload gives a 400 with a plain sentence, not a 500.
- Custom size on Confirm: empty, zero, negative, or over 10 m is rejected in the UI and by the server (422).
- Pipeline returns `{"error": ...}` (SAM found nothing): Analysing shows the reason and a "Film again" button; no blank screen.
- Double tap on Confirm sends exactly one `/api/analyze`.
- Mic denied or `MediaRecorder` unsupported: Playground and export show a one-line message, rest keeps working.
- A refused verdict never opens the Playground (what-if on an untrusted fit is hidden, as today).

## File Structure

- `ghostlab/pipeline.py` (modify): add `identify_clip`, used by `run` and the server.
- `ghostlab/server.py` (modify): `/api/identify`, JSON `/api/analyze`.
- `tests/test_server.py` (create): TestClient tests.
- `web/index.html`, `web/style.css` (rewrite): shell, five `<section data-screen>` containers, tokens.
- `web/js/api.js`, `screens.js`, `ghost.js`, `capture.js`, `confirm.js`, `verdict.js`, `playground.js`, `voice.js`, `export.js` (create); `web/app.js` (delete).
- `scripts/ui_check.py` (rewrite as a per-screen walk).

---

### Task 1: Two-step identify / analyze backend

**Files:**
- Modify: `ghostlab/pipeline.py:30-50` (extract the identify call), `ghostlab/server.py` (replace `/api/analyze`)
- Create: `tests/test_server.py`

**Interfaces:**
- Produces: `pipeline.identify_clip(c, clip: ingest.Clip, cache_root: Path | None = None) -> dict` (same dict as today's `ident`).
- Produces: `POST /api/identify` (multipart `file`) -> `{"id": str(32 hex), "identification": dict, "video": "/uploads/<id>.mp4", "clip": {"fps","n_frames","width","height"}}`.
- Produces: `POST /api/analyze` JSON `{"id": str, "size_m": float|null, "object": str|null, "motion": str|null}` -> the existing `pipeline.run` result plus `"video"`.

- [ ] **Step 1: Write failing tests** in `tests/test_server.py`, reusing `write_clip`, `sam_text`, `IDENT`, `EXPLAIN` from `tests/test_pipeline.py` and `FakeMeta`. Fixture sets `MODEL_API_KEY=x`, `GHOSTLAB_CACHE=tmp_path`, monkeypatches `server.meta_api.client` to return one shared `FakeMeta` and `server.WEB` to `tmp_path/"web"`. Tests:
  - `test_identify_returns_id_and_guess`: identify returns 32-hex id, `identification["real_size_m"] == 0.067`, `video` file exists under uploads.
  - `test_wrong_size_corrected_changes_verdict`: IDENT with `real_size_m` 0.2; `chat_replies=[ident_wrong, EXPLAIN, EXPLAIN]`; analyze with `size_m=None` gives `twin.verdict == "refused"`, then analyze with `size_m=0.067` gives `"certified"`; exactly one `("chat", ...)` identify call and one `("sam", ...)` call in `fake.calls` (cache hit on the second analyze).
  - `test_unknown_id_404`, `test_bad_id_rejected` (`"../x"` -> 4xx), `test_size_out_of_range_422` (`size_m=0` and `11`), `test_non_video_400`, `test_no_key_503` for both endpoints.

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_server.py -q` -> FAIL (no `/api/identify`).

- [ ] **Step 3: Implement.** In `pipeline.py` move the cached identify block into `identify_clip` and call it from `run`. In `server.py`: `UPLOAD_ID = re.compile(r"^[0-9a-f]{32}$")`; `/api/identify` writes the original to `WEB/uploads/<id>/src<suffix>`, runs `ingest.prepare` into a temp dir (ValueError / CalledProcessError -> 400 "That file could not be read as a video."), copies the normalised clip to `WEB/uploads/<id>.mp4`, returns the payload. `AnalyzeRequest(BaseModel)` with `size_m: float | None = Field(None, gt=0, lt=10)`. `/api/analyze` validates the id against `UPLOAD_ID`, 404 if the source is missing, runs `pipeline.run(src, tmp/"work", client, Overrides(...))` and sets `result["video"]`. Both endpoints 503 without `MODEL_API_KEY`.

- [ ] **Step 4: Run** full suite quietly -> all pass (existing tests unchanged).

- [ ] **Step 5: Commit** `git add ghostlab/pipeline.py ghostlab/server.py tests/test_server.py && git commit -m "Two-step identify/analyze so the size can be confirmed before the verdict"`

---

### Task 2: Shell, tokens, screen state machine, demo path

**Files:**
- Rewrite: `web/index.html`, `web/style.css`; Create: `web/js/api.js`, `web/js/screens.js`, `web/js/ghost.js`; Delete: `web/app.js`
- Rewrite: `scripts/ui_check.py`

**Interfaces:**
- Produces `api.js` exports: `api(path, opts) -> Promise<json>` (throws `Error(detail)`), `getDemos()`, `getDemo(name)`, `identify(file)`, `analyze(body)`, `simulate(body)`, `whatif(body)`, `voice(formData)`.
- Produces `screens.js`: `export const ctx = { result, ident, uploadId, video, demo }`; `export function go(name, data)` where `name` in `capture|analysing|confirm|verdict|playground`. Each screen module exports `mount(root, ctx)` and optional `unmount()`. `go` hides all `section[data-screen]` but one, calls the previous `unmount`, then the new `mount`. `document.body.dataset.screen` mirrors the current name.
- Produces `ghost.js`: `createGhost(canvas, video) -> { setResult(R), setGhost(pts), setWhat(pts), mode(name), replay(), destroy() }`; `pts` is `{t: number[], px: (number|null)[], py: (number|null)[]}`. Modes: `"analysing"` (dots for tracked frames up to `video.currentTime`, orange real path draws, then cyan ghost draws and extends past it), `"verdict"`, `"playground"` (ghost plus what-if in `--what`). Glow via `ctx.shadowBlur`. Port `dot/trail/at` logic from the old `app.js` (`DT = 1/60`).
- Consumes `/api/simulate` body shape from the old `simulate()` in `web/app.js` (blind ghost uses `R.twin.sim` and `t - R.twin.t_origin`); move that into `ghost.js` as `ghostPoints(R) -> Promise<pts>`.

- [ ] **Step 1: Write the failing check** in `scripts/ui_check.py`: helper `walk(page)` that loads `/`, asserts `body[data-screen="capture"]`, clicks the `bump` chip, asserts `body[data-screen="verdict"]` within 3 s with no Confirm step, asserts `scrollWidth - innerWidth <= 0` at 390x844, console errors empty, overlay ink > 0 after seeking video to 0.9 s and pausing. Run `.venv/Scripts/python scripts/ui_check.py` -> FAIL.

- [ ] **Step 2: Implement** the files above. Verdict screen in this task only needs the full-bleed video + canvas and the badge text (Task 5 completes it). Tokens: `--bg --card --ink --mute --real --ghost --what --ok --bad --glow --space-1..4 --t-1..4`; one `<section data-screen="...">` per screen in `index.html`; `<script type="module" src="js/screens.js">`. Demo chips call `getDemo` then `go("verdict", result)`; the Verdict mount sets `ctx.demo = true` and shows the tag.

- [ ] **Step 3: Run** `scripts/ui_check.py` -> `console_errors: []`, `overflow_px <= 0`, `overlay_ink_px > 0`. Run pytest quietly (server serves static files; no test should break).

- [ ] **Step 4: Commit** `git add -A web scripts && git commit -m "Dark shell, design tokens, screen state machine and ghost canvas module"`

---

### Task 3: Capture and Analysing screens

**Files:**
- Create: `web/js/capture.js`; Modify: `web/js/screens.js`, `web/js/ghost.js`, `web/index.html`, `web/style.css`, `scripts/ui_check.py`

**Interfaces:**
- Consumes: `identify(file)`, `go`, `createGhost`.
- Produces: `capture.js` `mount(root, ctx)`: wordmark, Film button (`<input type=file accept="video/*" capture="environment">`), Upload button (same without `capture`), demo chips, hint "Prop the phone against something and film at normal speed."
- Produces: `analysing` screen (in `screens.js` or its own tiny `analysing.js`): plays the uploaded `video` full-bleed with ghost mode `"analysing"`, status line "SAM 3.1 is tracking your clip". On `identify` success -> `go("confirm", {ident, uploadId, video})`; on error shows the message plus a "Film again" button -> `go("capture")`.

- [ ] **Step 1: Extend `ui_check.py`**: with `page.route("**/api/identify", ...)` fulfilling a canned `{id, identification, video: "/demos/bump.mp4", clip}`, set a file on `#film-input` (use `work/render/` or `web/demos/bump.mp4`), assert `body[data-screen]` passes through `analysing` then `confirm`. Add a second route returning HTTP 400 `{"detail": "That file could not be read as a video."}` and assert the message and "Film again" are visible. Run -> FAIL.

- [ ] **Step 2: Implement** the two screens.

- [ ] **Step 3: Run** `ui_check.py` -> pass, no console errors, no overflow on Capture or Analysing.

- [ ] **Step 4: Commit** `git commit -am "Capture and Analysing screens"` (plus new files by pathspec).

---

### Task 4: Confirm screen

**Files:**
- Create: `web/js/confirm.js`; Modify: `web/style.css`, `scripts/ui_check.py`

**Interfaces:**
- Consumes: `ctx.ident = {identification, uploadId, video}`, `analyze(body)`.
- Produces: `mount`: first video frame paused, with the label "Detected: <identification.object>" (no circle: the object's position is not known until SAM runs), guessed size as preset chips: tennis ball 6.7 cm, football 22 cm, basketball 24 cm, Custom (cm number input). The guess from `identification.real_size_m` is pre-selected (added as a chip if it matches none). Confirm button posts `analyze({id, size_m})`; during the call go to `analysing` mode; result -> `go("verdict", result)`; `result.error` -> Analysing error state with "Film again".
- Custom size valid range 1 to 999 cm; otherwise inline message "Enter the object's size in centimetres" and no request.

- [ ] **Step 1: Extend `ui_check.py`**: route `/api/analyze` to the `bump` demo JSON; assert chips render, tapping Confirm twice quickly issues exactly one request (count in the route handler), custom `0` and `-5` show the inline message and send nothing, then a valid value reaches `verdict`. Run -> FAIL.
- [ ] **Step 2: Implement** `confirm.js`; disable the button on first tap.
- [ ] **Step 3: Run** `ui_check.py` -> pass.
- [ ] **Step 4: Commit** `git commit` by pathspec: "Confirm screen: check the size before any verdict".

---

### Task 5: Verdict screen

**Files:**
- Create: `web/js/verdict.js`; Modify: `web/style.css`, `scripts/ui_check.py`

**Interfaces:**
- Consumes: `result` (`twin`, `fits`, `chosen`, `explanation`, `identification`), `createGhost`, `ghostPoints`.
- Produces: bottom card with badge "Twin certified" (green) or "Twin refused" (red) and "off by N cm" (`twin.test_error_cm`, one decimal); ghost replay runs on mount and again on a "Replay" button (`ghost.replay()`); drag-up sheet (pointer events on a handle, or tap to toggle) holding the prediction-test chart (port `drawChart` from old `app.js` to `verdict.js` using `--ghost`/`--real`/`--mute` tokens), the measured numbers table, and the explanation text. Certified: a "What if…" button -> `go("playground")`. Refused: plain-words reason (`twin.reason`), "Film again" tip, numbers withheld with "Show anyway" (reveals the table), no What-if button.

- [ ] **Step 1: Extend `ui_check.py`**: certified demo (`bump`) shows badge text, "off by", sheet opens and the chart canvas has ink; a refused result (take `bump` JSON, set `twin.verdict="refused"`, `twin.reason="the camera moved"`, via `page.route` on `/api/demo/bump`) shows the reason, no `#to-playground`, numbers hidden until "Show anyway". Run -> FAIL.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run** `ui_check.py` -> pass; screenshot `work/ui_verdict.png` and look at it.
- [ ] **Step 4: Commit** "Verdict screen with replay, sheet and refusal path".

---

### Task 6: Playground and voice

**Files:**
- Create: `web/js/playground.js`, `web/js/voice.js`; Modify: `web/style.css`, `scripts/ui_check.py`

**Interfaces:**
- Consumes: `simulate`, `whatif`, `voice`, `ghost.setWhat`.
- Produces: `playground.js` `mount`: planet chips Fitted, Moon 1.62, Mars 3.71, Jupiter 24.8; gravity slider (1 to 26, step 0.1, initialised to `fits[chosen].sim.g`); bounciness slider only when `chosen === "bounce"` (0.1 to 0.98); each change debounced 60 ms re-simulates and calls `ghost.setWhat(pts)` + `ghost.replay()`; text input "Say or type: what if this was on Mars?" posting `/api/whatif`; Back button -> `go("verdict")`.
- Produces: `voice.js` `export function holdToTalk(button, onAudio: (blob) => void, onError: (msg) => void)`: pointer-down starts `MediaRecorder`, pointer-up stops and calls `onAudio`; denied mic or missing `MediaRecorder` calls `onError("Microphone unavailable: ...")`. `playground.js` posts the blob to `/api/voice` with `g` and optional `e` and applies `{transcript, whatif}`; 503 detail shows as the message.

- [ ] **Step 1: Extend `ui_check.py`**: reach Playground from `bump`; tap Moon and assert slider value 1.6 and overlay ink changed (compare ink pixel sum before/after, or the what-if colour pixel count > 0); type "what if this was on Mars" and assert the slider moves to 3.7; stub `navigator.mediaDevices.getUserMedia` to reject and assert the message shows and the page still works. Run -> FAIL.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run** `ui_check.py` -> pass.
- [ ] **Step 4: Commit** "Playground: planet presets, live sliders, voice what-if".

---

### Task 7: Export clip

**Files:**
- Create: `web/js/export.js`; Modify: `web/js/playground.js`, `scripts/ui_check.py`

**Interfaces:**
- Produces: `exportClip(video: HTMLVideoElement, ghostCanvas: HTMLCanvasElement) -> Promise<Blob>`: draw video frame + overlay to an offscreen canvas each animation frame while the clip plays once from 0, record `canvas.captureStream(30)` with `MediaRecorder` (first supported of `video/mp4`, `video/webm;codecs=vp9`, `video/webm`), resolve with the blob at `ended`. Rejects with `Error("This browser cannot record the clip.")` when `MediaRecorder` or `captureStream` is missing.
- Playground "Export clip" button downloads the blob via an `<a download>` named `ghostlab-<object>.<ext>`; shows "Recording…" while running and the rejection message on failure.

- [ ] **Step 1: Extend `ui_check.py`**: in Playground call `exportClip` through `page.evaluate` on the demo and assert the returned blob `size > 0` and its `type` starts with `video/`. Run -> FAIL.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run** `ui_check.py` -> pass. If headless Edge cannot record, report that plainly rather than weakening the assertion.
- [ ] **Step 4: Commit** "Export the ghost replay as a clip in the browser".

---

### Task 8: Full walk, docs, final review

**Files:**
- Modify: `scripts/ui_check.py` (single end-to-end walk of all five screens at 390x844 saving `work/ui_<screen>.png`), `README.md` (run notes: `web/js` modules, screens), `docs/DEMO.md` (shots now follow Capture -> Analysing -> Confirm -> Verdict -> Playground)

- [ ] **Step 1:** Run the full suite quietly and `ui_check.py`; all green, zero console errors, zero overflow, ink on Analysing / Verdict / Playground.
- [ ] **Step 2:** Look at each screenshot; fix anything cut off, overlapping, or below 44 px touch height.
- [ ] **Step 3:** One whole-branch review (`superpowers:requesting-code-review`), fix findings.
- [ ] **Step 4: Commit** "Docs and full UI walk". Report what is verified (headless Edge at 390 px) and what is not (real iPhone Safari camera, mic, export; real `MODEL_API_KEY` run).
