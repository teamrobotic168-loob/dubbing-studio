"""Browser tests for v1.4.x: the table follows the playback (audio / MP4 video / YouTube preview), MP4 quality setting."""
import json
import re
import sys
import time

from lib import *  # noqa: E402,F401,F403
from ui_setup import build  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

c = Checker("Follow the playback + video quality")
srv = build(8014, "follow")
JID, VID = srv.new_job_id, srv.video_job_id
errors = []
captured = []
SHOTS = WORK / "shots"
SHOTS.mkdir(exist_ok=True)

FAKE_YT = """
window.__yt = { t: 0, state: -1, calls: [] };
window.YT = {
  PlayerState: { UNSTARTED: -1, ENDED: 0, PLAYING: 1, PAUSED: 2, BUFFERING: 3, CUED: 5 },
  Player: class {
    constructor(id, opts) { this.opts = opts; window.__yt.player = this; setTimeout(() => { try { opts.events && opts.events.onReady && opts.events.onReady({ target: this }); } catch (e) {} }, 10); }
    getCurrentTime() { return window.__yt.t; }
    getPlayerState() { return window.__yt.state; }
    seekTo(t, allow) { window.__yt.calls.push(['seekTo', t]); window.__yt.t = t; }
    playVideo() { window.__yt.calls.push(['playVideo']); window.__yt.state = 1; }
    pauseVideo() { window.__yt.state = 2; }
    mute() {} unMute() {} destroy() {}
  }
};
"""


def new_page(b, lang="en", theme="dark", w=1440, h=900, fake_yt=False):
    ctx = b.new_context(viewport={"width": w, "height": h})
    ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}');")
    # these tests are about the inline players; the docked (fixed) variant is covered by test_layout.py
    ctx.add_init_script("if (!localStorage.getItem('kds_settings')) localStorage.setItem('kds_settings', JSON.stringify({ ui: { dock: false } }));")
    if fake_yt:
        ctx.add_init_script(FAKE_YT)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
    pg.on("dialog", lambda d: d.accept())
    pg.on("request", lambda r: captured.append(r) if r.method == "POST" and "/regenerate" in r.url else None)
    return ctx, pg


def open_job(pg, job_id):
    pg.goto(srv.url + "/#history")
    pg.wait_for_selector("[data-open]", timeout=10000)
    pg.wait_for_timeout(500)
    pg.evaluate("(id) => { const b = [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id); b.click(); }", job_id)
    pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
    pg.wait_for_timeout(700)


def rows(pg):
    return pg.locator("#dub-result .seg-row")


def active_idx(pg):
    return pg.evaluate("() => [...document.querySelectorAll('#dub-result .seg-row')].map((r, i) => r.classList.contains('active') ? i : -1).filter((i) => i >= 0)")


def expected_row(segs, t):
    starts = [min(s["start"], s["out_start"] if s.get("out_start") is not None else s["start"]) for s in segs]
    k = -1
    for i, st in enumerate(starts):
        if st <= t + 0.05:
            k = i
        else:
            break
    return k


def in_view(pg, i):
    r = pg.evaluate("(i) => { const e = document.querySelectorAll('#dub-result .seg-row')[i].getBoundingClientRect(); return [e.top, e.bottom, window.innerHeight]; }", i)
    return r[0] >= 100 and r[1] <= r[2] - 70, r


def scroll_top(pg):
    return pg.evaluate("window.scrollY")


def settle(pg, ms=1500):
    pg.wait_for_timeout(ms)


