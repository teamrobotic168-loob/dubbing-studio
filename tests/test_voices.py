"""Tests for v1.12.0: "My voices" takes MANY clips at once (every clip = one character), a voice can be renamed, clips can be dropped on the VoxCPM2
area - and no text of the dashboard names the hardware of the computer (no GPU name, VRAM, CUDA, RAM ...)."""
import base64
import re
import shutil
import subprocess
import sys

from lib import *  # noqa: E402,F401,F403
from playwright.sync_api import sync_playwright  # noqa: E402

c = Checker("My voices: many clips, rename, no PC specs")
data = WORK / "data_voices"
shutil.rmtree(data, ignore_errors=True)
(data / "jobs").mkdir(parents=True)
srv = Server(8072, data, make_stub_home(WORK / "voxhome_voices"), name="voices").start()
errors = []

# ---------------------------------------------------------------- the clips
from app import audio  # noqa: E402

FX = WORK / "fx_voices"
shutil.rmtree(FX, ignore_errors=True)
FX.mkdir(parents=True)
(WORK / "shots").mkdir(exist_ok=True)


def clip(name, hz, sec, rate=24000):
    p = FX / name
    subprocess.run([audio.ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={hz}:duration={sec}:sample_rate={rate}", "-ac", "1", str(p)], check=True)
    return p


BOY, GIRL, MOTHER = clip("Boy.wav", 300, 9), clip("Girl.wav", 420, 9), clip("Mother.wav", 220, 9)
TINY = clip("tiny.wav", 500, 1)
SMALL = [clip("Drop A.wav", 260, 4, 8000), clip("Drop B.wav", 340, 4, 8000)]
NOTAUDIO = FX / "notes.wav"
NOTAUDIO.write_bytes(b"this is not audio at all" * 50)


def b64(p):
    return base64.b64encode(p.read_bytes()).decode()


def customs():
    return srv.api("GET", "/api/vox/voices").json()["custom"]


# ================================================================ A. the API
c.check(customs() == [], "no saved voices at the start")
r1 = srv.api("POST", "/api/vox/voices", json={"name": "Boy", "filename": "Boy.wav", "data": "data:audio/wav;base64," + b64(BOY)})
v1 = r1.json()
c.check(r1.status_code == 200 and re.fullmatch(r"vox:c:[0-9a-f]{8}", v1["id"]) and v1["name"] == "Boy" and 7 < v1["duration"] < 10, "POST /api/vox/voices saves a clip (name, id, duration)", r1.text[:200])
r2 = srv.api("POST", "/api/vox/voices", json={"name": "", "filename": "Girl.wav", "data": b64(GIRL)})
v2 = r2.json()
c.check(r2.status_code == 200 and v2["name"] == "My voice", "an empty name becomes 'My voice'", r2.text[:200])
c.check([v["name"] for v in customs()] == ["My voice", "Boy"], "the list shows the newest voice first")
cid1, cid2 = v1["id"].split(":")[2], v2["id"].split(":")[2]

r = srv.api("PATCH", f"/api/vox/voices/{cid1}", json={"name": "  The   Boy \u200b "})
c.check(r.status_code == 200 and r.json()["name"] == "The Boy" and r.json()["id"] == v1["id"] and abs(r.json()["duration"] - v1["duration"]) < 0.01, "PATCH renames a voice (spaces and zero-width characters cleaned)", r.text[:200])
c.check([v["name"] for v in customs()] == ["My voice", "The Boy"], "…the order of the list does not change")
r = srv.api("PATCH", f"/api/vox/voices/{cid1}", json={"name": "ក" * 90})
c.check(r.status_code == 200 and len(r.json()["name"]) == 60, "a name is cut at 60 characters", str(len(r.json().get("name", ""))))
for bad, why in (({"name": "   "}, "blank"), ({"name": "\u200b\u200b"}, "only zero-width characters"), ({"name": 123}, "a number"), ({}, "missing")):
    r = srv.api("PATCH", f"/api/vox/voices/{cid1}", json=bad)
    c.check(r.status_code == 400 and r.json()["detail"]["code"] in ("BAD_REQUEST",), f"PATCH with a name that is {why} -> 400 BAD_REQUEST", r.text[:160])
c.check(srv.api("PATCH", "/api/vox/voices/ffffffff", json={"name": "x"}).status_code == 404 and srv.api("PATCH", "/api/vox/voices/not-an-id", json={"name": "x"}).status_code == 404, "PATCH of an unknown / malformed id -> 404")
c.check(len(customs()[1]["name"]) == 60, "…and a failed rename changes nothing")
r = srv.api("POST", "/api/vox/voices", json={"name": "bad", "filename": "notes.wav", "data": b64(NOTAUDIO)})
c.check(r.status_code == 400 and r.json()["detail"]["code"] == "VOX_BAD_AUDIO", "a file that is not audio -> 400 VOX_BAD_AUDIO", r.text[:160])
r = srv.api("POST", "/api/vox/voices", json={"name": "short", "filename": "tiny.wav", "data": b64(TINY)})
c.check(r.status_code == 400 and r.json()["detail"]["code"] == "VOX_BAD_AUDIO" and len(customs()) == 2, "a clip that is too short -> 400, nothing is saved")
c.check(srv.api("DELETE", f"/api/vox/voices/{cid2}").status_code == 200 and srv.api("DELETE", f"/api/vox/voices/{cid2}").status_code == 404 and len(customs()) == 1, "DELETE removes a voice (a second DELETE -> 404)")
srv.api("DELETE", f"/api/vox/voices/{cid1}")
c.check(customs() == [] and not any((data / "voices").iterdir()), "…and its folder is gone")

# ================================================================ B. the page
dialogs = []
answers = []              # what the next prompt() gets: a text, "" (OK without text) or None (Cancel)


def on_dialog(d):
    dialogs.append((d.type, d.message, d.default_value))
    if d.type == "prompt" and answers:
        a = answers.pop(0)
        d.dismiss() if a is None else d.accept(a)
    else:
        d.accept()


def new_page(b, lang="en", engine="voxcpm", vp=(1440, 1000)):
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]})
    ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','dark');")
    ctx.add_init_script(f"if (!localStorage.getItem('kds_settings')) localStorage.setItem('kds_settings', JSON.stringify({{ ui: {{ dock: false }}, voice: {{ engine: '{engine}' }} }}));")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "400 (Bad Request)" not in m.text else None)
    pg.on("dialog", on_dialog)
    return ctx, pg


