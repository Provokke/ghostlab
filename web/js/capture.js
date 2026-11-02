import { getDemo, getDemos, identify } from "./api.js";
import { go } from "./screens.js";

function pick(file) {
  if (!file) return;
  const job = identify(file).then((r) => ({ go: "confirm", data: { ident: r, uploadId: r.id, video: r.video } }));
  go("analysing", { video: URL.createObjectURL(file), demo: false, status: "Muse Spark is looking at your clip.", job });
}

const SAMPLES = { drop: ["Drop", "bounces, certifies"], throw: ["Throw", "arc, certifies"], bump: ["Bump", "refuses"] };

export async function mount(root) {
  const chips = root.querySelector("#demos"), msg = root.querySelector(".msg");
  msg.textContent = "";
  chips.innerHTML = "";
  for (const id of ["film-input", "upload-input"]) {
    const input = root.querySelector(`#${id}`);
    input.value = "";
    input.onchange = () => pick(input.files[0]);
  }
  try {
    const order = ["drop", "throw", "bump"];
    const names = (await getDemos()).sort((a, b) => (order.indexOf(a) + 9) % 9 - (order.indexOf(b) + 9) % 9);
    for (const name of names) {
      const b = document.createElement("button"), [title, note] = SAMPLES[name] || [name, "sample clip"];
      b.className = "chip card"; b.dataset.demo = name;
      b.innerHTML = `<b>${title}</b><span>${note}</span>`;
      b.onclick = async () => {
        b.disabled = true;
        try { const res = await getDemo(name); await go("verdict", res); }
        catch (e) { msg.textContent = e.message; b.disabled = false; }
      };
      chips.append(b);
    }
  } catch (e) { msg.textContent = e.message; }
}
