"""Smoke test of a BUILT zip: unpack it into a scratch folder, start the server from there and walk the main paths (a real dub,
a vertical TikTok video, the launchers, the line endings, the file modes) - and run the unit suite of the UNPACKED copy.

    python tests/smoke_zip.py [path/to/khmer-dubbing-studio-vX.Y.Z.zip]     (default: the zip of the current version, next to the project folder)

It needs the fixtures that test_upload.py, test_tiktok.py and test_speakers.py build in WORK: run those three suites once before.
Uses the real Google Translate and Microsoft Edge TTS (internet).
"""
import os
import shutil
import subprocess
import sys
import time
import zipfile

from lib import *  # noqa: F401,F403
import httpx

ZIP = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PROJECT.parent / f"khmer-dubbing-studio-v{VERSION}.zip"
if not ZIP.exists():
    sys.exit(f"zip not found: {ZIP}  (build it with:  python tools/build_zip.py)")
for fx in (WORK / "fx_upload" / "with_subs.mp4", WORK / "fx_tiktok" / "wide.mp4", WORK / "fx_speakers" / "dialog.wav", WORK / "fx_speakers" / "dialog.srt"):
    if not fx.exists():
        sys.exit(f"fixture missing: {fx}  (run  python tests/test_upload.py, test_tiktok.py and test_speakers.py  once first)")

out = WORK / "zipcheck"
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)
with zipfile.ZipFile(ZIP) as _z:                      # extract AND restore the file modes (extractall alone drops the executable bit)
    for _i in _z.infolist():
        _p = _z.extract(_i, out)
        if (_i.external_attr >> 16) & 0o777:
            os.chmod(_p, (_i.external_attr >> 16) & 0o777)
