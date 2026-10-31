// Record the replay (video frame + ghost overlay) to a clip in the browser: canvas.captureStream + MediaRecorder.
const TYPES = ["video/mp4", "video/webm;codecs=vp9", "video/webm"];

export function exportClip(video, ghostCanvas) {
  return new Promise((resolve, reject) => {
    const off = document.createElement("canvas");
    if (typeof MediaRecorder === "undefined" || !off.captureStream) return reject(new Error("This browser cannot record the clip."));
    const type = TYPES.find((t) => MediaRecorder.isTypeSupported(t));
    if (!type) return reject(new Error("This browser cannot record the clip."));
    off.width = video.videoWidth || ghostCanvas.width; off.height = video.videoHeight || ghostCanvas.height;
    const c = off.getContext("2d"), wasLoop = video.loop;
    const rec = new MediaRecorder(off.captureStream(30), { mimeType: type });
    const chunks = [];
    let raf = 0, done = false;
    const paint = () => {
      c.drawImage(video, 0, 0, off.width, off.height);
      c.drawImage(ghostCanvas, 0, 0, off.width, off.height);
      raf = requestAnimationFrame(paint);
    };
    const finish = (err) => {
      if (done) return;
      done = true; cancelAnimationFrame(raf); video.loop = wasLoop; video.onended = null;
      if (err) return reject(err);
      if (rec.state === "recording") rec.stop();
    };
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onerror = () => finish(new Error("Recording failed."));
    rec.onstop = () => (chunks.length ? resolve(new Blob(chunks, { type: rec.mimeType || type })) : reject(new Error("Recording was empty.")));
    video.loop = false;
    video.onended = () => setTimeout(() => finish(), 150);
    video.currentTime = 0;
    video.play().then(() => { rec.start(); paint(); }).catch((e) => finish(new Error(`Could not play the clip: ${e.message}`)));
  });
}
