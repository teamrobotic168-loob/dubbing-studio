"""Browser tests for v1.6.0: the menu (sidebar) slides out and in; the video panels (Sync Preview, MP4) are fixed on the right."""
import json
import sys

from lib import *  # noqa: E402,F401,F403
from ui_setup import build  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

c = Checker("Menu + docked video")
srv = build(8017, "layout")
JID, VID = srv.new_job_id, srv.video_job_id
SHOTS = WORK / "shots"
SHOTS.mkdir(exist_ok=True)
errors = []

FAKE_YT = open(TESTS / "test_follow.py", encoding="utf-8").read().split('FAKE_YT = """')[1].split('"""')[0]


def new_page(b, lang="en", theme="dark", w=1440, h=900, fake_yt=False, storage=None):
    ctx = b.new_context(viewport={"width": w, "height": h})
    init = f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}');"
    for k, v in (storage or {}).items():
        init += f"localStorage.setItem('{k}', {json.dumps(v)});"
    ctx.add_init_script(init)
    if fake_yt:
        ctx.add_init_script(FAKE_YT)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
    pg.on("dialog", lambda d: d.accept())
    return ctx, pg


def open_job(pg, job_id):
    pg.goto(srv.url + "/#history")
    pg.wait_for_selector("[data-open]", timeout=10000)
    pg.wait_for_timeout(500)
    pg.evaluate("(id) => { const b = [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id); b.click(); }", job_id)
    pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
    pg.wait_for_timeout(700)


def rect(pg, sel):
    return pg.evaluate("(s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, r: r.right, b: r.bottom }; }", sel)


def css(pg, sel, prop):
    return pg.evaluate("([s, p]) => getComputedStyle(document.querySelector(s))[p]", [sel, prop])


def settings(pg):
    pg.wait_for_timeout(450)
    return json.loads(pg.evaluate("localStorage.getItem('kds_settings') || '{}'"))


def in_view(pg, i):
    r = pg.evaluate("(i) => { const e = document.querySelectorAll('#dub-result .seg-row')[i].getBoundingClientRect(); return [e.top, e.bottom, window.innerHeight]; }", i)
    return r[0] >= 100 and r[1] <= r[2] - 70, r


