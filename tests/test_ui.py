"""Browser tests (Playwright / Chromium): the editor table (voice + Start/End per line), designed voices."""
import json
import re
import sys
import time

from lib import *  # noqa: E402,F401,F403
from ui_setup import build  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

c = Checker(f"UI v{VERSION}")
srv = build(8012, "ui")
JID, VID = srv.new_job_id, srv.video_job_id
SHOTS = WORK / "shots"
SHOTS.mkdir(exist_ok=True)
errors = []
dialogs = []
dialog_answer = {"accept": True}
captured = []


def clock(txt):
    """'1:02.5' -> 62.5"""
    m = re.match(r"^(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)$", txt.strip())
    return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def new_page(b, lang="en", theme="dark", w=1440, h=900):
    ctx = b.new_context(viewport={"width": w, "height": h})
    ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}');")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)

    def on_dialog(d):
        dialogs.append(d.message)
        d.accept() if dialog_answer["accept"] else d.dismiss()

    pg.on("dialog", on_dialog)
    pg.on("request", lambda r: captured.append(r) if r.method == "POST" and "/regenerate" in r.url else None)
    return ctx, pg


def open_job(pg, job_id):
    pg.goto(srv.url + "/#history")
    pg.wait_for_selector("[data-open]", timeout=10000)
    pg.wait_for_timeout(500)
    pg.evaluate("(id) => { const b = [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id); b.click(); }", job_id)
    pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
    pg.wait_for_timeout(600)


def rows(pg):
    return pg.locator("#dub-result .seg-row")


def row(pg, i):
    return rows(pg).nth(i)


def dirty_label(pg):
    return pg.locator("#dub-result #dirty-label").inner_text()


def toasts(pg):
    return [t.inner_text() for t in pg.locator("#toasts .toast").all()]


