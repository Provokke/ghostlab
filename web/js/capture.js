import { getDemo, getDemos, identify } from "./api.js";
import { go } from "./screens.js";
import { friendly } from "./util.js";

const MAX_BYTES = 100 * 1024 * 1024;
const STAGES = ["Muse Spark is looking at your clip.", "Finding the object", "Checking its size"];

function check(file) {
  if (!file) return "No clip selected.";
  const okType = file.type ? file.type.startsWith("video/") : /\.(mp4|mov|m4v|webm)$/i.test(file.name);
  if (!okType) return "That file is not a video. Pick a clip filmed on your phone.";
  if (file.size > MAX_BYTES) return `That clip is ${Math.round(file.size / 1048576)} MB. Keep it under 100 MB (a few seconds is plenty).`;
  if (file.size === 0) return "That clip is empty. Film it again.";
  return "";
}

let loadId = 0, pending = 0;

function pick(file, msg) {
  pending++; // a sample still loading must not pull the user out of this flow
  const problem = check(file);
  if (problem) { msg.textContent = problem; return; }
  msg.textContent = "";
  const retry = () => identify(file).then((r) => (r?.error ? Promise.reject(new Error(r.error)) : { go: "confirm", data: { ident: r, uploadId: r.id, video: r.video } }));
  const url = URL.createObjectURL(file);
  go("analysing", { video: url, blobUrl: url, demo: false, status: STAGES[0], stages: STAGES, retry, job: retry() });
}

const SAMPLES = { drop: ["Drop", "bounces, certifies"], throw: ["Throw", "arc, certifies"], bump: ["Bump", "refuses"] };

async function loadSamples(root, chips, msg) {
  const mine = ++loadId;
  try {
    const order = ["drop", "throw", "bump"], rank = (n) => (order.includes(n) ? order.indexOf(n) : order.length);
    const list = await getDemos();
    if (mine !== loadId) return;
    const names = (Array.isArray(list) ? list.filter((n) => typeof n === "string") : []).sort((a, b) => rank(a) - rank(b));
    if (!names.length) throw new Error("none");
    const buttons = names.map((name) => {
      const b = document.createElement("button"), [title, note] = SAMPLES[name] || [name, "sample clip"];
      b.className = "chip card"; b.dataset.demo = name;
      const t = document.createElement("b"), n = document.createElement("span");
      t.textContent = title; n.textContent = note; b.append(t, n);
      b.onclick = async () => {
        const id = ++pending, all = () => chips.querySelectorAll("button");
        all().forEach((x) => (x.disabled = true));
        msg.textContent = "Loading sample...";
        try {
          const res = await getDemo(name);
          if (id !== pending || document.body.dataset.screen !== "capture") return;
          msg.textContent = "";
          await go("verdict", res);
        } catch (e) {
          if (id !== pending) return;
          msg.textContent = friendly(e);
          all().forEach((x) => (x.disabled = false));
        }
      };
      return b;
    });
    chips.replaceChildren(...buttons);
  } catch (e) {
    if (mine !== loadId) return;
    const card = document.createElement("div");
    card.className = "chip card"; card.setAttribute("role", "group");
    card.innerHTML = "<b>Samples unavailable</b><span>Upload a clip instead, or retry.</span>";
    const retry = document.createElement("button");
    retry.className = "chip"; retry.textContent = "Retry";
    retry.onclick = () => loadSamples(root, chips, msg);
    card.append(retry);
    chips.replaceChildren(card);
    console.warn("[ghostlab] samples failed", e);
  }
}

export async function mount(root) {
  const chips = root.querySelector("#demos"), msg = root.querySelector(".msg");
  msg.textContent = "";
  pending++;
  for (const id of ["film-input", "upload-input"]) {
    const input = root.querySelector(`#${id}`);
    input.value = "";
    input.onchange = () => pick(input.files[0], msg);
  }
  await loadSamples(root, chips, msg);
}