try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])

        # ============================================================== A. the menu slides out and in
        ctx, pg = new_page(b)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(1200)
        c.check(pg.locator("#side-toggle").is_visible() and pg.locator("#side-toggle").get_attribute("aria-expanded") == "true", "a toggle button for the menu is shown (menu open)")
        sb, mn = rect(pg, "#sidebar"), rect(pg, ".main")
        c.check(abs(sb["x"]) < 1 and abs(sb["w"] - 264) < 2 and abs(mn["x"] - 264) < 2, "open: the menu is 264 px wide and the content starts after it", f"{sb} {mn}")
        c.check(pg.locator("#side-toggle").get_attribute("title") == "Hide the menu", "tooltip: Hide the menu")
        pg.screenshot(path=str(SHOTS / "menu_open.png"))
        pg.locator("#side-toggle").click()
        pg.wait_for_timeout(600)
        mn = rect(pg, ".main")
        c.check(pg.evaluate("document.documentElement.classList.contains('side-collapsed')") and abs(mn["x"]) < 1 and mn["w"] > 1430, "click: the menu slides out and the content takes the whole width", str(mn))
        c.check(css(pg, "#sidebar", "visibility") == "hidden" and css(pg, "#nav button", "visibility") == "hidden", "the hidden menu cannot be reached with the keyboard (visibility: hidden)")
        c.check(pg.locator("#side-toggle").get_attribute("aria-expanded") == "false" and pg.locator("#side-toggle").get_attribute("title") == "Show the menu", "the toggle says 'Show the menu' (aria-expanded=false)")
        c.check(pg.evaluate("localStorage.getItem('kds_side')") == "1", "the choice is remembered")
        pg.screenshot(path=str(SHOTS / "menu_closed.png"))
        # remembered after a reload - and already collapsed when the page is first drawn
        pg.goto(srv.url + "/#dub", wait_until="domcontentloaded")
        first = pg.evaluate("() => ({ cls: document.documentElement.classList.contains('side-collapsed'), cols: getComputedStyle(document.querySelector('.app')).gridTemplateColumns })")
        pg.wait_for_timeout(900)
        c.check(first["cls"] and first["cols"].startswith("0px"), "after a reload the menu is collapsed from the first moment (no flash)", str(first))
        c.check(pg.evaluate("document.documentElement.classList.contains('anim')"), "(the slide animation is switched on after the first paint)")
        # the page title bar is still usable: navigate through the keyboard-free route (toggle open, click History)
        pg.locator("#side-toggle").click()
        pg.wait_for_timeout(600)
        sb = rect(pg, "#sidebar")
        c.check(css(pg, "#sidebar", "visibility") == "visible" and abs(sb["x"]) < 1 and pg.evaluate("localStorage.getItem('kds_side')") == "0", "click again: the menu slides back in", str(sb))
        pg.locator("#nav button[data-page=history]").click()
        pg.wait_for_timeout(400)
        c.check(pg.locator("#page-history.active").count() == 1, "the menu works after it came back")
        pg.locator("#lang-switch button[data-lang=km]").click()
        pg.wait_for_timeout(300)
        c.check(pg.locator("#side-toggle").get_attribute("title") == "លាក់ម៉ឺនុយ", "the tooltip follows the language (Khmer)", pg.locator("#side-toggle").get_attribute("title"))
        ctx.close()
        # phone: the menu is a top bar; no toggle, and a saved 'collapsed' state does not hide it
        ctx, pg = new_page(b, w=390, h=844, storage={"kds_side": "1"})
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(1000)
        c.check(not pg.locator("#side-toggle").is_visible() and css(pg, "#sidebar", "visibility") == "visible" and rect(pg, "#sidebar")["h"] > 30, "phone: no toggle, the menu bar stays")
        ctx.close()

        # ============================================================== B. the MP4 video is fixed on the right
        ctx, pg = new_page(b)
        open_job(pg, VID)
        pnl = rect(pg, "#mp4-panel")
        c.check(pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')") and css(pg, "#mp4-panel", "position") == "fixed", "the MP4 video panel is docked (position: fixed)")
        c.check(abs(pnl["r"] - (1440 - 18)) < 1.5 and abs(pnl["y"] - 104) < 1.5 and 380 < pnl["w"] < 400, "…on the right (18 px from the edge), under the title bar, ~27% of the width wide", str(pnl))
        c.check(pg.evaluate("document.body.classList.contains('has-dock')"), "the page makes room (body.has-dock)")
        pad = float(css(pg, ".main", "paddingRight").replace("px", ""))
        c.check(abs(pad - (pnl["w"] + 52)) < 2, "…by a right padding of the panel width + 52 px", str(pad))
        tbl = rect(pg, "#dub-result .seg-table")
        c.check(tbl["r"] < pnl["x"] - 8, "the table does not run under the video", f"{tbl['r']} < {pnl['x']}")
        tb = rect(pg, "#theme-btn")
        c.check(abs(tb["r"] - (1440 - 34)) < 1.5, "the language / theme buttons stay at the far right (above the panel), as on every other page", str(tb))
        cols = css(pg, "#page-dub .grid-2", "gridTemplateColumns").split()
        c.check(len(cols) == 1, "menu open + panel: the voice / translation cards are stacked (the column is narrow)", str(cols))
        c.check(css(pg, ".topbar", "backgroundAttachment").startswith("fixed") and css(pg, ".topbar", "maskImage") != "none", "the title bar is drawn like the page background and fades out at its bottom edge")
        # fixed while scrolling
        tops = []
        for y in (0, 600, 1500, 2500):
            pg.evaluate("(y) => window.scrollTo(0, y)", y)
            pg.wait_for_timeout(250)
            tops.append(round(rect(pg, "#mp4-panel")["y"], 1))
        c.check(max(tops) - min(tops) < 1.5, "scrolling up and down: the video does not move", str(tops))
        c.check(pg.locator("#mp4-panel video").is_visible(), "…and stays visible")
        pg.evaluate("window.scrollTo(0, 0)")
        c.check(pg.locator("#mp4-panel .dock-head [data-dock=pin]").get_attribute("aria-pressed") == "true" and pg.locator("#mp4-panel [data-dock=pin]").get_attribute("title") == "Unpin (back into the page)", "pin button shows 'pinned' and offers 'Unpin'")
        # minimize
        pg.locator("#mp4-panel [data-dock=min]").click()
        pg.wait_for_timeout(200)
        c.check(pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-min')") and rect(pg, "#mp4-panel")["h"] < 70 and css(pg, "#mp4-panel .dock-body", "display") == "none", "minimize: only the title bar remains")
        c.check(settings(pg)["ui"]["dockMin"] is True, "…and it is remembered")
        pg.locator("#mp4-panel [data-dock=min]").click()
        pg.wait_for_timeout(200)
        c.check(rect(pg, "#mp4-panel")["h"] > 200, "restore: the video is back")
        pg.screenshot(path=str(SHOTS / "dock_mp4.png"))
        # unpin -> back into the page
        pg.locator("#mp4-panel [data-dock=pin]").click()
        pg.wait_for_timeout(300)
        c.check(not pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')") and css(pg, "#mp4-panel", "position") == "static" and not pg.evaluate("document.body.classList.contains('has-dock')"), "unpin: the video goes back into the page and the space is released")
        c.check(abs(float(css(pg, ".main", "paddingRight").replace("px", "")) - 34) < 1, "…the page is full width again")
        c.check(pg.locator("#mp4-panel [data-dock=pin]").get_attribute("title") == "Pin to the right (fixed)" and settings(pg)["ui"]["dock"] is False, "…the button offers 'Pin to the right' and the choice is remembered")
        # remembered after reload
        open_job(pg, VID)
        c.check(not pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')"), "after a reload the video stays in the page (choice remembered)")
        pg.locator("#mp4-panel [data-dock=pin]").click()
        pg.wait_for_timeout(300)
        c.check(pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')"), "pin again: docked")
        ctx.close()

        # an old browser profile (v1.5.0: no `ui` saved) gets the dock by default
        ctx, pg = new_page(b, storage={"kds_settings": json.dumps({"output": {"format": "video", "sync": "fit", "max_height": 1080}, "subs": {"en": True, "follow": True}})})
        open_job(pg, VID)
        c.check(pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')"), "settings saved by an older version (no 'ui') get the dock by default")
        ctx.close()

        # ============================================================== C. the table makes use of the room: menu hidden + video docked
        ctx, pg = new_page(b)
        open_job(pg, VID)
        w_open = rect(pg, "#dub-result .seg-table")["w"]
        areas_open = css(pg, "#dub-result .seg-row", "gridTemplateAreas")
        pg.locator("#side-toggle").click()
        pg.wait_for_timeout(700)
        w_closed = rect(pg, "#dub-result .seg-table")["w"]
        areas_closed = css(pg, "#dub-result .seg-row", "gridTemplateAreas")
        c.check(w_closed > w_open + 230, "hiding the menu gives the table ~264 px more", f"{w_open:.0f} -> {w_closed:.0f}")
        c.check('"idx go"' in areas_open and '"idx tm en km go"' in areas_closed, "…enough to switch from the stacked layout to the side-by-side layout", f"{areas_open} | {areas_closed}")
        pg.screenshot(path=str(SHOTS / "dock_and_menu_closed.png"))
        tbl, pnl = rect(pg, "#dub-result .seg-table"), rect(pg, "#mp4-panel")
        c.check(tbl["r"] < pnl["x"] - 8, "table and docked video side by side without overlap", f"{tbl['r']} < {pnl['x']}")
        cols = css(pg, "#page-dub .grid-2", "gridTemplateColumns").split()
        c.check(len(cols) == 2, "menu hidden + panel: the two cards are side by side again", str(cols))
        ctx.close()

        # ============================================================== D. narrow window / phone: the players stay in the page
        for w, h, label in [(1100, 800, "narrow window"), (390, 844, "phone")]:
            ctx, pg = new_page(b, w=w, h=h)
            open_job(pg, VID)
            c.check(not pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')") and css(pg, "#mp4-panel", "position") == "static"
                    and not pg.evaluate("document.body.classList.contains('has-dock')"), f"{label}: the video stays inside the page (no room for a side panel)")
            c.check(css(pg, "#mp4-panel .dock-head", "display") == "none", f"{label}: no dock header")
            ctx.close()

        # resizing the window across the 1180 px limit switches the panel at once
        ctx, pg = new_page(b)
        open_job(pg, VID)
        c.check(css(pg, "#mp4-panel", "position") == "fixed", "(1440 px wide: docked)")
        pg.set_viewport_size({"width": 1100, "height": 800})
        pg.wait_for_timeout(500)
        c.check(css(pg, "#mp4-panel", "position") == "static" and not pg.evaluate("document.body.classList.contains('has-dock')") and not pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')"),
                "making the window narrower (< 1180 px): the video goes back into the page, the space is released")
        pg.set_viewport_size({"width": 1500, "height": 900})
        pg.wait_for_timeout(500)
        c.check(css(pg, "#mp4-panel", "position") == "fixed" and pg.evaluate("document.body.classList.contains('has-dock')"), "making it wider again: docked again")
        ctx.close()

        # ============================================================== E. Sync Preview is docked on the right (fake YouTube player)
        ctx, pg = new_page(b, fake_yt=True)
        open_job(pg, VID)
        c.check(pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')"), "(before: the MP4 video holds the dock)")
        pg.locator("#btn-sync").click()
        pg.wait_for_selector("#sync-panel #yt-player", timeout=5000)
        pg.wait_for_timeout(500)
        sp = rect(pg, "#sync-panel")
        c.check(pg.evaluate("document.querySelector('#sync-panel').classList.contains('is-docked')") and css(pg, "#sync-panel", "position") == "fixed" and abs(sp["r"] - 1422) < 1.5 and abs(sp["y"] - 104) < 1.5,
                "Open Sync Preview: the YouTube player is fixed on the right", str(sp))
        c.check(css(pg, "#mp4-panel", "position") == "static" and pg.evaluate("document.querySelector('#mp4-panel').classList.contains('dock-wait')") and css(pg, "#mp4-panel [data-dock=pin]", "display") == "none",
                "…and the MP4 video steps back into the page (one player at a time)")
        c.check(pg.locator("#sync-panel #sub-overlay").count() == 1 and pg.locator("#sync-panel #sync-subs .tog").count() == 4, "the subtitle overlay and the four switches are in the panel")
        tops = []
        for y in (0, 900, 2200):
            pg.evaluate("(y) => window.scrollTo(0, y)", y)
            pg.wait_for_timeout(250)
            tops.append(round(rect(pg, "#sync-panel")["y"], 1))
        c.check(max(tops) - min(tops) < 1.5 and pg.locator("#sync-panel #yt-player").is_visible(), "scrolling up and down: the YouTube player stays on the screen", str(tops))
        pg.screenshot(path=str(SHOTS / "dock_sync.png"))
        # the table follows while the video is docked (the video is on the screen, but it never scrolls away)
        segs = srv.api("GET", f"/api/jobs/{VID}").json()["segments"]
        pg.evaluate("window.scrollTo(0, 0)")
        pg.wait_for_timeout(500)
        pg.evaluate("window.__yt.state = 2")
        pg.evaluate("(t) => { window.__yt.t = t; }", segs[9]["start"] + 0.3)
        pg.wait_for_timeout(1700)
        ok, r = in_view(pg, 9)
        c.check(ok, "docked YouTube preview: the table still follows the playback (the video does not scroll away)", str(r))
        # minimize + close
        pg.locator("#sync-panel [data-dock=min]").click()
        pg.wait_for_timeout(200)
        c.check(rect(pg, "#sync-panel")["h"] < 70, "the YouTube panel can be minimized")
        pg.locator("#sync-panel [data-dock=min]").click()
        pg.locator("#sync-panel [data-dock=close]").click()
        pg.wait_for_timeout(400)
        c.check(pg.locator("#sync-panel").count() == 0 and pg.evaluate("document.querySelector('#mp4-panel').classList.contains('is-docked')"), "close (✕): the preview ends and the MP4 video takes the dock again")
        c.check(pg.locator("#btn-sync span").inner_text() == "Open Sync Preview", "…and the button in the page offers 'Open Sync Preview' again")
        # the table follows the docked MP4 video too
        pg.evaluate("window.scrollTo(0, 0)")
        pg.wait_for_timeout(500)
        pg.wait_for_function("(() => { const v = document.querySelector('#mp4-panel video'); return v && v.readyState >= 1; })()", timeout=20000)
        pg.evaluate("() => { const v = document.querySelector('#mp4-panel video'); v.muted = true; v.play().then(() => v.pause()); }")
        pg.wait_for_timeout(400)
        pg.evaluate("(t) => new Promise((res) => { const v = document.querySelector('#mp4-panel video'); v.addEventListener('seeked', () => res(), { once: true }); v.currentTime = t; })", segs[10]["start"] + 0.3)
        pg.wait_for_timeout(1700)
        ok, r = in_view(pg, 10)
        c.check(ok, "docked MP4 video: the table follows the playback as well", str(r))
        ctx.close()

        # ============================================================== F. page changes, Khmer + light theme
        ctx, pg = new_page(b)
        open_job(pg, VID)
        pg.locator("#nav button[data-page=settings]").click()
        pg.wait_for_timeout(500)
        c.check(not pg.evaluate("document.body.classList.contains('has-dock')") and abs(float(css(pg, ".main", "paddingRight").replace("px", "")) - 34) < 1, "on other pages (Settings) there is no reserved space")
        pg.locator("#nav button[data-page=dub]").click()
        pg.wait_for_timeout(500)
        c.check(pg.evaluate("document.body.classList.contains('has-dock')"), "…and it comes back on the Dubbing page")
        c.check(css(pg, "#mp4-panel", "position") == "fixed" and abs(rect(pg, "#mp4-panel")["y"] - 104) < 1.5, "…with the video fixed again")
        ctx.close()
        # dark / light / Khmer screenshot
        ctx, pg = new_page(b, lang="km", theme="light")
        open_job(pg, VID)
        pg.locator("#side-toggle").click()
        pg.wait_for_timeout(700)
        pg.screenshot(path=str(SHOTS / "dock_km_light.png"))
        c.check(pg.locator("#mp4-panel [data-dock=pin]").get_attribute("title") == "ដោះចេញ (ត្រឡប់ទៅក្នុងទំព័រ)", "Khmer tooltips on the dock")
        ctx.close()

        # ============================================================== G. the dock disappears with the result card (Regenerate)
        # (last: an audio-only regenerate drops the MP4 of the fixture job)
        ctx, pg = new_page(b)
        open_job(pg, VID)
        c.check(pg.evaluate("document.body.classList.contains('has-dock')"), "(docked)")
        pg.locator("#dub-result .seg-row").nth(1).locator("select.vsel").select_option("km-KH-PisethNeural")
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(300)
        c.check(not pg.evaluate("document.body.classList.contains('has-dock')"), "while the audio is being rebuilt (result card hidden) the page gets its full width back")
        pg.wait_for_function("() => { const r = document.querySelector('#dub-result'); return r && !r.classList.contains('hidden') && r.querySelector('.seg-row'); }", timeout=180000)
        pg.wait_for_timeout(500)
        c.check(pg.locator("#mp4-panel").count() == 0 and not pg.evaluate("document.body.classList.contains('has-dock')"), "(audio-only regenerate drops the MP4: nothing is docked)")
        ctx.close()
        b.close()
finally:
    srv.stop()

real = [e for e in errors if "favicon" not in e]
c.check(not real, "no JavaScript errors in any page", "; ".join(real[:4]))
sys.exit(c.done())
