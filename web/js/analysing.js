// Plays the clip full-bleed while a job runs. ctx.job resolves to {go: "confirm"|"verdict", data}.
// A verdict result first gets its reveal: real path draws in orange, then the cyan ghost draws and runs past it.
import { createGhost, ghostPoints } from "./ghost.js";
import { go } from "./screens.js";

const REVEAL_MS = 4200;
let ghost = null, cancelled = false, mounts = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function mount(root, ctx) {
  cancelled = false; const mine = ++mounts;
  const stale = () => cancelled || mine !== mounts; // a newer mount owns the screen now
  const video = document.getElementById("video"), canvas = document.getElementById("overlay");
  const text = root.querySelector(".status-text"), err = root.querySelector(".err"), status = root.querySelector(".status");
  const scan = root.querySelector(".scan");
  err.hidden = true; status.hidden = false; scan.hidden = false;
  text.textContent = ctx.status || "Working on your clip.";
  root.querySelector("#film-again").onclick = () => go("capture");

  video.loop = true;
  video.src = ctx.video;
  video.play().catch(() => {});
  canvas.width = 2;
  ghost = createGhost(canvas, video);

  const fail = (message) => {
    if (stale()) return;
    status.hidden = true; scan.hidden = true; err.hidden = false;
    root.querySelector(".err-text").textContent = message;
  };

  const job = ctx.job; ctx.job = null;
  if (!job) return fail("Nothing to analyse. Film a clip.");
  job.then(async (out) => {
    if (stale()) return;
    if (out.go !== "verdict") return go(out.go, out.data);
    const R = out.data;
    text.textContent = "Drawing the ghost.";
    ghost.setResult(R);
    ghost.setGhost(await ghostPoints(R));
    ghost.mode("analysing");
    scan.hidden = true;
    await sleep(REVEAL_MS);
    if (!stale()) go("verdict", R);
  }).catch((e) => fail(e.message || "Something went wrong."));
}

export function unmount() {
  cancelled = true;
  ghost?.destroy(); ghost = null;
}
