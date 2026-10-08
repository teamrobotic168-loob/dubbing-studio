"""Browser tests for v1.12.0: a click on a line of the script plays the video from that line - the MP4 preview, the YouTube preview (also when it is
closed or still loading), the Khmer audio when there is no picture, and a "Translate with Claude" draft (original video + its own sound)."""
import sys

from lib import *  # noqa: E402,F401,F403
from ui_setup import build  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

c = Checker("Click a line - the video plays from there")
srv = build(8071, "clickplay", extra=True)
JID, VID, DRAFT, MP3 = srv.new_job_id, srv.video_job_id, srv.draft_job_id, srv.mp3_job_id
errors = []

FAKE_YT = """
window.__yt = { t: 0, state: -1, calls: [], created: 0 };
window.YT = {
  PlayerState: { UNSTARTED: -1, ENDED: 0, PLAYING: 1, PAUSED: 2, BUFFERING: 3, CUED: 5 },
  Player: class {
    constructor(id, opts) {
      this.opts = opts; this.ready = false; window.__yt.player = this; window.__yt.created++;
      setTimeout(() => { this.ready = true; try { opts.events && opts.events.onReady && opts.events.onReady({ target: this }); } catch (e) {} }, window.__yt_delay || 10);
    }
    need() { if (window.__yt_strict && !this.ready) throw new TypeError('player is not ready'); }
    getCurrentTime() { return window.__yt.t; }
    getPlayerState() { return window.__yt.state; }
    seekTo(t, allow) { this.need(); window.__yt.calls.push(['seekTo', t]); window.__yt.t = t; }
    playVideo() { this.need(); window.__yt.calls.push(['playVideo']); window.__yt.state = 1; }
    pauseVideo() { window.__yt.state = 2; }
    mute() { window.__yt.calls.push(['mute']); } unMute() { window.__yt.calls.push(['unMute']); } destroy() {}
  }
};
"""


def new_page(b, lang="en", dock=False, delay=None, strict=False):
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','dark');")
    if not dock:   # the inline players keep these checks simple; the docked panel has its own check at the end
        ctx.add_init_script("if (!localStorage.getItem('kds_settings')) localStorage.setItem('kds_settings', JSON.stringify({ ui: { dock: false } }));")
    pre = FAKE_YT
    if delay:
        pre = f"window.__yt_delay = {delay};" + pre
    if strict:
        pre = "window.__yt_strict = true;" + pre
    ctx.add_init_script(pre)
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


def starts_of(job_id):
    segs = srv.api("GET", f"/api/jobs/{job_id}").json()["segments"]
    return [min(s["start"], s["out_start"] if s.get("out_start") is not None else s["start"]) for s in segs]


def yt_calls(pg):
    return pg.evaluate("window.__yt.calls")


def mp4(pg):
    return pg.evaluate("() => { const v = document.querySelector('#mp4-panel video'); return { t: v.currentTime, paused: v.paused }; }")


def audio(pg):
    return pg.evaluate("() => { const a = document.querySelector('#dub-audio'); return { t: a.currentTime, paused: a.paused }; }")


def set_mp4(pg, t):
    pg.evaluate("(t) => new Promise((res) => { const v = document.querySelector('#mp4-panel video'); v.pause(); v.addEventListener('seeked', () => res(), { once: true }); v.currentTime = t; })", t)


def seeks(pg):
    return [x[1] for x in yt_calls(pg) if x[0] == "seekTo"]


def moves(pg):
    return [x for x in yt_calls(pg) if x[0] in ("seekTo", "playVideo")]


