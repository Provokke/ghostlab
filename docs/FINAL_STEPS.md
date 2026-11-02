# Final steps: iPhone test and demo recording

Deadline: Thu Nov 5, 1:00 PM AEDT (Nov 4, 9:00 PM ET). Do the phone test first: it decides what the demo can show.

## 1. iPhone test (about 10 minutes)

Start the server (PowerShell, in `D:\External\Ghostlab`):

    powershell -ExecutionPolicy Bypass -File scripts/run_phone.ps1

- It asks for the Meta key with hidden input. Paste it there, not into chat. Enter alone serves the bundled demos only.
- It prints `https://<PC IP>:8791`. The PC and phone must be on the same Wi-Fi.
- Windows may ask to allow Python through the firewall: allow it on **Private** networks.
- In Safari, accept the certificate warning (Show Details, then visit this website). HTTPS is needed because Safari only allows the microphone on secure pages.
- Stop with Ctrl+C. The certificate lives in `work/cert/` (ignored by git) and lasts 7 days.

Tick each line; write down what fails and what Safari says.

1. Capture screen loads, dark theme, no horizontal scroll, buttons easy to hit.
2. Tap a sample clip: Analysing plays, orange path draws, cyan ghost follows. The sample tag says "Sample clip (synthetic)".
3. Verdict shows CERTIFIED for throw and drop, REFUSED for bump (off by about 76 cm). Drag the sheet up: chart and numbers appear.
4. Refused clip: What if does not open the Playground.
5. Playground: Moon / Mars / Jupiter chips move the purple ghost; gravity and bounciness sliders respond.
6. Type "what if this was on Mars?": the slider moves.
7. Hold to talk: Safari asks for the microphone. Say "what if this was on the moon". Expect the Moon chip to select (live Voice Transcribe, needs the key).
8. Export clip: a video downloads or shares and plays in Photos. (Safari recording support is the most likely failure.)
9. Upload a short video from Photos (use the Upload button, not Film): Confirm screen asks the size, then a verdict. Needs the key. Use a clip with a plain background and one ball.
10. Film button opens the camera (works over plain HTTP too, but you are on HTTPS now).

If 7 or 8 fail on Safari, the demo can be recorded from desktop Edge or Chrome instead; say so honestly in the video. Send me the failures.

## 2. Recording the demo (3:00 max)

Shot list and lines: `docs/DEMO.md`. Record on the phone screen (iOS Screen Recording, with microphone on for your voice) or on the PC with the phone view at 390 px wide.

Prepare:
- Clips to use, all in the app's sample row or in `work/render/`: `bounce.mp4`, `pendulum.mp4`, `camera_shake.mp4` (the refusal), `toss.mp4`. Say "rendered clips with known physics" on screen at least once. Never imply they are filmed footage.
- For live runs of a rendered clip, put it on the phone via AirDrop or the Photos app, then Upload. The ball size is **10 cm**: choose or type 10 on the Confirm screen, otherwise the model guesses 6.7 cm and the g check refuses the clip.
- Results are cached, so a repeat run of the same clip is instant and free. Do one run before recording so the take is fast.
- No faces, no minors, no music in frame or audio (the rules and the project rules).

Takes, in order of the shot list:
1. 0:00-0:12 hook: ghost appearing over the bounce clip.
2. 0:12-0:35 the pipeline on the phone: Capture, Analysing, name the three Meta models as you go.
3. 0:35-1:10 Confirm the size, then Verdict CERTIFIED, "off by 0.8 cm" (bounce), drag up the prediction-test chart.
4. 1:10-1:35 the refusal: camera_shake ("the camera moved") and say why refusing is the feature.
5. 1:35-2:10 Playground by voice: "what if this was on the moon", then Export clip.
6. 2:10-2:35 results table from `docs/SUBMISSION.md` (bounce e 0.748 vs 0.75, pendulum period 2.027 s vs 2.006 s, 2 refusals).
7. 2:35-3:00 stack: SAM 3.1, Muse Spark, Muse Voice Transcribe; repo URL.

## 3. Submit

1. Make the repo public after a last look (`gh repo edit Provokke/ghostlab --visibility public --accept-visibility-change-consequences`).
2. Paste from `docs/SUBMISSION.md`; check the track wording on the form (the README says Push the Frontier, the entry notes say Indie).
3. Upload the video and the repo URL before the deadline.
4. After judging: rotate the Meta key. Old chat logs on this PC contain it in plain text.
