// Thin fetch wrapper: every call throws Error(detail) with the server's plain-words message.
export async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
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
