# part D of test_tiktok.py (browser) - it is run with exec() inside test_tiktok.py, so `c`, `FX`, `WORK`, `Server`, `make_job`, `upload`, `Img`, ... exist.
from playwright.sync_api import sync_playwright  # noqa: E402

DATA_UI = WORK / "data_tiktok_ui"
shutil.rmtree(DATA_UI, ignore_errors=True)
srv = Server(8062, DATA_UI, make_stub_home(WORK / "vox_tiktok_ui"), name="tiktok_ui").start()
errors = []
posts = []


def new_page(b, lang="en", theme="dark", w=1440, h=900, settings=None, dock=False):
    ctx = b.new_context(viewport={"width": w, "height": h})
    st = dict(settings or {})
    st.setdefault("ui", {"dock": dock})
    ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}'); if (!localStorage.getItem('kds_settings')) localStorage.setItem('kds_settings', JSON.stringify({json.dumps(st)}));")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.on("request", lambda r: posts.append((r.url.split("/api/")[-1], r.post_data)) if r.method == "POST" and ("/api/jobs/" in r.url) else None)
    pg.on("dialog", lambda d: d.accept())
    pg.goto(srv.url + "/", wait_until="networkidle")
    return ctx, pg


def s4(pg, sel):
    return f"#frame-row {sel}"


def active(pg, bind):
    return pg.evaluate("(b) => { const e = document.querySelector(`#frame-row .seg[data-bind='${b}'] button.active`); return e ? e.dataset.value : null; }", bind)


def settings_of(pg):
    return pg.evaluate("() => JSON.parse(localStorage.getItem('kds_settings') || '{}')")


def set_range(pg, root_sel, bind, value):
    pg.evaluate("([r, b, v]) => { const e = document.querySelector(`${r} input[data-bind='${b}']`); e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); }", [root_sel, bind, value])
    pg.wait_for_timeout(350)                                   # the settings are saved 200 ms after the last change


def open_job(pg, jid):
    pg.goto(srv.url + "/#history")
    pg.wait_for_selector("[data-open]")
    pg.wait_for_timeout(400)
    pg.evaluate("(id) => { [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id).click(); }", jid)
    pg.wait_for_selector("#dub-result .seg-row", timeout=20000)
    pg.wait_for_timeout(700)


def wait_job_ui(pg, timeout=240000):
    pg.wait_for_function("() => document.querySelector('#dub-result').classList.contains('hidden') || !document.querySelector('#dub-result .seg-row')", timeout=15000)      # the old result is gone ...
    pg.wait_for_selector("#dub-result .seg-row", timeout=timeout)                                                                                                           # ... and the new one is there
    pg.wait_for_timeout(700)


