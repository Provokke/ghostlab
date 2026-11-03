// Confirm the object's size before any verdict: the guess from Muse Spark is pre-selected.
import { analyze } from "./api.js";
import { go } from "./screens.js";
import { watchVideo } from "./util.js";

const STAGES = ["SAM 3.1 is tracking your clip. About a minute.", "Finding the ball", "Tracking its path", "Fitting physics", "Testing the prediction blind"];
let backBtn = null, onLoaded = null, parkTimer = 0, parkFrame = 0, mounts = 0;

const PRESETS = [["Tennis ball", 0.067], ["Football", 0.22], ["Basketball", 0.24]];
const CUSTOM = "custom";
const cm = (m) => `${+(m * 100).toFixed(1)} cm`;

export function unmount() {
  const video = document.getElementById("video");
  mounts++; // invalidates any pending park()
  if (onLoaded) video.removeEventListener("loadeddata", onLoaded);
  onLoaded = null;
  clearTimeout(parkTimer);
  if (parkFrame && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(parkFrame);
  parkFrame = 0;
  backBtn?.remove(); backBtn = null; video.onerror = null;
}

export function mount(root, ctx) {
  const video = document.getElementById("video");
  video.src = ctx.video; video.loop = false;
  // Show frame 0 reliably (iOS Safari can leave a paused, unseeked video black): play a beat, then park on the first frame.
  const mine = ++mounts;
  const park = () => { if (mine !== mounts) return; parkFrame = 0; video.pause(); try { video.currentTime = 0.001; } catch {} };
  if (onLoaded) video.removeEventListener("loadeddata", onLoaded);
  onLoaded = () => {
    onLoaded = null;
    if (mine !== mounts) return;
    video.play().then(() => {
      if (mine !== mounts) return;
      if (video.requestVideoFrameCallback) parkFrame = video.requestVideoFrameCallback(park); else parkTimer = setTimeout(park, 120);
    }).catch(park);
  };
  video.addEventListener("loadeddata", onLoaded, { once: true });
  video.pause();
  watchVideo(video);

  backBtn?.remove();
  backBtn = document.createElement("button");
  backBtn.className = "btn back"; backBtn.textContent = "← Back";
  backBtn.onclick = () => go("capture");
  root.append(backBtn);

  const id = ctx.ident?.identification;
  if (!id || !id.object) {
    root.querySelector(".obj").textContent = "nothing yet";
    root.querySelector(".sizes").innerHTML = "";
    root.querySelector(".custom").hidden = true;
    root.querySelector(".msg").textContent = "Could not find an object in that clip. Film again with the object in view.";
    const b = root.querySelector("#confirm-go");
    b.disabled = false; b.textContent = "Film again"; b.onclick = () => go("capture");
    return;
  }
  root.querySelector("#confirm-go").textContent = "Confirm and measure";
  const guess = Number.isFinite(id.real_size_m) && id.real_size_m > 0 ? id.real_size_m : PRESETS[0][1];
  root.querySelector(".obj").textContent = id.object;
  const options = PRESETS.map(([name, m]) => ({ key: String(m), label: `${name} ${cm(m)}`, m }));
  if (!options.some((o) => Math.abs(o.m - guess) < 1e-3)) options.unshift({ key: String(guess), label: `${id.object} ${cm(guess)}`, m: guess });
  options.push({ key: CUSTOM, label: "Custom" });
  let selected = options.find((o) => o.m != null && Math.abs(o.m - guess) < 1e-3).key;

  const chips = root.querySelector(".sizes"), custom = root.querySelector(".custom"), input = root.querySelector("#custom-cm");
  const msg = root.querySelector(".msg"), confirmBtn = root.querySelector("#confirm-go");
  msg.textContent = ""; input.value = ""; confirmBtn.disabled = false;

  const paint = () => {
    chips.innerHTML = "";
    for (const o of options) {
      const b = document.createElement("button");
      const on = o.key === selected;
      b.className = "chip" + (on ? " on" : ""); b.textContent = (on ? "✓ " : "") + o.label; b.dataset.size = o.key;
      b.setAttribute("aria-pressed", String(on));
      b.onclick = () => { selected = o.key; msg.textContent = ""; paint(); };
      chips.append(b);
    }
    custom.hidden = selected !== CUSTOM;
  };
  paint();
  input.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); confirmBtn.click(); } };

  confirmBtn.onclick = () => {
    let size;
    if (selected === CUSTOM) {
      const v = parseFloat(input.value);
      if (!(v >= 1 && v <= 999)) { msg.textContent = "Enter the object's size in centimetres (1 to 999)."; return; }
      size = v / 100;
    } else size = options.find((o) => o.key === selected).m;
    confirmBtn.disabled = true; // one tap, one request
    msg.textContent = "";
    const retry = () => analyze({ id: ctx.uploadId, size_m: size })
      .then((r) => (r.error ? Promise.reject(new Error(`${r.error}. Film again with the object in view.`)) : { go: "verdict", data: r }));
    go("analysing", { status: STAGES[0], stages: STAGES, retry, job: retry() });
  };
}
