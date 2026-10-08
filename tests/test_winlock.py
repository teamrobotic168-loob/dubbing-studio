"""v1.13.0 - WINDOWS: a file that the browser still has open must never break "Regenerate".

The bug (seen by a user on Windows): the dub was ready, the user corrected some Khmer lines, pressed "Regenerate audio" and got
"Internal error" - every time.  The MP4 was still open in the page (a <video> leaves its request half-read), the server kept the file
open while it answered, and Windows cannot delete an open file: `PermissionError: [WinError 32]` when Regenerate removed the old
dubbed.mp4.  macOS / Linux never show that, so the sandbox needs a Python that behaves like Windows: tests/winlock/sitecustomize.py.

  A. units     Range parsing, MediaFile (headers, ranges, nothing open between two chunks, a file replaced while it is sent), remove_file,
               the job guard (PermissionError -> FILE_IN_USE)
  B. API       a server that behaves like Windows + the real pipeline (real Edge TTS): Regenerate while three streams are half-read,
               a program outside that holds the old files (for a moment / for good), the way back (remake the video)
  C. browser   Chromium: the MP4 is playing, a line is edited, Regenerate works; a Regenerate that fails keeps the editor and the edits
Set ONLY=A,B,C to run a part.
"""
import asyncio
import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from lib import *  # noqa: E402,F401,F403

WORK.mkdir(parents=True, exist_ok=True)
os.environ["KDS_DATA_DIR"] = str(WORK / "data_winlock_units")
shutil.rmtree(WORK / "data_winlock_units", ignore_errors=True)
from app import audio, jobs, mediafile, pipeline  # noqa: E402

ONLY = set((os.environ.get("ONLY") or "A,B,C").split(","))
c = Checker("Windows: files that are still open")
FF = audio.ffmpeg_exe()
FX = WORK / "fx_winlock"
FX.mkdir(exist_ok=True)
WINLOCK = TESTS / "winlock"
errors = []

