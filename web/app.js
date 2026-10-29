const $ = (id) => document.getElementById(id);
const video = $("video"), canvas = $("overlay"), ctx = canvas.getContext("2d");
let R = null, ghostG = null, whatPts = null, timer = null;
const DT = 1 / 60;
const LABEL = { g: "Gravity", e: "Bounciness", launch_angle: "Launch angle", L: "String length", period: "Period", a: "Acceleration", angle: "Slope angle" };

const fmt = (v, d = 2) => (v == null ? "-" : Number(v).toFixed(d));
const msg = (t) => ($("msg").textContent = t || "");

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

async function init() {
  const names = await api("/api/demos");
  $("demos").innerHTML = "";
  names.forEach((n, i) => {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = n; b.onclick = () => loadDemo(n, b);
    $("demos").append(b);
    if (i === 0) loadDemo(n, b);
  });
}

async function loadDemo(name, btn) {
  document.querySelectorAll("#demos .chip").forEach((c) => c.classList.remove("on"));
  btn.classList.add("on");
  await show(await api(`/api/demo/${name}`));
}

$("file").onchange = async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  $("msg").innerHTML = '<span class="spin"></span>SAM 3.1 is tracking your clip. About a minute.';
  const body = new FormData(); body.append("file", f);
  try { await show(await api("/api/analyze", { method: "POST", body })); msg(""); }
  catch (e) { msg(e.message); }
};

async function show(res) {
  R = res; whatPts = null; ghostG = null;
  if (res.error) { msg(res.error); return; }
  msg("");
  ["stage", "trust", "chart", "whatif", "numbers", "words"].forEach((id) => ($(id).hidden = false));
  $("tag").hidden = !res.demo; $("tag").textContent = "Sample clip (synthetic)";
  video.src = res.video; video.play().catch(() => {});
  canvas.width = res.clip.width; canvas.height = res.clip.height;
  const fit = res.fits[res.chosen], tw = res.twin;
  const ok = tw.verdict === "certified";
  $("trust").innerHTML = `
    <span class="badge ${ok ? "ok" : "bad"}">${ok ? "Twin certified" : "Twin refused"}</span>
    <div class="big">${tw.test_error_cm == null ? "-" : fmt(tw.test_error_cm, 1) + " cm"}</div>
    <div class="sub">${ok
      ? `Fitted on the first ${Math.round(tw.train_frac * 100)}% of the clip, then predicted the last ${tw.test_n} frames it never saw. Off by this much.`
      : `Not trusted: ${tw.reason}. Ghostlab will not show numbers it cannot back up.`}</div>
    <div class="sub">${res.identification.object} &middot; ${res.chosen} &middot; fit quality ${fit.quality}</div>`;
  const table = "<table>" + Object.entries(fit.params)
    .filter(([, p]) => p.error > 0 || p.value !== Math.round(p.value))
    .map(([k, p]) => `<tr><td>${LABEL[k] || k.replace(/_/g, " ")}</td><td>${fmt(p.value, 3)} &plusmn; ${fmt(p.error, 3)} ${p.unit}</td></tr>`).join("") + "</table>";
  $("numbers").innerHTML = ok ? "<h2>Measured</h2>" + table
    : `<h2>Numbers withheld</h2><p class="sub">This fit did not predict the part of the clip it never saw, so its numbers are not trustworthy.</p><button class="chip" id="showany">Show anyway</button><div id="untrusted" hidden>${table}</div>`;
  if (!ok) $("showany").onclick = () => { $("untrusted").hidden = false; $("showany").hidden = true; };
  $("whatif").hidden = !ok; $("words").hidden = !ok;
  const ex = res.explanation;
  $("words").innerHTML = ex ? `<h2>What it means</h2><p>${ex.explanation}</p><p class="sub">Ask: ${ex.class_question}</p>` : "";
  const g = fit.sim.g ?? 9.81;
  $("g").value = g; $("gval").textContent = fmt(g, 1);
  $("erow").hidden = res.chosen !== "bounce";
  if (res.chosen === "bounce") { $("e").value = fit.sim.e; $("eval").textContent = fmt(fit.sim.e); }
  presets(g);
  await simulate(null, null, "ghost");
}

function presets(g0) {
  $("presets").innerHTML = "";
  [["Fitted", g0], ["Moon", 1.62], ["Mars", 3.71], ["Jupiter", 24.8]].forEach(([n, g]) => {
    const b = document.createElement("button"); b.className = "chip"; b.textContent = n;
    b.onclick = () => { $("g").value = g; update(); };
    $("presets").append(b);
  });
}

function times() {
  const end = Math.max(...R.track.t), out = [];
  for (let t = 0; t <= end + 1e-9; t += DT) out.push(t);
  return out;
}

async function simulate(g, e, which) {
  const tr = R.track, fit = R.fits[R.chosen], t = times();
  const blind = which === "ghost" && R.twin.sim;
  const body = JSON.stringify({ motion: R.chosen, sim: blind ? R.twin.sim : fit.sim, m_per_px: tr.m_per_px, origin_px: tr.origin_px,
    t: blind ? t.map((v) => v - R.twin.t_origin) : t, g: blind ? null : g, e: blind ? null : e });
  const out = await api("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" },
    body });
  const pts = { t, px: out.px, py: out.py };
  if (which === "ghost") { ghostG = pts; drawChart(); } else whatPts = pts;
}

