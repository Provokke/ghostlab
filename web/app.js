const $ = (id) => document.getElementById(id);
const video = $("video"), canvas = $("overlay"), ctx = canvas.getContext("2d");
let R = null, ghostG = null, whatPts = null, timer = null;
const DT = 1 / 60;

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
  msg("Analysing your clip: SAM 3.1 is tracking it. About a minute.");
  const body = new FormData(); body.append("file", f);
  try { await show(await api("/api/analyze", { method: "POST", body })); msg(""); }
  catch (e) { msg(e.message); }
};

async function show(res) {
  R = res; whatPts = null; ghostG = null;
  if (res.error) { msg(res.error); return; }
  msg("");
  ["stage", "trust", "whatif", "numbers", "words"].forEach((id) => ($(id).hidden = false));
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
  $("numbers").innerHTML = "<h2>Measured</h2><table>" + Object.entries(fit.params)
    .map(([k, p]) => `<tr><td>${k.replace(/_/g, " ")}</td><td>${fmt(p.value, 3)} &plusmn; ${fmt(p.error, 3)} ${p.unit}</td></tr>`).join("") + "</table>";
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
  const out = await api("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ motion: R.chosen, sim: fit.sim, t, m_per_px: tr.m_per_px, origin_px: tr.origin_px, g, e }) });
  const pts = { t, px: out.px, py: out.py };
  if (which === "ghost") ghostG = pts; else whatPts = pts;
}

function update() {
  const g = parseFloat($("g").value), e = R.chosen === "bounce" ? parseFloat($("e").value) : null;
  $("gval").textContent = fmt(g, 1); if (e != null) $("eval").textContent = fmt(e);
  clearTimeout(timer);
  timer = setTimeout(() => simulate(g, e, "what"), 60);
}
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
