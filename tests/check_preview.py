"""A quick look at a RUNNING dashboard (for example the live preview): health, the five pages in both languages, no raw translation
keys on the screen, no JavaScript errors and - when a finished dubbing job exists - that its editor table opens.

    python tests/check_preview.py [http://127.0.0.1:8000]
"""
import sys

from lib import *  # noqa: F401,F403
import httpx
from playwright.sync_api import sync_playwright

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
c = Checker("live preview")
h = httpx.get(base + "/api/health", timeout=10).json()
print(h)
c.check(h["version"] == VERSION and h["ui_ok"], f"the server runs v{VERSION} and its UI files match it", str(h))
jobs = httpx.get(base + "/api/jobs", timeout=10).json()["jobs"]
done = [j for j in jobs if j["kind"] == "dub" and j["status"] == "done" and j.get("segment_count")]
print(f"{len(jobs)} job(s), {len(done)} finished dubbing job(s) with lines")
errs = []
RAW_KEYS = """() => [...document.querySelectorAll('[data-i18n]')]
  .map((e) => e.textContent.trim()).filter((t) => /^[a-z0-9]+(\\.[a-z0-9]+)+$/i.test(t)).slice(0, 5)"""
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for lang in ("km", "en"):
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','dark');")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        pg.goto(base + "/", wait_until="networkidle")
        for page in ("dub", "tts", "terms", "history", "settings"):
            pg.click(f"#nav button[data-page='{page}']")
            pg.wait_for_timeout(300)
            c.check(pg.locator(f"#page-{page}.active").count() == 1, f"[{lang}] page '{page}' opens")
            raw = pg.evaluate(RAW_KEYS)
            c.check(not raw, f"[{lang}] page '{page}': no raw translation keys on the screen", str(raw))
        if done and lang == "km":
            j = done[0]
            pg.click("#nav button[data-page='history']")
            pg.wait_for_selector("[data-open]")
            pg.wait_for_timeout(500)
            pg.evaluate("(id) => { const b = [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id); if (b) b.click(); }", j["id"])
            pg.wait_for_selector("#dub-result .seg-row", timeout=15000)
            n = pg.locator("#dub-result .seg-row").count()
            c.check(n == j["segment_count"], f"job {j['id']} opens with all {j['segment_count']} lines in the editor table", str(n))
        ctx.close()
    b.close()
c.check(not errs, "no JavaScript errors", "; ".join(errs[:3]))
sys.exit(c.done())