# ==================================================================================================================== A. units
if "A" in ONLY:
    # ---- the Range header
    P = mediafile.parse_range
    c.check([P("bytes=0-99", 1000), P("bytes=900-", 1000), P("bytes=-100", 1000), P("bytes=-5000", 1000), P("bytes=0-5000", 1000), P("bytes=0-0", 1000), P("bytes=999-999", 1000)]
            == [(0, 99), (900, 999), (900, 999), (0, 999), (0, 999), (0, 0), (999, 999)], "Range: first-last, first-, -last N, too big (clamped), one byte")
    bad = 0
    for h, n in (("bytes=1000-", 1000), ("bytes=2000-3000", 1000), ("bytes=-0", 1000), ("bytes=0-", 0), ("bytes=-5", 0)):
        try:
            P(h, n)
        except mediafile.RangeNotSatisfiable:
            bad += 1
    c.check(bad == 5, "Range: behind the end of the file (or an empty file) -> 416", str(bad))
    c.check([P(h, 1000) for h in ("bytes=5-2", "items=0-1", "bytes=0-1,5-6", "bytes=", "bytes=abc", "", "bytes=-", "bytes=1-x")] == [None] * 8,
            "Range: nonsense, another unit, several ranges -> ignored (the whole file is sent, which is always allowed)")

    # ---- MediaFile, called like a server would call it
    def call(resp, method="GET", headers=None, on_chunk=None):
        scope = {"type": "http", "method": method, "path": "/", "query_string": b"", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]}
        out = {"status": None, "headers": {}, "body": b"", "chunks": 0}

        async def run():
            first = True
            gate = asyncio.Event()

            async def receive():
                nonlocal first
                if first:
                    first = False
                    return {"type": "http.request", "body": b"", "more_body": False}
                await gate.wait()
                return {"type": "http.disconnect"}

            async def send(m):
                if m["type"] == "http.response.start":
                    out["status"], out["headers"] = m["status"], {k.decode(): v.decode() for k, v in m["headers"]}
                elif m["type"] == "http.response.body":
                    out["body"] += m.get("body", b"")
                    out["chunks"] += 1
                    if on_chunk:
                        on_chunk(out["chunks"])

            await resp(scope, receive, send)
        asyncio.run(run())
        return out

    DATA = os.urandom(mediafile.CHUNK * 2 + 777)
    f1 = FX / "unit.mp3"
    f1.write_bytes(DATA)
    n = len(DATA)
    r = call(mediafile.MediaFile(f1, "audio/mpeg"))
    c.check(r["status"] == 200 and r["body"] == DATA and r["headers"]["content-length"] == str(n) and r["headers"]["accept-ranges"] == "bytes"
            and r["headers"]["content-type"] == "audio/mpeg" and r["headers"].get("etag") and r["headers"].get("last-modified") and "content-disposition" not in r["headers"]
            and r["chunks"] == 3, "MediaFile: the whole file in 3 chunks, Content-Length, Accept-Ranges, type, ETag, Last-Modified", str(r["headers"]))
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), headers={"Range": "bytes=10-19"})
    c.check(r["status"] == 206 and r["body"] == DATA[10:20] and r["headers"]["content-range"] == f"bytes 10-19/{n}" and r["headers"]["content-length"] == "10", "MediaFile: bytes=10-19 -> 206, Content-Range, the 10 bytes")
    a, b = mediafile.CHUNK - 10, mediafile.CHUNK * 2 + 10
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), headers={"Range": f"bytes={a}-{b}"})
    c.check(r["status"] == 206 and r["body"] == DATA[a:b + 1], "MediaFile: a range across the chunk borders is exact")
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), headers={"Range": "bytes=-5"})
    c.check(r["status"] == 206 and r["body"] == DATA[-5:], "MediaFile: bytes=-5 -> the last 5 bytes")
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), headers={"Range": f"bytes={n}-"})
    c.check(r["status"] == 416 and r["headers"]["content-range"] == f"bytes */{n}", "MediaFile: a range behind the end -> 416 with Content-Range: bytes */size")
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), headers={"Range": "bytes=5-2"})
    c.check(r["status"] == 200 and r["body"] == DATA, "MediaFile: a nonsense range -> the whole file")
    etag = call(mediafile.MediaFile(f1, "audio/mpeg"))["headers"]["etag"]
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), headers={"Range": "bytes=0-9", "If-Range": '"something-else"'})
    c.check(r["status"] == 200 and r["body"] == DATA, "MediaFile: If-Range of an older file -> the whole (new) file, not a piece of it")
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), headers={"Range": "bytes=0-9", "If-Range": etag})
    c.check(r["status"] == 206 and r["body"] == DATA[:10], "MediaFile: If-Range of this file -> the piece")
    r = call(mediafile.MediaFile(f1, "audio/mpeg"), method="HEAD")
    c.check(r["status"] == 200 and r["body"] == b"" and r["headers"]["content-length"] == str(n), "MediaFile: HEAD -> headers only")
    r = call(mediafile.MediaFile(f1, "audio/mpeg", headers={"Cache-Control": "max-age=3600"}, filename="my_dub.mp3"))
    c.check(r["headers"]["content-disposition"] == 'attachment; filename="my_dub.mp3"' and r["headers"]["cache-control"] == "max-age=3600", "MediaFile: download name and extra headers")
    r = call(mediafile.MediaFile(f1, "audio/mpeg", filename="ខ្មែរ dub.mp3"))
    c.check(r["headers"]["content-disposition"].startswith("attachment; filename*=utf-8''%E1%9E%81"), "MediaFile: a Khmer download name -> RFC 5987 (filename*=utf-8'')", r["headers"]["content-disposition"])
    r = call(mediafile.MediaFile(FX / "nothing.mp3", "audio/mpeg"))
    c.check(r["status"] == 404, "MediaFile: a missing file -> 404")
    empty = FX / "empty.bin"
    empty.write_bytes(b"")
    r = call(mediafile.MediaFile(empty, "audio/mpeg"))
    c.check(r["status"] == 200 and r["body"] == b"" and r["headers"]["content-length"] == "0", "MediaFile: an empty file -> 200, length 0")

    # nothing is open between two chunks (Linux: /proc/self/fd); the starlette FileResponse of before DOES hold the file - the check is meaningful
    if Path("/proc/self/fd").is_dir():
        def fds_of(p):
            real = os.path.realpath(p)
            out = []
            for fd in os.listdir("/proc/self/fd"):
                try:
                    if os.path.realpath(f"/proc/self/fd/{fd}") == real:
                        out.append(fd)
                except OSError:
                    pass
            return out
        seen = []
        call(mediafile.MediaFile(f1, "audio/mpeg"), on_chunk=lambda k: seen.append(len(fds_of(f1))))
        c.check(seen and max(seen) == 0, "MediaFile: between two chunks the file is NOT open (open handles seen: " + str(seen) + ")")
        from starlette.responses import FileResponse
        seen = []
        call(FileResponse(f1, media_type="audio/mpeg"), on_chunk=lambda k: seen.append(len(fds_of(f1))))
        c.check(seen and max(seen) >= 1, "…while Starlette's FileResponse keeps it open all the time (this is what blocked Windows)", str(seen))
    else:
        print("  (no /proc/self/fd here: the 'nothing is open' check is skipped)")

    # a file that is replaced while it is being sent: the response ends early, it is never a mixture of the old and the new file
    f2 = FX / "unit_replace.mp3"
    old = os.urandom(mediafile.CHUNK * 3)
    f2.write_bytes(old)

    def swap(k):
        if k == 1:
            tmp = FX / "unit_replace.new"
            tmp.write_bytes(os.urandom(mediafile.CHUNK * 3))
            os.replace(tmp, f2)
    r = call(mediafile.MediaFile(f2, "audio/mpeg"), on_chunk=swap)
    c.check(0 < len(r["body"]) < len(old) and r["body"] == old[:len(r["body"])], "MediaFile: the file is replaced while it is sent -> the response ends early with the OLD bytes only", f"{len(r['body'])} of {len(old)}")

    # ---- remove_file: a file that Windows still holds is retried; one that stays locked never fails the job
    f3 = FX / "unit_rm.txt"
    f3.write_text("x")
    c.check(audio.remove_file(f3) is True and not f3.exists() and audio.remove_file(f3) is True, "remove_file: deletes; a file that is not there counts as gone")
    real_unlink, calls = Path.unlink, {"n": 0}

    def flaky(self, missing_ok=False):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(13, "The process cannot access the file because it is being used by another process")
        return real_unlink(self, missing_ok=missing_ok)
    f3.write_text("x")
    Path.unlink = flaky
    try:
        ok = audio.remove_file(f3, tries=5, wait=0.01)
        c.check(ok is True and calls["n"] == 3 and not f3.exists(), "remove_file: still held for two tries -> retried, then deleted", str(calls))
        f3.write_text("x")

        def locked(self, missing_ok=False):
            calls["n"] += 1
            raise PermissionError(13, "locked")
        Path.unlink = locked
        calls["n"] = 0
        t0 = time.time()
        ok = audio.remove_file(f3, tries=4, wait=0.01)
        c.check(ok is False and calls["n"] == 4 and time.time() - t0 < 2, "remove_file: locked for good -> False after the last try (no exception)", str(calls))
    finally:
        Path.unlink = real_unlink

    # ---- the job guard
    job = jobs.Job("dub", {}, "guard")

    def locked_file():
        raise PermissionError(13, "The process cannot access the file because it is being used by another process", str(FX / "dubbed.mp4"))
    pipeline._guard(job, locked_file)
    c.check(job.status == "error" and job.error["code"] == "FILE_IN_USE" and "dubbed.mp4" in job.error["message"] and "used by another process" in job.error["message"],
            "a PermissionError during a job -> FILE_IN_USE (not 'Internal error'), with the file name", str(job.error))
    job2 = jobs.Job("dub", {}, "guard2")

    def bug():
        raise KeyError("x")
    pipeline._guard(job2, bug)
    c.check(job2.status == "error" and job2.error["code"] == "INTERNAL" and "KeyError" in job2.error["message"], "…any other exception is still INTERNAL, with its name in the details", str(job2.error))
    for src in ("static/js/i18n.js",):
        txt = (PROJECT / src).read_text(encoding="utf-8")
        c.check(txt.count("'err.FILE_IN_USE'") == 2 and txt.count("'res.regen_failed'") == 2, "i18n: err.FILE_IN_USE and res.regen_failed exist in Khmer and English")

