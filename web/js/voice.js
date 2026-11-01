// Hold-to-talk: pointer down records, pointer up stops and hands the audio over.
export function holdToTalk(button, onAudio, onError) {
  let rec = null, stream = null, chunks = [], wantStop = false, starting = false;

  const stop = () => {
    wantStop = true;
    if (rec && rec.state === "recording") rec.stop();
  };

  button.onpointerdown = async (e) => {
    e.preventDefault();
    try { button.setPointerCapture(e.pointerId); } catch {}
    if (rec || starting) return;
    wantStop = false; starting = true;
    try {
      if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) throw new Error("recording is not supported here");
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      rec = new MediaRecorder(stream);
      rec.ondataavailable = (ev) => ev.data.size && chunks.push(ev.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        rec = null; button.classList.remove("rec"); button.textContent = "Hold to talk";
        if (blob.size) onAudio(blob);
      };
      rec.start();
      button.classList.add("rec"); button.textContent = "Listening…";
      if (wantStop) stop(); // finger already lifted while the mic permission was pending
    } catch (err) {
      stream?.getTracks().forEach((t) => t.stop()); stream = null; rec = null;
      onError(`Microphone unavailable: ${err.message}`);
    } finally { starting = false; }
  };
  button.onpointerup = button.onpointercancel = stop;
  return stop;
}
