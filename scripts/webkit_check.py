"""Smoke test in Playwright WebKit (Safari's engine) at phone size. Needs: python -m playwright install webkit, and the server on port 8792
(.venv/Scripts/python -m uvicorn ghostlab.server:app --port 8792). Playwright's Windows WebKit has no MediaRecorder or canvas capture, so it cannot test
export or the microphone: those need a real iPhone (docs/PHONE_TESTING.md)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.webkit.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    pg = ctx.new_page(); logs = []
    pg.on("console", lambda m: logs.append((m.type, m.text[:150]))); pg.on("pageerror", lambda e: logs.append(("pageerror", str(e)[:200])))
    pg.goto("http://localhost:8792/"); pg.wait_for_timeout(1500)
    print("caps:", pg.evaluate("() => ({mr: typeof MediaRecorder, mp4: typeof MediaRecorder!=='undefined' && MediaRecorder.isTypeSupported('video/mp4'), webm: typeof MediaRecorder!=='undefined' && MediaRecorder.isTypeSupported('video/webm'), gum: !!navigator.mediaDevices, capture: typeof HTMLCanvasElement.prototype.captureStream})"))
    print("demo chips:", len(pg.locator("#demos > *").all()))
    pg.locator("#demos > *").first.click(); pg.wait_for_timeout(9000)
    print("screen after demo click:", pg.evaluate("document.body.dataset.screen"))
    Path("work").mkdir(exist_ok=True); pg.screenshot(path="work/wk_after_demo.png")
    print("video:", pg.evaluate("() => { const v=document.getElementById('video'); return {rs:v.readyState, w:v.videoWidth, err:v.error&&v.error.code} }"))
    bad = [l for l in logs if l[0] in ("error","pageerror")]
    print("logs:", [l for l in logs if l[0] in ("error","pageerror","warning")][:6])
    screen = pg.evaluate("document.body.dataset.screen")
    b.close()
    if bad or screen != "verdict":
        print("FAIL: page errors or not on verdict"); sys.exit(1)
