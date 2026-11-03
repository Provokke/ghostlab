import { createGhost, ghostPoints, startClip } from "./ghost.js";
import { go } from "./screens.js";
import { watchVideo } from "./util.js";

const LABEL = { g: "Gravity", e: "Bounciness", launch_angle: "Launch angle", L: "String length", period: "Period", a: "Acceleration", angle: "Slope angle" };
const fmt = (v, d = 2) => (v == null ? "-" : Number(v).toFixed(d));
const $ = (root, sel) => root.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const max = (a) => a.reduce((m, v) => (v > m ? v : m), -Infinity);
const min = (a) => a.reduce((m, v) => (v < m ? v : m), Infinity);

let ghost = null, ghostPts = null, tone = "ghost", R = null, onResize = null, gone = false, mounts = 0;

const heightAxis = (tr) => max(tr.y) - min(tr.y) >= max(tr.x) - min(tr.x);
const dec = (span) => (span < 0.3 ? 3 : span < 3 ? 2 : 1); // tick decimals that stay distinct for the span

function table(fit) {
  if (!fit?.params) return "";
  return "<table>" + Object.entries(fit.params)
    .filter(([, p]) => p && (p.error > 0 || p.value !== Math.round(p.value)))
    .map(([k, p]) => `<tr><td>${esc(LABEL[k] || k.replace(/_/g, " "))}</td><td>${fmt(p.value, 3)}${p.error == null ? "" : ` &plusmn; ${fmt(p.error, 3)}`} ${esc(p.unit ?? "")}</td></tr>`).join("") + "</table>";
}

// Plain-words versions of the twin's refusal reasons.
function whyRefused(reason) {
  const r = String(reason || "");
  let m;
  if ((m = r.match(/unseen (\d+)% off by ([\d.]+) cm/))) return `its blind prediction for the last ${m[1]}% of the clip was typically off by ${m[2]} cm`;
  if (/camera moved/i.test(r)) return "the camera moved, so pixel positions are not real positions";
  if (/not about 9\.8/i.test(r)) return "the physics came out wrong, so the object size or playback speed is probably off";
  if (/not enough frames/i.test(r)) return "there was not enough clip left after the fit to test a prediction";
  if (/no prediction/i.test(r)) return "the model could not predict the part of the clip it never saw";
  if (/fit failed/i.test(r)) return "no physics model fit the whole clip";
  return "the fit could not be backed up by a blind test";
}

