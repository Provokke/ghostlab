// What-if playground: planets, live gravity / bounciness, spoken or typed what-ifs, export.
import { voice, whatif } from "./api.js";
import { exportClip } from "./export.js";
import { createGhost, ghostPoints, resumeClip, startClip, whatPoints } from "./ghost.js";
import { go } from "./screens.js";
import { friendly, watchVideo } from "./util.js";
import { holdToTalk } from "./voice.js";

const PLANETS = [["Moon", 1.62], ["Mars", 3.71], ["Jupiter", 24.8]];
const fmt = (v, d = 2) => Number(v).toFixed(d);
const G_RANGE = [0.1, 50], clamp = (v, [lo, hi]) => Math.min(hi, Math.max(lo, v));
let ghost = null, timer = null, gone = false, exporter = {}, talk = { cancel() {} };

export async function mount(root, ctx) {
  if (ctx.result?.twin?.verdict !== "certified") return go("verdict"); // a refused fit never gets what-ifs
  gone = false;
  const R = ctx.result, fit = R.fits?.[R.chosen];
  if (!fit?.sim) return go("verdict");
  const video = document.getElementById("video"), canvas = document.getElementById("overlay");
  const $ = (s) => root.querySelector(s);
  const msg = $(".msg"), heard = $(".heard"), gIn = $("#g"), eIn = $("#e"), bounce = R.chosen === "bounce";
  msg.textContent = ""; heard.textContent = ""; $("#say").value = "";
  const say = $("#say");
  say.setAttribute("enterkeyhint", "go");
  let goBtn = root.querySelector("#say-go");
  if (!goBtn) {
    goBtn = document.createElement("button");
    goBtn.id = "say-go"; goBtn.type = "button"; goBtn.className = "btn"; goBtn.textContent = "Go"; goBtn.setAttribute("aria-label", "Apply typed what-if");
    $("#mic").before(goBtn);
  }

  startClip(video, R.video);
  watchVideo(video);
  ghost = createGhost(canvas, video);
  ghost.setResult(R);
  ghost.mode("playground");
  let haveGhost = false;
  const loadGhost = async () => {
    try {
      const pts = await ghostPoints(R);
      if (gone) return;
      ghost.setGhost(pts); haveGhost = !!pts;
    } catch { if (!gone) msg.textContent = "Could not draw the ghost. Moving a slider will retry."; }
  };
  loadGhost();

  // The exact what-if values live in `state`; the sliders only show them (their step would round e.g. Mars 3.71 to 3.7).
  const g0 = fit.sim.g ?? 9.81;
  const state = { g: clamp(g0, G_RANGE), e: bounce ? fit.sim.e : null };
  gIn.min = "0.5"; gIn.max = "30";
  $("#erow").hidden = !bounce;
  gIn.setAttribute("aria-label", "Gravity"); eIn.setAttribute("aria-label", "Bounciness");
  const curG = () => state.g, curE = () => state.e;
  let seq = 0, exporting = false, pending = null;
  const inputs = () => [gIn, eIn, say, goBtn, $("#mic"), ...presets.querySelectorAll(".chip")];
  const lock = (on) => inputs().forEach((el) => { el.disabled = on; });
  const show = () => {
    gIn.value = state.g; $("#gval").textContent = fmt(state.g, 1);
    gIn.setAttribute("aria-valuetext", `${fmt(state.g, 1)} metres per second squared`);
    if (bounce) {
      eIn.value = state.e; $("#eval").textContent = fmt(state.e);
      eIn.setAttribute("aria-valuetext", `${Math.round(state.e * 100)} percent bounce kept`);
    }
  };
  const fill = (el) => el.style.setProperty("--pct", `${((el.value - el.min) / (el.max - el.min)) * 100}%`);
  const update = () => {
    show(); fill(gIn); fill(eIn); markPreset();
    if (pending) { pending = null; exp.textContent = "Export clip"; } // the recorded clip no longer matches the what-if
    clearTimeout(timer);
    if (exporting) return;
    if (!haveGhost) loadGhost();
    timer = setTimeout(async () => {
      const my = ++seq;
      try {
        const pts = await whatPoints(R, curG(), curE());
        if (gone || my !== seq || exporting) return;
        ghost.setWhat(pts); ghost.replay();
      } catch (e) { if (!gone && my === seq) msg.textContent = friendly(e); }
    }, 60);
  };
  gIn.oninput = () => { state.g = clamp(parseFloat(gIn.value), G_RANGE); update(); };
  eIn.oninput = () => { state.e = parseFloat(eIn.value); update(); };

  const presets = $(".presets");
  // Highlight the preset whose gravity matches the slider; "Fitted" lights up again when the slider returns to it.
  function markPreset() {
    const g = curG();
    presets.querySelectorAll(".chip").forEach((c) => {
      const on = Math.abs(parseFloat(c.dataset.g) - g) < 0.05;
      c.classList.toggle("on", on); c.setAttribute("aria-pressed", String(on));
    });
  }
  presets.innerHTML = "";
  for (const [name, g] of [["Fitted", g0], ...PLANETS]) {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = name; b.dataset.planet = name; b.dataset.g = g;
    b.onclick = () => { state.g = g; update(); };
    presets.append(b);
  }

  const apply = (r) => {
    const w = r.whatif ?? {}, notes = [];
    if (r.transcript) notes.push(`Heard: "${r.transcript}"`);
    if (w.g != null) state.g = clamp(Number(w.g), G_RANGE);
    if (w.e != null && bounce) state.e = clamp(Number(w.e), [0, 1]);
    if (w.e != null && !bounce) notes.push("This motion has no bounciness.");
    else if (w.g == null && w.e == null) notes.push("No gravity or bounce change found.");
    heard.textContent = notes.join(" ").trim();
    update();
  };
  const submit = async () => {
    msg.textContent = "";
    if (!say.value.trim()) { msg.textContent = "Type a what-if first, for example: what if this was on Mars?"; return; }
    try { apply(await whatif({ text: say.value, g: curG(), e: curE() })); } catch (e) { msg.textContent = friendly(e); }
  };
  say.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } };
  say.onchange = null;
  goBtn.onclick = submit;
  heard.setAttribute("role", "status");
  talk = holdToTalk($("#mic"), async (blob) => {
    if (gone) return;
    msg.textContent = "";
    const body = new FormData(); body.append("audio", blob); body.append("g", curG());
    if (curE() != null) body.append("e", curE());
    try { const r = await voice(body); if (!gone) apply(r); } catch (e) { if (!gone) msg.textContent = friendly(e); }
  }, (m) => { msg.textContent = m; });
  show(); markPreset();

  const back = $("#back");
  back.onclick = () => go("verdict");
  const exp = $("#export");
  let box = root.querySelector("#export-progress");
  if (!box) {
    box = document.createElement("div");
    box.id = "export-progress"; box.hidden = true; box.style.cssText = "display:flex;align-items:center;gap:8px;margin:8px 0";
    box.innerHTML = '<div style="flex:1;height:6px;border-radius:3px;background:var(--line,#2a3040);overflow:hidden"><div class="bar" style="height:100%;width:0;background:var(--ghost,#5be7ff)"></div></div><span class="pct" aria-hidden="true" style="font-size:12px;min-width:3.5em;text-align:right"></span><button type="button" class="chip cancel">Cancel</button>';
    exp.closest(".row").after(box);
  }
  const bar = box.querySelector(".bar"), pct = box.querySelector(".pct");
  let raf = 0;
  const idle = () => { exporting = false; lock(false); exp.disabled = false; exp.textContent = "Export clip"; box.hidden = true; back.disabled = false; cancelAnimationFrame(raf); };
  const tick = () => {
    const d = video.duration || 1, f = Math.min(1, video.currentTime / d);
    bar.style.width = `${f * 100}%`; pct.textContent = `${Math.max(0, d - video.currentTime).toFixed(0)} s left`;
    raf = requestAnimationFrame(tick);
  };
  box.querySelector(".cancel").onclick = () => exporter.cancel?.();
  const download = (blob, name) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  };
  exp.onclick = async () => {
    if (pending) { // recorded: a fresh tap shares (iOS needs a user gesture) or saves
      const { file, blob, name } = pending; pending = null; idle();
      try { await navigator.share({ files: [file], title: "Ghostlab" }); }
      catch (e) { if (e?.name !== "AbortError") download(blob, name); }
      return;
    }
    exporting = true; clearTimeout(timer); seq++; lock(true);
    exp.disabled = true; exp.textContent = "Recording…"; msg.textContent = ""; back.disabled = true; box.hidden = false; tick();
    try {
      const blob = await exportClip(video, canvas, (exporter = {}));
      const name = `ghostlab-${(R.identification?.object || "clip").replace(/\W+/g, "-")}.${blob.type.includes("mp4") ? "mp4" : "webm"}`;
      const file = new File([blob], name, { type: blob.type.split(";")[0] }); // codec parameters can make canShare refuse
      if (!gone && navigator.canShare?.({ files: [file] })) {
        idle(); pending = { file, blob, name }; exp.textContent = "Share clip"; msg.textContent = "";
        resumeClip(video); // the exported clip ended the video; loop it again behind the share button
        return;
      }
      download(blob, name); idle();
    } catch (e) { if (!gone) { msg.textContent = friendly(e); idle(); } }
    if (!gone) resumeClip(video);
  };
}

export function unmount() {
  gone = true; clearTimeout(timer);
  exporter.cancel?.(); talk.cancel();
  document.getElementById("video").onerror = null;
  ghost?.destroy(); ghost = null;
  document.getElementById("video").pause();
}
