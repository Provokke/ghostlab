# iPhone test checklist

Camera and microphone need HTTPS on a phone. From `D:\External\Ghostlab` in PowerShell:

    powershell -ExecutionPolicy Bypass -File scripts/run_phone.ps1

- It asks for the Meta key with hidden input. Enter alone serves the bundled demos only.
- It prints `https://<PC IP>:8791`. The PC and phone must be on the same Wi-Fi; allow Python through the firewall on Private networks.
- In Safari, accept the certificate warning. The self-signed certificate lives in `work/cert/` (ignored by git) and lasts 7 days.

Already checked in Playwright WebKit (`scripts/webkit_check.py`): the page loads, a sample clip reaches Verdict, the H.264 clip plays, no console errors. That WebKit has no MediaRecorder, so steps 7 and 8 need a real iPhone.

1. Capture screen loads, dark theme, no horizontal scroll, buttons easy to hit.
2. Tap a sample clip: Analysing plays, the orange path draws, the cyan ghost follows. The tag reads "Sample clip (synthetic)".
3. Verdict shows CERTIFIED for throw and drop, REFUSED for bump. Drag the sheet up: chart and numbers appear.
4. On a refused clip, What if does not open the Playground.
5. Playground: Moon / Mars / Jupiter chips move the purple ghost; gravity and bounciness sliders respond.
6. Type "what if this was on Mars?": the slider moves.
7. Hold to talk: Safari asks for the microphone. Say "what if this was on the moon"; the Moon chip selects (needs the key).
8. Export clip: a video downloads or shares and plays in Photos (Safari recording support is the likeliest failure).
9. Upload a short video from Photos: Confirm asks the size (use 10 cm for the rendered test clips), then a verdict. Needs the key.
10. Film opens the camera.

Test clips: render them with `scripts/render_clips.py` (output in `work/render/`). They are rendered with known physics, not filmed footage.
