// Small shared helpers: plain-words errors, toast, reduced-motion check, video error watcher.
export const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// Turn any thrown thing into a sentence a person can act on. Raw detail goes to the console only.
export function friendly(e, fallback = "Something went wrong. Please try again.") {
  const raw = String(e?.message ?? e ?? "");
  if (raw) console.warn("[ghostlab]", raw);
  if (e?.name === "AbortError" || /timed out|timeout/i.test(raw)) return "That took too long. Check your connection and try again.";
  if (/failed to fetch|networkerror|load failed|network request failed/i.test(raw)) return "Can't reach Ghostlab. Check your connection and try again.";
  if (e?.name === "SyntaxError") return fallback;
  if (!raw || /^(undefined|null|internal server error|bad gateway|service unavailable|gateway time-?out)$/i.test(raw.trim())) return fallback;
  if (/^\s*[\[{]/.test(raw) || raw.length > 220) return fallback;
  return raw;
}

let toastEl = null, toastTimer = 0;
export function toast(message) {
  if (!message) return;
  if (!toastEl) {
    toastEl = document.createElement("div");
    toastEl.setAttribute("role", "status"); toastEl.setAttribute("aria-live", "polite");
    toastEl.style.cssText = "position:fixed;left:50%;transform:translateX(-50%);bottom:calc(16px + env(safe-area-inset-bottom));max-width:min(92vw,420px);z-index:50;background:rgba(6,8,13,.92);color:#fff;border:1px solid var(--line,#333);border-radius:14px;padding:10px 14px;font-size:14px;text-align:center;pointer-events:none;transition:opacity .2s";
    document.body.append(toastEl);
  }
  toastEl.textContent = message; toastEl.style.opacity = "1";
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (toastEl.style.opacity = "0"), 5000);
}

// Tell the user when the browser cannot decode the clip (for example HEVC on a non-Safari browser).
export function watchVideo(video, onBad) {
  video.onerror = () => {
    const m = "This clip could not be played here. Try Safari or film it again.";
    onBad ? onBad(m) : toast(m);
  };
}
