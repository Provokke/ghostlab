"""Ground-truth test clips (10 cm ball): analytic physics, photographic-ish scene, motion blur, noise, H.264. No Blender.
Run: python scripts/render_clips.py [bounce toss pendulum camera_shake slowmo]  ->  work/render/*.mp4 and truth.json"""
import json, subprocess, sys
from pathlib import Path
import numpy as np, cv2
from scipy.integrate import solve_ivp

OUT = Path(__file__).resolve().parent.parent / "work" / "render"
OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS, PXM = 1280, 720, 30, 320.0          # 320 px per metre
G, D = 9.81, 0.10
FLOOR_Y = 640                                   # floor line (px)
rng = np.random.default_rng(7)

def scene():
    wall = np.zeros((H, W, 3), np.float32)
    base = rng.normal(0, 1, (H // 8, W // 8)); base = cv2.resize(base, (W, H), interpolation=cv2.INTER_CUBIC)
    fine = rng.normal(0, 1, (H, W))
    tex = 150 + 12 * base + 1.5 * fine
    wall[:] = tex[..., None] * np.array([0.92, 0.95, 1.0])
    grad = np.linspace(1.08, 0.88, H)[:, None, None]; wall *= grad
    wall[FLOOR_Y:] = (95 + 10 * base[FLOOR_Y:, :, None]) * np.array([0.55, 0.65, 0.95])
    for x in range(0, W, 160): cv2.line(wall, (x, 0), (x, FLOOR_Y - 2), (140, 140, 140), 1)  # panel seams
    cv2.line(wall, (0, FLOOR_Y), (W, FLOOR_Y), (60, 60, 60), 3)
    return wall

BG = scene()

def sprite(r_px, ss=4):
    n = int(2 * r_px * ss) | 1
    yy, xx = np.mgrid[:n, :n] - n // 2
    rr = np.hypot(xx, yy) / (r_px * ss)
    nz = np.sqrt(np.clip(1 - rr**2, 0, 1))
    light = np.clip((-0.4 * xx / (r_px * ss) - 0.5 * yy / (r_px * ss)) + 0.75 * nz, 0.05, 1)
    col = np.stack([40 * light + 10, 215 * light + 20, 200 * light + 25], -1)  # BGR yellow-green
    col += 120 * np.clip(light - 0.93, 0, 1)[..., None] * 8
    a = np.clip((1 - rr) * r_px * ss, 0, 1)
    d = int(round(2 * r_px))
    col = cv2.resize(col.astype(np.float32), (d, d), interpolation=cv2.INTER_AREA)
    a = cv2.resize(a.astype(np.float32), (d, d), interpolation=cv2.INTER_AREA)
    return col, a

SPR = sprite(D * PXM / 2)

def paste(img, cx, cy, spr=SPR, sh=0.0):
    col, a = spr; h, w = a.shape
    s = col.shape[0]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xb <= xa or yb <= ya: return
    c = col[ya - y0:yb - y0, xa - x0:xb - x0]; al = a[ya - y0:yb - y0, xa - x0:xb - x0, None]
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - al) + c * al

def render(name, pos_fn, dur, string_pivot=None, stretch=1.0, cam=None):
    """pos_fn(t)->(x_m,y_m) with origin at bottom-left of frame, y up; cam(t)->(dx_px,dy_px)."""
    d = OUT / f"frames_{name}"; d.mkdir(exist_ok=True)
    for f in d.glob("*.png"): f.unlink()
    n = int(dur * FPS); sub = 8
    for i in range(n):
        acc = np.zeros((H, W, 3), np.float32)
        for k in range(sub):
            t = (i + (k / sub) * 0.5) / FPS / stretch          # 180-degree shutter
            x, y = pos_fn(t)
            img = BG.copy()
            cx, cy = x * PXM, FLOOR_Y - y * PXM
            if string_pivot is not None:
                px, py = string_pivot[0] * PXM, FLOOR_Y - string_pivot[1] * PXM
                cv2.line(img, (int(px), int(py)), (int(cx), int(cy)), (200, 200, 200), 1, cv2.LINE_AA)
                cv2.circle(img, (int(px), int(py)), 5, (30, 30, 30), -1, cv2.LINE_AA)
            paste(img, cx, cy)
            acc += img
        img = acc / sub
        if cam:
            dx, dy = cam(i / FPS)
            img = cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
        img = img + rng.normal(0, 2.5, img.shape)
        cv2.imwrite(str(d / f"{i:04d}.png"), np.clip(img, 0, 255).astype(np.uint8))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(d / "%04d.png"),
                    "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", str(OUT / f"{name}.mp4")], check=True)
    for f in d.glob("*.png"): f.unlink()
    d.rmdir()

R = D / 2
def bounce(t, h0=1.5, e=0.75):
    y, v, tt = h0, 0.0, 0.0
    # analytic: fall, then restitution bounces
    t_fall = np.sqrt(2 * (h0 - R) / G)
    if t < t_fall: return 1.2, R + (h0 - R) - 0.5 * G * t**2
    t -= t_fall; v = G * t_fall * e
    while True:
        T = 2 * v / G
        if t < T: return 1.2, R + v * t - 0.5 * G * t**2
        t -= T; v *= e
        if v < 0.05: return 1.2, R
def toss(t):
    return 0.4 + 2.0 * t, 1.0 + 4.0 * t - 0.5 * G * t**2
PIV, L, TH0, GAM = (2.0, 1.95), 1.0, np.radians(25), 0.02
sol = solve_ivp(lambda t, s: [s[1], -G / L * np.sin(s[0]) - 2 * GAM * s[1]], (0, 12), [TH0, 0], dense_output=True, rtol=1e-10, atol=1e-12)
def pend(t):
    th = sol.sol(t)[0]
    return PIV[0] + L * np.sin(th), PIV[1] - L * np.cos(th)
def shake(t):
    return (8 * np.sin(2.1 * t) + 6 * np.sin(7.3 * t + 1) + 25 * t * 0.3, 7 * np.sin(1.7 * t + 2) + 5 * np.sin(9.1 * t))

todo = sys.argv[1:] or ["bounce", "toss", "pendulum", "camera_shake", "slowmo"]
if "bounce" in todo: render("bounce", bounce, 4.0)
if "toss" in todo: render("toss", toss, 1.4)
if "pendulum" in todo: render("pendulum", pend, 8.0, PIV)
if "camera_shake" in todo: render("camera_shake", toss, 1.4, cam=shake)
if "slowmo" in todo: render("slowmo", pend, 8.0, PIV, stretch=3.0)
tt = (4 + np.sqrt(16 + 2 * G * 1.0)) / G
(OUT / "truth.json").write_text(json.dumps({
    "g": G, "ball_diameter_m": D, "fps": FPS, "px_per_m": PXM,
    "bounce": {"drop_height_m": 1.5, "restitution": 0.75},
    "toss": {"vx": 2.0, "vy": 4.0, "launch_speed": float(np.hypot(2, 4)), "launch_angle_deg": float(np.degrees(np.arctan2(4, 2)))},
    "pendulum": {"length_m": L, "amplitude_deg": 25, "damping": GAM, "small_angle_period_s": float(2 * np.pi * np.sqrt(L / G))},
    "camera_shake": "toss with handheld shake: must refuse", "slowmo": "pendulum at 1/3 speed: g would read 1.09"}, indent=1))
