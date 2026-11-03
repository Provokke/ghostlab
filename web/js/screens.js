// Screen state machine. Five screens; each module exports mount(root, ctx) and optional unmount().
// go("verdict", result) stores the result; go(other, patch) merges the patch into ctx.
import { friendly, reduced, toast } from "./util.js";

const FRESH = { result: null, ident: null, uploadId: null, video: null, blobUrl: null, retry: null, job: null, status: null, stages: null };
export const ctx = { ...FRESH };

const SCREENS = ["capture", "analysing", "confirm", "verdict", "playground"];
const BACK = { analysing: "capture", confirm: "capture", verdict: "capture", playground: "verdict" };
let currentMod = null, current = null, token = 0;
// History policy: capture is the single root entry; every other screen pushes one entry on top of it.
let depth = 0, ignorePop = false;
const toRoot = () => { if (depth > 0) { ignorePop = true; history.go(-depth); depth = 0; } };

const enter = (section) => {
  section.dataset.entering = "";
  setTimeout(() => section.removeAttribute("data-entering"), 260);
  if (reduced() || !section.animate) return;
  section.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 240, easing: "ease-out" });
  section.querySelector(".dock")?.animate([{ transform: "translateY(14px)" }, { transform: "none" }], { duration: 260, easing: "ease-out" });
};

export async function go(name, data, opts = {}) {
  if (!SCREENS.includes(name)) throw new Error(`unknown screen ${name}`);
  const mine = ++token;
  if (name === "verdict") ctx.result = data ?? ctx.result;
  else Object.assign(ctx, data || {});
  if (name === "capture") Object.assign(ctx, FRESH, { blobUrl: ctx.blobUrl }); // drop the previous clip's state
  if (name !== "analysing" && ctx.blobUrl) { URL.revokeObjectURL(ctx.blobUrl); ctx.blobUrl = null; }
  let mod;
  try { mod = await import(`./${name}.js`); }
  catch (e) { console.error(e); toast(friendly(e, "Could not load this screen. Check your connection and reload.")); return; }
  if (mine !== token) return; // a newer go() superseded this one
  currentMod?.unmount?.();
  document.querySelectorAll("section[data-screen]").forEach((s) => (s.hidden = s.dataset.screen !== name));
  document.body.dataset.screen = name;
  const section = document.querySelector(`section[data-screen="${name}"]`);
  if (name === "capture") { if (!opts.pop) toRoot(); history.replaceState({ screen: name }, ""); }
  else if (opts.pop) history.replaceState({ screen: name }, "");
  else if (current && current !== name) { history.pushState({ screen: name }, ""); depth++; }
  else history.replaceState({ screen: name }, "");
  const first = current === null;
  current = name; currentMod = mod;
  enter(section);
  try {
    await mod.mount(section, ctx);
    if (mine === token && !first) section.focus({ preventScroll: true }); // keep keyboard and screen-reader users oriented
  } catch (e) {
    console.error(e);
    const message = friendly(e, "Something went wrong with that clip. Try again or pick a sample.");
    if (name !== "capture") await go("capture");
    const msg = document.querySelector('section[data-screen="capture"] .msg');
    if (msg) msg.textContent = message; else toast(message);
  }
}

// Hardware / browser Back walks one step back through the flow instead of leaving the app.
window.addEventListener("popstate", () => {
  if (ignorePop) { ignorePop = false; return; }
  const target = BACK[current];
  if (!target) return;
  depth = Math.max(0, depth - 1);
  go(target, null, { pop: true }).then(() => { if (target === "capture") toRoot(); });
});

// Last-resort handlers: say something plain instead of failing silently.
const report = (e) => {
  console.error(e);
  const msg = document.querySelector("section[data-screen]:not([hidden]) .msg");
  const text = navigator.onLine === false ? "You are offline. Reconnect and try again." : friendly(e?.reason ?? e?.error ?? e);
  if (msg && !msg.textContent) msg.textContent = text; else toast(text);
};
window.addEventListener("unhandledrejection", (e) => { e.preventDefault(); report(e); });
window.addEventListener("offline", () => toast("You are offline. Samples and analysis need a connection."));
window.addEventListener("online", () => toast("Back online."));

// Keep the video above the bottom panel (verdict sheet, playground controls) instead of under it.
const syncDock = () => {
  const d = document.querySelector("section[data-screen]:not([hidden]) .dock");
  document.body.style.setProperty("--dock-h", d && ["verdict", "playground", "confirm", "analysing"].includes(document.body.dataset.screen) ? `${d.offsetHeight}px` : "0px");
};
const dockObserver = new ResizeObserver(syncDock);
document.querySelectorAll(".dock").forEach((d) => dockObserver.observe(d));
new MutationObserver(syncDock).observe(document.body, { attributes: true, attributeFilter: ["data-screen"] });

go("capture").then(() => {
  // Warm the other screens so the first transition does not wait on a module waterfall.
  const warm = () => [...SCREENS.slice(1), "ghost", "api"].forEach((m) => import(`./${m}.js`).catch(() => {}));
  (window.requestIdleCallback || ((f) => setTimeout(f, 800)))(warm);
});
