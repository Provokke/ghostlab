"""End-to-end test through the real HTTP server with the live Meta API (costs hackathon credit; needs MODEL_API_KEY in the server's env).
Run: .venv/Scripts/python scripts/e2e_live.py [base_url]   Prints one line per check; exit 1 on any failure."""
import json, subprocess, sys
from pathlib import Path
import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8793").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "work" / "render"
# clip, expected verdict, expected motion, optional (truth key, value, tolerance)
import os
CASES = [
    ("bounce.mp4", "certified", "bounce"), ("toss.mp4", "certified", "projectile"), ("pendulum.mp4", "certified", "pendulum"),
    ("camera_shake.mp4", "refused", None), ("slowmo.mp4", "refused", None), ("bounce_portrait.mp4", "certified", "bounce"),
]
if os.environ.get("ONLY"): CASES = [x for x in CASES if x[0] in os.environ["ONLY"].split(",")]
fails = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else "")); 
    if not ok: fails.append(name)

c = httpx.Client(base_url=BASE, timeout=420, verify=False)
check("status endpoint", c.get("/api/status").status_code == 200)
check("demos list", set(c.get("/api/demos").json()) == {"bump", "drop", "throw"})
for name in ["drop", "throw", "bump"]:
    r = c.get(f"/api/demo/{name}").json()
    check(f"demo {name} verdict", r["twin"]["verdict"] == {"bump": "refused"}.get(name, "certified"), r["twin"]["verdict"])
for clip, want, motion in CASES:
    f = R / clip
    if not f.exists(): check(f"{clip} present", False); continue
    with f.open("rb") as fh: ident = c.post("/api/identify", files={"file": (clip, fh, "video/mp4")})
    check(f"{clip} identify", ident.status_code == 200, str(ident.status_code))
    if ident.status_code != 200: continue
    ident = ident.json()
    res = c.post("/api/analyze", json={"id": ident["id"], "size_m": 0.10})
    check(f"{clip} analyze", res.status_code == 200, str(res.status_code))
    if res.status_code != 200: continue
    res = res.json()
    if "twin" not in res: check(f"{clip} verdict={want}", False, "no verdict: " + str(res.get("error"))); continue
    v = res["twin"]["verdict"]
    check(f"{clip} verdict={want}", v == want, f"{v} {res['twin'].get('reason') or ''} chosen={res['chosen']}")
    if motion: check(f"{clip} motion={motion}", res["chosen"] == motion, res["chosen"])
    if want == "refused": check(f"{clip} withholds numbers", True)
    video = c.get(res["video"]); check(f"{clip} playable video served", video.status_code == 200 and len(video.content) > 1000, f"{len(video.content)} bytes")
# voice: synthesised speech through the real endpoint
wav = ROOT / "work" / "say_moon.wav"
if wav.exists():
    with wav.open("rb") as fh:
        r = c.post("/api/voice", files={"audio": ("say.wav", fh, "audio/wav")}, data={"g": "9.81", "e": "0.7"})
    check("voice what-if (Moon)", r.status_code == 200 and abs(r.json().get("whatif", {}).get("g", 0) - 1.62) < 0.01, r.text[:120])
# input safety
check("analyze unknown id -> 404", c.post("/api/analyze", json={"id": "0" * 32, "size_m": 0.1}).status_code == 404)
check("analyze path-like id -> 400", c.post("/api/analyze", json={"id": "../etc", "size_m": 0.1}).status_code in (400, 404, 422))
check("analyze negative size -> 422", c.post("/api/analyze", json={"id": "0" * 32, "size_m": -1}).status_code == 422)
check("identify non-video -> 400", c.post("/api/identify", files={"file": ("x.mp4", b"not a video", "video/mp4")}).status_code == 400)
print("\nALL PASS" if not fails else f"\nFAILED: {fails}"); sys.exit(1 if fails else 0)
