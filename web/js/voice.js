// Hold-to-talk: pointer down (or Space / Enter) records, release stops and hands the audio over.
import { reduced } from "./util.js";

const MIN_MS = 400, MAX_MS = 8000;

export function holdToTalk(button, onAudio, onError) {
  let rec = null, stream = null, chunks = [], wantStop = false, cancelled = false, starting = false, startedAt = 0, capTimer = 0, pulse = null;
  button.style.touchAction = "none"; button.style.userSelect = "none";
  button.style.webkitUserSelect = "none"; button.style.webkitTouchCallout = "none";
  button.oncontextmenu = (e) => e.preventDefault();

  const stop = () => {
    wantStop = true; clearTimeout(capTimer);
    if (rec && rec.state === "recording") rec.stop();
  };

  // Stop and drop whatever was recorded (screen torn down).
  const cancel = () => { cancelled = true; stop(); };

  const begin = async () => {
    if (rec || starting || cancelled) return;
    wantStop = false; starting = true;
    try {
      if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) throw new Error("recording is not supported here");
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      rec = new MediaRecorder(stream);
      rec.ondataavailable = (ev) => ev.data.size && chunks.push(ev.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const discard = cancelled;
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" }), held = Date.now() - startedAt;
        rec = null; pulse?.cancel(); pulse = null;
        button.classList.remove("rec"); button.textContent = "Hold to talk";
        if (discard) return;
        if (held < MIN_MS) return onError("Hold a little longer, then speak.");
        if (blob.size) onAudio(blob);
      };
      rec.start(); startedAt = Date.now();
      button.classList.add("rec"); button.textContent = "Listening\u2026";
      pulse = reduced() ? null : button.animate?.([{ boxShadow: "0 0 0 0 rgba(255,93,108,.6)" }, { boxShadow: "0 0 0 10px rgba(255,93,108,0)" }], { duration: 900, iterations: Infinity }) ?? null;
      capTimer = setTimeout(stop, MAX_MS);
      if (wantStop) stop(); // finger already lifted while the mic permission was pending
    } catch (err) {
      stream?.getTracks().forEach((t) => t.stop()); stream = null; rec = null;
      const denied = /denied|notallowed|permission/i.test(`${err.name} ${err.message}`);
      onError(`Microphone unavailable${denied ? " (access blocked)" : ""}. Type your what-if instead.`);
    } finally { starting = false; }
  };

  button.onpointerdown = (e) => {
    e.preventDefault();
    try { button.setPointerCapture(e.pointerId); } catch {}
    begin();
  };
  button.onpointerup = button.onpointercancel = stop;
  button.onkeydown = (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); begin(); } };
  button.onkeyup = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); stop(); } };
  button.onblur = stop;
  return { stop, cancel };
}