proj = out / "khmer-dubbing-studio"
home = make_stub_home(WORK / "voxhome_zip")
env = dict(os.environ, KDS_VOX_HOME=str(home), KDS_VOX_STUB="1", KDS_VOX_DISABLE_INSTALL="1", PYTHONPATH=str(STUB), HOST="127.0.0.1", PORT="8020", NO_BROWSER="1")
env.pop("KDS_DATA_DIR", None)
fh = open(WORK / "zip.log", "wb")
p = subprocess.Popen([sys.executable, "server.py"], cwd=str(proj), env=env, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
c = Checker("extracted zip")
base = "http://127.0.0.1:8020"
try:
    for _ in range(100):
        try:
            if httpx.get(base + "/api/health", timeout=2).status_code == 200: break
        except Exception: time.sleep(0.2)
    h = httpx.get(base + "/api/health").json(); print(h)
    c.check(h["version"] == VERSION and h["ui_ok"], f"health: {VERSION}, UI files match", str(h))
    idx = httpx.get(base + "/").text
    c.check("kds-ui" in idx and VERSION in idx, f"index page is v{VERSION}")
    v = httpx.get(base + "/api/voices").json()
    c.check(len(v["vox"]["presets"]) == 8, "8 designed voices listed")
    srt = (proj / "samples" / "technical-tutorial.zh.srt").read_text(encoding="utf-8")
    body = {"source": {"type": "transcript", "text": srt, "lang": "auto"},
            "voice": {"id": "km-KH-SreymomNeural", "engine": "edge", "vox": {"id": "vox:original", "quality": "fast", "consent": False}},
            "translate": {"engine": "google", "keep_terms": True}, "output": {"sync": "fit", "max_speedup": 1.4}}
    jid = httpx.post(base + "/api/jobs/dub", json=body, timeout=30).json()["id"]
    def wait(jid, t=300):
        t0 = time.time()
        while time.time() - t0 < t:
            j = httpx.get(f"{base}/api/jobs/{jid}").json()
            if j["status"] in ("done", "error"): return j
            time.sleep(1)
    j = wait(jid)
    c.check(j["status"] == "done" and j["meta"]["src_lang"] == "zh", "Chinese sample dubbed (Google + Edge)", str(j.get("error")))
    n = len(j["segments"])
    r = httpx.post(f"{base}/api/jobs/{jid}/regenerate", json={"segments": [{"idx": 1, "voice": "km-KH-PisethNeural"}, {"idx": 2, "voice": "vox:p:f_calm"}, {"idx": 3, "t0": j["segments"][3]["start"] + 0.4}]}, timeout=30)
    c.check(r.status_code == 200, "regenerate accepted", r.text[:200])
    j = wait(jid)
    c.check(j["status"] == "done" and j["segments"][1]["voice"] == "km-KH-PisethNeural" and j["segments"][2]["voice"] == "vox:p:f_calm" and j["segments"][3]["t0"] > j["segments"][3]["start"], "per-line voice + time work from the zip", str(j.get("error")))
    c.check(j["meta"]["vox"]["voices"] == ["vox:p:f_calm"] and abs(j["segments"][3]["out_start"] - j["segments"][3]["t0"]) < 0.5, "designed voice + hand-set start used", str(j["meta"].get("vox")))
    mp3 = httpx.get(f"{base}/api/jobs/{jid}/file/dub.mp3")
    c.check(mp3.status_code == 200 and len(mp3.content) > 20000, "dub.mp3 downloadable")
    kh = httpx.get(f"{base}/api/jobs/{jid}/file/khmer.srt").text
    c.check(kh.count("-->") >= n - 2, "khmer.srt has the lines")
    bad = httpx.post(f"{base}/api/jobs/{jid}/regenerate", json={"segments": [{"idx": 1, "voice": "nonsense"}]}, timeout=30)
    c.check(bad.status_code == 400, "bad voice -> 400")
    # v1.8: upload a video
    fxp = WORK / "fx_upload" / "with_subs.mp4"
    ui = httpx.post(base + "/api/uploads", params={"name": "with_subs.mp4"}, content=fxp.read_bytes(), timeout=60).json()
    c.check(ui["has_video"] and ui["subtitles"] and ui["pick"] == 0 and httpx.get(base + ui["thumbnail"]).status_code == 200, "upload works from the zip (probe + subtitles + thumbnail)", str(ui)[:150])
    ub = {"source": {"type": "upload", "upload_id": ui["id"], "lang": "auto"}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google", "keep_terms": True},
          "output": {"sync": "fit", "video": True, "orig_volume": 20}}
    ujid = httpx.post(base + "/api/jobs/dub", json=ub, timeout=30).json()["id"]
    uj = wait(ujid)
    c.check(uj["status"] == "done" and "dubbed.mp4" in uj["outputs"] and uj["meta"]["transcript"]["source"] == "embedded", "upload job: embedded subtitles -> Khmer dub + MP4 from the zip", str(uj.get("error")))
    c.check(httpx.get(f"{base}/api/jobs/{ujid}/source", headers={"Range": "bytes=0-9"}).status_code == 206, "uploaded video is served with Range")
    c.check("installed" in httpx.get(base + "/api/whisper/status").json(), "whisper status endpoint")
    c.check((proj / "app" / "uploads.py").exists() and (proj / "app" / "whisper_setup.py").exists() and not (proj / "data" / "uploads").exists() or (proj / "data" / "uploads").exists(), "new modules are in the zip")
    # ---- vertical (TikTok) video from the zip
    upw = httpx.post(base + "/api/uploads", params={"name": "wide.mp4"}, content=(WORK / "fx_tiktok" / "wide.mp4").read_bytes(), timeout=60).json()
    tb = {"source": {"type": "upload", "upload_id": upw["id"], "lang": "en", "text": "1\n00:00:00,500 --> 00:00:03,000\nWelcome to this tutorial about the API.\n\n2\n00:00:03,500 --> 00:00:06,500\nWe will build a Dashboard with Python.\n"},
          "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google", "keep_terms": True},
          "output": {"sync": "fit", "video": True, "max_height": 720, "aspect": "9:16", "fit": "blur", "crop_x": 50}}
    tjid = httpx.post(base + "/api/jobs/dub", json=tb, timeout=30).json()["id"]
    tj = wait(tjid)
    mvv = tj["meta"].get("video") or {}
    c.check(tj["status"] == "done" and mvv.get("aspect") == "9:16" and (mvv.get("out_width"), mvv.get("out_height")) == (720, 1280), "TikTok job from the zip: 720x1280 vertical MP4", str(tj.get("error")) + str(mvv))
    rr = httpx.post(f"{base}/api/jobs/{tjid}/video", json={"aspect": "9:16", "fit": "crop", "crop_x": 0, "max_height": 720}, timeout=30)
    tj = wait(tjid)
    c.check(rr.status_code == 200 and tj["status"] == "done" and tj["meta"]["video"]["fit"] == "crop", "POST /video (make only the video again) works from the zip", rr.text[:120] + str(tj.get("error")))
    dl = httpx.get(f"{base}/api/jobs/{tjid}/file/dubbed.mp4", params={"download": 1})
    c.check(dl.status_code == 200 and "_khmer_tiktok_9x16.mp4" in dl.headers.get("content-disposition", ""), "the vertical video downloads with a TikTok file name")
    c.check((proj / "app" / "frame.py").exists(), "app/frame.py is in the zip")
    # ---- v1.13: voices by character from the zip - a man and a woman talk, the app listens, Piseth speaks the man's lines, Srey Mom the woman's
    ud = httpx.post(base + "/api/uploads", params={"name": "dialog.wav"}, content=(WORK / "fx_speakers" / "dialog.wav").read_bytes(), timeout=60).json()
    db = {"source": {"type": "upload", "upload_id": ud["id"], "lang": "en", "text": (WORK / "fx_speakers" / "dialog.srt").read_text(encoding="utf-8")},
          "voice": {"id": "km-KH-SreymomNeural", "engine": "edge", "auto": {"on": True, "male": "", "female": ""}},
          "translate": {"engine": "google", "keep_terms": True}, "output": {"sync": "fit"}}
    djid = httpx.post(base + "/api/jobs/dub", json=db, timeout=30).json()["id"]
    dj = wait(djid)
    chs, cvs = dj["meta"].get("characters") or [], dj["meta"].get("char_voices") or {}
    c.check(dj["status"] == "done" and sorted(x["gender"] for x in chs) == ["female", "male"] and sorted(cvs.values()) == ["km-KH-PisethNeural", "km-KH-SreymomNeural"],
            "voices by character from the zip: a man and a woman found; Piseth + Srey Mom (Google + Edge)", str(dj.get("error")) + str(cvs))
    c.check(all(s.get("char") for s in dj["segments"]) and next(s for s in dj["steps"] if s["key"] == "speakers")["status"] == "done", "…every line has its character; the 'speakers' step is done")
    rr = httpx.post(f"{base}/api/jobs/{djid}/speakers", json={}, timeout=30)
    dj2 = wait(djid)
    c.check(rr.status_code == 200 and dj2["status"] == "done" and len(dj2["meta"]["characters"]) == len(chs), "POST /speakers (detect again) works from the zip", rr.text[:120])
    # ---- Windows + macOS files in the zip
    zf = zipfile.ZipFile(ZIP)
    names = {i.filename: i for i in zf.infolist()}
    for f in ("start.sh", "start.command", "install-voxcpm.sh", "install-voxcpm.command", "tests/run_all.sh"):
        info = names.get("khmer-dubbing-studio/" + f)
        c.check(info is not None and (info.external_attr >> 16) & 0o111 == 0o111, f"zip: {f} is stored executable (a double-click on a Mac needs it)", str(info and oct(info.external_attr >> 16)))
        c.check(info is not None and b"\r" not in zf.read(info), f"zip: {f} has Unix line endings")
    for f in ("start.bat", "install-voxcpm.bat"):
        raw = zf.read("khmer-dubbing-studio/" + f)
        c.check(raw.count(b"\r\n") == raw.count(b"\n"), f"zip: {f} has Windows line endings")
    r = subprocess.run(["sh", "start.sh"], cwd=str(proj), capture_output=True, text=True, env=dict(os.environ, KDS_DRY_RUN="1"))
    c.check(r.returncode == 0 and r.stdout.startswith("PYTHON="), "extracted start.sh finds a Python (dry run)", r.stdout + r.stderr)
    rc = subprocess.run(["sh", "start.command"], cwd=str(proj), capture_output=True, text=True, env=dict(os.environ, KDS_DRY_RUN="1"), input="")
    c.check(rc.returncode == 0 and rc.stdout.startswith("PYTHON="), "extracted start.command works (dry run)")
    # ---- the developer kit
    for f in ("DEVELOPMENT.md", "HANDOFF_PROMPT.md", "tests/lib.py", "tests/run_all.sh", "tests/requirements-dev.txt", "tools/bump_version.py",
              "tools/build_zip.py", "tests/fixtures/jobs/6b011b123f/job.json"):
        c.check("khmer-dubbing-studio/" + f in names, f"zip: {f} is included")
    # ---- installable app (PWA, v1.11): the files are in the zip and the server hands them out
    for u, ct in (("/manifest.webmanifest", "application/manifest+json"), ("/sw.js", "javascript"), ("/offline.html", "text/html"), ("/static/icons/icon-512.png", "image/png")):
        rp = httpx.get(base + u)
        c.check(rp.status_code == 200 and ct in rp.headers["content-type"], f"PWA from the zip: {u} is served ({ct})", str(rp.status_code))
    c.check(f"kds-offline-{VERSION}" in httpx.get(base + "/sw.js").text, "PWA from the zip: sw.js carries the version")
    c.check(all("khmer-dubbing-studio/" + f in names for f in ("static/manifest.webmanifest", "static/sw.js", "static/offline.html", "static/icons/icon-192.png", "static/icons/icon-512.png",
                                                              "static/icons/icon-maskable-512.png", "static/icons/apple-touch-icon.png", "tools/make_icons.py", "tests/test_pwa.py")), "zip: the PWA files are included")
    c.check(all("khmer-dubbing-studio/" + f in names for f in ("app/speakers.py", "app/autovoice.py", "tests/test_speakers.py", "tests/synthvoice.py")), "zip: the voices-by-character modules and their tests are included")
    bad = [n for n in names if "/data/" in n or "__pycache__" in n or n.endswith((".pyc", ".DS_Store", ".zip"))]
    c.check(not bad, "zip: no user data, caches or other zips inside", str(bad[:5]))
    r = subprocess.run([sys.executable, "tools/bump_version.py", "--check"], cwd=str(proj), capture_output=True, text=True)
    c.check(r.returncode == 0 and VERSION in r.stdout, "tools/bump_version.py --check works in the unpacked folder", r.stdout + r.stderr)
    env2 = dict(os.environ, KDS_TEST_WORK=str(WORK / "zipcheck_work"))
    env2.pop("KDS_DATA_DIR", None)
    r = subprocess.run([sys.executable, "tests/test_units.py"], cwd=str(proj), capture_output=True, text=True, env=env2, timeout=600)
    c.check(r.returncode == 0 and " 0 failed" in r.stdout, "the unit suite passes in the UNPACKED copy (the tests are portable)", (r.stdout + r.stderr)[-400:])
    r = subprocess.run([sys.executable, "tests/test_speakers.py"], cwd=str(proj), capture_output=True, text=True, env=dict(env2, ONLY="A"), timeout=600)
    c.check(r.returncode == 0 and " 0 failed" in r.stdout, "the voices-by-character unit tests pass in the UNPACKED copy (numpy only)", (r.stdout + r.stderr)[-400:])
finally:
    try:
        os.killpg(os.getpgid(p.pid), 15)
    except Exception:
        p.terminate()
    subprocess.run(["sh", "-c", "pkill -f 'vox_worker.py.*voxhome_zip' || true"], capture_output=True)
sys.exit(c.done())