def names(pg, page="#page-dub"):
    return pg.locator(f'{page} .voice-card[data-voxvoice^="vox:c:"] .voice-name').all_inner_texts()


def status(pg, page="#page-dub"):
    return pg.locator(f"{page} [data-vox-upload-status]").first.inner_text().replace("\n", " | ")


def wait_status(pg, text, page="#page-dub"):
    pg.wait_for_function("([sel, t]) => { const e = document.querySelector(sel); return !!e && e.innerText.includes(t); }", arg=[f"{page} [data-vox-upload-status]", text], timeout=60000)


def toasts(pg):
    return " | ".join(pg.locator("#toasts .toast").all_inner_texts())


def settings(pg):
    return pg.evaluate("() => JSON.parse(localStorage.getItem('kds_settings') || '{}')")


try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # ------------------------------------------------------------ the engine hint is gone, the add button takes many files
        ctx, pg = new_page(b, engine="edge")
        pg.goto(srv.url + "/#dub")
        pg.wait_for_selector("#nav", timeout=15000)
        pg.wait_for_timeout(700)
        hint = pg.locator("#page-dub [data-engine-hint]").first
        c.check(hint.is_visible() and hint.inner_text() == "Free and fast (needs Internet) · 2 Khmer voices.", "Microsoft Edge: the short hint under the engine switch is still there")
        pg.locator("#page-dub .voice-block .seg[data-bind='voice.engine'] button[data-value=voxcpm]").first.click()
        pg.wait_for_timeout(400)
        c.check(not hint.is_visible() and hint.inner_text() == "" and pg.locator("#page-dub .engine-vox").is_visible(), "VoxCPM2: NO paragraph about the computer ('Runs on your own computer … needs an NVIDIA GPU …')")
        c.check("Runs on your own computer" not in pg.inner_text("#page-dub") and "NVIDIA" not in pg.inner_text("#page-dub"), "…the words are nowhere on the page")
        inp = pg.locator("#page-dub input[data-vox-upload]").first
        c.check(inp.get_attribute("multiple") is not None, "the file box of 'My voices' accepts many files")
        c.check(pg.locator("#page-dub .vox-add-row .file-btn").inner_text().strip() == "Add voices (upload clips)" and "Select one or many clips at once" in pg.inner_text("#page-dub .vox-add-row .hint"), "the button and the hint say so")
        c.check(pg.locator("#page-tts input[data-vox-upload]").first.get_attribute("multiple") is not None, "…also in the Text to Speech tab")
        c.check(pg.locator("#page-dub [data-vox-upload-status]").first.is_hidden(), "no progress line before the first upload")
        before_id = settings(pg)["voice"]["vox"]["id"]

        # ------------------------------------------------------------ three clips at once = three characters
        dialogs.clear()
        inp.set_input_files([str(BOY), str(GIRL), str(MOTHER)])
        wait_status(pg, "3 of 3 voices added")
        c.check(names(pg) == ["Boy", "Girl", "Mother"], "three clips at once -> three voices, in the order of the file dialog", str(names(pg)))
        c.check(not [d for d in dialogs if d[0] == "prompt"], "…no question is asked for each file (the names come from the file names)", str(dialogs))
        c.check("3 voices added" in toasts(pg), "…a message says how many", toasts(pg))
        c.check(names(pg, "#page-tts") == ["Boy", "Girl", "Mother"], "…the Text to Speech tab lists the same voices")
        c.check([v["name"] for v in customs()] == ["Boy", "Girl", "Mother"], "…and so does the server")
        pg.wait_for_timeout(400)
        c.check(settings(pg)["voice"]["vox"]["id"] == before_id, "several clips do not change the selected voice")
        c.check(pg.locator("#page-dub .voice-card[data-voxvoice^='vox:c:'] [data-voxrename]").count() == 3 and pg.locator("#page-dub .voice-card[data-voxvoice^='vox:c:'] [data-voxdel]").count() == 3, "every saved voice has a rename ✎ and a delete 🗑 button")
        c.check(pg.locator("#page-dub .voice-card.designed [data-voxrename]").count() == 0, "(the designed voices have no rename button)")
        pg.screenshot(path=str(WORK / "shots" / "voices_many.png"))

        # ------------------------------------------------------------ the same file names again: numbered, never confusing
        inp.set_input_files([str(BOY), str(GIRL)])
        wait_status(pg, "2 of 2 voices added")
        c.check(names(pg) == ["Boy 2", "Girl 2", "Boy", "Girl", "Mother"], "the same file names again -> 'Boy 2', 'Girl 2'", str(names(pg)))

        # ------------------------------------------------------------ a bad file does not stop the others; the problems are listed with the file name
        inp.set_input_files([str(MOTHER), str(TINY), str(NOTAUDIO)])
        wait_status(pg, "1 of 3 voices added")
        st = status(pg)
        c.check("Not added:" in st and "tiny.wav" in st and "notes.wav" in st and "too short" in st, "1 good + 2 bad files -> '1 of 3 voices added' and the two problems are listed by name", st)
        c.check(names(pg)[0] == "Mother 2" and len(names(pg)) == 6, "…the good one was added", str(names(pg)))
        c.check(pg.locator("#page-dub [data-vox-upload-status] ul li").count() == 2, "…one line per problem")
        c.check("1 voice" in toasts(pg) or "Voice added" in toasts(pg), "…and the toast reports the one that worked", toasts(pg))

        # ------------------------------------------------------------ nothing works: only the problems
        inp.set_input_files([str(NOTAUDIO), str(TINY)])
        wait_status(pg, "0 of 2 voices added")
        c.check(len(names(pg)) == 6, "two bad files: nothing is added")

        # ------------------------------------------------------------ a file that is too big is refused WITHOUT sending it
        posts = []
        pg.on("request", lambda r: posts.append(r.url) if r.method == "POST" and r.url.endswith("/api/vox/voices") else None)
        inp.set_input_files([{"name": "huge.wav", "mimeType": "audio/wav", "buffer": b"\x00" * (31 * 1024 * 1024)}, {"name": "Boy.wav", "mimeType": "audio/wav", "buffer": BOY.read_bytes()}])
        wait_status(pg, "1 of 2 voices added")
        c.check("huge.wav" in status(pg) and len(posts) == 1, "a file over 30 MB is refused in the browser (only the other file was sent)", status(pg) + " | posts=" + str(len(posts)))

        # ------------------------------------------------------------ ONE clip: it is named in a question (as before) and picked
        dialogs.clear()
        answers[:] = ["Narrator"]
        inp.set_input_files([str(GIRL)])
        pg.wait_for_function("() => [...document.querySelectorAll('#page-dub .voice-card[data-voxvoice^=\"vox:c:\"] .voice-name')].some((e) => e.textContent === 'Narrator')", timeout=30000)
        pg.wait_for_timeout(500)
        pr = [d for d in dialogs if d[0] == "prompt"]
        c.check(len(pr) == 1 and pr[0][1] == "Name for this voice?" and pr[0][2] == "Girl", "one clip: the name is asked (default = the file name)", str(pr))
        sel = pg.locator("#page-dub .engine-vox .voice-card[aria-checked='true']").first
        c.check(sel.inner_text().startswith("Narrator") and settings(pg)["voice"]["vox"]["id"].startswith("vox:c:"), "…and the new voice is the selected one")
        c.check(status(pg) == "" or pg.locator("#page-dub [data-vox-upload-status]").first.is_hidden(), "…no summary line for a single clip")
        answers[:] = [None]
        n0 = len(names(pg))
        inp.set_input_files([str(GIRL)])
        pg.wait_for_timeout(700)
        c.check(len(names(pg)) == n0, "one clip, 'Cancel' in the question: nothing is added")

        # ------------------------------------------------------------ rename (the name of the character)
        card = pg.locator("#page-dub .voice-card[data-voxvoice^='vox:c:']", has_text="Narrator").first
        vid = card.get_attribute("data-voxvoice")
        dialogs.clear()
        answers[:] = ["  Grandpa Sok  "]
        card.locator("[data-voxrename]").click()
        pg.wait_for_function("() => [...document.querySelectorAll('#page-dub .voice-card[data-voxvoice^=\"vox:c:\"] .voice-name')].some((e) => e.textContent === 'Grandpa Sok')", timeout=10000)
        pr = [d for d in dialogs if d[0] == "prompt"]
        c.check(len(pr) == 1 and pr[0][1] == "New name for this voice (e.g. the character)?" and pr[0][2] == "Narrator", "✎ asks for the new name (the old one is the default)", str(pr))
        c.check("Voice renamed" in toasts(pg) and srv.api("GET", "/api/vox/voices").json()["custom"][names(pg).index("Grandpa Sok")]["name"] == "Grandpa Sok", "…the name is saved (spaces trimmed)")
        c.check(pg.locator(f"#page-dub .engine-vox .voice-card[data-voxvoice='{vid}'][aria-checked='true']").count() == 1, "…the voice stays selected")
        c.check("Grandpa Sok" in names(pg, "#page-tts"), "…and the other tab shows the new name")
        answers[:] = [None]
        pg.locator(f"#page-dub .voice-card[data-voxvoice='{vid}'] [data-voxrename]").click()
        pg.wait_for_timeout(500)
        c.check("Grandpa Sok" in names(pg), "✎ + Cancel: the name stays")
        patches = []
        pg.on("request", lambda r: patches.append(r.url) if r.method == "PATCH" else None)
        answers[:] = ["Grandpa Sok"]
        pg.locator(f"#page-dub .voice-card[data-voxvoice='{vid}'] [data-voxrename]").click()
        pg.wait_for_timeout(500)
        c.check(not patches, "✎ with the same name: nothing is sent to the server")
        pg.reload()
        pg.wait_for_selector("#nav", timeout=15000)
        pg.wait_for_timeout(900)
        c.check("Grandpa Sok" in names(pg), "after a reload the new name is still there")

        # ------------------------------------------------------------ drop clips on the VoxCPM2 area
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(700)
        files = [[p.name, b64(p)] for p in SMALL]
        dt = pg.evaluate_handle("(fs) => { const dt = new DataTransfer(); for (const [n, b] of fs) { const bin = Uint8Array.from(atob(b), (ch) => ch.charCodeAt(0)); dt.items.add(new File([bin], n, { type: 'audio/wav' })); } return dt; }", files)
        n0 = len(names(pg))
        pg.dispatch_event("#page-dub .engine-vox", "dragover", {"dataTransfer": dt})
        c.check("drop" in (pg.locator("#page-dub .engine-vox").get_attribute("class") or ""), "dragging files over the area: it gets a dashed frame")
        pg.dispatch_event("#page-dub .engine-vox", "drop", {"dataTransfer": dt})
        wait_status(pg, "2 of 2 voices added")
        c.check(len(names(pg)) == n0 + 2 and names(pg)[:2] == ["Drop A", "Drop B"], "dropping 2 clips adds 2 voices (in order)", str(names(pg)[:3]))
        c.check("drop" not in (pg.locator("#page-dub .engine-vox").get_attribute("class") or ""), "…the frame goes away")
        c.check(pg.locator("#src-tabs button.active").get_attribute("data-tab") == "youtube" and pg.locator("#up-box [data-up]").count() == 0, "…and the clips were NOT taken for a video to dub (the Upload tab stays closed)")
        dt2 = pg.evaluate_handle("() => { const dt = new DataTransfer(); dt.items.add(new File(['x'], 'a.txt', { type: 'text/plain' })); return dt; }")
        pg.dispatch_event("#page-dub .engine-vox", "dragover", {"dataTransfer": dt2})
        pg.dispatch_event("#page-dub .engine-vox", "dragleave", {"relatedTarget": None})
        c.check("drop" not in (pg.locator("#page-dub .engine-vox").get_attribute("class") or ""), "dragging out of the area removes the frame")

        # ------------------------------------------------------------ a second batch while the first one is still running
        inp = pg.locator("#page-dub input[data-vox-upload]").first
        inp.set_input_files([str(BOY), str(GIRL), str(MOTHER)])
        inp.set_input_files([str(BOY)])
        pg.wait_for_timeout(250)
        c.check("still being added" in toasts(pg), "a second batch while one is running: 'please wait'", toasts(pg))
        wait_status(pg, "3 of 3 voices added")

        # ------------------------------------------------------------ delete
        card = pg.locator("#page-dub .voice-card[data-voxvoice^='vox:c:']", has_text="Grandpa Sok").first
        n0 = len(names(pg))
        card.locator("[data-voxdel]").click()
        pg.wait_for_function("(n) => document.querySelectorAll('#page-dub .voice-card[data-voxvoice^=\"vox:c:\"]').length === n - 1", arg=n0, timeout=10000)
        c.check("Grandpa Sok" not in names(pg), "🗑 deletes a voice")
        ctx.close()

        # ------------------------------------------------------------ Khmer
        ctx, pg = new_page(b, lang="km")
        pg.goto(srv.url + "/#dub")
        pg.wait_for_selector("#nav", timeout=15000)
        pg.wait_for_timeout(800)
        inp = pg.locator("#page-dub input[data-vox-upload]").first
        c.check(pg.locator("#page-dub .vox-add-row .file-btn").inner_text().strip() == "បន្ថែមសំឡេង (Upload ច្រើនឯកសារ)" and "១ ឯកសារ = ១ តួអង្គ" in pg.inner_text("#page-dub .vox-add-row .hint"), "Khmer: the button and the hint")
        inp.set_input_files([str(BOY), str(GIRL)])
        wait_status(pg, "បានបន្ថែមសំឡេង 2 ក្នុងចំណោម 2")
        c.check(pg.locator("#page-dub .voice-card[data-voxvoice^='vox:c:'] [data-voxrename]").first.get_attribute("title") == "ប្តូរឈ្មោះសំឡេង", "Khmer: the rename button and the progress / result line")
        ctx.close()

        # ================================================================ C. no PC specs - whatever the computer is
        real = srv.api("GET", "/api/vox/status").json()
        BAD = re.compile(r"NVIDIA|GeForce|RTX|VRAM|CUDA|\bGPU\b|\bRAM\b|4090|\bcuda\b", re.I)

        def fake(kind):
            st = dict(real, hardware=dict(real["hardware"]), install=dict(real["install"]), speed=dict(real["speed"]))
            if kind == "gpu":          # an NVIDIA GPU, running
                st["hardware"].update(nvidia={"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24, "cuda_driver": "12.6", "cc": "8.9"}, ram_gb=64, cpu_cores=16)
                st["install"].update(cuda=True, device="cuda")
                st["speed"] = {"kind": "gpu", "rtf": 0.4, "device": "cuda", "measured": True}
                st["worker"] = {"state": "ready", "device": "cuda", "gpu": "NVIDIA GeForce RTX 4090", "phase": "", "turbo": {}}
            elif kind == "none":       # no usable graphics card
                st["hardware"].update(nvidia=None, ram_gb=16)
                st["install"].update(cuda=False, device="cpu")
                st["worker"] = {"state": "stopped"}
            elif kind == "small":      # an NVIDIA GPU with 6 GB
                st["hardware"].update(nvidia={"name": "NVIDIA GeForce GTX 1660", "vram_gb": 6.0, "cuda_driver": "12.1", "cc": "7.5"}, ram_gb=16)
                st["install"].update(cuda=True, device="cuda")
                st["worker"] = {"state": "stopped"}
            elif kind == "mac8":       # an Apple Silicon Mac with 8 GB
                st["hardware"].update(nvidia=None, mac="arm64", ram_gb=8.0)
                st["install"].update(cuda=False, mps=True, device="mps")
                st["speed"] = {"kind": "gpu", "rtf": 1.6, "device": "mps", "measured": True}
                st["worker"] = {"state": "ready", "device": "mps", "gpu": "Apple M2", "phase": "", "turbo": {}}
            return st

        def with_status(kind, lang):
            ctx = b.new_context(viewport={"width": 1440, "height": 1000})
            ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_settings', JSON.stringify({{ ui: {{ dock: false }}, voice: {{ engine: 'voxcpm' }} }}));")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            body = fake(kind)
            pg.route("**/api/vox/status", lambda route: route.fulfill(json=body))
            return ctx, pg

        def page_text(pg, hash_):
            pg.goto(srv.url + "/#" + hash_)
            pg.wait_for_selector("#nav", timeout=15000)
            pg.wait_for_timeout(900)
            return pg.evaluate("() => document.body.innerText")

        for lang in ("en", "km"):
            for kind in ("gpu", "none", "small", "mac8"):
                ctx, pg = with_status(kind, lang)
                bad = []
                for h in ("dub", "tts", "settings"):
                    txt = page_text(pg, h)
                    bad += [f"{h}: {m.group(0)}" for m in BAD.finditer(txt)]
                c.check(not bad, f"[{lang}] {kind}: no GPU name / VRAM / CUDA / RAM on the Dubbing, Text to Speech and Settings pages", str(bad[:6]))
                if lang == "en":
                    pg.goto(srv.url + "/#dub")
                    pg.wait_for_timeout(900)
                    banner = pg.inner_text("#page-dub .vox-banner")
                    pg.goto(srv.url + "/#settings")
                    pg.wait_for_timeout(900)
                    chip, speed, warn = pg.inner_text("#vox-chip"), pg.inner_text("#vox-speed"), pg.inner_text("#vox-hw-warn").strip()
                    if kind == "gpu":
                        c.check(banner.strip() == "Engine running" and chip == "Running" and speed == "Measured during install: 1 second of speech takes 0.4 s to create" and warn == "", "GPU, running: 'Engine running' · 'Running' · the speed WITHOUT the device · no warning", f"{banner!r} {chip!r} {speed!r} {warn!r}")
                    elif kind == "none":
                        c.check("very slow on this computer" in banner and warn == "VoxCPM2 will be very slow on this computer.", "no usable card: the warnings say 'very slow on this computer' - and name nothing", f"{banner!r} {warn!r}")
                    elif kind == "small":
                        c.check("may not have enough memory" in warn and not re.search(r"\d", warn.replace("VoxCPM2", "")), "small card: 'may not have enough memory' (no numbers)", warn)
                    else:
                        c.check("may not have enough memory" in warn and "Edge voices" in warn and not re.search(r"\d", warn.replace("VoxCPM2", "")), "a Mac with 8 GB: 'may not have enough memory' (no numbers)", warn)
                ctx.close()
        b.close()
finally:
    srv.stop()

real_errors = [e for e in errors if "favicon" not in e]
c.check(not real_errors, "no JavaScript errors in any page", "; ".join(real_errors[:4]))
sys.exit(c.done())