# ==================================================================================================================== fixtures for B + C
srv = None
if "B" in ONLY or "C" in ONLY:
    import httpx

    BIG = FX / "big.mp4"
    if not BIG.exists() or BIG.stat().st_size < 20_000_000:
        # ~30 MB: far more than the socket buffers hold, so a browser that stops reading leaves the server in the middle of the file
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25", "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=44100",
                        "-vf", "noise=alls=40:allf=t+u", "-t", "10", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "24M", "-minrate", "24M", "-maxrate", "24M", "-bufsize", "24M",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(BIG)], check=True)
    SRT = ("1\n00:00:00,500 --> 00:00:03,500\nWelcome to this tutorial.\n\n2\n00:00:04,000 --> 00:00:07,000\nWe will build a dashboard.\n\n"
           "3\n00:00:07,500 --> 00:00:09,800\nThank you for watching.\n")
    KM = ["សូមស្វាគមន៍មកកាន់មេរៀននេះ។", "យើងនឹងសាងសង់ Dashboard មួយ។", "សូមអរគុណដែលបានទស្សនា។"]
    data = WORK / "data_winlock"
    shutil.rmtree(data, ignore_errors=True)
    (data / "jobs").mkdir(parents=True)
    LOG, HELD = WORK / "winlock_refused.log", WORK / "winlock_held.txt"
    LOG.write_text("")
    HELD.write_text("")
    env = {"PYTHONPATH": f"{WINLOCK}{os.pathsep}{STUB}", "KDS_WINLOCK_SIM": "1", "KDS_WINLOCK_LOG": str(LOG), "KDS_WINLOCK_FILE": str(HELD)}
    srv = Server(8074, data, make_stub_home(WORK / "voxhome_winlock"), extra_env=env, name="winlock").start()
    import atexit
    atexit.register(srv.stop)

    EDGE = {"id": "km-KH-SreymomNeural", "engine": "edge", "auto": {"on": False}}
    OUT = {"sync": "fit", "video": True, "max_height": 720}

    def refused():
        return [x for x in LOG.read_text().splitlines() if x.strip()]

    def hold(*names):
        HELD.write_text("\n".join(names))

    def regen(jid, segs=None, voice=None, timeout=240):
        body = {"voice": voice or EDGE, "output": OUT}
        if segs is not None:
            body["segments"] = segs
        r = srv.api("POST", f"/api/jobs/{jid}/regenerate", json=body)
        assert r.status_code == 200, r.text
        return srv.wait_job(jid, timeout)

    up = srv.api("POST", "/api/uploads", params={"name": "big.mp4"}, content=BIG.read_bytes(), timeout=120).json()
    body = {"source": {"type": "upload", "upload_id": up["id"], "text": SRT, "lang": "en", "subs": "auto"}, "translate": {"engine": "manual"}, "voice": EDGE, "output": OUT}
    first = srv.wait_job(srv.api("POST", "/api/jobs/dub", json=body).json()["id"], 120)
    JID = first["id"]
    j = regen(JID, [{"idx": i, "km": KM[i]} for i in range(3)])
    JD = data / "jobs" / JID
    print(f"  fixture: the video is {BIG.stat().st_size / 1e6:.0f} MB, the dubbed MP4 {(JD / 'dubbed.mp4').stat().st_size / 1e6:.0f} MB")
    c.check(first["status"] == "done" and j["status"] == "done" and "dubbed.mp4" in j["outputs"] and "dub.mp3" in j["outputs"] and (JD / "dubbed.mp4").stat().st_size > 20_000_000,
            "fixture: a finished job with a big dubbed.mp4 on a server that behaves like Windows", str(j.get("error")))

