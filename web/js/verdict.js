import { createGhost, ghostPoints } from "./ghost.js";

let ghost = null;
const $ = (root, sel) => root.querySelector(sel);

export async function mount(root, ctx) {
  const R = ctx.result, video = document.getElementById("video"), canvas = document.getElementById("overlay");
  const tw = R.twin, ok = tw.verdict === "certified";
  const badge = $(root, ".badge");
  badge.className = `badge ${ok ? "ok" : "bad"}`;
  badge.textContent = ok ? "CERTIFIED" : "REFUSED";
  $(root, ".off").textContent = tw.test_error_cm == null ? "" : `off by ${tw.test_error_cm.toFixed(1)} cm`;
  $(root, ".tag").hidden = !R.demo;
  video.src = R.video;
  video.play().catch(() => {});
  ghost = createGhost(canvas, video);
  ghost.setResult(R);
  ghost.mode("verdict");
  ghost.setGhost(await ghostPoints(R));
}

export function unmount() {
  ghost?.destroy(); ghost = null;
  document.getElementById("video").pause();
}
