"""Drive the web app in a phone-sized Edge: console errors, horizontal overflow, ghost actually drawn."""
import subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 8791
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "ghostlab.server:app", "--port", str(PORT)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/api/status"); break
        except Exception:
            time.sleep(0.2)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://localhost:{PORT}/")
        page.wait_for_selector("#trust:not([hidden])"); page.click("text=bump"); page.wait_for_timeout(1500)
        page.evaluate("document.getElementById('video').pause()")
        page.evaluate("document.getElementById('video').currentTime = 0.9")
        page.wait_for_timeout(800)
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        ink = page.evaluate("""() => { const c=document.getElementById('overlay'); const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++; return n; }""")
        Path("work").mkdir(exist_ok=True)
        page.screenshot(path="work/ui_phone.png", full_page=True)
        print({"overflow_px": overflow, "overlay_ink_px": ink, "console_errors": errors})
        b.close()
finally:
    srv.terminate()