# ==================================================================================================================== B. API
if "B" in ONLY:
    try:
        # ---- three downloads that the browser does not finish: the MP4 (Range), the Khmer audio and the original video
        old_mp4 = (JD / "dubbed.mp4").read_bytes()
        urls = [f"/api/jobs/{JID}/file/dubbed.mp4", f"/api/jobs/{JID}/file/dub.mp3", f"/api/jobs/{JID}/source"]
        streams = []
        for u in urls:
            cm = httpx.stream("GET", srv.url + u, headers={"Range": "bytes=0-"}, timeout=60)
            r = cm.__enter__()
            it = r.iter_bytes(65536)
            streams.append((cm, r, it, next(it)))
        c.check(all(s[1].status_code == 206 and s[1].headers.get("accept-ranges") == "bytes" for s in streams), "three streams are open and half-read, like a browser that has a <video> and two players in the page",
                str([s[1].status_code for s in streams]))
        time.sleep(1.0)
        j = regen(JID, [{"idx": 0, "km": KM[0] + " "}], {"id": "km-KH-PisethNeural", "engine": "edge", "auto": {"on": False}})
        c.check(j["status"] == "done" and j["error"] is None and "dubbed.mp4" in j["outputs"], "Regenerate while the MP4 / audio / video are open: DONE (before: 'Internal error' - PermissionError WinError 32)", str(j.get("error")))
        c.check([s["status"] for s in j["steps"] if s["key"] in ("tts", "mix", "video")] == ["done", "done", "done"], "…the three steps ran: speech, mix, MP4")
        c.check(refused() == [], "…and Windows never had to refuse a delete or a replace", str(refused()))
        # the half-read MP4 stream: it ends (it does not hang, and it is never a mixture of the old and the new file)
        cm, r, it, first_chunk = streams[0]
        got, err = first_chunk, None
        try:
            for ch in it:
                got += ch
        except Exception as e:  # noqa: BLE001 - the browser sees a response that is shorter than announced
            err = e
        c.check(len(got) < len(old_mp4) and got == old_mp4[:len(got)] and err is not None, "the stalled MP4 download ends early and carries only bytes of the OLD file",
                f"{len(got)} of {len(old_mp4)} bytes, {type(err).__name__}")
        for cm, *_ in streams:
            try:
                cm.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
        # what the browser asks for next is the NEW file, byte for byte
        new_mp4 = (JD / "dubbed.mp4").read_bytes()
        r = srv.api("GET", urls[0], timeout=120)
        c.check(r.status_code == 200 and hashlib.sha1(r.content).digest() == hashlib.sha1(new_mp4).digest() and new_mp4 != old_mp4 and r.headers["content-length"] == str(len(new_mp4)),
                "a new request gets the new dubbed.mp4, byte for byte (Content-Length right)", str(r.status_code))
        r = srv.api("GET", urls[0], headers={"Range": "bytes=1000-1999"})
        c.check(r.status_code == 206 and r.content == new_mp4[1000:2000] and r.headers["content-range"] == f"bytes 1000-1999/{len(new_mp4)}", "…and a Range request (seeking) gets the right piece")
        r = srv.api("GET", f"/api/jobs/{JID}/file/dub.mp3", params={"download": 1})
        c.check(r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('_khmer_dub.mp3"') and r.headers["content-type"].startswith("audio/mpeg"),
                "the download of the audio keeps its name and type", r.headers.get("content-disposition", ""))
        c.check(srv.api("GET", "/api/health").status_code == 200 and srv.api("GET", f"/api/jobs/{JID}/file/nothing.mp3").status_code == 404, "the server is healthy; an unknown file is a clean 404")

        # ---- a program OUTSIDE holds the old MP4 for a moment (an antivirus scan, a player): Regenerate waits and goes on
        hold("dubbed.mp4")
        threading.Timer(1.5, lambda: hold()).start()
        j = regen(JID, [{"idx": 1, "km": KM[1] + " "}])
        ref = refused()
        c.check(j["status"] == "done" and "dubbed.mp4" in j["outputs"] and any(x.startswith("unlink") for x in ref), "an outside program holds the old MP4 for 1.5 s: Regenerate retries the delete and finishes", f"{j['status']} {j.get('error')} {ref}")
        hold()
        LOG.write_text("")

        # ---- ... and for good: the audio is made, the MP4 is not, and the user is told in plain words; the way back is 'make the video again'
        hold("dubbed.mp4")
        j = regen(JID, [{"idx": 2, "km": KM[2] + " "}])
        vid = next(s for s in j["steps"] if s["key"] == "video")
        c.check(j["status"] == "done" and "dub.mp3" in j["outputs"] and "dubbed.mp4" not in j["outputs"] and vid["status"] == "error" and any(w["code"] == "FFMPEG_FAILED" and "in use by another program" in w["message"] for w in j["warnings"]),
                "the old MP4 is held for good: the new audio is ready, the MP4 step says so (a warning, not an 'Internal error')", f"{j['status']} {vid} {j['warnings']}")
        c.check(any("still open in another program" in x for x in j["logs"]), "…the log says that the old file could not be removed")
        hold()
        r = srv.api("POST", f"/api/jobs/{JID}/video", json={"aspect": "original", "max_height": 720})
        j = srv.wait_job(JID, 240) if r.status_code == 200 else {"status": r.text, "outputs": {}}
        c.check(r.status_code == 200 and j["status"] == "done" and "dubbed.mp4" in j["outputs"], "…the lock is gone: 'make the video again' brings the MP4 back (the audio and the edits stay)", str(j.get("error") or j.get("status")))
        LOG.write_text("")

        # ---- a Regenerate that fails for another reason (a saved voice that does not exist any more): the job keeps its audio and the edits
        j = regen(JID, [{"idx": 0, "km": KM[0] + " ផង"}], {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:c:deadbeef", "quality": "fast", "consent": True}, "auto": {"on": False}})
        c.check(j["status"] == "error" and j["error"]["code"] == "VOX_NO_REF" and "dub.mp3" in j["outputs"] and " ផង" in next(s for s in j["segments"] if s["idx"] == 0)["km"],
                "a Regenerate that fails (a saved voice is gone): the old audio stays in the job and the edit is saved", str(j.get("error")))
        j = regen(JID, [{"idx": 0, "km": KM[0]}])
        c.check(j["status"] == "done" and "dubbed.mp4" in j["outputs"] and j["error"] is None, "…and the next Regenerate just works", str(j.get("error")))
        LOG.write_text("")
    except Exception:
        hold()
        raise

# ==================================================================================================================== C. browser
if "C" in ONLY:
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script("localStorage.setItem('kds_lang','en'); localStorage.setItem('kds_settings', JSON.stringify({ ui: { dock: true }, output: { format: 'video' } }));")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "favicon" not in m.text and "Failed to load resource" not in m.text else None)
            pg.on("dialog", lambda d: d.accept())

            def open_job():
                pg.goto(srv.url + "/#history")
                pg.wait_for_selector("[data-open]", timeout=10000)
                pg.wait_for_timeout(500)
                pg.evaluate("(id) => { [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id).click(); }", JID)
                pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
                pg.wait_for_timeout(1200)

            def stamp():
                return srv.api("GET", f"/api/jobs/{JID}").json()["updated"]

            def finish(since, timeout=180):
                """Wait for the job that was started by a click AFTER `since` (the old 'done' of the previous run must not count)."""
                t0 = time.time()
                while time.time() - t0 < timeout:
                    s = srv.api("GET", f"/api/jobs/{JID}").json()
                    if s["status"] in ("done", "error", "cancelled") and s["updated"] > since:
                        pg.wait_for_timeout(1500)
                        return s
                    time.sleep(0.4)
                raise TimeoutError("job did not finish")

            def edit_line(i, extra):
                ta = pg.locator("#dub-result .seg-row textarea").nth(i)
                ta.click()
                ta.press("End")
                ta.type(extra)
                pg.wait_for_timeout(250)

            # ---- the MP4 plays, a line is clicked (the video plays from there), a line is edited, Regenerate
            open_job()
            c.check(pg.locator("#mp4-panel video").count() == 1, "the result shows the MP4 preview (a <video> that the browser reads from the server)")
            pg.locator("#dub-result .seg-row .en").nth(1).click()
            pg.wait_for_timeout(2000)
            st = pg.evaluate("() => { const v = document.querySelector('#mp4-panel video'); return [v.currentTime, v.paused, v.readyState]; }")
            c.check(not st[1] and st[0] > 3.5 and st[2] >= 2, "a click on line 2 plays the video from there", str(st))
            src_before = pg.evaluate("document.querySelector('#mp4-panel video').getAttribute('src')")
            edit_line(0, " ណាស់")
            t_0 = stamp()
            pg.locator("#btn-regen").click()
            s = finish(t_0)
            c.check(s["status"] == "done" and s["error"] is None, "click 'Regenerate audio' while the video plays: the job is DONE (before: 'Internal error')", str(s.get("error")))
            c.check(refused() == [], "…Windows had nothing to refuse", str(refused()))
            c.check("Internal error" not in pg.inner_text("#dub-progress") and pg.locator("#dub-result .seg-row").count() == 3 and "ណាស់" in pg.locator("#dub-result .seg-row textarea").nth(0).input_value(),
                    "the page shows the finished job again with the corrected line")
            src_after = pg.evaluate("document.querySelector('#mp4-panel video').getAttribute('src')")
            c.check(src_after and src_after != src_before, "…and the new MP4 is a new address (the browser does not show the old file from its cache)", f"{src_before} -> {src_after}")

            # ---- a Regenerate that is cancelled keeps the editor and the corrected text: no need to make the whole video again
            words = (" ជាមួយ", " ផង", " ទៀត")
            for attempt in range(3):                       # the job is quick: if it was done before the click arrived, edit again and retry
                for i, w in enumerate(words):
                    edit_line(i, w)
                t_0 = stamp()
                pg.locator("#btn-regen").click()
                pg.wait_for_selector("#btn-cancel:not(.hidden)", timeout=15000)
                pg.locator("#btn-cancel").click()
                s = finish(t_0)
                if s["status"] == "cancelled":
                    break
                words = tuple(w + "ៗ" for w in words)
            c.check(s["status"] == "cancelled", "a Regenerate that is cancelled by the user", str(s["status"]) + str(s.get("error")))
            c.check(pg.locator("#dub-result").is_visible() and pg.locator("#dub-result .seg-row").count() == 3, "…the editor is STILL there with all lines (before: gone, the whole video had to be made again)")
            c.check(all(w.strip() in pg.locator("#dub-result .seg-row textarea").nth(i).input_value() for i, w in enumerate(words)), "…with the text the user typed (it is saved in the job)")
            c.check("The last Regenerate did not finish" in pg.inner_text("#dub-result") and pg.locator("#dub-audio").count() == 1, "…and a notice says that the audio shown is the old one")
            t_0 = stamp()
            pg.locator("#btn-regen").click()
            s = finish(t_0)
            c.check(s["status"] == "done" and "dubbed.mp4" in s["outputs"], "…Regenerate audio again, from the same editor -> DONE", str(s.get("error")))
            c.check("The last Regenerate did not finish" not in pg.inner_text("#dub-result") and pg.locator("#dub-result .seg-row").count() == 3, "…the notice is gone")

            # ---- a Regenerate that failed (before the page was opened): open the job from the history -> the editor, the notice, the error
            j = regen(JID, [{"idx": 0, "km": KM[0] + " ណា"}], {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:c:deadbeef", "quality": "fast", "consent": True}, "auto": {"on": False}})
            c.check(j["status"] == "error", "a Regenerate that failed (a saved voice is gone)", str(j["status"]))
            open_job()
            c.check(pg.locator("#dub-result .seg-row").count() == 3 and "The last Regenerate did not finish" in pg.inner_text("#dub-result") and "ណា" in pg.locator("#dub-result .seg-row textarea").nth(0).input_value(),
                    "opened from the history: the editor with the saved text and the notice (the job is not a dead end)")
            c.check(pg.locator("#dub-progress").is_visible() and "Error" in pg.inner_text("#dub-progress") and "Internal error" not in pg.inner_text("#dub-progress"), "…and the progress card names the error (not 'Internal error')")
            t_0 = stamp()
            pg.locator("#btn-regen").click()
            s = finish(t_0)
            c.check(s["status"] == "done" and "The last Regenerate did not finish" not in pg.inner_text("#dub-result"), "…Regenerate audio from there -> DONE", str(s.get("error")))
            b.close()
    finally:
        hold()

if srv:
    srv.stop()
real = [e for e in errors if "favicon" not in e]
c.check(not real, "no JavaScript errors in any page", "; ".join(real[:4]))
sys.exit(c.done())