function drawChart() {
  const cv = document.getElementById("plot");
  if (!R || !cv.clientWidth) return;
  const tr = R.track, c = cv.getContext("2d"), dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr; c.setTransform(dpr, 0, 0, dpr, 0, 0);
  const useY = heightAxis(tr);
  const real = useY ? tr.y : tr.x;
  const gh = (ghostPts?.t ?? []).map((_, i) => (ghostPts.px[i] == null ? null : useY ? (tr.origin_px[1] - ghostPts.py[i]) * tr.m_per_px : (ghostPts.px[i] - tr.origin_px[0]) * tr.m_per_px));
  const vals = real.concat(gh.filter((v) => v != null)), lo = min(vals), hi = max(vals), span = hi - lo || 1;
  const T = max(tr.t) || 1, pad = [44, 44, 50, 58][dec(span)], top = 26, base = H - 34;
  const X = (t) => pad + (t / T) * (W - pad - 8), Y = (v) => base - ((v - lo) / span) * (base - top);
  const cut = tr.t[0] + R.twin.train_frac * (T - tr.t[0]);
  const css = getComputedStyle(document.documentElement), font = getComputedStyle(document.body).fontFamily || "system-ui";
  const tok = (n, d) => css.getPropertyValue(n).trim() || d;
  const mute = tok("--mute", "#8a93a6"), cy = tok(tone === "bad" ? "--bad" : "--ghost", tone === "bad" ? "#ff5d6c" : "#5be7ff"), co = tok("--real", "#ff9f43"), line = tok("--line", "#2a3040");
  c.globalAlpha = 0.08; c.fillStyle = cy; c.fillRect(X(0), top - 4, X(cut) - X(0), base - top + 8);
  c.fillStyle = co; c.fillRect(X(cut), top - 4, X(T) - X(cut), base - top + 8); c.globalAlpha = 1;
  // ticks and gridlines
  c.font = `12px ${font}`; c.fillStyle = mute; c.strokeStyle = line; c.lineWidth = 1; c.textBaseline = "middle"; c.textAlign = "right";
  for (let i = 0; i <= 3; i++) {
    const v = lo + (span * i) / 3, y = Y(v);
    c.beginPath(); c.moveTo(pad, y); c.lineTo(W - 8, y); c.stroke();
    c.fillText(v.toFixed(dec(span)), pad - 5, y);
  }
  c.textBaseline = "alphabetic"; c.textAlign = "center";
  for (let i = 0; i <= 3; i++) { const t = (T * i) / 3; c.fillText(t.toFixed(1), X(t), base + 14); }
  c.strokeStyle = mute; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(X(cut), top - 4); c.lineTo(X(cut), base + 4); c.stroke(); c.setLineDash([]);
  c.strokeStyle = cy; c.lineWidth = 2; c.beginPath(); let pen = false;
  gh.forEach((v, i) => { if (v == null) { pen = false; return; } const x = X(ghostPts.t[i]), y = Y(v); pen ? c.lineTo(x, y) : c.moveTo(x, y); pen = true; }); c.stroke();
  c.fillStyle = co; real.forEach((v, i) => { c.beginPath(); c.arc(X(tr.t[i]), Y(v), 2.8, 0, 7); c.fill(); });
  // legend above the plot
  c.textAlign = "left"; c.textBaseline = "middle"; c.fillStyle = co; c.beginPath(); c.arc(pad + 5, 10, 4, 0, 7); c.fill();
  c.fillStyle = mute; c.fillText("measured", pad + 14, 10);
  const lx = pad + 14 + c.measureText("measured").width + 18;
  if (gh.length) {
    c.strokeStyle = cy; c.lineWidth = 2.5; c.beginPath(); c.moveTo(lx, 10); c.lineTo(lx + 16, 10); c.stroke();
    c.fillStyle = mute; c.fillText("ghost (predicted)", lx + 22, 10);
  }
  c.textBaseline = "alphabetic";
  c.fillText("fit window", X(0) + 2, H - 4); c.textAlign = "right"; c.fillText(`predicted blind · ${T.toFixed(1)} s`, W - 2, H - 4); c.textAlign = "center";
  c.save(); c.translate(8, (top + base) / 2); c.rotate(-Math.PI / 2); c.fillText(useY ? "height (m)" : "position (m)", 0, 0); c.restore(); c.textAlign = "left";
}

