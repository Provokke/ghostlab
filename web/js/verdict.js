import { createGhost, ghostPoints } from "./ghost.js";
import { go } from "./screens.js";

const LABEL = { g: "Gravity", e: "Bounciness", launch_angle: "Launch angle", L: "String length", period: "Period", a: "Acceleration", angle: "Slope angle" };
const fmt = (v, d = 2) => (v == null ? "-" : Number(v).toFixed(d));
const $ = (root, sel) => root.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let ghost = null, ghostPts = null, R = null, onResize = null, gone = false, mounts = 0;

function table(fit) {
  return "<table>" + Object.entries(fit.params)
    .filter(([, p]) => p.error > 0 || p.value !== Math.round(p.value))
    .map(([k, p]) => `<tr><td>${LABEL[k] || k.replace(/_/g, " ")}</td><td>${fmt(p.value, 3)} &plusmn; ${fmt(p.error, 3)} ${esc(p.unit)}</td></tr>`).join("") + "</table>";
}

function drawChart() {
  const cv = document.getElementById("plot");
  if (!R || !ghostPts || !cv.clientWidth) return;
  const tr = R.track, c = cv.getContext("2d"), dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr; c.setTransform(dpr, 0, 0, dpr, 0, 0);
  const useY = Math.max(...tr.y) - Math.min(...tr.y) >= Math.max(...tr.x) - Math.min(...tr.x);
  const real = useY ? tr.y : tr.x;
  const gh = ghostPts.t.map((_, i) => (ghostPts.px[i] == null ? null : useY ? (tr.origin_px[1] - ghostPts.py[i]) * tr.m_per_px : (ghostPts.px[i] - tr.origin_px[0]) * tr.m_per_px));
  const vals = real.concat(gh.filter((v) => v != null)), lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const T = Math.max(...tr.t), pad = 28, X = (t) => pad + (t / T) * (W - pad - 8), Y = (v) => H - 22 - ((v - lo) / span) * (H - 36);
  const cut = tr.t[0] + R.twin.train_frac * (T - tr.t[0]), css = getComputedStyle(document.documentElement);
  const mute = css.getPropertyValue("--mute"), cy = css.getPropertyValue("--ghost"), co = css.getPropertyValue("--real");
  c.fillStyle = "rgba(91,231,255,.07)"; c.fillRect(X(0), 4, X(cut) - X(0), H - 26);
  c.fillStyle = "rgba(255,159,67,.09)"; c.fillRect(X(cut), 4, X(T) - X(cut), H - 26);
  c.strokeStyle = mute; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(X(cut), 4); c.lineTo(X(cut), H - 22); c.stroke(); c.setLineDash([]);
  c.strokeStyle = cy; c.lineWidth = 2; c.beginPath(); let pen = false;
  gh.forEach((v, i) => { if (v == null) { pen = false; return; } const x = X(ghostPts.t[i]), y = Y(v); pen ? c.lineTo(x, y) : c.moveTo(x, y); pen = true; }); c.stroke();
  c.fillStyle = co; real.forEach((v, i) => { c.beginPath(); c.arc(X(tr.t[i]), Y(v), 2.6, 0, 7); c.fill(); });
  c.fillStyle = mute; c.font = "11px system-ui"; c.fillText("fit window", X(0) + 4, H - 18); c.fillText("predicted blind", X(cut) + 6, H - 18);
  c.fillText(useY ? "height (m)" : "position (m)", 2, H - 6); c.fillText(T.toFixed(1) + " s", W - 34, H - 6);
}

export async function mount(root, ctx) {
  gone = false; const mine = ++mounts;
  R = ctx.result;
  const video = document.getElementById("video"), canvas = document.getElementById("overlay");
  const tw = R.twin, ok = tw.verdict === "certified", fit = R.fits[R.chosen];
  const badge = $(root, ".badge");
  badge.className = `badge ${ok ? "ok" : "bad"}`;
  badge.textContent = ok ? "CERTIFIED" : "REFUSED";
  $(root, ".off").textContent = tw.test_error_cm == null ? "" : `off by ${tw.test_error_cm.toFixed(1)} cm`;
  $(root, ".tag").hidden = !R.demo;

  const reason = $(root, ".reason");
  reason.hidden = ok;
  reason.textContent = ok ? "" : `Not trusted: ${tw.reason}. Ghostlab will not show numbers it cannot back up. Prop the phone against something, keep the whole motion in frame, and film again.`;
  $(root, "#to-playground").hidden = !ok;
  $(root, "#film-again-v").hidden = ok;
  $(root, "#to-playground").onclick = () => go("playground");
  $(root, "#film-again-v").onclick = () => go("capture");

  const numbers = $(root, "#numbers"), words = $(root, "#words");
  if (ok) {
    numbers.innerHTML = "<h2>Measured</h2>" + table(fit);
    const ex = R.explanation;
    words.innerHTML = ex ? `<h2>What it means</h2><p>${esc(ex.explanation)}</p><p class="sub">Ask: ${esc(ex.class_question)}</p>` : "";
  } else {
    numbers.innerHTML = `<h2>Numbers withheld</h2><p class="sub">This fit did not predict the part of the clip it never saw.</p><button class="chip" id="showany">Show anyway</button><div id="untrusted" hidden>${table(fit)}</div>`;
    words.innerHTML = "";
    $(root, "#showany").onclick = () => { $(root, "#untrusted").hidden = false; $(root, "#showany").hidden = true; };
  }

  // Sheet: tap the handle (or drag it up) to open the chart and numbers.
  const handle = $(root, ".handle"), body = $(root, ".sheet-body");
  const setOpen = (open) => {
    body.hidden = !open; handle.setAttribute("aria-expanded", String(open));
    if (open) requestAnimationFrame(drawChart);
  };
  setOpen(false);
  let startY = null;
  handle.onpointerdown = (e) => { startY = e.clientY; handle.setPointerCapture(e.pointerId); };
  handle.onpointerup = (e) => {
    const dy = startY == null ? 0 : e.clientY - startY; startY = null;
    setOpen(dy < -25 ? true : dy > 25 ? false : body.hidden);
  };
  handle.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(body.hidden); } };
  onResize = drawChart; window.addEventListener("resize", onResize);

  video.loop = true; video.src = R.video; video.play().catch(() => {});
  ghost = createGhost(canvas, video);
  ghost.setResult(R);
  ghost.mode("verdict");
  $(root, "#replay").onclick = () => ghost?.replay();
  const pts = await ghostPoints(R);
  if (gone || mine !== mounts) return;
  ghostPts = pts;
  ghost.setGhost(pts);
  if (!body.hidden) drawChart();
}

export function unmount() {
  gone = true;
  ghost?.destroy(); ghost = null; ghostPts = null;
  window.removeEventListener("resize", onResize);
  document.getElementById("video").pause();
}