try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])

        # ============================================================== A. a job with an MP4 preview (and a YouTube video)
        S = starts_of(VID)
        ctx, pg = new_page(b)
        open_job(pg, VID)
        n = pg.locator("#dub-result .seg-row").count()
        c.check(n == len(S) and n >= 8, f"the table has {n} lines")
        chips = pg.locator("#dub-result .card-head .tog").all_inner_texts()
        c.check(chips[:1] == ["Click line → play"] and pg.locator("[data-sub=clickplay]").get_attribute("aria-pressed") == "true", "the editor has a 'Click line → play' switch, ON by default", str(chips))
        c.check("clickplay" in (pg.locator(".seg-table").get_attribute("class") or ""), "the table is marked (pointer cursor, hover colour)")
        c.check(pg.evaluate("() => getComputedStyle(document.querySelector('.seg-row')).cursor") == "pointer", "a line shows the 'hand' cursor")
        c.check("Click any line to play the video from there" in pg.inner_text("#dub-result"), "the hint under the title says so")

        # the YouTube preview is closed, but the MP4 is on the page: the MP4 plays from the line
        pg.locator("#dub-result .seg-row .en").nth(2).click()
        pg.wait_for_timeout(700)
        m = mp4(pg)
        c.check(abs(m["t"] - S[2]) < 1.3 and m["t"] >= S[2] - 0.1 and not m["paused"], f"click on the original text of line 3 -> the MP4 plays from {S[2]:.1f} s", str(m))
        c.check(pg.locator("#sync-panel").count() == 0 and audio(pg)["paused"], "…no second player is opened, the Khmer audio stays quiet")
        c.check(pg.evaluate("() => [...document.querySelectorAll('#dub-result .seg-row')].findIndex((r) => r.classList.contains('active'))") == 2, "…and the line is marked (follow)")
        # the empty part of a line works too
        pg.locator("#dub-result .seg-row").nth(5).click(position={"x": 6, "y": 6})
        pg.wait_for_timeout(600)
        m = mp4(pg)
        c.check(abs(m["t"] - S[5]) < 1.3 and m["t"] >= S[5] - 0.1 and not m["paused"], f"click on the edge of line 6 -> plays from {S[5]:.1f} s", str(m))

        # controls inside a line do not start the video
        set_mp4(pg, 2.0)
        row = pg.locator("#dub-result .seg-row").nth(7)
        row.locator("[data-pick]").click()
        row.locator(".tin").first.click()
        row.locator(".vsel").click()
        pg.keyboard.press("Escape")
        row.locator("[data-extend]").click()
        pg.wait_for_timeout(500)
        m = mp4(pg)
        c.check(abs(m["t"] - 2.0) < 0.05 and m["paused"], "the checkbox, a time box, the voice list and the ↔ button do NOT start the video", str(m))
        # a text selection is not a click
        pg.evaluate("() => { const e = document.querySelectorAll('#dub-result .seg-row .en')[3]; const r = document.createRange(); r.selectNodeContents(e); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); e.click(); }")
        pg.wait_for_timeout(400)
        m = mp4(pg)
        c.check(abs(m["t"] - 2.0) < 0.05 and m["paused"], "selecting text to copy it does not start the video")
        pg.evaluate("window.getSelection().removeAllRanges()")

        # the Khmer box: clicking INTO it plays that line; a second click in the same box (moving the cursor) does not restart it
        pg.locator("#dub-result .seg-row textarea").nth(4).click()
        pg.wait_for_timeout(600)
        m = mp4(pg)
        c.check(abs(m["t"] - S[4]) < 1.3 and m["t"] >= S[4] - 0.1 and not m["paused"], f"click into the Khmer box of line 5 -> plays from {S[4]:.1f} s", str(m))
        set_mp4(pg, 40.0)
        pg.locator("#dub-result .seg-row textarea").nth(4).click(position={"x": 30, "y": 10})
        pg.wait_for_timeout(400)
        m = mp4(pg)
        c.check(abs(m["t"] - 40.0) < 0.05 and m["paused"], "a second click in the same box only moves the cursor (no restart)", str(m))
        pg.locator("#dub-result .seg-row textarea").nth(5).focus()
        pg.wait_for_timeout(300)
        m = mp4(pg)
        c.check(abs(m["t"] - 40.0) < 0.05 and m["paused"], "moving into a box with the keyboard (Tab / focus) does not start the video either", str(m))
        pg.locator("#dub-result .seg-row textarea").nth(6).click()
        pg.wait_for_timeout(500)
        c.check(abs(mp4(pg)["t"] - S[6]) < 1.3, "…but a click into another box does")

        # the switch
        pg.locator("[data-sub=clickplay]").click()
        pg.wait_for_timeout(450)
        st = pg.evaluate("() => JSON.parse(localStorage.getItem('kds_settings')).subs.clickplay")
        c.check(pg.locator("[data-sub=clickplay]").get_attribute("aria-pressed") == "false" and st is False and "clickplay" not in (pg.locator(".seg-table").get_attribute("class") or ""), "switch OFF: saved, the table is not marked any more")
        c.check(pg.evaluate("() => getComputedStyle(document.querySelector('.seg-row')).cursor") != "pointer", "…the 'hand' cursor is gone")
        set_mp4(pg, 3.0)
        pg.locator("#dub-result .seg-row .en").nth(8).click()
        pg.locator("#dub-result .seg-row textarea").nth(9).click()
        pg.wait_for_timeout(500)
        m = mp4(pg)
        c.check(abs(m["t"] - 3.0) < 0.05 and m["paused"], "switch OFF: clicking a line or a box does nothing", str(m))
        pg.reload()
        open_job(pg, VID)
        c.check(pg.locator("[data-sub=clickplay]").get_attribute("aria-pressed") == "false", "…and it stays off after a reload")
        pg.locator("[data-sub=clickplay]").click()
        pg.locator("#dub-result .seg-row .en").nth(3).click()
        pg.wait_for_timeout(600)
        m = mp4(pg)
        c.check(abs(m["t"] - S[3]) < 1.3 and not m["paused"], "switch ON again: works", str(m))

        # the YouTube preview open: the click seeks it (and the MP4 stops: one picture at a time)
        pg.locator("#btn-sync").click()
        pg.wait_for_selector("#sync-panel", timeout=5000)
        pg.wait_for_function("window.__yt.player && window.__yt.player.ready")
        pg.wait_for_timeout(400)
        pg.evaluate("window.__yt.calls.length = 0")
        pg.locator("#dub-result .seg-row .en").nth(4).click()
        pg.wait_for_timeout(300)
        c.check(moves(pg) == [["seekTo", S[4]], ["playVideo"]], f"preview open: a click on line 5 -> seekTo({S[4]}) + play", str(yt_calls(pg)))
        c.check(mp4(pg)["paused"], "…the MP4 is paused")
        pg.locator("#dub-result .seg-row textarea").nth(1).click()
        pg.wait_for_timeout(300)
        c.check(seeks(pg)[-1] == S[1], "…a click into the Khmer box of line 2 -> seekTo(line 2)", str(yt_calls(pg)))
        k0 = len(moves(pg))
        pg.locator("#dub-result .seg-row").nth(8).locator(".vsel").click()
        pg.keyboard.press("Escape")
        pg.locator("#dub-result .seg-row [data-pick]").nth(8).click()
        c.check(len(moves(pg)) == k0, "…the voice list and the checkbox do nothing")
        ctx.close()

        # ============================================================== A2. a YouTube job with the Khmer audio but no MP4 (MP3 only): the click opens the preview
        S = starts_of(MP3)
        ctx, pg = new_page(b)
        open_job(pg, MP3)
        pg.wait_for_function("document.querySelector('#dub-audio').readyState >= 1", timeout=15000)
        c.check(pg.locator("#mp4-panel").count() == 0 and pg.locator("#btn-sync").count() == 1 and pg.locator("#sync-panel").count() == 0, "MP3-only job from YouTube: no MP4, the preview is closed")
        pg.locator("#dub-result .seg-row .en").nth(3).click()
        pg.wait_for_selector("#sync-panel", timeout=5000)
        pg.wait_for_function("window.__yt.calls.some((x) => x[0] === 'playVideo')", timeout=5000)
        pg.wait_for_timeout(1400)
        calls = yt_calls(pg)
        a = audio(pg)
        c.check(moves(pg) == [["seekTo", S[3]], ["playVideo"]] and ["mute"] in calls and ["unMute"] not in calls, f"a click on line 4 opens the preview at {S[3]} s (the original sound stays off: the Khmer voice speaks)", str(calls))
        c.check(not a["paused"] and abs(a["t"] - S[3]) < 1.6 and pg.locator("#sync-panel #sync-subs .tog").count() == 4, "…the Khmer audio plays along from the same place; the panel has its four switches", str(a))
        pg.evaluate("window.__yt.t = %s" % (S[3] + 0.5))
        pg.locator("#dub-result .seg-row textarea").nth(7).click()
        pg.wait_for_timeout(1300)
        a = audio(pg)
        c.check(seeks(pg)[-1] == S[7] and abs(a["t"] - S[7]) < 1.6 and not a["paused"], f"a click into the Khmer box of line 8 -> the picture AND the Khmer audio move to {S[7]} s", f"{seeks(pg)} {a}")
        ctx.close()

        # ============================================================== B. a finished job without a picture: the Khmer audio
        S = starts_of(JID)
        ctx, pg = new_page(b)
        open_job(pg, JID)
        pg.wait_for_function("document.querySelector('#dub-audio').readyState >= 1", timeout=15000)
        c.check(pg.locator("#btn-sync").count() == 0 and pg.locator("#mp4-panel").count() == 0, "a job from a pasted transcript: no picture at all")
        pg.locator("#dub-result .seg-row .en").nth(3).click()
        pg.wait_for_timeout(800)
        a = audio(pg)
        c.check(abs(a["t"] - S[3]) < 1.5 and a["t"] >= S[3] - 0.1 and not a["paused"], f"click on line 4 -> the Khmer audio plays from {S[3]:.1f} s", str(a))
        # it goes on after the end of the line (the little ▶ button of a line plays only that line)
        segs = srv.api("GET", f"/api/jobs/{JID}").json()["segments"]
        ln = min((s["out_end"] - s["out_start"], i) for i, s in enumerate(segs) if s.get("out_start") is not None and 0 < i < len(segs) - 2)
        pg.locator("#dub-result .seg-row .en").nth(ln[1]).click()
        pg.wait_for_timeout(int((ln[0] + 1.2) * 1000))
        a = audio(pg)
        c.check(not a["paused"] and a["t"] > segs[ln[1]]["out_end"] + 0.3, f"…and it does not stop at the end of the line (line {ln[1] + 1}, {ln[0]:.1f} s long)", str(a))
        pg.evaluate("document.querySelector('#dub-audio').pause()")
        pg.locator("#dub-result .seg-row").nth(2).locator(".go").click()
        pg.wait_for_timeout(300)
        a = audio(pg)
        c.check(not a["paused"] and abs(a["t"] - segs[2]["out_start"]) < 1.2, "the little ▶ button of a line still plays that line", str(a))
        ctx.close()

        # ============================================================== C. a draft ("Translate with Claude") of a YouTube video: the original video + its own sound
        S = starts_of(DRAFT)
        ctx, pg = new_page(b)
        open_job(pg, DRAFT)
        c.check(pg.locator("#dub-audio").count() == 0 and pg.locator("#mp4-panel").count() == 0 and pg.locator(".seg-table.no-audio").count() == 1, "the draft has no audio and no MP4")
        c.check(pg.locator("#btn-sync").count() == 1 and pg.inner_text(".sync-preview b").strip() == "Watch the original video" and "its own sound" in pg.inner_text(".sync-preview .hint"), "…but it offers the original video ('Watch the original video', with its own sound)")
        c.check(pg.locator("[data-sub=clickplay]").count() == 1 and pg.locator("[data-sub=follow]").count() == 0, "the editor has the 'Click line → play' switch (no 'Follow playback': there is no audio)")
        c.check("Click any line to watch the original video from there" in pg.inner_text("#dub-result"), "…and a hint")
        pg.locator("#dub-result .seg-row .en").nth(3).click()                       # the preview is closed: it opens at the line
        pg.wait_for_selector("#sync-panel", timeout=5000)
        pg.wait_for_function("window.__yt.calls.some((x) => x[0] === 'playVideo')", timeout=5000)
        calls = yt_calls(pg)
        c.check(["unMute"] in calls and ["mute"] not in calls and moves(pg) == [["seekTo", S[3]], ["playVideo"]], f"a click on line 4 opens the preview, with sound ON, at {S[3]} s", str(calls))
        c.check(pg.locator("#sync-panel #sync-subs .tog").count() == 1 and pg.locator("#sync-panel #yt-player").count() == 1, "…the panel has only the 'Original subtitle' switch (nothing about Khmer sound)")
        pg.wait_for_timeout(300)
        pg.evaluate("window.__yt.calls.length = 0")
        pg.locator("#dub-result .seg-row textarea").nth(6).click()
        pg.wait_for_timeout(300)
        c.check(moves(pg) == [["seekTo", S[6]], ["playVideo"]], "preview open: a click into the Khmer box of line 7 -> seeks there", str(yt_calls(pg)))
        pg.evaluate("window.__yt.state = 1; window.__yt.t = 20.0")
        pg.wait_for_timeout(500)
        c.check(pg.evaluate("() => [...document.querySelectorAll('#dub-result .seg-row')].findIndex((r) => r.classList.contains('active'))") == max(i for i, x in enumerate(S) if x <= 20.05), "the line that the preview has reached is marked (also in a draft)")
        pg.locator("#btn-sync").click()
        c.check(pg.locator("#sync-panel").count() == 0, "the button closes the preview again")
        ctx.close()

        # the preview is still loading when a second line is clicked: ONE player, and it starts at the LAST line clicked
        ctx, pg = new_page(b, delay=900, strict=True)
        open_job(pg, DRAFT)
        pg.locator("#dub-result .seg-row .en").nth(2).click()
        pg.wait_for_selector("#sync-panel", timeout=5000)
        pg.locator("#dub-result .seg-row .en").nth(5).click()
        pg.locator("#dub-result .seg-row .en").nth(7).click()
        pg.wait_for_function("window.__yt.player && window.__yt.player.ready", timeout=8000)
        pg.wait_for_timeout(400)
        c.check(pg.evaluate("window.__yt.created") == 1 and seeks(pg)[-1] == S[7] and moves(pg)[-1] == ["playVideo"], f"clicks while the player loads: one player, it starts at the last line ({S[7]} s)", str(yt_calls(pg)) + " created=" + str(pg.evaluate("window.__yt.created")))
        pg.locator("#dub-result .seg-row .en").nth(1).click()
        pg.wait_for_timeout(300)
        c.check(seeks(pg)[-1] == S[1], "…and later clicks seek it as usual", str(yt_calls(pg)))
        ctx.close()

        # ============================================================== D. the docked panel (the default layout) and Khmer
        ctx, pg = new_page(b, lang="km", dock=True)
        open_job(pg, DRAFT)
        c.check(pg.inner_text("[data-sub=clickplay]").strip() == "ចុចជួរ → លេង" and "ចុចលើជួរណាមួយ" in pg.inner_text("#dub-result"), "Khmer: the switch and the hint")
        pg.locator("#dub-result .seg-row .en").nth(4).click()
        pg.wait_for_selector("#sync-panel", timeout=5000)
        pg.wait_for_function("window.__yt.calls.some((x) => x[0] === 'playVideo')", timeout=5000)
        pg.wait_for_timeout(300)
        c.check(pg.evaluate("document.querySelector('#sync-panel').classList.contains('is-docked')") and pg.evaluate("getComputedStyle(document.querySelector('#sync-panel')).position") == "fixed" and seeks(pg)[-1] == S[4], "the default layout: the preview opens docked (fixed on the right) at the clicked line")
        ctx.close()
        b.close()
finally:
    srv.stop()

real = [e for e in errors if "favicon" not in e]
c.check(not real, "no JavaScript errors in any page", "; ".join(real[:4]))
sys.exit(c.done())
