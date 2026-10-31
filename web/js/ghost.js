// Canvas overlay: orange real path, glowing cyan ghost, purple what-if. Drawn in clip pixel space.
import { simulate } from "./api.js";

export const DT = 1 / 60;
const COLORS = { real: "#ff9f43", ghost: "#5be7ff", what: "#c58bff" };

const times = (R) => { const end = Math.max(...R.track.t), out = []; for (let t = 0; t <= end + 1e-9; t += DT) out.push(t); return out; };

// Blind ghost: the twin's fit on the first part of the clip, run over the whole clip.
export async function ghostPoints(R) {
  const tr = R.track, t = times(R), blind = !!R.twin.sim, fit = R.fits[R.chosen];
  const out = await simulate({ motion: R.chosen, sim: blind ? R.twin.sim : fit.sim, m_per_px: tr.m_per_px, origin_px: tr.origin_px,
    t: blind ? t.map((v) => v - R.twin.t_origin) : t, g: null, e: null });
  return { t, px: out.px, py: out.py };
}

// What-if: the full-clip fit with gravity / bounciness replaced.
export async function whatPoints(R, g, e) {
  const tr = R.track, t = times(R);
  const out = await simulate({ motion: R.chosen, sim: R.fits[R.chosen].sim, m_per_px: tr.m_per_px, origin_px: tr.origin_px, t, g, e });
  return { t, px: out.px, py: out.py };
}

export function createGhost(canvas, video) {
  const c = canvas.getContext("2d");
  let R = null, ghost = null, what = null, mode = "verdict", started = performance.now(), raf = 0, alive = true;

  const at = (pts, t) => {
    if (!pts) return null;
    const i = Math.round(t / DT);
    return i < 0 || i >= pts.t.length || pts.px[i] == null ? null : [pts.px[i], pts.py[i]];
  };
  const dot = (p, r, color, alpha) => {
    if (!p) return;
    c.globalAlpha = alpha; c.fillStyle = color; c.shadowColor = color; c.shadowBlur = r * 2.2;
    c.beginPath(); c.arc(p[0], p[1], r, 0, 7); c.fill();
    c.globalAlpha = 1; c.shadowBlur = 0;
  };
  const trail = (pts, upto, color, alpha) => {
    if (!pts) return;
    const n = Math.min(Math.round(upto / DT), pts.t.length - 1);
    for (let i = 0; i <= n; i += 2) if (pts.px[i] != null) dot([pts.px[i], pts.py[i]], 3, color, alpha);
  };

  function frame() {
    if (!alive) return;
    raf = requestAnimationFrame(frame);
    if (!R || !R.track || canvas.width < 2) return;
    c.clearRect(0, 0, canvas.width, canvas.height);
    const tr = R.track, t = video.currentTime - tr.t0;
    const r = Math.max(10, (R.identification?.real_size_m ?? 0.067) / tr.m_per_px / 2);
    const rx = tr.x.map((x) => tr.origin_px[0] + x / tr.m_per_px), ry = tr.y.map((y) => tr.origin_px[1] - y / tr.m_per_px);
    const ri = tr.t.findIndex((v) => v >= t), last = ri < 0 ? tr.t.length - 1 : ri;
    for (let i = 0; i <= last; i++) dot([rx[i], ry[i]], 3.5, COLORS.real, 0.9);
    if (mode === "analysing") {
      // The ghost draws itself over ~2.5 s after the real path, then keeps extending past the clip.
      const span = ghost ? Math.max(...ghost.t) : 0;
      trail(ghost, Math.max(0, (performance.now() - started) / 1000 - 1.0) * (span / 2.5), COLORS.ghost, 0.6);
      return;
    }
    trail(ghost, t, COLORS.ghost, 0.5);
    dot(at(ghost, t), r, COLORS.ghost, 0.6);
    if (mode === "playground" && what) { trail(what, t, COLORS.what, 0.5); dot(at(what, t), r, COLORS.what, 0.65); }
  }
  raf = requestAnimationFrame(frame);

  return {
    setResult(res) { R = res; canvas.width = res.clip.width; canvas.height = res.clip.height; },
    setGhost(pts) { ghost = pts; },
    setWhat(pts) { what = pts; },
    mode(name) { mode = name; started = performance.now(); },
    replay() { started = performance.now(); video.currentTime = 0; video.play().catch(() => {}); },
    destroy() { alive = false; cancelAnimationFrame(raf); c.clearRect(0, 0, canvas.width, canvas.height); },
  };
}
