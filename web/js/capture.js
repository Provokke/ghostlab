import { getDemo, getDemos } from "./api.js";
import { go } from "./screens.js";

export async function mount(root) {
  const chips = root.querySelector("#demos"), msg = root.querySelector(".msg");
  msg.textContent = "";
  chips.innerHTML = "";
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
