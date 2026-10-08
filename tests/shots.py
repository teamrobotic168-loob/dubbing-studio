"""Screenshots of the dashboard for a visual check - the "look at it with your own eyes" step of the workflow.

    python tests/shots.py                                  start a fixture server (the demo jobs, VoxCPM2 stubbed) and photograph it in 4 screen sizes
    python tests/shots.py --url http://127.0.0.1:8000      photograph a dashboard that is already running
    python tests/shots.py --pages dub,history --sizes 1440x900 --langs en --themes dark --out /tmp/shots
    python tests/shots.py --job 6b011b123f                 also open that finished job from History and photograph the result

PNG files go to  <WORK>/shots/shot_<page>_<size>_<lang>_<theme>.png  (or --out).  An AI agent looks at them with its image viewer,
a person opens them.  Look for: text that is cut off or overlaps, a raw key such as "set.vox.install", an empty area, something that
breaks when the window is narrow (390 px = a phone) or wide (1920 px).
"""
import argparse
import sys
from pathlib import Path

from lib import WORK
from playwright.sync_api import sync_playwright

ALL_PAGES = ["dub", "tts", "terms", "history", "settings"]
ALL_SIZES = ["1440x900", "1366x768", "1920x1080", "390x844"]
CLICK_NAV = "(p) => { const b = document.querySelector(`#nav button[data-page='${p}']`); if (b) b.click(); }"          # through the DOM: a phone hides the menu
OPEN_JOB = "(id) => { const b = [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id); if (b) b.click(); }"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="a running dashboard (default: start a fixture server on port 8070)")
    ap.add_argument("--pages", default=",".join(ALL_PAGES))
    ap.add_argument("--sizes", default=",".join(ALL_SIZES))
    ap.add_argument("--langs", default="km,en")
    ap.add_argument("--themes", default="dark,light")
    ap.add_argument("--job", help="id of a finished job to open from History (fixture server: the English demo job by default)")
    ap.add_argument("--out", default=str(WORK / "shots"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    srv, url, job = None, a.url, a.job
    if not url:
        from ui_setup import build
        srv = build(8070, "shots")
        url, job = srv.url, job or "6b011b123f"
    url = url.rstrip("/")
    errors, taken = [], []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for size in a.sizes.split(","):
                w, h = (int(x) for x in size.split("x"))
                for lang in a.langs.split(","):
                    for theme in a.themes.split(","):
                        ctx = b.new_context(viewport={"width": w, "height": h})
                        ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}');")
                        pg = ctx.new_page()
                        pg.on("pageerror", lambda e: errors.append(str(e)))
                        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
                        pg.goto(url + "/", wait_until="networkidle")
                        for page in a.pages.split(","):
                            pg.evaluate(CLICK_NAV, page)
                            pg.wait_for_timeout(350)
                            f = out / f"shot_{page}_{size}_{lang}_{theme}.png"
                            pg.screenshot(path=str(f), full_page=True)
                            taken.append(f)
                        if job:
                            pg.evaluate(CLICK_NAV, "history")
                            pg.wait_for_selector("[data-open]", timeout=10000)
                            pg.evaluate(OPEN_JOB, job)
                            pg.wait_for_selector("#dub-result .seg-row", timeout=15000)
                            pg.wait_for_timeout(500)
                            f = out / f"shot_job_{size}_{lang}_{theme}.png"
                            pg.screenshot(path=str(f), full_page=True)
                            taken.append(f)
                        ctx.close()
            b.close()
    finally:
        if srv:
            srv.stop()
    print(f"{len(taken)} screenshot(s) in {out}")
    for f in taken[:6]:
        print("  ", f.name)
    if len(taken) > 6:
        print(f"   ... and {len(taken) - 6} more")
    print("JavaScript errors:", errors[:5] if errors else "none")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