export async function mount(root, ctx) {
  gone = false; const mine = ++mounts;
  R = ctx.result;
  const video = document.getElementById("video"), canvas = document.getElementById("overlay");
  const tw = R.twin, ok = tw.verdict === "certified", fit = R.fits?.[R.chosen], hasFit = !!fit?.params;
  tone = ok ? "ghost" : "bad";
  const badge = $(root, ".badge");
  badge.className = `badge ${ok ? "ok" : "bad"}`;
  badge.textContent = ok ? "CERTIFIED" : "REFUSED";
  badge.setAttribute("role", "img");
  badge.setAttribute("aria-label", ok ? "Prediction passed" : "Prediction failed. Ghostlab refused to guess.");
  $(root, ".row").setAttribute("aria-live", "polite");
  $(root, ".off").textContent = tw.test_error_cm == null ? "" : `typically off by ${tw.test_error_cm.toFixed(1)} cm`;
  $(root, ".tag").hidden = !R.demo;

  const reason = $(root, ".reason");
  reason.hidden = ok;
  reason.textContent = "";
  if (!ok) {
    const lead = document.createElement("strong");
    lead.textContent = "Ghostlab refused to guess. ";
    reason.append(lead, `Why: ${whyRefused(tw.reason)}. It will not show numbers it cannot back up, and that refusal is the point. Prop the phone against something, keep the whole motion in frame, and film again.`);
  }
  $(root, "#to-playground").hidden = !ok;
  $(root, "#film-again-v").hidden = ok;
  $(root, "#film-again-v").textContent = "Film again";
  $(root, "#to-playground").onclick = () => go("playground");
  $(root, "#film-again-v").onclick = () => go("capture");

  const numbers = $(root, "#numbers"), words = $(root, "#words");
  if (ok) {
    numbers.innerHTML = "<h2>Measured</h2>" + table(fit);
    const ex = R.explanation;
    words.innerHTML = ex ? `<h2>What it means</h2><p>${esc(ex.explanation)}</p><p class="sub">Ask: ${esc(ex.class_question)}</p>` : "";
  } else {
    numbers.innerHTML = `<h2>Numbers withheld</h2><p class="sub">${hasFit ? "This fit did not predict the part of the clip it never saw." : "No physics model fit the whole clip."}</p>`
      + (hasFit ? `<button class="chip" id="showany">Show anyway</button><div id="untrusted" hidden>${table(fit)}</div>` : "");
    words.innerHTML = "";
    if (hasFit) $(root, "#showany").onclick = () => { $(root, "#untrusted").hidden = false; $(root, "#showany").hidden = true; };
  }

  // Sheet: tap the handle (or drag it) to open the chart and numbers.
  const handle = $(root, ".handle"), body = $(root, ".sheet-body"), dock = $(root, ".dock");
  body.id = "sheet-body"; handle.setAttribute("aria-controls", "sheet-body");
  handle.style.minHeight = "44px"; handle.style.display = "flex"; handle.style.alignItems = "center"; handle.style.justifyContent = "center"; handle.style.touchAction = "none";
  const setOpen = (open) => {
    body.hidden = !open; handle.setAttribute("aria-expanded", String(open));
    handle.setAttribute("aria-label", open ? "Hide the prediction test" : "Show the prediction test");
    if (open) requestAnimationFrame(drawChart);
  };
  setOpen(false);
  let startY = null;
  const settle = () => { dock.style.transition = "transform .2s ease-out"; dock.style.transform = ""; };
  handle.onpointerdown = (e) => { startY = e.clientY; dock.style.transition = "none"; try { handle.setPointerCapture(e.pointerId); } catch {} };
  handle.onpointermove = (e) => { if (startY != null) dock.style.transform = `translateY(${Math.max(-24, Math.min(60, (e.clientY - startY) * 0.5))}px)`; };
  handle.onpointercancel = () => { startY = null; settle(); };
  handle.onpointerup = (e) => {
    const dy = startY == null ? 0 : e.clientY - startY; startY = null; settle();
    setOpen(dy < -25 ? true : dy > 25 ? false : body.hidden);
  };
  handle.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(body.hidden); } };
  onResize = drawChart; window.addEventListener("resize", onResize);

  startClip(video, R.video);
  watchVideo(video);
  ghost = createGhost(canvas, video);
  ghost.setResult(R);
  ghost.mode("verdict");
  ghost.setTone(tone);
  $(root, "#replay").onclick = () => ghost?.replay();
  let pts = null;
  try { pts = await ghostPoints(R); } catch { /* keep the verdict on screen; the ghost line is just missing */ }
  if (gone || mine !== mounts) return;
  ghostPts = pts;
  ghost.setGhost(pts);
  const plot = document.getElementById("plot");
  plot.setAttribute("aria-label", `${heightAxis(R.track) ? "Height" : "Position"} over time: measured points${pts ? " and the ghost prediction" : ""}. The blind prediction was ${ok ? "certified" : "refused"}${tw.test_error_cm == null ? "" : `, typically off by ${tw.test_error_cm.toFixed(1)} centimetres`}.`);
  if (!body.hidden) drawChart();
}

export function unmount() {
  gone = true;
  ghost?.destroy(); ghost = null; ghostPts = null;
  window.removeEventListener("resize", onResize);
  const v = document.getElementById("video");
  v.pause(); v.onerror = null;
}
