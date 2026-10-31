"""Drive the web app in a phone-sized Edge: console errors, horizontal overflow, ghost actually drawn."""
import subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 8791
INK_JS = """() => { const c=document.getElementById('overlay'); const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++; return n; }"""


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - window.innerWidth")


def ink(page):
    return page.evaluate(INK_JS)


def freeze_at(page, seconds):
    page.evaluate(f"() => {{ const v=document.getElementById('video'); v.pause(); v.currentTime={seconds}; }}")
    page.wait_for_timeout(800)


def walk(page, base, report, shots, demo="drop"):
    page.goto(base)
    page.wait_for_selector('body[data-screen="capture"]')
    report["capture_overflow_px"] = overflow(page)
    page.screenshot(path=str(shots / "1_capture.png"))
    page.click(f'[data-demo="{demo}"]')
    page.wait_for_selector('body[data-screen="verdict"]', timeout=3000)  # demo clips skip Confirm
    page.wait_for_timeout(1200)
    freeze_at(page, 0.9)
    report["verdict_overflow_px"] = overflow(page)
    report["verdict_ink_px"] = ink(page)
    report["video_ready"] = page.evaluate("() => [document.getElementById('video').readyState, document.getElementById('video').videoWidth]")
    page.screenshot(path=str(shots / "4_verdict.png"))


srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "ghostlab.server:app", "--port", str(PORT)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/api/status"); break
        except Exception:
            time.sleep(0.2)
    errors, report = [], {}
    shots = Path("work/ui"); shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        walk(page, f"http://localhost:{PORT}/", report, shots)
        report["console_errors"] = errors
        print(report)
        b.close()
finally:
    srv.terminate()
