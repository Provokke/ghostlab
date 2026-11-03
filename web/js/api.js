// Thin fetch wrapper: every call throws Error(detail) with the server's plain-words message.
import { friendly } from "./util.js";

const TIMEOUT_MS = 120000;
export async function api(path, opts = {}) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    const r = await fetch(path, { ...opts, signal: ctl.signal });
    if (!r.ok) {
      const detail = (await r.json().catch(() => ({}))).detail;
      throw new Error(typeof detail === "string" && detail ? detail : r.status >= 500 ? "Ghostlab hit a problem on its side. Please try again." : "That request was not accepted. Please try again.");
    }
    try { return await r.json(); }
    catch { throw new Error("Ghostlab sent back something unreadable. Please try again."); }
  } catch (e) {
    if (e?.friendly) throw e;
    const err = new Error(friendly(e)); err.friendly = true;
    throw err;
  } finally { clearTimeout(timer); }
}

const json = (body) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const getDemos = () => api("/api/demos");
export const getDemo = (name) => api(`/api/demo/${encodeURIComponent(name)}`);
export const status = () => api("/api/status");
export const identify = (file) => { const body = new FormData(); body.append("file", file); return api("/api/identify", { method: "POST", body }); };
export const analyze = (body) => api("/api/analyze", json(body));
export const simulate = (body) => api("/api/simulate", json(body));
export const whatif = (body) => api("/api/whatif", json(body));
export const voice = (formData) => api("/api/voice", { method: "POST", body: formData });