function drawChart() {
  if (!R || !ghostG) return;
  const tr = R.track, cv = $("plot"), c = cv.getContext("2d"), dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr; c.setTransform(dpr, 0, 0, dpr, 0, 0);
  const useY = Math.max(...tr.y) - Math.min(...tr.y) >= Math.max(...tr.x) - Math.min(...tr.x);
  const real = useY ? tr.y : tr.x;
  const gh = ghostG.t.map((_, i) => (ghostG.px[i] == null ? null : useY ? (tr.origin_px[1] - ghostG.py[i]) * tr.m_per_px : (ghostG.px[i] - tr.origin_px[0]) * tr.m_per_px));
  const vals = real.concat(gh.filter((v) => v != null)), lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const T = Math.max(...tr.t), pad = 28, X = (t) => pad + (t / T) * (W - pad - 8), Y = (v) => H - 22 - ((v - lo) / span) * (H - 36);
  const cut = tr.t[0] + R.twin.train_frac * (T - tr.t[0]), css = getComputedStyle(document.body);
  const mute = css.getPropertyValue("--mute"), cy = css.getPropertyValue("--ghost"), co = css.getPropertyValue("--real");
  c.fillStyle = "rgba(91,231,255,.07)"; c.fillRect(X(0), 4, X(cut) - X(0), H - 26);
  c.fillStyle = "rgba(255,159,67,.09)"; c.fillRect(X(cut), 4, X(T) - X(cut), H - 26);
  c.strokeStyle = mute; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(X(cut), 4); c.lineTo(X(cut), H - 22); c.stroke(); c.setLineDash([]);
  c.strokeStyle = cy; c.lineWidth = 2; c.beginPath(); let pen = false;
  gh.forEach((v, i) => { if (v == null) { pen = false; return; } const x = X(ghostG.t[i]), y = Y(v); pen ? c.lineTo(x, y) : c.moveTo(x, y); pen = true; }); c.stroke();
  c.fillStyle = co; real.forEach((v, i) => { c.beginPath(); c.arc(X(tr.t[i]), Y(v), 2.6, 0, 7); c.fill(); });
  c.fillStyle = mute; c.font = "11px system-ui"; c.fillText("fit window", X(0) + 4, H - 6 - 12); c.fillText("predicted blind", X(cut) + 6, H - 6 - 12);
  c.fillText(useY ? "height (m)" : "position (m)", 2, H - 6); c.fillText(T.toFixed(1) + " s", W - 34, H - 6);
}
window.addEventListener("resize", drawChart);

function update() {
  const g = parseFloat($("g").value), e = R.chosen === "bounce" ? parseFloat($("e").value) : null;
  $("gval").textContent = fmt(g, 1); if (e != null) $("eval").textContent = fmt(e);
  clearTimeout(timer);
  timer = setTimeout(() => simulate(g, e, "what"), 60);
}
function applyWhatIf(r) {
  $("heard").textContent = r.transcript ? `Heard: "${r.transcript}"` : "";
  if (r.whatif.g != null) $("g").value = r.whatif.g;
  if (r.whatif.e != null) $("e").value = r.whatif.e;
  if (!Object.keys(r.whatif).length) $("heard").textContent += " (no gravity or bounce change found)";
  update();
}
const curE = () => (R.chosen === "bounce" ? parseFloat($("e").value) : null);
$("say").onchange = async () => {
  const r = await api("/api/whatif", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: $("say").value, g: parseFloat($("g").value), e: curE() }) });
  applyWhatIf(r);
};
let rec = null, chunks = [];
$("mic").onclick = async () => {
  if (rec) { rec.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    rec = new MediaRecorder(stream); chunks = [];
    rec.ondataavailable = (ev) => chunks.push(ev.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop()); rec = null; $("mic").textContent = "Speak";
      const body = new FormData(); body.append("audio", new Blob(chunks)); body.append("g", $("g").value);
      if (curE() != null) body.append("e", curE());
      try { applyWhatIf(await api("/api/voice", { method: "POST", body })); } catch (err) { msg(err.message); }
    };
    rec.start(); $("mic").textContent = "Stop";
  } catch (err) { msg("Microphone unavailable: " + err.message); }
};
$("g").oninput = update; $("e").oninput = update;

function at(pts, t) {
  if (!pts) return null;
  const i = Math.round(t / DT);
  if (i < 0 || i >= pts.t.length || pts.px[i] == null) return null;
  return [pts.px[i], pts.py[i]];
}

function dot(p, r, color, alpha) {
  if (!p) return;
  ctx.globalAlpha = alpha; ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
}

function trail(pts, upto, color, alpha) {
  if (!pts) return;
  const n = Math.min(Math.round(upto / DT), pts.t.length - 1);
  for (let i = 0; i <= n; i += 2) if (pts.px[i] != null) dot([pts.px[i], pts.py[i]], 3, color, alpha);
}

function frame() {
  requestAnimationFrame(frame);
  if (!R || !R.track || canvas.width < 2) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const tr = R.track, t = video.currentTime - tr.t0;
  const r = Math.max(10, 0.067 / tr.m_per_px / 2);
  const rx = tr.x.map((x) => tr.origin_px[0] + x / tr.m_per_px), ry = tr.y.map((y) => tr.origin_px[1] - y / tr.m_per_px);
  const ri = tr.t.findIndex((v) => v >= t);
  for (let i = 0; i <= (ri < 0 ? tr.t.length - 1 : ri); i++) dot([rx[i], ry[i]], 3.5, "#ff9f43", .9);
  trail(ghostG, t, "#5be7ff", .5);
  dot(at(ghostG, t), r, "#5be7ff", .55);
  if (whatPts) { trail(whatPts, t, "#c58bff", .5); dot(at(whatPts, t), r, "#c58bff", .6); }
}
frame();
init().catch((e) => msg(e.message));