try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # ================================================================== Step 4
        ctx, pg = new_page(b)
        c.check(not pg.is_visible("#frame-row"), "Step 4: 'audio only' (default) -> no video shape row")
        pg.click('.seg[data-bind="output.format"] button[data-value="video"]')
        pg.wait_for_timeout(150)
        c.check(pg.is_visible("#frame-row") and active(pg, "output.aspect") == "original" and not pg.is_visible("#frame-row [data-frame-vertical]"), "Step 4: MP4 -> the row shows, 'Original shape' is selected, nothing else yet")
        lab = pg.inner_text("#frame-row > label")
        c.check(lab == "Video shape (aspect ratio)", "Step 4: label", lab)
        pg.click(s4(pg, '.seg[data-bind="output.aspect"] button[data-value="9:16"]'))
        pg.wait_for_timeout(150)
        mock = pg.locator("#frame-row [data-frame-mock]")
        c.check(pg.is_visible("#frame-row [data-frame-vertical]") and active(pg, "output.fit") == "blur" and not pg.is_visible("#frame-row [data-frame-crop]"), "TikTok: the fit choices show, 'Blur background' is selected, no crop slider")
        c.check(mock.get_attribute("data-fit") == "blur" and pg.inner_text("#frame-row .fm-cap") == "1080×1920" and pg.is_visible("#frame-row .fm-phone"), "TikTok: the phone preview is in blur mode, 1080×1920")
        src0 = pg.get_attribute("#frame-row .fm-img", "src") or ""
        c.check(src0.startswith("data:image/svg+xml"), "preview: with no video chosen a sample picture is shown")
        hints = pg.evaluate("() => [...document.querySelectorAll('#frame-row [data-frame-hint]')].map((e) => e.textContent)")
        c.check(len(hints) == 3 and all(hints) and "1080×1920" in hints[1] and "10 minutes" in hints[2] and "287 MB" in hints[2] and "blurred copy" in hints[0], "TikTok: three hints (this fit, the size, TikTok's limits)", str(hints))
        pg.click(s4(pg, '.seg[data-bind="output.fit"] button[data-value="crop"]'))
        pg.wait_for_timeout(150)
        c.check(pg.is_visible("#frame-row [data-frame-crop]") and mock.get_attribute("data-fit") == "crop" and "cut off" in pg.inner_text("#frame-row [data-frame-hint='fit']"), "crop: the position slider shows, the preview and the hint follow")
        c.check(pg.inner_text("#frame-row [data-frame-cropx]") == "Center" and (mock.evaluate("e => e.style.getPropertyValue('--cx')") == "50%"), "crop: the slider starts in the middle")
        set_range(pg, "#frame-row", "output.crop_x", 25)
        c.check(pg.inner_text("#frame-row [data-frame-cropx]") == "25%" and mock.evaluate("e => e.style.getPropertyValue('--cx')") == "25%" and settings_of(pg)["output"]["crop_x"] == 25, "crop: 25 % -> shown, the preview moves, saved")
        set_range(pg, "#frame-row", "output.crop_x", 0)
        c.check(pg.inner_text("#frame-row [data-frame-cropx]") == "Left", "crop: 0 = Left")
        set_range(pg, "#frame-row", "output.crop_x", 100)
        c.check(pg.inner_text("#frame-row [data-frame-cropx]") == "Right", "crop: 100 = Right")
        pos = pg.evaluate("() => getComputedStyle(document.querySelector('#frame-row .fm-img')).objectPosition")
        c.check(pos.startswith("100%") and pg.evaluate("() => getComputedStyle(document.querySelector('#frame-row .fm-img')).objectFit") == "cover", "crop: the preview picture is enlarged (cover) and pushed to the right", pos)
        set_range(pg, "#frame-row", "output.crop_x", 35)
        pg.click(s4(pg, '.seg[data-bind="output.fit"] button[data-value="bars"]'))
        pg.wait_for_timeout(150)
        c.check(not pg.is_visible("#frame-row [data-frame-crop]") and mock.get_attribute("data-fit") == "bars" and "black above and below" in pg.inner_text("#frame-row [data-frame-hint='fit']")
                and pg.evaluate("() => getComputedStyle(document.querySelector('#frame-row .fm-img')).objectFit") == "contain" and not pg.is_visible("#frame-row .fm-bg"), "bars: no slider; the preview shows the whole picture on black")
        pg.click(s4(pg, '.seg[data-bind="output.fit"] button[data-value="blur"]'))
        pg.wait_for_timeout(100)
        c.check(pg.is_visible("#frame-row .fm-bg") and pg.evaluate("() => getComputedStyle(document.querySelector('#frame-row .fm-bg')).filter").startswith("blur"), "blur: the preview has a blurred background")
        pg.click('#vq-row .seg[data-bind="output.max_height"] button[data-value="720"]')
        pg.wait_for_timeout(400)
        c.check(pg.inner_text("#frame-row .fm-cap") == "720×1280" and "720×1280" in pg.inner_text("#frame-row [data-frame-hint='note']"), "720p -> 720×1280 in the preview and in the hint")
        st = settings_of(pg)["output"]
        c.check((st["aspect"], st["fit"], st["crop_x"], st["max_height"]) == ("9:16", "blur", 35, "720") or (st["aspect"], st["fit"], st["crop_x"], int(st["max_height"])) == ("9:16", "blur", 35, 720), "settings are saved in the browser", str(st))
        pg.keyboard.press("Tab")
        pg.focus(s4(pg, '.seg[data-bind="output.aspect"] button[data-value="original"]'))
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(100)
        c.check(active(pg, "output.aspect") == "original" and not pg.is_visible("#frame-row [data-frame-vertical]"), "keyboard: Enter on 'Original shape' selects it and hides the vertical options")
        pg.focus(s4(pg, '.seg[data-bind="output.aspect"] button[data-value="9:16"]'))
        pg.keyboard.press("Space")
        pg.wait_for_timeout(450)
        c.check(active(pg, "output.aspect") == "9:16", "keyboard: Space on 'TikTok 9:16' selects it")
        # reload: remembered
        pg.reload(wait_until="networkidle")
        pg.wait_for_timeout(200)
        c.check(pg.is_visible("#frame-row") and active(pg, "output.aspect") == "9:16" and active(pg, "output.fit") == "blur" and pg.inner_text("#frame-row .fm-cap") == "720×1280", "reload: shape, fit and size are remembered")
        # Khmer
        pg.click('#lang-switch button[data-lang="km"]')
        pg.wait_for_timeout(200)
        km_label = pg.inner_text("#frame-row > label")
        c.check(km_label == "ទម្រង់ Video (Aspect ratio)" and "TikTok" in pg.inner_text(s4(pg, '.seg[data-bind="output.aspect"] button[data-value="9:16"]')) and "Blur" in pg.inner_text(s4(pg, '.seg[data-bind="output.fit"] button[data-value="blur"]')), "Khmer: labels and buttons", km_label)
        c.check(pg.inner_text("#frame-row [data-frame-hint='fit']").startswith("រូបភាពទាំងមូល") and "287 MB" in pg.inner_text("#frame-row [data-frame-hint='limits']"), "Khmer: the hints")
        pg.click(s4(pg, '.seg[data-bind="output.fit"] button[data-value="crop"]'))
        c.check(pg.inner_text("#frame-row [data-frame-cropx]") in ("កណ្តាល", "35%"), "Khmer: the slider value", pg.inner_text("#frame-row [data-frame-cropx]"))
        pg.click('#lang-switch button[data-lang="en"]')
        pg.wait_for_timeout(200)
        c.check(pg.inner_text("#frame-row > label") == "Video shape (aspect ratio)" and active(pg, "output.fit") == "crop", "back to English: the label changes, the choice stays")
        ctx.close()

        # what is sent to the server (a pasted transcript job: the request is captured, no job is made)
        ctx, pg = new_page(b, settings={"output": {"format": "video", "aspect": "9:16", "fit": "crop", "crop_x": 25, "max_height": 720, "sync": "fit", "orig_volume": 0, "duck": True, "max_speedup": 1.4}})
        captured = {}

        def fake_dub(route):
            captured["body"] = json.loads(route.request.post_data)
            route.fulfill(status=200, content_type="application/json", body='{"id":"zzzzzzzzzz"}')
        pg.route("**/api/jobs/dub", fake_dub)
        pg.click('#src-tabs button[data-tab="transcript"]')
        pg.fill("#tr-text", SRT2)
        pg.click("#btn-generate")
        pg.wait_for_timeout(600)
        ob = (captured.get("body") or {}).get("output") or {}
        c.check(ob.get("aspect") == "9:16" and ob.get("fit") == "crop" and ob.get("crop_x") == 25 and ob.get("max_height") == 720 and ob.get("video") is True, "Generate: the request carries aspect / fit / crop_x / max_height", str(ob))
        ctx.close()
        ctx, pg = new_page(b)
        captured.clear()
        pg.route("**/api/jobs/dub", fake_dub)
        pg.click('#src-tabs button[data-tab="transcript"]')
        pg.fill("#tr-text", SRT2)
        pg.click("#btn-generate")
        pg.wait_for_timeout(600)
        ob = (captured.get("body") or {}).get("output") or {}
        c.check(ob.get("aspect") == "original" and ob.get("fit") == "blur" and ob.get("crop_x") == 50 and ob.get("video") is False, "Generate with the defaults: original shape, blur, 50 (nothing changes for people who ignore the new row)", str(ob))
        ctx.close()

        # the preview shows the picture of the uploaded file
        ctx, pg = new_page(b, settings={"output": {"format": "video", "aspect": "9:16", "fit": "blur", "crop_x": 50, "max_height": 1080, "sync": "fit", "orig_volume": 0, "duck": True, "max_speedup": 1.4}})
        pg.click('#src-tabs button[data-tab="upload"]')
        pg.set_input_files("#up-file", str(FX / "wide.mp4"))
        pg.wait_for_selector("#up-box .up-card.is-ready", timeout=30000)
        pg.wait_for_timeout(500)
        img_src = pg.get_attribute("#frame-row .fm-img", "src") or ""
        bg = pg.evaluate("() => document.querySelector('#frame-row .fm-bg').style.backgroundImage")
        c.check("/api/uploads/" in img_src and img_src.endswith("/thumb") and "/api/uploads/" in bg, "preview: the little phone shows the picture of the uploaded video", img_src)
        ctx.close()

        # a thumbnail that cannot be loaded: the sample picture takes its place (no broken-image icon in the little phone)
        ctx, pg = new_page(b, settings={"output": {"format": "video", "aspect": "9:16", "fit": "blur", "crop_x": 50, "max_height": 1080, "sync": "fit", "orig_volume": 0, "duck": True, "max_speedup": 1.4}})
        pg.route("**/api/uploads/*/thumb", lambda route: route.abort())
        pg.click('#src-tabs button[data-tab="upload"]')
        pg.set_input_files("#up-file", str(FX / "wide.mp4"))
        pg.wait_for_selector("#up-box .up-card.is-ready", timeout=30000)
        pg.wait_for_timeout(900)
        img_src = pg.get_attribute("#frame-row .fm-img", "src") or ""
        c.check(img_src.startswith("data:image/svg+xml") and pg.evaluate("() => document.querySelector('#frame-row .fm-bg').style.backgroundImage").startswith('url("data:image/svg+xml'), "preview: a thumbnail that cannot be loaded -> the sample picture (also in the blurred background)", img_src[:60])
        pg.set_input_files("#up-file", str(FX / "wide.mp4"))
        pg.wait_for_timeout(1200)
        c.check((pg.get_attribute("#frame-row .fm-img", "src") or "").startswith("data:image/svg+xml"), "preview: and it stays the sample (no endless reloading) after another update")
        ctx.close()

        # ================================================================== the result card
        up = upload(srv, FX / "wide.mp4").json()
        r, jv = make_job(srv, up["id"], aspect="9:16", fit="blur", max_height=720)
        JV = r.json()["id"]
        up2 = upload(srv, FX / "wide.mp4").json()
        r, jn = make_job(srv, up2["id"], video=False)
        JN = r.json()["id"]
        rt = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "transcript", "text": SRT2, "lang": "en"}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google"}, "output": {"video": False}}).json()["id"]
        jt = srv.wait_job(rt, 200)
        up3 = upload(srv, FX / "wide.mp4").json()
        rd = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "upload", "upload_id": up3["id"], "lang": "en", "text": SRT2}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "manual"}, "output": {"video": True}}).json()["id"]
        jd = srv.wait_job(rd, 100)
        c.check(jv["status"] == "done" and jn["status"] == "done" and jt["status"] == "done" and jd["status"] == "done" and jd["meta"].get("draft"), "jobs for the browser tests are ready", f"{jv['status']} {jn['status']} {jt['status']} {jd['status']}")

        ctx, pg = new_page(b, w=1440, h=900, dock=True)
        open_job(pg, JV)
        c.check(pg.locator("#reframe-box").count() == 1 and not pg.evaluate("document.querySelector('#reframe-box').open"), "result: the 'Video shape' panel is there, closed")
        summ = pg.inner_text("#reframe-box > summary")
        c.check("Video shape (TikTok)" in summ and "Now: TikTok 9:16 · 720×1280 · Blur background" in summ, "result: the summary says what the video is now", summ)
        stats = pg.inner_text("#dub-result .player-box .stats")
        c.check("MP4 720×1280 · TikTok 9:16" in stats and ("KB" in stats or "MB" in stats), "result: the numbers line shows 720×1280 · TikTok 9:16 · size", stats)
        c.check(pg.locator("#mp4-panel .mp4-frame.portrait").count() == 1 and (pg.get_attribute("#mp4-panel video", "src") or "").endswith("#t=0.1") and pg.get_attribute("#mp4-panel video", "poster") is None, "result: the MP4 player is the tall one (no poster, first frame)")
        pg.evaluate("window.scrollTo(0, 560)")
        pg.wait_for_timeout(500)
        m = pg.evaluate("""() => { const p = document.querySelector('#mp4-panel'); const f = p.querySelector('.mp4-frame'); const r = f.getBoundingClientRect();
            return {docked: p.classList.contains('is-docked'), over: p.scrollHeight - p.clientHeight, w: r.width, h: r.height, bottom: p.getBoundingClientRect().bottom, vh: innerHeight}; }""")
        c.check(m["docked"] and m["over"] <= 1 and abs(m["w"] / m["h"] - 9 / 16) < 0.01 and m["bottom"] <= m["vh"] and m["h"] > 400, "1440×900 docked: the tall player fits in the panel without scrolling (9:16)", str(m))
        # the panel starts from the job (not from the Step 4 settings)
        pg.click("#reframe-box > summary")
        pg.wait_for_timeout(300)
        rs = lambda bind: pg.evaluate("(b) => { const e = document.querySelector(`#reframe-box .seg[data-bind='${b}'] button.active`); return e ? e.dataset.value : null; }", bind)  # noqa: E731
        c.check(rs("remake.aspect") == "9:16" and rs("remake.fit") == "blur" and rs("remake.max_height") == "720", "result panel: starts from the job (TikTok, blur, 720p)", str([rs("remake.aspect"), rs("remake.fit"), rs("remake.max_height")]))
        c.check(pg.inner_text("#reframe-box .fm-cap") == "720×1280" and pg.inner_text("#btn-reframe") == "Make the video again", "result panel: size and button label")
        c.check("/api/jobs/" in (pg.get_attribute("#reframe-box .fm-img", "src") or "") and (pg.get_attribute("#reframe-box .fm-img", "src") or "").endswith("/thumb"), "result panel: the little phone shows the picture of this job")
        c.check(active(pg, "output.aspect") == "original" and not pg.is_visible("#frame-row [data-frame-vertical]"), "Step 4 is NOT changed by the panel of a job (still 'Original shape')")
        pg.screenshot(path=str(SHOTS / "tt_ui_panel.png"))
        pg.click("#reframe-box .seg[data-bind='remake.fit'] button[data-value='crop']")
        pg.wait_for_timeout(150)
        c.check(pg.is_visible("#reframe-box [data-frame-crop]") and active(pg, "output.fit") == "blur", "result panel: crop shows its slider; Step 4 keeps its own fit")
        set_range(pg, "#reframe-box", "remake.crop_x", 0)
        c.check(pg.inner_text("#reframe-box [data-frame-cropx]") == "Left", "result panel: slider 0 = Left")
        posts.clear()
        pg.click("#btn-reframe")
        pg.wait_for_timeout(500)
        body = next((json.loads(d) for u, d in posts if u.endswith("/video")), None)
        c.check(body == {"aspect": "9:16", "fit": "crop", "crop_x": 0, "max_height": 720, "hide_subs": False, "hide_effect": "blur", "hide_bottom": 3, "hide_height": 16, "hide_strength": 50},
                "result panel: 'Make the video again' sends exactly the panel settings (the shape + the hidden-subtitles band, off by default - v1.10)", str(body))
        c.check(pg.is_visible("#dub-progress") or pg.locator("#dub-result.hidden").count() == 1, "result panel: the progress card replaces the result while the video is made")
        wait_job_ui(pg)
        summ = pg.inner_text("#reframe-box > summary")
        c.check("Crop to fill" in summ and "720×1280" in summ, "after it: the summary says 'Crop to fill'", summ)
        dlp = WORK / "tt_ui_dl.mp4"
        dlp.write_bytes(srv.api("GET", f"/api/jobs/{JV}/file/dubbed.mp4").content)
        im = Img(dlp)
        c.check(red(im.at(60, 640)) and red(im.at(660, 640)), "after it: the MP4 really is the left part of the picture (red)", str([im.at(60, 640), im.at(660, 640)]))
        # again, as the original shape
        pg.click("#reframe-box > summary")
        pg.click("#reframe-box .seg[data-bind='remake.aspect'] button[data-value='original']")
        pg.wait_for_timeout(150)
        c.check(not pg.is_visible("#reframe-box [data-frame-vertical]"), "result panel: 'Original shape' hides the vertical options")
        posts.clear()
        pg.click("#btn-reframe")
        pg.wait_for_timeout(400)
        body = next((json.loads(d) for u, d in posts if u.endswith("/video")), None)
        c.check(body and body["aspect"] == "original" and body["max_height"] == 720, "result panel: original shape is sent", str(body))
        wait_job_ui(pg)
        stats = pg.inner_text("#dub-result .player-box .stats")
        c.check("MP4 720p" in stats and "TikTok" not in stats and pg.locator("#mp4-panel .mp4-frame.portrait").count() == 0, "back to the original shape: '720p', the player is wide again", stats)
        c.check("Now: Original shape · 1280×720" in pg.inner_text("#reframe-box > summary"), "summary: original shape 1280×720", pg.inner_text("#reframe-box > summary"))
        # Khmer in the result
        pg.click('#lang-switch button[data-lang="km"]')
        pg.wait_for_timeout(400)
        c.check("ឥឡូវនេះ៖" in pg.inner_text("#reframe-box > summary") and "ទម្រង់ Video (TikTok)" in pg.inner_text("#reframe-box > summary"), "Khmer: the panel summary", pg.inner_text("#reframe-box > summary"))
        pg.click('#lang-switch button[data-lang="en"]')
        pg.wait_for_timeout(300)
        ctx.close()

        # smaller laptop: 1366 x 768, docked, a tall video
        r = srv.api("POST", f"/api/jobs/{JV}/video", json={"aspect": "9:16", "fit": "bars", "max_height": 1080})
        srv.wait_job(JV, 200)
        for (w, h) in ((1366, 768), (1920, 1080)):
            ctx, pg = new_page(b, w=w, h=h, dock=True)
            open_job(pg, JV)
            pg.evaluate("window.scrollTo(0, 560)")
            pg.wait_for_timeout(500)
            m = pg.evaluate("""() => { const p = document.querySelector('#mp4-panel'); const f = p.querySelector('.mp4-frame'); const r = f.getBoundingClientRect();
                return {docked: p.classList.contains('is-docked'), over: p.scrollHeight - p.clientHeight, w: r.width, h: r.height, bottom: p.getBoundingClientRect().bottom, vh: innerHeight}; }""")
            c.check(m["docked"] and m["over"] <= 1 and abs(m["w"] / m["h"] - 9 / 16) < 0.01 and m["bottom"] <= m["vh"] and m["h"] > 300, f"{w}×{h} docked: the 1080×1920 player fits without scrolling", str(m))
            ctx.close()
        # phone
        ctx, pg = new_page(b, w=390, h=844, lang="km", theme="light")
        open_job(pg, JV)
        m = pg.evaluate("""() => { const f = document.querySelector('#mp4-panel .mp4-frame'); const r = f.getBoundingClientRect(); return {w: r.width, h: r.height, page: document.documentElement.scrollWidth, vw: innerWidth, docked: document.querySelector('#mp4-panel').classList.contains('is-docked')}; }""")
        c.check(not m["docked"] and m["w"] <= 361 and abs(m["w"] / m["h"] - 9 / 16) < 0.01 and m["page"] <= m["vw"], "phone 390 px: the tall player is not docked, ≤ 360 px wide, no sideways scrolling", str(m))
        pg.click("#reframe-box > summary")
        pg.wait_for_timeout(300)
        m = pg.evaluate("() => ({page: document.documentElement.scrollWidth, vw: innerWidth, panel: document.querySelector('#reframe-box').getBoundingClientRect().width})")
        c.check(m["page"] <= m["vw"] and m["panel"] <= m["vw"], "phone: the open panel does not overflow", str(m))
        ctx.close()

        # a job without an MP4, a pasted transcript, a copy / paste draft
        ctx, pg = new_page(b, w=1440, h=900, dock=True, settings={"output": {"format": "video", "aspect": "9:16", "fit": "crop", "crop_x": 20, "max_height": 720, "sync": "fit", "orig_volume": 0, "duck": True, "max_speedup": 1.4}})
        open_job(pg, JN)
        c.check(pg.locator("#reframe-box").count() == 1 and pg.locator("#mp4-panel").count() == 0 and "No MP4 yet" in pg.inner_text("#reframe-box > summary"), "audio-only job: the panel offers an MP4 ('No MP4 yet')")
        pg.click("#reframe-box > summary")
        pg.wait_for_timeout(250)
        c.check(pg.inner_text("#btn-reframe") == "Make the MP4 video" and rs("remake.aspect") == "9:16" and rs("remake.fit") == "crop" and pg.inner_text("#reframe-box .fm-cap") == "720×1280", "audio-only job: the panel starts from the Step 4 choices (TikTok, crop, 720p)")
        pg.click("#btn-reframe")
        wait_job_ui(pg)
        c.check(pg.locator("#mp4-panel .mp4-frame.portrait").count() == 1 and "MP4 720×1280 · TikTok 9:16" in pg.inner_text("#dub-result .player-box .stats"), "audio-only job: the MP4 was made (720×1280) and the tall player shows up")
        ctx.close()
        ctx, pg = new_page(b)
        open_job(pg, rt)
        c.check(pg.locator("#reframe-box").count() == 0 and pg.locator("#mp4-panel").count() == 0, "pasted transcript job (no video): no video panel")
        ctx.close()
        ctx, pg = new_page(b)
        pg.goto(srv.url + "/#history")
        pg.wait_for_selector("[data-open]")
        pg.wait_for_timeout(400)
        pg.evaluate("(id) => { [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id).click(); }", rd)
        pg.wait_for_timeout(1500)
        c.check(pg.locator("#reframe-box").count() == 0, "copy / paste draft (no audio yet): no video panel")
        ctx.close()
        c.check(not errors, "no JavaScript errors in the whole browser test", str(errors[:4]))
        b.close()
finally:
    srv.stop()
