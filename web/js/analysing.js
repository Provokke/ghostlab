// Plays the clip full-bleed while a job runs. ctx.job resolves to {go: "confirm"|"verdict", data}.
// A verdict result first gets its reveal: real path draws in orange, then the cyan ghost draws and runs past it.
import { createGhost, ghostPoints } from "./ghost.js";
import { go } from "./screens.js";
import { friendly, reduced, watchVideo } from "./util.js";

const REVEAL_MS = 4200;
const DEFAULT_STAGES = ["Working on your clip.", "Detecting the object", "Fitting physics", "Testing the prediction blind"];
let ghost = null, cancelled = false, mounts = 0, ticker = 0, cancelBtn = null;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function mount(root, ctx) {
  cancelled = false; const mine = ++mounts;
  const stale = () => cancelled || mine !== mounts; // a newer mount owns the screen now
  const job = ctx.job; ctx.job = null;
  const video = document.getElementById("video"), canvas = document.getElementById("overlay");
  const text = root.querySelector(".status-text"), err = root.querySelector(".err"), status = root.querySelector(".status");
  const scan = root.querySelector(".scan");
  err.hidden = true; status.hidden = false; scan.hidden = false; root.style.opacity = "";
  const stages = ctx.stages?.length ? ctx.stages : DEFAULT_STAGES;
  text.textContent = ctx.status || stages[0];

  // Elapsed time and stepped copy, so a ~1 minute job never looks frozen.
  clearInterval(ticker);
  let elapsed = root.querySelector(".elapsed");
  if (!elapsed) { elapsed = document.createElement("span"); elapsed.className = "elapsed"; elapsed.setAttribute("aria-hidden", "true"); elapsed.style.cssText = "margin-left:8px;opacity:.7;font-variant-numeric:tabular-nums"; text.after(elapsed); }
  const t0 = Date.now(); elapsed.textContent = "";
  ticker = setInterval(() => {
    const s = Math.floor((Date.now() - t0) / 1000);
    elapsed.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    if (s > 0) text.textContent = stages[Math.min(Math.floor(s / 6), stages.length - 1)];
  }, 1000);

  cancelBtn?.remove();
  cancelBtn = document.createElement("button");
  cancelBtn.className = "btn back"; cancelBtn.textContent = "\u2190 Cancel";
  cancelBtn.onclick = () => go("capture");
  root.append(cancelBtn);

  const filmAgain = root.querySelector("#film-again");
  filmAgain.onclick = () => go("capture");
  let retryBtn = root.querySelector("#retry-job");
  if (!retryBtn) {
    retryBtn = document.createElement("button");
    retryBtn.id = "retry-job"; retryBtn.className = "btn primary wide"; retryBtn.textContent = "Retry";
    filmAgain.before(retryBtn);
  }
  const retry = ctx.retry;
  retryBtn.hidden = !retry;
  retryBtn.onclick = () => go("analysing", { job: retry() });

  if (ctx.video) {
    video.loop = true;
    video.src = ctx.video;
    video.play().catch(() => {});
  }
  canvas.width = 2;
  const g = ghost = createGhost(canvas, video);

  const fail = (message) => {
    if (stale()) return;
    clearInterval(ticker);
    status.hidden = true; scan.hidden = true; err.hidden = false;
    root.querySelector(".err-text").textContent = message;
  };
  watchVideo(video, (m) => { if (!stale() && !status.hidden) text.textContent = m; });

  if (!job) return fail("Nothing to analyse. Film a clip.");
  job.then(async (out) => {
    if (stale()) return;
    clearInterval(ticker);
    if (out.go !== "verdict") return go(out.go, out.data);
    const R = out.data;
    elapsed.textContent = "";
    text.textContent = "Drawing the ghost.";
    let pts = null;
    try { pts = await ghostPoints(R); } catch (e) { console.warn("[ghostlab] ghost preview failed", e); } // cosmetic: the verdict is already in hand
    if (stale()) return;
    if (pts) {
      g.setResult(R); g.setGhost(pts); g.mode("analysing");
      scan.hidden = true;
      await sleep(REVEAL_MS);
      if (stale()) return;
    }
    if (pts && !reduced()) { // hand the reveal off to the verdict with a short cross-fade
      root.style.transition = "opacity .3s"; root.style.opacity = "0";
      await sleep(300);
      if (stale()) return;
    }
    go("verdict", R);
  }).catch((e) => fail(friendly(e)));
}

export function unmount() {
  cancelled = true;
  clearInterval(ticker); cancelBtn?.remove(); cancelBtn = null;
  const root = document.querySelector('section[data-screen="analysing"]');
  if (root) { root.style.transition = ""; root.style.opacity = ""; }
  ghost?.destroy(); ghost = null;
  document.getElementById("video").onerror = null;
}
