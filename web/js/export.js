// Record the replay (video frame + ghost overlay) to a clip in the browser: canvas.captureStream + MediaRecorder.
const TYPES = ["video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm"];

export function exportClip(video, ghostCanvas, handle = {}) {
  return new Promise((resolve, reject) => {
    const off = document.createElement("canvas");
    if (typeof MediaRecorder === "undefined" || !off.captureStream) return reject(new Error("This browser cannot record the clip."));
    const type = TYPES.find((t) => MediaRecorder.isTypeSupported(t));
    if (!type) return reject(new Error("This browser cannot record the clip."));
    // Even dimensions: H.264 encoders reject odd sizes.
    const even = (n) => Math.max(2, Math.round(n / 2) * 2);
    off.width = even(video.videoWidth || ghostCanvas.width); off.height = even(video.videoHeight || ghostCanvas.height);
    const c = off.getContext("2d"), wasLoop = video.loop;
    const rec = new MediaRecorder(off.captureStream(30), { mimeType: type });
    const chunks = [];
    let raf = 0, done = false;
    const draw = () => {
      c.drawImage(video, 0, 0, off.width, off.height);
      c.drawImage(ghostCanvas, 0, 0, off.width, off.height);
    };
    const paint = () => { draw(); raf = requestAnimationFrame(paint); };
    const finish = (err) => {
      if (done) return;
      done = true; cancelAnimationFrame(raf); video.loop = wasLoop; video.onended = null;
      if (err) { if (rec.state === "recording") rec.stop(); return reject(err); }
      if (rec.state === "recording") rec.stop();
    };
    handle.cancel = () => finish(new Error("Export cancelled."));
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onerror = () => finish(new Error("Recording failed."));
    rec.onstop = () => (chunks.length ? resolve(new Blob(chunks, { type: rec.mimeType || type })) : reject(new Error("Recording was empty.")));
    video.loop = false;
    video.onended = () => setTimeout(() => finish(), 150);
    video.currentTime = 0;
    video.play().then(() => { draw(); rec.start(); paint(); }).catch((e) => finish(new Error(`Could not play the clip: ${e.message}`)));
  });
}
