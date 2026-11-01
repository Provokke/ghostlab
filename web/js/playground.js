// What-if playground: planets, live gravity / bounciness, spoken or typed what-ifs, export.
import { voice, whatif } from "./api.js";
import { exportClip } from "./export.js";
import { createGhost, ghostPoints, whatPoints } from "./ghost.js";
import { go } from "./screens.js";
import { holdToTalk } from "./voice.js";

const PLANETS = [["Moon", 1.62], ["Mars", 3.71], ["Jupiter", 24.8]];
const fmt = (v, d = 2) => Number(v).toFixed(d);
let ghost = null, timer = null, gone = false, exporter = {}, stopTalk = () => {};

export async function mount(root, ctx) {
  if (ctx.result?.twin?.verdict !== "certified") return go("verdict"); // a refused fit never gets what-ifs
  gone = false;
  const R = ctx.result, fit = R.fits[R.chosen];
  const video = document.getElementById("video"), canvas = document.getElementById("overlay");
  const $ = (s) => root.querySelector(s);
  const msg = $(".msg"), heard = $(".heard"), gIn = $("#g"), eIn = $("#e"), bounce = R.chosen === "bounce";
  msg.textContent = ""; heard.textContent = ""; $("#say").value = "";

  video.loop = true; video.src = R.video; video.play().catch(() => {});
  ghost = createGhost(canvas, video);
  ghost.setResult(R);
  ghost.mode("playground");
  ghostPoints(R).then((pts) => !gone && ghost.setGhost(pts));

  const g0 = fit.sim.g ?? 9.81;
  gIn.value = g0; $("#gval").textContent = fmt(g0, 1);
  $("#erow").hidden = !bounce;
  if (bounce) { eIn.value = fit.sim.e; $("#eval").textContent = fmt(fit.sim.e); }

  const curG = () => parseFloat(gIn.value), curE = () => (bounce ? parseFloat(eIn.value) : null);
  const update = () => {
    $("#gval").textContent = fmt(curG(), 1);
    if (bounce) $("#eval").textContent = fmt(curE());
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        const pts = await whatPoints(R, curG(), curE());
        if (gone) return;
        ghost.setWhat(pts); ghost.replay();
      } catch (e) { msg.textContent = e.message; }
    }, 60);
  };
  gIn.oninput = update; eIn.oninput = update;

  const presets = $(".presets");
  presets.innerHTML = "";
  for (const [name, g] of [["Fitted", g0], ...PLANETS]) {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = name; b.dataset.planet = name;
    b.onclick = () => { gIn.value = g; presets.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c === b)); update(); };
    presets.append(b);
  }

  const apply = (r) => {
    heard.textContent = r.transcript ? `Heard: "${r.transcript}"` : "";
    if (!Object.keys(r.whatif).length) heard.textContent += " (no gravity or bounce change found)";
    if (r.whatif.g != null) gIn.value = r.whatif.g;
    if (r.whatif.e != null && bounce) eIn.value = r.whatif.e;
    presets.querySelectorAll(".chip").forEach((c) => c.classList.remove("on"));
    update();
  };
  $("#say").onchange = async () => {
    msg.textContent = "";
    try { apply(await whatif({ text: $("#say").value, g: curG(), e: curE() })); } catch (e) { msg.textContent = e.message; }
  };
  stopTalk = holdToTalk($("#mic"), async (blob) => {
    msg.textContent = "";
    const body = new FormData(); body.append("audio", blob); body.append("g", curG());
    if (curE() != null) body.append("e", curE());
    try { apply(await voice(body)); } catch (e) { msg.textContent = e.message; }
  }, (m) => { msg.textContent = m; });

  $("#back").onclick = () => go("verdict");
  const exp = $("#export");
  exp.onclick = async () => {
    exp.disabled = true; exp.textContent = "Recording…"; msg.textContent = "";
    try {
      const blob = await exportClip(video, canvas, (exporter = {}));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `ghostlab-${R.identification.object.replace(/\W+/g, "-")}.${blob.type.includes("mp4") ? "mp4" : "webm"}`;
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    } catch (e) { if (!gone) msg.textContent = e.message; }
    exp.disabled = false; exp.textContent = "Export clip";
    if (!gone) video.play().catch(() => {});
  };
}

export function unmount() {
  gone = true; clearTimeout(timer);
  exporter.cancel?.(); stopTalk();
  ghost?.destroy(); ghost = null;
  document.getElementById("video").pause();
}