def wait_regen_done(pg, jid, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = srv.api("GET", f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.6)
    pg.wait_for_function("() => { const r = document.querySelector('#dub-result'); return r && !r.classList.contains('hidden') && r.querySelector('.seg-row'); }", timeout=30000)
    pg.wait_for_timeout(700)
    return srv.api("GET", f"/api/jobs/{jid}").json()


def expect_req(pg, label, predicate, action, timeout=8000):
    """Run `action` and check that a matching request is made. Returns the request (or None)."""
    try:
        with pg.expect_request(predicate, timeout=timeout) as rq:
            action()
        c.check(True, label)
        return rq.value
    except Exception as exc:  # noqa: BLE001
        c.check(False, label, f"no matching request ({type(exc).__name__})")
        return None


def settings(pg):
    pg.wait_for_timeout(450)       # saved after a 200 ms debounce
    return json.loads(pg.evaluate("localStorage.getItem('kds_settings') || '{}'"))


try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # ============================================================== A. the table
        ctx, pg = new_page(b)
        pg.goto(srv.url)
        pg.wait_for_timeout(1200)
        health = srv.api("GET", "/api/health").json()
        c.check(health["version"] == VERSION and health["ui_ok"], f"server + UI files are version {VERSION}", str(health))
        c.check(pg.evaluate("document.querySelector('#ui-ver').textContent") == VERSION, f"footer shows UI {VERSION}")
        open_job(pg, JID)
        job = srv.api("GET", f"/api/jobs/{JID}").json()
        segs = job["segments"]
        n = len(segs)
        c.check(rows(pg).count() == n and n >= 10, f"{n} rows in the table")
        c.check(pg.locator("#dub-result .seg-head > div").count() == 5, "5 header cells (# / time / source / Khmer / play) - the voice sits under the Khmer text")
        for i in (0, 3, n - 1):
            r = row(pg, i)
            s0 = clock(r.locator("[data-t=start]").input_value())
            e0 = clock(r.locator("[data-t=end]").input_value())
            exp_end = (segs[i + 1]["start"] - 0.10) if i + 1 < n else segs[i]["end"] + 3.9
            c.check(abs(s0 - segs[i]["start"]) < 0.06, f"row {i + 1}: Start shows the caption start", f"{s0} vs {segs[i]['start']}")
            c.check(abs(e0 - exp_end) < 0.06, f"row {i + 1}: End shows the default (next start - 0.1 s)", f"{e0} vs {exp_end}")
        c.check(row(pg, 0).locator("select.vsel").count() == 1 and row(pg, 0).locator("[data-vprev]").count() == 1 and row(pg, 0).locator("[data-pick]").count() == 1,
                "each row has a voice select, a hear-this-line button and a checkbox")
        groups = pg.evaluate("() => { const s = document.querySelector('#dub-result .vsel'); return [...s.querySelectorAll('optgroup')].map((g) => [g.label, g.children.length]); }")
        first = pg.evaluate("() => document.querySelector('#dub-result .vsel option').textContent")
        c.check(first == "Same as above (Srey Mom)", "first option = same as above (names the voice chosen in step 2)", first)
        c.check(groups[0] == ["Microsoft Edge", 2], "group Microsoft Edge (2 voices)", str(groups))
        c.check(len(groups) == 2 and groups[1][1] == 8 and "Designed" in groups[1][0], "group Designed voices (8) - no clone group for a transcript job", str(groups))
        spd = pg.evaluate("() => [...document.querySelectorAll('#dub-result .spd')].map((e) => e.textContent).filter(Boolean)")
        sped_rows = [s for s in segs if s.get("speed") and s["speed"] > 1.045]
        c.check(len(spd) == len(sped_rows) and len(spd) > 0, "speed badges only on the lines that are read faster", f"{len(spd)} vs {len(sped_rows)}")
        c.check(row(pg, 0).locator(".tin.set").count() == 0 and pg.locator("#dub-result .seg-row.dirty").count() == 0, "nothing is marked as changed at the start")
        c.check(dirty_label(pg) == "No edits yet", "label: no edits yet")
        c.check(pg.locator("#dub-result .seg-tip").count() == 1, "tip about the time boxes is shown")
        pg.screenshot(path=str(SHOTS / "ui_table_initial.png"))

        # ============================================================== B. voice per line, selecting, bulk
        row(pg, 1).locator("select.vsel").select_option("km-KH-PisethNeural")
        c.check(row(pg, 1).evaluate("e => e.classList.contains('dirty')"), "changing a voice marks the row")
        c.check(row(pg, 1).locator("select.vsel").evaluate("e => e.classList.contains('set')"), "the voice select gets the accent frame")
        c.check(dirty_label(pg) == "1 line(s) changed", "label counts it", dirty_label(pg))
        row(pg, 1).locator("select.vsel").select_option("")
        c.check(dirty_label(pg) == "No edits yet" and not row(pg, 1).evaluate("e => e.classList.contains('dirty')"), "back to 'same as above' = no change again")
        # shift-click range
        row(pg, 2).locator("[data-pick]").click()
        row(pg, 4).locator("[data-pick]").click(modifiers=["Shift"])
        c.check(pg.locator("#dub-result .seg-row.picked").count() == 3, "shift-click selects a range (3 lines)")
        info = pg.locator("#seg-selinfo").inner_text()
        c.check(info == "3 line(s) selected" and not pg.locator("#bulk-apply").is_disabled(), "selection info + Apply enabled", info)
        c.check(pg.locator("#seg-all").evaluate("e => e.indeterminate"), "'select all' is indeterminate")
        pg.locator("#bulk-voice").select_option("km-KH-PisethNeural")
        pg.locator("#bulk-apply").click()
        vals = [row(pg, i).locator("select.vsel").input_value() for i in range(n)]
        c.check(vals[2:5] == ["km-KH-PisethNeural"] * 3 and all(v == "" for i, v in enumerate(vals) if i not in (2, 3, 4)), "bulk apply sets only the selected lines", str(vals))
        c.check(dirty_label(pg) == "3 line(s) changed", "3 lines changed", dirty_label(pg))
        pg.locator("#bulk-clear").click()
        c.check(pg.locator("#dub-result .seg-row.picked").count() == 0 and pg.locator("#bulk-apply").is_disabled(), "clear selection")
        pg.locator("#seg-all").check()
        c.check(pg.locator("#dub-result .seg-row.picked").count() == n and pg.locator("#seg-selinfo").inner_text() == f"{n} line(s) selected", "select all")
        pg.locator("#seg-all").uncheck()
        c.check(pg.locator("#dub-result .seg-row.picked").count() == 0, "unselect all")
        # designed voice for one line: no consent question
        dialogs.clear()
        row(pg, 6).locator("select.vsel").select_option("vox:p:m_deep")
        c.check(not dialogs and row(pg, 6).locator("select.vsel").input_value() == "vox:p:m_deep", "a designed voice needs no consent question")
        # put everything back
        for i in range(n):
            row(pg, i).locator("select.vsel").select_option("")
        c.check(dirty_label(pg) == "No edits yet", "all voices back to default")

        # ============================================================== C. Start / End
        r3 = row(pg, 3)
        start3 = clock(r3.locator("[data-t=start]").input_value())
        end2_before = clock(row(pg, 2).locator("[data-t=end]").input_value())
        r3.locator("[data-t=start]").fill(f"{start3 + 1.0:.1f}")
        r3.locator("[data-t=start]").press("Enter")
        c.check(abs(clock(r3.locator("[data-t=start]").input_value()) - (start3 + 1.0)) < 0.06, "typing a number of seconds is understood and shown as m:ss.s",
                r3.locator("[data-t=start]").input_value())
        c.check(r3.locator("[data-t=start]").evaluate("e => e.classList.contains('set')"), "a changed Start gets the accent frame")
        end2_after = clock(row(pg, 2).locator("[data-t=end]").input_value())
        c.check(abs((end2_after - end2_before) - 1.0) < 0.12, "the line BEFORE gets the time (its End follows the next Start)", f"{end2_before} -> {end2_after}")
        c.check(not row(pg, 2).locator("[data-t=end]").evaluate("e => e.classList.contains('set')"), "…but its End is not marked as hand-set")
        c.check(r3.evaluate("e => e.classList.contains('dirty')") and not row(pg, 2).evaluate("e => e.classList.contains('dirty')"), "only the moved line is marked as changed")
        c.check(not r3.locator("[data-treset]").is_hidden(), "the reset button appears")
        r3.locator("[data-t=start]").focus()
        r3.locator("[data-t=start]").press("ArrowUp")
        v1 = clock(r3.locator("[data-t=start]").input_value())
        r3.locator("[data-t=start]").press("Shift+ArrowDown")
        v2 = clock(r3.locator("[data-t=start]").input_value())
        c.check(abs(v1 - (start3 + 1.1)) < 0.06 and abs(v2 - (start3 + 0.1)) < 0.06, "ArrowUp = +0.1 s, Shift+ArrowDown = -1 s", f"{v1:.2f} {v2:.2f}")
        r3.locator("[data-treset]").click()
        c.check(abs(clock(r3.locator("[data-t=start]").input_value()) - start3) < 0.06 and not r3.evaluate("e => e.classList.contains('dirty')"), "reset button brings the caption time back")
        c.check(r3.locator("[data-treset]").is_hidden(), "…and hides itself")
        # arrow up until it equals the caption again -> not an override
        r3.locator("[data-t=start]").focus()
        r3.locator("[data-t=start]").press("ArrowUp")
        r3.locator("[data-t=start]").press("ArrowDown")
        c.check(not r3.locator("[data-t=start]").evaluate("e => e.classList.contains('set')"), "going back to the caption time (±0.05 s) is not an override")
        # invalid text
        before = r3.locator("[data-t=end]").input_value()
        r3.locator("[data-t=end]").fill("abc")
        r3.locator("[data-t=end]").press("Enter")
        c.check(r3.locator("[data-t=end]").input_value() == before, "an invalid time is refused and the old value comes back", r3.locator("[data-t=end]").input_value())
        c.check(any("Not a valid time" in t for t in toasts(pg)), "…with a message", str(toasts(pg)))
        # End hand-set
        r5 = row(pg, 5)
        s5 = clock(r5.locator("[data-t=start]").input_value())
        r5.locator("[data-t=end]").fill(f"{s5 + 2.0:.1f}")
        r5.locator("[data-t=end]").press("Enter")
        c.check(r5.locator("[data-t=end]").evaluate("e => e.classList.contains('set')") and r5.evaluate("e => e.classList.contains('dirty')"), "End hand-set: frame + marked")
        badge = r5.locator(".spd").inner_text()
        c.check(badge != "" and r5.locator(".spd").evaluate("e => e.classList.contains('bad') || e.classList.contains('warn')"), "a 2 s window shows a warning speed badge", badge)
        # extend: End back to the default
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        r5.locator("[data-extend]").click()
        e5 = clock(r5.locator("[data-t=end]").input_value())
        exp5 = (segs[6]["start"] - 0.10)
        c.check(abs(e5 - exp5) < 0.1 or e5 > s5 + 2.05, "extend uses the free time after the line", f"{e5} (default {exp5})")
        c.check(any("time extended" in t or "already fits" in t for t in toasts(pg)), "extend says what it did", str(toasts(pg)))
        r5.locator("[data-treset]").click() if not r5.locator("[data-treset]").is_hidden() else None
        # End too close to Start -> red box, Regenerate refuses
        r1 = row(pg, 1)
        s1 = clock(r1.locator("[data-t=start]").input_value())
        r1.locator("[data-t=end]").fill(f"{s1 + 0.1:.1f}")
        r1.locator("[data-t=end]").press("Enter")
        c.check(r1.locator("[data-t=end]").evaluate("e => e.classList.contains('bad')"), "End < Start + 0.3 s turns the box red")
        captured.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(500)
        c.check(not captured and any("Line 2: End must be at least 0.3" in t for t in toasts(pg)), "Regenerate refuses and names the line", str(toasts(pg)))
        r1.locator("[data-treset]").click()
        c.check(dirty_label(pg) == "No edits yet", "everything reset again", dirty_label(pg))

        # ============================================================== D. regenerate with edits
        km2 = row(pg, 2).locator("textarea").input_value()
        row(pg, 1).locator("select.vsel").select_option("km-KH-PisethNeural")
        row(pg, 2).locator("textarea").fill(km2 + " ហើយ")
        s3 = clock(row(pg, 3).locator("[data-t=start]").input_value())
        row(pg, 3).locator("[data-t=start]").fill(f"{s3 + 0.5:.1f}")
        row(pg, 3).locator("[data-t=start]").press("Enter")
        s5 = clock(row(pg, 5).locator("[data-t=start]").input_value())
        row(pg, 5).locator("[data-t=end]").fill(f"{s5 + 2.5:.1f}")
        row(pg, 5).locator("[data-t=end]").press("Enter")
        c.check(dirty_label(pg) == "4 line(s) changed", "4 lines changed", dirty_label(pg))
        captured.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(800)
        c.check(len(captured) == 1, "one regenerate request")
        body = captured[0].post_data_json if captured else {}
        edits = {e["idx"]: e for e in body.get("segments", [])}
        c.check(set(edits) == {1, 2, 3, 5}, "the request lists exactly the 4 changed lines", str(sorted(edits)))
        c.check(set(edits[1]) == {"idx", "voice"} and edits[1]["voice"] == "km-KH-PisethNeural", "line 2: only the voice", str(edits.get(1)))
        c.check(set(edits[2]) == {"idx", "km"} and edits[2]["km"].endswith("ហើយ"), "line 3: only the text", str(edits.get(2)))
        c.check(set(edits[3]) == {"idx", "t0"} and abs(edits[3]["t0"] - (s3 + 0.5)) < 0.06, "line 4: only Start", str(edits.get(3)))
        c.check(set(edits[5]) == {"idx", "t1"} and abs(edits[5]["t1"] - (s5 + 2.5)) < 0.06, "line 6: only End", str(edits.get(5)))
        c.check(all(k in body for k in ("voice", "output", "youtube")), "the request still carries voice / output / youtube settings")
        job = wait_regen_done(pg, JID)
        c.check(job["status"] == "done", "regenerate finished", str(job.get("error")))
        sg = {s["idx"]: s for s in job["segments"]}
        c.check(sg[1].get("voice") == "km-KH-PisethNeural" and abs(sg[3]["t0"] - (s3 + 0.5)) < 0.06 and abs(sg[5]["t1"] - (s5 + 2.5)) < 0.06 and "ហើយ" in sg[2]["km"],
                "everything was stored in the job", str({k: sg[k].get(f) for k, f in ((1, "voice"), (3, "t0"), (5, "t1"))}))
        c.check(job["meta"]["row_voices"] == 1 and job["meta"]["row_times"] == 2, "meta counts (1 voice, 2 times)", str((job["meta"]["row_voices"], job["meta"]["row_times"])))
        c.check(row(pg, 1).locator("select.vsel").input_value() == "km-KH-PisethNeural" and row(pg, 1).locator("select.vsel").evaluate("e => e.classList.contains('set')"), "table re-drawn: line 2 keeps Piseth")
        c.check(row(pg, 3).locator("[data-t=start]").evaluate("e => e.classList.contains('set')") and row(pg, 5).locator("[data-t=end]").evaluate("e => e.classList.contains('set')"), "table re-drawn: hand-set times are framed")
        c.check(dirty_label(pg) == "No edits yet", "…and nothing is 'changed' any more")
        c.check(abs(clock(row(pg, 2).locator("[data-t=end]").input_value()) - (sg[3]["t0"] - 0.10)) < 0.1, "line 3's End follows line 4's new Start")
        out3 = sg[3]["out_start"]
        c.check(out3 >= sg[3]["t0"] - 0.02, "the audio of line 4 starts at (or after) its Start", f"{out3} vs {sg[3]['t0']}")
        pg.screenshot(path=str(SHOTS / "ui_table_after_regen.png"))
        # a line that cannot fit: the 'too long' label
        long_rows = [i for i, s in sg.items() if "long" in (s.get("warn") or "")]
        c.check(5 in long_rows or sg[5].get("speed", 0) > 1.3, "the 2.5 s window of line 6 is flagged or sped up to the limit", str((sg[5].get("warn"), sg[5].get("speed"))))
        if "long" in (sg[5].get("warn") or ""):
            c.check("too long" in row(pg, 5).locator(".tinfo").inner_text(), "'too long' label is shown on the row")

        # ============================================================== D2. reset through the table
        row(pg, 3).locator("[data-treset]").click()
        row(pg, 5).locator("[data-treset]").click()
        row(pg, 1).locator("select.vsel").select_option("")
        captured.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(800)
        body = captured[0].post_data_json
        edits = {e["idx"]: e for e in body["segments"]}
        c.check(edits == {1: {"idx": 1, "voice": None}, 3: {"idx": 3, "t0": None}, 5: {"idx": 5, "t1": None}}, "resetting sends nulls (and not the unchanged line 3 text)", str(edits))
        job = wait_regen_done(pg, JID)
        c.check(all("voice" not in s and "t0" not in s and "t1" not in s for s in job["segments"]) and job["meta"]["row_voices"] == 0, "all overrides removed from the job")

        # ============================================================== E. unsaved edits survive a language switch
        row(pg, 4).locator("select.vsel").select_option("vox:p:f_pro")
        row(pg, 7).locator("[data-t=start]").fill("0:50.0")
        row(pg, 7).locator("[data-t=start]").press("Enter")
        row(pg, 8).locator("textarea").fill("សាកល្បងអត្ថបទថ្មី")
        c.check(dirty_label(pg) == "3 line(s) changed", "3 unsaved edits", dirty_label(pg))
        pg.locator("#lang-switch button[data-lang=km]").click()
        pg.wait_for_timeout(900)
        c.check(row(pg, 4).locator("select.vsel").input_value() == "vox:p:f_pro", "voice survives the language switch")
        c.check(abs(clock(row(pg, 7).locator("[data-t=start]").input_value()) - 50.0) < 0.06, "Start survives the language switch")
        c.check(row(pg, 8).locator("textarea").input_value() == "សាកល្បងអត្ថបទថ្មី", "text survives the language switch")
        c.check(dirty_label(pg) == "បានកែ 3 ជួរ", "label is Khmer now and still counts 3", dirty_label(pg))
        pg.locator("#lang-switch button[data-lang=en]").click()
        pg.wait_for_timeout(700)
        # discard: reset by hand
        row(pg, 4).locator("select.vsel").select_option("")
        row(pg, 7).locator("[data-treset]").click()
        row(pg, 8).locator("textarea").fill(job["segments"][8]["km"])
        c.check(dirty_label(pg) == "No edits yet", "edits discarded by hand")

        # ============================================================== F. hear one line
        rq = expect_req(pg, "Edge: 'hear this line' asks the server to speak the row's text",
                        lambda r: "/api/voices/preview" in r.url and "text=" in r.url and "voice=km-KH-SreymomNeural" in r.url,
                        lambda: row(pg, 0).locator("[data-vprev]").click())
        if rq:
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(rq.url).query)
            c.check(q["text"][0] == row(pg, 0).locator("textarea").input_value().strip(), "…and sends exactly the text of the row")
        pg.wait_for_timeout(1500)
        pg.locator("body").click(position={"x": 5, "y": 5})
        row(pg, 1).locator("select.vsel").select_option("km-KH-PisethNeural")
        expect_req(pg, "Edge: uses the voice chosen for THAT row",
                   lambda r: "/api/voices/preview" in r.url and "voice=km-KH-PisethNeural" in r.url,
                   lambda: row(pg, 1).locator("[data-vprev]").click())
        pg.wait_for_timeout(1200)
        row(pg, 1).locator("select.vsel").select_option("")
        row(pg, 2).locator("select.vsel").select_option("vox:p:m_young")
        got_audio = []
        pg.on("response", lambda r: got_audio.append(r.url) if "/api/vox/preview/" in r.url and r.url.endswith("/audio") else None)
        rq = expect_req(pg, "designed voice: 'hear this line' starts a VoxCPM2 preview",
                        lambda r: r.url.endswith("/api/vox/preview") and r.method == "POST",
                        lambda: row(pg, 2).locator("[data-vprev]").click())
        if rq:
            pbody = rq.post_data_json
            c.check(pbody["voice"] == "vox:p:m_young" and pbody.get("text") == row(pg, 2).locator("textarea").input_value().strip(),
                    "…with the voice and the row's text", str(pbody)[:150])
        pg.wait_for_timeout(3000)
        c.check(len(got_audio) == 1, "…and the audio is fetched when it is ready", str(got_audio))
        row(pg, 2).locator("select.vsel").select_option("")
        # empty text
        row(pg, 3).locator("textarea").fill("")
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        row(pg, 3).locator("[data-vprev]").click()
        c.check(any("no Khmer text" in t for t in toasts(pg)), "an empty line says so", str(toasts(pg)))
        row(pg, 3).locator("textarea").fill(job["segments"][3]["km"])
        c.check(dirty_label(pg) == "No edits yet", "clean again")
        ctx.close()

        # ============================================================== G. a YouTube job: the speaker in the video + consent
        ctx, pg = new_page(b)
        open_job(pg, VID)
        groups = pg.evaluate("() => { const s = document.querySelector('#dub-result .vsel'); return [...s.querySelectorAll('optgroup')].map((g) => [g.label, [...g.children].map((o) => o.value)]); }")
        clone = [g for g in groups if g[0].startswith("Clone")]
        c.check(clone and "vox:original" in clone[0][1], "a job with a video offers 'Original speaker'", str(groups))
        dialogs.clear()
        dialog_answer["accept"] = False
        row(pg, 1).locator("select.vsel").select_option("vox:original")
        c.check(len(dialogs) == 1 and dialogs[0].startswith("I own this voice or have permission to clone it"), "clone voice asks for consent", str(dialogs))
        c.check(row(pg, 1).locator("select.vsel").input_value() == "", "…and a 'no' puts the choice back")
        c.check(not settings(pg).get("voice", {}).get("vox", {}).get("consent"), "consent stays off")
        dialog_answer["accept"] = True
        row(pg, 1).locator("select.vsel").select_option("vox:original")
        c.check(row(pg, 1).locator("select.vsel").input_value() == "vox:original" and settings(pg)["voice"]["vox"]["consent"] is True, "'yes' keeps the voice and remembers the consent")
        dialogs.clear()
        row(pg, 2).locator("select.vsel").select_option("vox:original")
        c.check(not dialogs, "no second question")
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        row(pg, 1).locator("[data-vprev]").click()
        c.check(any("only be heard after" in t for t in toasts(pg)), "the speaker of the video cannot be auditioned before Regenerate", str(toasts(pg)))
        row(pg, 1).locator("select.vsel").select_option("")
        row(pg, 2).locator("select.vsel").select_option("")
        ctx.close()

        # ============================================================== H. designed voices in step 2 + re-roll + the TTS tab
        ctx, pg = new_page(b)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(1200)
        pg.locator("#page-dub .seg[data-bind='voice.engine'] button[data-value='voxcpm']").click()
        pg.wait_for_timeout(900)
        c.check(pg.locator("#page-dub .voice-card.vox[data-voxvoice^='vox:p:']").count() == 8, "8 designed voice cards")
        c.check(pg.locator("#page-dub .voice-card.vox[data-voxvoice='vox:original']").count() == 1, "…plus the speaker of the video")
        c.check(pg.locator("#page-dub .voice-card.vox.designed .chip").first.inner_text() in ("Female", "Male"), "cards show the gender chip")
        card = pg.locator("#page-dub .voice-card.vox[data-voxvoice='vox:p:f_warm']")
        card.click()
        c.check(card.evaluate("e => e.classList.contains('selected')") and settings(pg)["voice"]["vox"]["id"] == "vox:p:f_warm", "clicking a card selects it (and saves)")
        c.check(pg.locator("#page-dub .vox-consent").evaluate("e => e.classList.contains('hidden')"), "no consent box for a designed voice")
        # preview of a designed voice
        rq = expect_req(pg, "▶ on a designed card starts a preview", lambda r: r.url.endswith("/api/vox/preview") and r.method == "POST",
                        lambda: card.locator("[data-voxplay]").click())
        c.check(rq is not None and rq.post_data_json["voice"] == "vox:p:f_warm", "…of that voice")
        pg.wait_for_timeout(2500)
        pres = {p["key"]: p for p in srv.api("GET", "/api/voices").json()["vox"]["presets"]}
        c.check(pres["f_warm"]["ready"] is True and pres["f_warm"]["variant"] == 0, "its anchor was made", str(pres["f_warm"]))
        # re-roll
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        expect_req(pg, "🎲 sends the re-roll request", lambda r: "/api/vox/presets/f_warm/reroll" in r.url, lambda: card.locator("[data-voxreroll]").click())
        pg.wait_for_timeout(300)
        c.check(any("New voice chosen" in t for t in toasts(pg)), "…and says so", str(toasts(pg)))
        pg.wait_for_timeout(2500)
        pres = {p["key"]: p for p in srv.api("GET", "/api/voices").json()["vox"]["presets"]}
        c.check(pres["f_warm"]["variant"] == 1, "🎲 re-roll bumps the variant", str(pres["f_warm"]))
        c.check(pres["f_warm"]["ready"] is True, "…and the new voice was made and played (auto preview)", str(pres["f_warm"]))
        pg.locator("#page-dub .voice-card.vox[data-voxvoice='vox:original']").click()
        # Text to Speech tab
        pg.goto(srv.url + "/#tts")
        pg.wait_for_timeout(900)
        pg.locator("#page-tts .seg[data-bind='voice.engine'] button[data-value='voxcpm']").click()
        pg.wait_for_timeout(900)
        c.check(pg.locator("#page-tts .voice-card.vox[data-voxvoice^='vox:p:']").count() == 8, "TTS tab: 8 designed voices")
        c.check(pg.locator("#page-tts .voice-card.vox[data-voxvoice='vox:original']").count() == 0, "TTS tab: no 'speaker of the video' (there is no video)")
        c.check(pg.locator("#page-tts .notice.info:has-text('My voices')").count() == 0, "TTS tab: the old 'only My voices' notice is gone")
        pg.locator("#tts-text").fill("សួស្តី! នេះគឺជាការសាកល្បងសំឡេងដែលបានបង្កើត។ យើងអាចប្រើ API ជា English ក្នុងប្រយោគខ្មែរ។")
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        pg.locator("#tts-generate").click()          # the saved voice is still 'original speaker' -> not possible here
        pg.wait_for_timeout(500)
        c.check(any("designed voice" in t for t in toasts(pg)), "TTS with 'original speaker' selected is refused with a clear message", str(toasts(pg)))
        pg.locator("#page-tts .voice-card.vox[data-voxvoice='vox:p:m_deep']").click()
        pg.locator("#tts-generate").click()
        pg.wait_for_selector("#tts-result audio", timeout=60000)
        pg.wait_for_timeout(500)
        head = pg.locator("#tts-result .player-box b").first.inner_text()
        c.check("Deep narrator" in head, "TTS result is labelled with the designed voice", head)
        ctx.close()

        # ============================================================== I. responsive layout (container queries)
        for w, h, label in [(1920, 1000, "wide screen"), (1440, 900, "laptop"), (1100, 900, "narrow"), (390, 844, "phone")]:
            ctx, pg = new_page(b, w=w, h=h)
            open_job(pg, JID)
            lay = pg.evaluate("""() => {
              const r = document.querySelector('#dub-result .seg-row'), km = r.querySelector('.kmcell').getBoundingClientRect(),
                    vc = r.querySelector('.vc').getBoundingClientRect(), en = r.querySelector('.en').getBoundingClientRect(),
                    head = document.querySelector('#dub-result .seg-head'), tm = r.querySelector('.tm').getBoundingClientRect(),
                    tl = [...r.querySelectorAll('.tline')].map((e) => e.getBoundingClientRect()),
                    tbl = document.querySelector('#dub-result .seg-table').getBoundingClientRect();
              return { kmTop: km.top, kmBottom: km.bottom, vcTop: vc.top, vcLeft: vc.left, kmLeft: km.left, enTop: en.top,
                       headShown: getComputedStyle(head).display !== 'none', tmW: tm.width, tmH: tm.height, tblW: tbl.width,
                       tlineSameRow: Math.abs(tl[0].top - tl[1].top) < 3, vcW: vc.width, kmW: km.width,
                       overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 };
            }""")
            if label in ("wide screen", "laptop"):
                c.check(lay["headShown"] and lay["vcTop"] >= lay["kmBottom"] and abs(lay["vcLeft"] - lay["kmLeft"]) < 4 and abs(lay["enTop"] - lay["kmTop"]) < 6 and not lay["tlineSameRow"],
                        f"{label}: voice under the Khmer text; source and Khmer side by side; Start above End", str(lay))
                c.check(lay["kmW"] > 330, f"{label}: the Khmer box is wide enough ({lay['kmW']:.0f}px)")
            else:
                c.check(not lay["headShown"] and lay["enTop"] < lay["kmTop"] and lay["vcTop"] >= lay["kmBottom"] and lay["tlineSameRow"] and lay["tmW"] > 240,
                        f"{label}: one column per line, Start and End side by side", str(lay))
            c.check(not lay["overflow"], f"{label}: no horizontal scrolling", str(lay))
            pg.locator(".seg-tools").scroll_into_view_if_needed()
            pg.wait_for_timeout(200)
            pg.screenshot(path=str(SHOTS / f"ui_layout_{label.replace(' ', '_')}.png"))
            ctx.close()

        # ============================================================== J. light theme + Khmer UI
        ctx, pg = new_page(b, lang="km", theme="light")
        open_job(pg, JID)
        pg.locator(".seg-tools").scroll_into_view_if_needed()
        pg.wait_for_timeout(500)
        pg.screenshot(path=str(SHOTS / "ui_table_km_light.png"))
        c.check(pg.locator("#dub-result .seg-tools #seg-all + span").inner_text() == "ជ្រើសទាំងអស់", "Khmer tools bar")
        ctx.close()

        # ============================================================== K. a job made by v1.3 (no slot / dur in the data)
        OLD = "6b011b123f"
        ctx, pg = new_page(b)
        open_job(pg, OLD)
        oj = srv.api("GET", f"/api/jobs/{OLD}").json()
        c.check("slot" not in oj["segments"][0] and "dur" not in oj["segments"][0], "(the old job really has no slot / dur)")
        nb = pg.evaluate("() => [...document.querySelectorAll('#dub-result .spd')].map((e) => e.textContent).filter(Boolean).length")
        old_fast = len([s for s in oj["segments"] if s.get("speed") and s["speed"] > 1.045])
        c.check(rows(pg).count() == len(oj["segments"]) and abs(nb - old_fast) <= 1, "v1.3 job: table works, badges are derived from the old speed values", f"{nb} badges vs {old_fast}")
        row(pg, 2).locator("select.vsel").select_option("km-KH-PisethNeural")
        captured.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(600)
        job = wait_regen_done(pg, OLD)
        c.check(job["status"] == "done" and job["segments"][2].get("voice") == "km-KH-PisethNeural" and all("slot" in s for s in job["segments"]), "v1.3 job: regenerate adds slot / dur and keeps working", str(job.get("error")))
        ctx.close()

        # ============================================================== N. the extend button with exact numbers
        EXT = srv.extend_job_id

        def ext_page():
            ctx_, pg_ = new_page(b)
            open_job(pg_, EXT)
            return ctx_, pg_

        def vals(pg_, i):
            r_ = row(pg_, i)
            return clock(r_.locator("[data-t=start]").input_value()), clock(r_.locator("[data-t=end]").input_value()), r_.locator(".spd").inner_text()

        ctx, pg = ext_page()
        s_, e_, badge_ = vals(pg, 1)
        c.check(abs(s_ - 5.0) < 0.06 and abs(e_ - 9.4) < 0.06 and badge_ == "×1.17", "fixture: line 2 starts at 5.0, ends at 9.4 and is read ×1.17", f"{s_} {e_} {badge_!r}")
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        row(pg, 1).locator("[data-extend]").click()
        s_, e_, badge_ = vals(pg, 1)
        c.check(abs(s_ - 4.3) < 0.06 and abs(e_ - 9.4) < 0.06 and badge_ == "", "extend takes 0.7 s from the free time BEFORE the line (the line before is short)", f"{s_} {e_} {badge_!r}")
        c.check(any("Line 2: time extended" in t_ and "×1.17 → ×1.00" in t_ for t_ in toasts(pg)), "…and tells the speed before → after", str(toasts(pg)))
        c.check(row(pg, 1).locator("[data-t=start]").evaluate("e => e.classList.contains('set')") and not row(pg, 1).locator("[data-t=end]").evaluate("e => e.classList.contains('set')"), "only Start is marked as hand-set")
        c.check(abs(vals(pg, 0)[1] - 4.2) < 0.06, "the line before now ends at the new Start - 0.1 s", str(vals(pg, 0)))
        ctx.close()

        ctx, pg = ext_page()
        row(pg, 2).locator("[data-t=end]").fill("0:11.0")
        row(pg, 2).locator("[data-t=end]").press("Enter")
        c.check(row(pg, 2).locator(".spd").evaluate("e => e.classList.contains('bad')") and "✕" in row(pg, 2).locator(".spd").inner_text(), "a 1.5 s window for 2.9 s of speech is red (does not fit even at ×1.4)", row(pg, 2).locator(".spd").inner_text())
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        row(pg, 2).locator("[data-extend]").click()
        s_, e_, badge_ = vals(pg, 2)
        c.check(abs(e_ - 12.1) < 0.06 and not row(pg, 2).locator("[data-t=end]").evaluate("e => e.classList.contains('set')"), "extend: End goes back to the default (next Start - 0.1 s) and is no longer 'hand-set'", f"{s_} {e_}")
        c.check(abs(s_ - 9.39) < 0.06, "…and the little free time before the line (0.11 s) is taken too", f"{s_}")
        ctx.close()

        ctx, pg = ext_page()
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        before = vals(pg, 4)
        row(pg, 4).locator("[data-extend]").click()
        c.check(vals(pg, 4) == before and any("Line 5 has no free time left" in t_ for t_ in toasts(pg)) and not row(pg, 4).evaluate("e => e.classList.contains('dirty')"),
                "no free time (the line before needs all of its time): nothing changes and it says so", f"{before} {toasts(pg)}")
        pg.locator("#toasts").evaluate("e => { e.innerHTML = ''; }")
        row(pg, 5).locator("[data-extend]").click()
        c.check(any("Line 6 already fits at normal speed" in t_ for t_ in toasts(pg)), "a line that already fits at normal speed says so", str(toasts(pg)))
        # editing the text changes the estimate (the badge gets a ≈)
        row(pg, 1).locator("textarea").fill(row(pg, 1).locator("textarea").input_value() + " " + "ក" * 40)
        est = row(pg, 1).locator(".spd").inner_text()
        c.check(est.startswith("≈×") and "Estimated from the text length" in row(pg, 1).locator(".spd").get_attribute("title"), "a longer text -> the badge becomes an estimate (≈) with an explanation", est)
        ctx.close()

        # ============================================================== O. a job without timestamps (plain text): no time boxes, but voices work
        body = {"source": {"type": "transcript", "text": "Welcome to the channel. Today we will build a dashboard.\n\nFirst we set up a Python server.\n\nThen we train a model.", "lang": "en"},
                "voice": {"id": "km-KH-SreymomNeural", "engine": "edge", "vox": {"id": "vox:original", "quality": "fast", "consent": False}},
                "translate": {"engine": "google", "keep_terms": True}, "output": {"sync": "fit", "max_speedup": 1.4}}
        PJ = srv.api("POST", "/api/jobs/dub", json=body).json()["id"]
        pj = srv.wait_job(PJ, 200)
        c.check(pj["status"] == "done" and pj["meta"]["timed"] is False, "plain-text job created (no timestamps)", str(pj.get("error")))
        ctx, pg = new_page(b)
        open_job(pg, PJ)
        c.check(pg.locator("#dub-result .tin").count() == 0 and pg.locator("#dub-result .seg-tip").count() == 0, "untimed job: no Start / End boxes and no time tip")
        c.check(pg.locator("#dub-result .seg-row .vsel").count() == len(pj["segments"]) and pg.locator("#dub-result .seg-row .tm").count() == len(pj["segments"]), "…but every line has a voice (and the old static time cell)")
        row(pg, 1).locator("select.vsel").select_option("km-KH-PisethNeural")
        captured.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(500)
        edits = captured[0].post_data_json["segments"] if captured else None
        c.check(edits == [{"idx": 1, "voice": "km-KH-PisethNeural"}], "untimed job: the request only has the voice", str(edits))
        pj = wait_regen_done(pg, PJ)
        c.check(pj["status"] == "done" and pj["segments"][1].get("voice") == "km-KH-PisethNeural" and all(s.get("t0") is None and s.get("t1") is None for s in pj["segments"]), "untimed job regenerates with the voice", str(pj.get("error")))
        ctx.close()

        # ============================================================== P. every page opens without errors (and the voice block is unchanged for Edge)
        ctx, pg = new_page(b)
        for hsh in ("dub", "tts", "terms", "history", "settings"):
            pg.goto(srv.url + "/#" + hsh)
            pg.wait_for_timeout(900)
        c.check(pg.locator("#page-settings.active").count() == 1, "settings page opens")
        c.check(pg.locator("#page-dub .voice-card[data-voice]").count() == 2, "step 2 still shows the two Microsoft voices")
        ctx.close()

        # ============================================================== Q. the whole flow in the browser: paste an SRT -> generate -> table -> edit -> regenerate; then Text to Speech
        ctx, pg = new_page(b)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(1000)
        pg.locator("#src-tabs button[data-tab=transcript]").click()
        srt_text = (PROJECT / "samples" / "technical-tutorial.srt").read_text(encoding="utf-8")
        pg.locator("#tr-text").fill(srt_text)
        pg.locator("#btn-generate").click()
        pg.wait_for_selector("#dub-result .seg-row", timeout=240000)
        pg.wait_for_timeout(800)
        nrows = rows(pg).count()
        c.check(nrows >= 10, f"generated in the browser: the table has {nrows} lines")
        c.check(pg.locator("#dub-result .tin").count() == 2 * nrows and pg.locator("#dub-result .vsel").count() == nrows, "…each with Start / End and a voice")
        c.check(all(clock(rows(pg).nth(i).locator("[data-t=end]").input_value()) > clock(rows(pg).nth(i).locator("[data-t=start]").input_value()) for i in range(nrows)), "…and End is after Start on every line")
        # the job id that the browser tracked
        job_id = pg.evaluate("() => (document.querySelector('#dub-result .player-box audio').src.match(/jobs\\/([0-9a-f]+)\\//) || [])[1]")
        c.check(bool(job_id), "result belongs to a job", str(job_id))
        row(pg, 0).locator("select.vsel").select_option("km-KH-PisethNeural")
        row(pg, 1).locator("[data-t=start]").fill(f"{clock(row(pg, 1).locator('[data-t=start]').input_value()) + 0.3:.1f}")
        row(pg, 1).locator("[data-t=start]").press("Enter")
        pg.locator("#btn-regen").click()
        pj = wait_regen_done(pg, job_id)
        c.check(pj["status"] == "done" and pj["segments"][0].get("voice") == "km-KH-PisethNeural" and pj["segments"][1].get("t0") is not None, "edit + regenerate in the same page works", str(pj.get("error")))
        c.check(row(pg, 0).locator("select.vsel").input_value() == "km-KH-PisethNeural", "…and the table shows the saved choice")
        pg.goto(srv.url + "/#tts")
        pg.wait_for_timeout(800)
        pg.locator("#tts-text").fill("សួស្តី! នេះគឺជាការសាកល្បងសំឡេង។ យើងអាចប្រើ API ជា English ក្នុងប្រយោគខ្មែរ។")
        pg.locator("#tts-generate").click()
        pg.wait_for_selector("#tts-result audio", timeout=120000)
        c.check(pg.locator("#tts-result .player-box b").first.inner_text().startswith("Sreymom") or "Sreymom" in pg.locator("#tts-result .player-box b").first.inner_text() or "Srey" in pg.locator("#tts-result .player-box b").first.inner_text(), "Text to Speech with the Microsoft voice still works")
        ctx.close()

        # ============================================================== L. a Chinese job keeps its fonts / language marks
        ZH = "801e920088"
        ctx, pg = new_page(b)
        open_job(pg, ZH)
        c.check(pg.locator("#dub-result .seg-row .en[lang='zh-Hans']").count() == 12, "Chinese job: source column is marked lang=zh-Hans")
        ctx.close()
        b.close()
finally:
    srv.stop()

real_errors = [e for e in errors if "favicon" not in e]
c.check(not real_errors, "no JavaScript errors / console errors in any page", "; ".join(real_errors[:4]))
sys.exit(c.done())
