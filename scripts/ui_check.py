"""Walk the phone UI in headless Edge at 390x844, 430x932 and 1440x900 (screenshots in work/ui/): all five screens, error paths, console errors, overflow, ghost ink,
touch-target height and export. Meta API calls are stubbed with canned JSON; nothing here spends credits.
Run: .venv/Scripts/python scripts/ui_check.py   (exit 1 on any failed check)"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("GHOSTLAB_UI_PORT", "8791"))
BASE = f"http://localhost:{PORT}/"
SHOTS = ROOT / "work" / "ui"
VIEWPORTS = [(390, 844), (430, 932), (1440, 900)]  # phone, large phone, desktop
VIEW = ""
DEMOS = ROOT / "web" / "demos"
FILE = str(DEMOS / "bump.mp4")

INK_JS = """() => { const c=document.getElementById('overlay'); if(c.width<3) return 0;
  const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++; return n; }"""
PURPLE_JS = """() => { const c=document.getElementById('overlay'); if(c.width<3) return 0;
  const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0;
  for(let i=0;i<d.length;i+=4) if(d[i+3]>40 && d[i]>140 && d[i+2]>200 && d[i]>d[i+1]+25) n++; return n; }"""
PLOT_INK_JS = """() => { const c=document.getElementById('plot'); const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++; return n; }"""
SMALL_JS = """() => [...document.querySelectorAll('section:not([hidden]) button, section:not([hidden]) .btn, section:not([hidden]) .chip, section:not([hidden]) input:not([type=file]):not([type=range])')]
  .filter(e => e.offsetParent !== null).map(e => [e.textContent.trim() || e.id || e.type, e.getBoundingClientRect().height])
  .filter(([, h]) => h < 44)"""
SCREEN_LOG = """document.addEventListener('DOMContentLoaded', () => { window.__s = [document.body.dataset.screen];
  new MutationObserver(() => { const s = document.body.dataset.screen; if (window.__s.at(-1) !== s) window.__s.push(s); })
    .observe(document.body, {attributes: true, attributeFilter: ['data-screen']}); });"""

failures, report = [], {}


def check(name, ok, detail=""):
    report[name] = "ok" if ok else f"FAIL {detail}"
    if not ok:
        failures.append(name)


def demo(name, live=False):
    d = json.loads((DEMOS / f"{name}.json").read_text(encoding="utf-8"))
    if live:
        d["demo"] = False
    return d


def layout(page, name):
    name = f"{name}{VIEW}"
    check(f"{name}: no horizontal overflow", page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0)
    small = page.evaluate(SMALL_JS)
    check(f"{name}: touch targets >= 44px", not small, str(small))


DOC_SHOTS = {"capture", "analysing", "verdict", "verdict_refused", "playground"}  # filenames README.md uses
EXPORT_DOCS = "--export-docs" in sys.argv


def shot(page, name):
    page.wait_for_timeout(900)  # let fade-in transitions finish before capturing
    page.screenshot(path=str(SHOTS / f"ui_{name}{VIEW}.png"))
    if EXPORT_DOCS and VIEW == "_390x844" and name in DOC_SHOTS:
        out = ROOT / "docs" / "img"
        out.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out / f"{name}.png"))


def freeze(page, t):
    page.evaluate(f"() => {{ const v=document.getElementById('video'); v.pause(); v.currentTime={t}; }}")
    page.wait_for_timeout(700)


def new_page(ctx, errors, stub=True):
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(SCREEN_LOG)
    return page


def stub_identify(page, ident_of, delay=0.5, status=200, body=None):
    def handler(route):
        time.sleep(delay)
        if status != 200:
            return route.fulfill(status=status, content_type="application/json", body=json.dumps(body))
        d = ident_of
        route.fulfill(status=200, content_type="application/json", body=json.dumps(
            {"id": "0" * 32, "identification": d["identification"], "video": "/demos/drop.mp4", "clip": d["clip"]}))
    page.route("**/api/identify", handler)


def stub_analyze(page, result, calls, delay=0.8):
    def handler(route):
        calls.append(json.loads(route.request.post_data))
        time.sleep(delay)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))
    page.route("**/api/analyze", handler)


def scenario_demo_and_verdict(ctx):
    errors = []
    page = new_page(ctx, errors)
    page.goto(BASE)
    page.wait_for_selector('body[data-screen="capture"]')
    page.wait_for_selector("[data-demo]")
    layout(page, "capture"); shot(page, "capture")
    page.click('[data-demo="drop"]')
    page.wait_for_selector('body[data-screen="verdict"]', timeout=3000)
    check("demo skips confirm", page.evaluate("window.__s") == ["capture", "verdict"], str(page.evaluate("window.__s")))
    page.wait_for_timeout(1200); freeze(page, 0.9)
    check("verdict: certified badge", page.inner_text(".badge") == "CERTIFIED")
    check("verdict: off by", "off by" in page.inner_text(".off"))
    check("verdict: sample tag", page.is_visible(".tag"))
    check("verdict: what-if offered", page.is_visible("#to-playground"))
    check("verdict: ghost ink", page.evaluate(INK_JS) > 0)
    check("verdict: video decodes", page.evaluate("document.getElementById('video').readyState") >= 2)
    check("verdict: sheet closed", not page.is_visible(".sheet-body"))
    layout(page, "verdict"); shot(page, "verdict")
    page.click(".handle")
    page.wait_for_selector(".sheet-body", state="visible"); page.wait_for_timeout(300)
    check("verdict: chart ink", page.evaluate(PLOT_INK_JS) > 0)
    check("verdict: numbers + explanation", "Measured" in page.inner_text("#numbers") and page.inner_text("#words") != "")
    layout(page, "verdict sheet open"); shot(page, "verdict_sheet")
    page.click("#replay"); page.wait_for_timeout(300)
    check("verdict: console clean", not errors, str(errors))
    page.close()

    # Refused: bump is refused by the real twin test. No numbers until "Show anyway", no playground.
    errors = []
    page = new_page(ctx, errors)
    page.goto(BASE); page.wait_for_selector("[data-demo]")
    page.click('[data-demo="bump"]'); page.wait_for_selector('body[data-screen="verdict"]')
    page.wait_for_timeout(800)
    check("refused: badge", page.inner_text(".badge") == "REFUSED")
    check("refused: reason shown", len(page.inner_text(".reason")) > 20)
    check("refused: no playground", not page.is_visible("#to-playground"))
    check("refused: film again offered", page.is_visible("#film-again-v"))
    page.click(".handle"); page.wait_for_selector(".sheet-body", state="visible")
    check("refused: numbers withheld", "withheld" in page.inner_text("#numbers") and not page.is_visible("#untrusted"))
    page.click("#showany")
    check("refused: show anyway reveals", page.is_visible("#untrusted"))
    shot(page, "verdict_refused")
    page.click("#film-again-v"); page.wait_for_selector('body[data-screen="capture"]')
    check("refused: console clean", not errors, str(errors))
    page.close()


def scenario_upload_flow(ctx):
    errors = []
    page = new_page(ctx, errors)
    live = demo("drop", live=True)
    calls = []
    stub_identify(page, live)
    stub_analyze(page, live, calls)
    page.goto(BASE); page.wait_for_selector("[data-demo]")
    page.set_input_files("#film-input", FILE)
    page.wait_for_selector('body[data-screen="confirm"]', timeout=5000)
    seen = page.evaluate("window.__s")
    check("upload: analysing then confirm", seen[:3] == ["capture", "analysing", "confirm"], str(seen))
    page.wait_for_timeout(500)
    check("confirm: detected label", "Detected" in page.inner_text(".detected"))
    check("confirm: size chips", page.locator(".sizes .chip").count() >= 4)
    check("confirm: guess preselected", page.locator(".sizes .chip.on").count() == 1)
    layout(page, "confirm"); shot(page, "confirm")
    page.click('[data-size="custom"]')
    for bad in ("0", "-5"):
        page.fill("#custom-cm", bad); page.click("#confirm-go")
        check(f"confirm: custom {bad} rejected", "centimetres" in page.inner_text("section[data-screen=confirm] .msg") and not calls)
    page.fill("#custom-cm", "7")
    page.dblclick("#confirm-go")
    page.wait_for_selector('body[data-screen="analysing"]', timeout=3000)
    page.wait_for_function("document.querySelector('.status-text').textContent.includes('Drawing')", timeout=8000)
    page.wait_for_timeout(2200)
    check("analysing: ghost ink", page.evaluate(INK_JS) > 0)
    layout(page, "analysing"); shot(page, "analysing")
    page.wait_for_selector('body[data-screen="verdict"]', timeout=8000)
    check("confirm: exactly one analyze on double tap", len(calls) == 1, str(len(calls)))
    check("confirm: custom size sent in metres", calls and abs(calls[0]["size_m"] - 0.07) < 1e-9, str(calls))
    check("upload: live result has no sample tag", not page.is_visible(".tag"))
    check("upload: console clean", not errors, str(errors))
    page.close()


def scenario_errors(ctx):
    errors = []
    page = new_page(ctx, errors)
    stub_identify(page, None, delay=0.2, status=400, body={"detail": "That file could not be read as a video."})
    page.goto(BASE); page.wait_for_selector("[data-demo]")
    page.set_input_files("#upload-input", FILE)
    page.wait_for_selector(".err:not([hidden])", timeout=5000)
    check("error: message shown", "could not be read" in page.inner_text(".err-text"))
    check("error: film again visible", page.is_visible("#film-again"))
    layout(page, "analysing error"); shot(page, "analysing_error")
    page.click("#film-again"); page.wait_for_selector('body[data-screen="capture"]')
    page.close()

    # SAM found nothing: pipeline returns {"error": ...} with HTTP 200
    page = new_page(ctx, errors)
    live = demo("drop", live=True)
    stub_identify(page, live, delay=0.2)
    stub_analyze(page, {"error": "SAM found nothing usable", "identification": live["identification"], "warnings": []}, [], delay=0.2)
    page.goto(BASE); page.wait_for_selector("[data-demo]")
    page.set_input_files("#film-input", FILE)
    page.wait_for_selector('body[data-screen="confirm"]'); page.click("#confirm-go")
    page.wait_for_selector(".err:not([hidden])", timeout=5000)
    check("sam-empty: reason and film again", "SAM found nothing" in page.inner_text(".err-text") and page.is_visible("#film-again"))
    check("errors: console clean", not errors, str(errors))
    page.close()


def scenario_playground(ctx):
    errors = []
    page = new_page(ctx, errors)
    page.add_init_script("navigator.mediaDevices.getUserMedia = () => Promise.reject(new Error('denied'));")
    page.goto(BASE); page.wait_for_selector("[data-demo]")
    page.click('[data-demo="drop"]'); page.wait_for_selector('body[data-screen="verdict"]')
    page.click("#to-playground"); page.wait_for_selector('body[data-screen="playground"]')
    page.wait_for_timeout(800)
    bounce = demo("drop")["chosen"] == "bounce"
    check("playground: bounciness slider only for bounces", page.is_visible("#erow") == bounce, f"chosen={demo('drop')['chosen']}")
    page.click('[data-planet="Moon"]')
    check("playground: moon g", abs(float(page.input_value("#g")) - 1.6) < 0.06, page.input_value("#g"))
    page.wait_for_timeout(900); freeze(page, 1.2)
    check("playground: what-if ghost drawn", page.evaluate(PURPLE_JS) > 0)
    check("playground: ghost ink", page.evaluate(INK_JS) > 0)
    layout(page, "playground"); shot(page, "playground")
    page.fill("#say", "what if this was on Mars"); page.press("#say", "Enter")
    page.wait_for_function("Math.abs(parseFloat(document.getElementById('g').value) - 3.7) < 0.06", timeout=4000)
    check("playground: typed what-if moves slider", "Heard" in page.inner_text(".heard"), page.inner_text(".heard"))
    page.dispatch_event("#mic", "pointerdown")
    page.wait_for_function("document.querySelector('section[data-screen=playground] .msg').textContent.includes('Microphone unavailable')", timeout=3000)
    check("playground: mic denied shows message", True)
    page.click('[data-planet="Jupiter"]')
    check("playground: still works after mic denied", abs(float(page.input_value("#g")) - 24.8) < 0.06)
    # Export in the browser: non-empty video blob
    res = page.evaluate("""async () => { const m = await import('/js/export.js');
      try { const b = await m.exportClip(document.getElementById('video'), document.getElementById('overlay')); return {size: b.size, type: b.type}; }
      catch (e) { return {error: e.message}; } }""")
    report["export"] = res
    check("export: non-empty video blob", res.get("size", 0) > 0 and res.get("type", "").startswith("video/"), str(res))
    check("playground: console clean", not errors, str(errors))
    page.click("#back"); page.wait_for_selector('body[data-screen="verdict"]')
    page.close()


srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "ghostlab.server:app", "--port", str(PORT)],
                       cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/api/status"); break
        except Exception:
            time.sleep(0.2)
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        for w, h in VIEWPORTS:
            VIEW = f"_{w}x{h}"
            desktop = w > 600
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if desktop else 2,
                                has_touch=not desktop, is_mobile=not desktop)
            for scenario in (scenario_demo_and_verdict, scenario_upload_flow, scenario_errors, scenario_playground):
                try:
                    scenario(ctx)
                except Exception as e:  # a crashed scenario is a failure, not a skip
                    check(f"{VIEW} {scenario.__name__} crashed", False, repr(e)[:300])
            ctx.close()
        b.close()
finally:
    srv.terminate()

print(json.dumps(report, indent=1))
print("FAILED:" if failures else "ALL OK", failures if failures else "")
sys.exit(1 if failures else 0)
