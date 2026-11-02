// Screen state machine. Five screens; each module exports mount(root, ctx) and optional unmount().
// go("verdict", result) stores the result; go(other, patch) merges the patch into ctx.
export const ctx = { result: null, ident: null, uploadId: null, video: null, demo: false };

const SCREENS = ["capture", "analysing", "confirm", "verdict", "playground"];
let currentMod = null, token = 0;

export async function go(name, data) {
  if (!SCREENS.includes(name)) throw new Error(`unknown screen ${name}`);
  const mine = ++token;
  if (name === "verdict") ctx.result = data ?? ctx.result;
  else Object.assign(ctx, data || {});
  const mod = await import(`./${name}.js`);
  if (mine !== token) return; // a newer go() superseded this one
  currentMod?.unmount?.();
  document.querySelectorAll("section[data-screen]").forEach((s) => (s.hidden = s.dataset.screen !== name));
  document.body.dataset.screen = name;
  currentMod = mod;
  try { await mod.mount(document.querySelector(`section[data-screen="${name}"]`), ctx); }
  catch (e) {
    console.error(e);
    if (name !== "capture") { await go("capture"); document.querySelector('section[data-screen="capture"] .msg').textContent = e.message || "Something went wrong."; }
  }
}

// Keep the video above the bottom panel (verdict sheet, playground controls) instead of under it.
const syncDock = () => {
  const d = document.querySelector("section[data-screen]:not([hidden]) .dock");
  document.body.style.setProperty("--dock-h", d && ["verdict", "playground", "confirm", "analysing"].includes(document.body.dataset.screen) ? `${d.offsetHeight}px` : "0px");
};
const dockObserver = new ResizeObserver(syncDock);
document.querySelectorAll(".dock").forEach((d) => dockObserver.observe(d));
new MutationObserver(syncDock).observe(document.body, { attributes: true, attributeFilter: ["data-screen"] });

go("capture");
