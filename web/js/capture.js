import { getDemo, getDemos, identify } from "./api.js";
import { go } from "./screens.js";

function pick(file) {
  if (!file) return;
  const job = identify(file).then((r) => ({ go: "confirm", data: { ident: r, uploadId: r.id, video: r.video } }));
  go("analysing", { video: URL.createObjectURL(file), demo: false, status: "Muse Spark is looking at your clip.", job });
}

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
    for (const name of await getDemos()) {
      const b = document.createElement("button");
      b.className = "chip"; b.textContent = name; b.dataset.demo = name;
      b.onclick = async () => {
        b.disabled = true;
        try { const res = await getDemo(name); await go("verdict", res); }
        catch (e) { msg.textContent = e.message; b.disabled = false; }
      };
      chips.append(b);
    }
  } catch (e) { msg.textContent = e.message; }
}