try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])

        # ============================================================== A. the audio player marks the line it has reached
        ctx, pg = new_page(b)
        open_job(pg, JID)
        segs = srv.api("GET", f"/api/jobs/{JID}").json()["segments"]
        n = len(segs)
        pg.wait_for_function("document.querySelector('#dub-audio').readyState >= 1", timeout=15000)
        c.check(pg.locator("#btn-nowline").is_hidden() and not active_idx(pg), "nothing is marked before anything plays; the 'now' button is hidden")
        c.check(pg.locator("[data-sub=follow]").get_attribute("aria-pressed") == "true", "'Follow playback' is on by default")
        for t in (0.3, 1.0, 3.2, segs[3]["start"] + 0.1, segs[7]["out_start"] + 0.5, segs[n - 1]["out_end"] + 1.0):
            pg.evaluate("(t) => new Promise((res) => { const a = document.querySelector('#dub-audio'); a.addEventListener('seeked', () => res(), { once: true }); a.currentTime = t; })", t)
            pg.wait_for_timeout(150)
            now = pg.evaluate("document.querySelector('#dub-audio').currentTime")
            exp = expected_row(segs, now)
            got = active_idx(pg)
            c.check(got == ([exp] if exp >= 0 else []), f"audio at {now:.1f}s marks line {exp + 1 if exp >= 0 else 'none'}", f"got {got}")
        pg.evaluate("(t) => new Promise((res) => { const a = document.querySelector('#dub-audio'); a.addEventListener('seeked', () => res(), { once: true }); a.currentTime = t; })", segs[4]["start"] + 0.2)
        pg.wait_for_timeout(200)
        c.check(pg.locator("#dub-result .seg-row.active").evaluate("e => e.getAttribute('aria-current')") == "true", "the marked line has aria-current")
        bs = pg.locator("#dub-result .seg-row.active").evaluate("e => getComputedStyle(e).boxShadow")
        c.check(bs and bs != "none", "the marked line has a visible frame", bs)
        txt = pg.locator("#btn-nowline").inner_text()
        c.check(re.match(rf"^Now: line 5 / {n} · \d+:\d\d$", txt) is not None and not pg.locator("#btn-nowline").is_hidden(), "the 'now' button says which line and when", txt)
        c.check(pg.locator("#dub-result .seg-row.active .idx").inner_text().strip().startswith("5"), "…and it is line 5 of the table")
        # the follow scroll: a far line comes into view
        pg.evaluate("window.scrollTo(0, 0)")
        settle(pg, 400)
        pg.evaluate("(t) => new Promise((res) => { const a = document.querySelector('#dub-audio'); a.addEventListener('seeked', () => res(), { once: true }); a.currentTime = t; })", segs[10]["start"] + 0.3)
        settle(pg)
        ok, r = in_view(pg, 10)
        c.check(ok, "moving the playhead to line 11 scrolls the table to it", str(r))
        c.check(abs((r[0] + r[1]) / 2 - r[2] / 2) < 160, "…and puts it in the middle of the screen", str(r))
        # Follow off: no scrolling
        pg.locator("[data-sub=follow]").first.click()
        pg.wait_for_timeout(450)
        st_ = json.loads(pg.evaluate("localStorage.getItem('kds_settings')"))
        c.check(st_["subs"]["follow"] is False and pg.locator("[data-sub=follow]").first.get_attribute("aria-pressed") == "false", "'Follow playback' can be turned off (and is remembered)")
        pg.evaluate("window.scrollTo(0, 0)")
        settle(pg, 400)
        y0 = scroll_top(pg)
        pg.evaluate("(t) => new Promise((res) => { const a = document.querySelector('#dub-audio'); a.addEventListener('seeked', () => res(), { once: true }); a.currentTime = t; })", segs[9]["start"] + 0.3)
        settle(pg, 900)
        c.check(abs(scroll_top(pg) - y0) < 5 and active_idx(pg) == [9], "with Follow off the line is still marked but the table does not move", f"{y0} -> {scroll_top(pg)} {active_idx(pg)}")
        # ...but the 'now' button jumps there
        pg.locator("#btn-nowline").click()
        settle(pg)
        c.check(in_view(pg, 9)[0], "the 'now' button scrolls to the playing line (even with Follow off)", str(in_view(pg, 9)[1]))
        pg.locator("[data-sub=follow]").first.click()                      # on again
        # not while typing
        pg.evaluate("window.scrollTo(0, 0)")
        settle(pg, 400)
        row_ta = rows(pg).nth(0).locator("textarea")
        row_ta.click()
        y0 = scroll_top(pg)
        pg.evaluate("(t) => new Promise((res) => { const a = document.querySelector('#dub-audio'); a.addEventListener('seeked', () => res(), { once: true }); a.currentTime = t; })", segs[11]["start"] + 0.3)
        settle(pg, 900)
        c.check(abs(scroll_top(pg) - y0) < 5 and active_idx(pg) == [11], "while the user types in the table it does not jump", f"{y0} -> {scroll_top(pg)}")
        pg.screenshot(path=str(SHOTS / "follow_audio.png"))
        ctx.close()

        # ============================================================== B. the MP4 video: marks lines, 'play this line' uses the player that is in use
        ctx, pg = new_page(b)
        open_job(pg, VID)
        vsegs = srv.api("GET", f"/api/jobs/{VID}").json()["segments"]
        pg.wait_for_function("(() => { const v = document.querySelector('#dub-result video'); return v && v.readyState >= 1; })()", timeout=20000)
        c.check(pg.locator("#dub-result .player-box .stats").inner_text().count("MP4 1080p") == 1, "the result shows the MP4 quality (1080p)", pg.locator("#dub-result .player-box .stats").inner_text())
        for t in (2.0, vsegs[2]["start"] + 0.2, vsegs[6]["out_start"] + 0.3):
            pg.evaluate("(t) => new Promise((res) => { const v = document.querySelector('#dub-result video'); v.addEventListener('seeked', () => res(), { once: true }); v.currentTime = t; })", t)
            pg.wait_for_timeout(200)
            now = pg.evaluate("document.querySelector('#dub-result video').currentTime")
            exp = expected_row(vsegs, now)
            c.check(active_idx(pg) == ([exp] if exp >= 0 else []), f"MP4 video at {now:.1f}s marks line {exp + 1}", f"got {active_idx(pg)}")
        # the user WATCHES the video (it is on the screen): the line is marked, the bar names it, but the page does not scroll the picture away
        pg.evaluate("() => { const v = document.querySelector('#dub-result video'); v.muted = true; v.play(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("document.querySelector('#dub-result video').pause()")
        pg.evaluate("document.querySelector('#dub-result video').scrollIntoView({ block: 'center' })")
        settle(pg, 800)
        y0 = scroll_top(pg)
        pg.evaluate("(t) => new Promise((res) => { const v = document.querySelector('#dub-result video'); v.addEventListener('seeked', () => res(), { once: true }); v.currentTime = t; })", vsegs[10]["start"] + 0.3)
        settle(pg, 1400)
        c.check(active_idx(pg) == [10] and abs(scroll_top(pg) - y0) < 5, "watching the MP4 video: line 11 is marked but the page stays where it is", f"{y0} -> {scroll_top(pg)} {active_idx(pg)}")
        c.check(pg.locator("#btn-nowline").inner_text().startswith("Now: line 11 /"), "…and the bar names the line", pg.locator("#btn-nowline").inner_text())
        pg.evaluate("document.querySelectorAll('#dub-result .seg-row')[2].scrollIntoView({ block: 'center' })")      # the user now works in the table: the video is out of view
        settle(pg, 800)
        pg.evaluate("(t) => new Promise((res) => { const v = document.querySelector('#dub-result video'); v.addEventListener('seeked', () => res(), { once: true }); v.currentTime = t; })", vsegs[11]["start"] + 0.3)
        settle(pg, 1400)
        c.check(active_idx(pg) == [11] and in_view(pg, 11)[0], "video scrolled out of view (working in the table): the table follows again", str(in_view(pg, 11)[1]))
        # playing: the mark moves by itself
        k = 4
        pg.evaluate("(t) => new Promise((res) => { const v = document.querySelector('#dub-result video'); v.addEventListener('seeked', () => res(), { once: true }); v.currentTime = t; })", vsegs[k]["start"] - 1.0)
        pg.evaluate("() => { const v = document.querySelector('#dub-result video'); v.muted = true; return v.play(); }")
        pg.wait_for_timeout(300)
        first = active_idx(pg)
        pg.wait_for_function("(k) => document.querySelectorAll('#dub-result .seg-row')[k].classList.contains('active')", arg=k, timeout=6000)
        c.check(first == [k - 1] and active_idx(pg) == [k], f"playing the MP4 video moves the mark from line {k} to line {k + 1} by itself", f"{first} -> {active_idx(pg)}")
        c.check(pg.evaluate("document.querySelector('#dub-audio').paused"), "(the separate audio player stays paused)")
        # 'play this line' follows the player in use (video)
        t_row = float(rows(pg).nth(8).get_attribute("data-start"))
        rows(pg).nth(8).locator("[data-go]").click()
        pg.wait_for_timeout(500)
        vt = pg.evaluate("document.querySelector('#dub-result video').currentTime")
        c.check(abs(vt - t_row) < 1.0 and pg.evaluate("document.querySelector('#dub-audio').paused"), "▶ on a line plays it in the MP4 video (the player in use), not in the audio player", f"{vt} vs {t_row}")
        end_row = float(rows(pg).nth(8).get_attribute("data-end"))
        pg.wait_for_function("document.querySelector('#dub-result video').paused", timeout=int((end_row - t_row + 6) * 1000))
        c.check(abs(pg.evaluate("document.querySelector('#dub-result video').currentTime") - end_row) < 1.0, "…and stops at the end of that line", str(pg.evaluate("document.querySelector('#dub-result video').currentTime")))
        # playing the audio player makes it the one in use (and stops the video)
        pg.evaluate("() => { const v = document.querySelector('#dub-result video'); v.muted = true; v.play(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { const a = document.querySelector('#dub-audio'); a.muted = true; return a.play(); }")
        pg.wait_for_timeout(300)
        c.check(pg.evaluate("document.querySelector('#dub-result video').paused"), "starting the audio player pauses the video (no double sound)")
        rows(pg).nth(3).locator("[data-go]").click()
        pg.wait_for_timeout(500)
        at = pg.evaluate("document.querySelector('#dub-audio').currentTime")
        c.check(abs(at - float(rows(pg).nth(3).get_attribute("data-start"))) < 1.0 and pg.evaluate("document.querySelector('#dub-result video').paused"), "…so ▶ on a line now plays in the audio player")
        pg.evaluate("document.querySelector('#dub-audio').pause()")
        ctx.close()

        # ============================================================== C. the YouTube preview (fake player that we control)
        ctx, pg = new_page(b, fake_yt=True)
        open_job(pg, VID)
        pg.locator("#btn-sync").click()
        pg.wait_for_selector("#yt-player", timeout=5000)
        pg.wait_for_timeout(400)
        pg.evaluate("document.querySelector('#sync-holder .yt-frame').scrollIntoView({ block: 'center' })")
        settle(pg, 800)
        y0 = scroll_top(pg)
        pg.evaluate("window.__yt.state = 2")
        pg.evaluate("(t) => { window.__yt.t = t; }", vsegs[9]["start"] + 0.3)
        settle(pg, 1400)
        c.check(active_idx(pg) == [9] and abs(scroll_top(pg) - y0) < 5, "watching the YouTube preview: line 10 is marked but the page stays where it is", f"{y0} -> {scroll_top(pg)} {active_idx(pg)}")
        c.check(pg.locator("#btn-nowline").inner_text().startswith("Now: line 10 /"), "…and the bar names the line", pg.locator("#btn-nowline").inner_text())
        pg.evaluate("window.scrollTo(0, 0)")
        settle(pg, 500)
        pg.evaluate("window.__yt.t = 0.4")
        pg.wait_for_timeout(400)
        c.check(not active_idx(pg), "YouTube preview before the first line: nothing marked")
        pg.evaluate("window.__yt.state = 2")
        pg.evaluate("(t) => { window.__yt.t = t; }", vsegs[3]["start"] + 0.2)
        pg.wait_for_timeout(500)
        c.check(active_idx(pg) == [3], "YouTube preview marks the line it has reached (also while paused)", str(active_idx(pg)))

        def advance(t_from, t_to, step=1.0):
            t = t_from
            while t < t_to:
                t = min(t + step, t_to)
                pg.evaluate("(t) => { window.__yt.t = t; }", t)
                pg.wait_for_timeout(170)

        pg.evaluate("window.__yt.state = 1")
        pg.evaluate("window.scrollTo(0, 0)")
        settle(pg, 500)
        pg.evaluate("(t) => { window.__yt.t = t; }", vsegs[5]["start"] - 0.5)
        settle(pg, 1500)
        advance(vsegs[5]["start"] - 0.5, vsegs[7]["start"] + 0.2)         # playing: small steps, crossing two line boundaries
        settle(pg, 1400)
        c.check(active_idx(pg) == [7], "playing: the mark moved to line 8", str(active_idx(pg)))
        ok, r = in_view(pg, 7)
        c.check(ok, "…and the table scrolled along (it was scrolled by following, not by a jump)", str(r))
        # the user scrolls by hand -> following pauses for a while
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, -700)
        pg.wait_for_timeout(500)
        top_before = scroll_top(pg)
        advance(vsegs[7]["start"] + 0.2, vsegs[9]["start"] + 0.2)
        settle(pg, 900)
        c.check(active_idx(pg) == [9] and abs(scroll_top(pg) - top_before) < 5, "after a manual scroll the table stops following (the mark still moves)", f"{top_before} -> {scroll_top(pg)} {active_idx(pg)}")
        # moving the playhead (a jump) follows again at once
        pg.evaluate("(t) => { window.__yt.t = t; }", vsegs[11]["start"] + 0.3)
        settle(pg, 1400)
        c.check(active_idx(pg) == [11] and in_view(pg, 11)[0], "a jump of the playhead (seek) always scrolls to the line", str(in_view(pg, 11)[1]))
        # the 'now' button after another manual scroll
        pg.mouse.wheel(0, -700)
        pg.wait_for_timeout(500)
        c.check(not in_view(pg, 11)[0], "(scrolled away again)")
        pg.locator("#btn-nowline").click()
        settle(pg)
        c.check(in_view(pg, 11)[0], "the 'now' button brings the playing line back", str(in_view(pg, 11)[1]))
        # row ▶ drives the YouTube player
        pg.evaluate("window.__yt.calls.length = 0")
        t_row = float(rows(pg).nth(2).get_attribute("data-start"))
        rows(pg).nth(2).scroll_into_view_if_needed()
        rows(pg).nth(2).locator("[data-go]").click()
        calls = pg.evaluate("window.__yt.calls")
        c.check(calls and calls[0][0] == "seekTo" and abs(calls[0][1] - t_row) < 0.01 and ["playVideo"] in calls, "▶ on a line seeks the YouTube player and plays", str(calls))
        pg.screenshot(path=str(SHOTS / "follow_sync.png"))
        # closing the preview stops the ticks
        pg.locator("#btn-sync").click()
        pg.wait_for_timeout(300)
        before = active_idx(pg)
        pg.evaluate("(t) => { window.__yt.t = t; }", vsegs[0]["start"] + 0.2)
        pg.wait_for_timeout(500)
        c.check(active_idx(pg) == before, "after closing the preview the table no longer reacts to it", str(active_idx(pg)))
        ctx.close()

        # ============================================================== D. MP4 quality (1080p / 720p)
        ctx, pg = new_page(b)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(1000)
        c.check(pg.locator("#vq-row").is_hidden() and pg.locator("#video-hint").is_hidden(), "quality choice is hidden while the output is MP3")
        pg.locator(".seg[data-bind='output.format'] button[data-value='video']").click()
        pg.wait_for_timeout(200)
        c.check(pg.locator("#vq-row").is_visible(), "…and appears with the MP4 option")
        c.check(pg.locator("#vq-row .seg button.active").inner_text() == "1080p", "1080p is the default")
        hint = pg.locator("#video-hint").inner_text()
        c.check(hint.startswith("Downloads the YouTube video (≤1080p)"), "the hint says ≤1080p", hint)
        pg.locator("#vq-row .seg button[data-value='720']").click()
        pg.wait_for_timeout(200)
        c.check(pg.locator("#video-hint").inner_text().startswith("Downloads the YouTube video (≤720p)") and pg.locator("#vq-row .seg button.active").inner_text() == "720p", "choosing 720p changes the hint and the button")
        pg.locator("#lang-switch button[data-lang=km]").click()
        pg.wait_for_timeout(300)
        c.check("(≤720p)" in pg.locator("#video-hint").inner_text() and "ត្រូវទាញយក" in pg.locator("#video-hint").inner_text(), "Khmer hint also follows the choice", pg.locator("#video-hint").inner_text())
        pg.locator("#lang-switch button[data-lang=en]").click()
        # the choice goes into the request of Regenerate
        open_job(pg, JID)
        rows(pg).nth(1).locator("select.vsel").select_option("km-KH-PisethNeural")
        captured.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(600)
        body = captured[0].post_data_json if captured else {}
        c.check(body.get("output", {}).get("max_height") == 720, "Regenerate sends output.max_height = 720 (a number)", str(body.get("output")))
        pg.wait_for_function("() => { const r = document.querySelector('#dub-result'); return r && !r.classList.contains('hidden') && r.querySelector('.seg-row'); }", timeout=120000)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(500)
        pg.locator(".seg[data-bind='output.format'] button[data-value='audio']").click()
        pg.wait_for_timeout(200)
        c.check(pg.locator("#vq-row").is_hidden(), "back to MP3: the choice is hidden again")
        # an old browser profile (v1.5.0: no max_height / follow saved) gets the defaults
        ctx.close()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("localStorage.setItem('kds_settings', JSON.stringify({output: {format: 'video', sync: 'fit'}, subs: {en: true}}));")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(900)
        c.check(pg.locator("#vq-row").is_visible() and pg.locator("#vq-row .seg button.active").inner_text() == "1080p", "settings saved by an older version get the new default (1080p)")
        open_job(pg, JID)
        c.check(pg.locator("[data-sub=follow]").first.get_attribute("aria-pressed") == "true", "…and 'Follow playback' is on")
        ctx.close()
        b.close()
finally:
    srv.stop()

real = [e for e in errors if "favicon" not in e]
c.check(not real, "no JavaScript errors in any page", "; ".join(real[:4]))
sys.exit(c.done())
