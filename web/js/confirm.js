// Confirm the object's size before any verdict: the guess from Muse Spark is pre-selected.
import { analyze } from "./api.js";
import { go } from "./screens.js";

const PRESETS = [["Tennis ball", 0.067], ["Football", 0.22], ["Basketball", 0.24]];
const CUSTOM = "custom";
const cm = (m) => `${+(m * 100).toFixed(1)} cm`;

export function mount(root, ctx) {
  const video = document.getElementById("video");
  video.src = ctx.video; video.loop = false;
  video.addEventListener("loadeddata", () => { video.currentTime = 0; video.pause(); }, { once: true });
  video.pause();

  const id = ctx.ident.identification, guess = id.real_size_m;
  root.querySelector(".obj").textContent = id.object;
  const options = PRESETS.map(([name, m]) => ({ key: String(m), label: `${name} ${cm(m)}`, m }));
  if (!options.some((o) => Math.abs(o.m - guess) < 1e-3)) options.unshift({ key: String(guess), label: `${id.object} ${cm(guess)}`, m: guess });
  options.push({ key: CUSTOM, label: "Custom" });
  let selected = options.find((o) => o.m != null && Math.abs(o.m - guess) < 1e-3).key;

  const chips = root.querySelector(".sizes"), custom = root.querySelector(".custom"), input = root.querySelector("#custom-cm");
  const msg = root.querySelector(".msg"), go_ = root.querySelector("#confirm-go");
  msg.textContent = ""; input.value = ""; go_.disabled = false;

  const paint = () => {
    chips.innerHTML = "";
    for (const o of options) {
      const b = document.createElement("button");
      b.className = "chip" + (o.key === selected ? " on" : ""); b.textContent = o.label; b.dataset.size = o.key;
      b.onclick = () => { selected = o.key; msg.textContent = ""; paint(); };
      chips.append(b);
    }
    custom.hidden = selected !== CUSTOM;
  };
  paint();

  go_.onclick = () => {
    let size;
    if (selected === CUSTOM) {
      const v = parseFloat(input.value);
      if (!(v >= 1 && v <= 999)) { msg.textContent = "Enter the object's size in centimetres (1 to 999)."; return; }
      size = v / 100;
    } else size = options.find((o) => o.key === selected).m;
    go_.disabled = true; // one tap, one request
    msg.textContent = "";
    const job = analyze({ id: ctx.uploadId, size_m: size })
      .then((r) => (r.error ? Promise.reject(new Error(`${r.error}. Film again with the object in view.`)) : { go: "verdict", data: r }));
    go("analysing", { status: "SAM 3.1 is tracking your clip. About a minute.", job });
  };
}
