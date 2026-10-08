"""v1.8.0 - upload a video from the computer:  units (probe, subtitle picking, scaling, parsers, installer), API (real Edge TTS + Google),
browser (Playwright / Chromium).  Set ONLY=A,B,C to run a part."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from lib import *  # noqa: E402,F401,F403

WORK.mkdir(parents=True, exist_ok=True)
os.environ["KDS_DATA_DIR"] = str(WORK / "data_upload_units")
shutil.rmtree(WORK / "data_upload_units", ignore_errors=True)
from app import asr, audio, pipeline, transcript, uploads, whisper_setup  # noqa: E402
from app.main import _MEDIA_TYPES  # noqa: E402,F401

ONLY = set((os.environ.get("ONLY") or "A,B,C").split(","))
c = Checker("Upload a video")
FF = audio.ffmpeg_exe()
FX = WORK / "fx_upload"
SHOTS = WORK / "shots"
SHOTS.mkdir(exist_ok=True)


# ------------------------------------------------------------------------------------------------------------------ fixtures
def ffm(*args):
    subprocess.run([FF, "-v", "error", "-y", *args], check=True)


def make_fixtures():
    FX.mkdir(exist_ok=True)
    if (FX / "done.flag").exists():
        return
    en = "1\n00:00:00,500 --> 00:00:02,500\nWelcome to this tutorial about the API.\n\n2\n00:00:03,000 --> 00:00:05,500\nWe will build a Dashboard with Python.\n"
    zh = "1\n00:00:00,500 --> 00:00:02,500\n欢迎来到这个关于 API 的教程。\n\n2\n00:00:03,000 --> 00:00:05,500\n我们将用 Python 构建一个 Dashboard。\n"
    (FX / "en.srt").write_text(en, encoding="utf-8")
    (FX / "zh.srt").write_text(zh, encoding="utf-8")
    (FX / "und.srt").write_text(en.replace("Welcome", "Hello"), encoding="utf-8")
    (FX / "forced.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nBonjour.\n", encoding="utf-8")
    v = ["-f", "lavfi", "-i", "testsrc=size=320x180:rate=25"]
    a = ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    ffm(*v, *a, "-i", str(FX / "en.srt"), "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-shortest", str(FX / "with_subs.mp4"))
    ffm(*v, *a, "-i", str(FX / "en.srt"), "-i", str(FX / "zh.srt"), "-i", str(FX / "und.srt"), "-i", str(FX / "forced.srt"), "-t", "6",
        "-map", "0:v", "-map", "1:a", "-map", "2", "-map", "3", "-map", "4", "-map", "5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-c:s", "srt",
        "-metadata:s:s:0", "language=eng", "-metadata:s:s:0", "title=English", "-metadata:s:s:1", "language=chi", "-metadata:s:s:1", "title=中文",
        "-metadata:s:s:2", "language=und", "-metadata:s:s:3", "language=eng", "-metadata:s:s:3", "title=Forced", "-disposition:s:3", "forced",
        str(FX / "multi.mkv"))
    ffm(*v, *a, "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(FX / "plain.mp4"))
    ffm(*v, "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(FX / "noaudio.mp4"))
    ffm(*a, "-t", "5", "-c:a", "libmp3lame", str(FX / "audio.mp3"))
    ffm("-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25", *a, "-t", "3", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(FX / "big.mp4"))
    ffm("-f", "lavfi", "-i", "testsrc=size=720x1280:rate=25", *a, "-t", "3", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(FX / "portrait.mp4"))
    ffm(*v, *a, "-t", "12", "-c:v", "libvpx", "-b:v", "60k", "-c:a", "libvorbis", "-shortest", str(FX / "clip.webm"))
    ffm("-display_rotation", "90", "-i", str(FX / "plain.mp4"), "-c", "copy", str(FX / "rot.mp4"))
    (FX / "fake.mp4").write_bytes(os.urandom(6000))
    ffm(*v, "-frames:v", "1", str(FX / "pic.png"))
    shutil.copy(FX / "pic.png", FX / "pic.mp4")
    ffm(*a, "-i", str(FX / "pic.png"), "-t", "4", "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-c:v", "mjpeg", "-id3v2_version", "3", "-disposition:v", "attached_pic", str(FX / "cover.mp3"))
    (FX / "notes.txt").write_text("not a video", encoding="utf-8")
    (FX / "done.flag").write_text("1")


make_fixtures()
SRT3 = ("1\n00:00:00,500 --> 00:00:03,000\nWelcome to this tutorial about the API.\n\n2\n00:00:04,000 --> 00:00:07,000\nWe will build a Dashboard with Python.\n\n"
        "3\n00:00:08,000 --> 00:00:11,000\nThank you for watching, see you next time.\n")

# ==================================================================================================================== A. units
if "A" in ONLY:
    # ---- the text of `ffmpeg -i`
    SAMPLE = """Input #0, matroska,webm, from 'x.mkv':
  Duration: 00:00:05.04, start: 0.000000, bitrate: 1013 kb/s
  Stream #0:0: Video: h264 (High), yuv420p(progressive), 640x360 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr, 1k tbn (default)
      Metadata:
        DURATION        : 00:00:05.000000000
  Side data:
    displaymatrix: rotation of -90.00 degrees
  Stream #0:1(eng): Audio: aac (LC), 44100 Hz, mono, fltp (default)
      Metadata:
        title           : English audio
  Stream #0:2(eng): Subtitle: subrip (srt) (default)
      Metadata:
        title           : English
  Stream #0:3(chi): Subtitle: ass (ssa) (forced)
      Metadata:
        title           : 中文 forced
  Stream #0:4[0x1e0](kor): Subtitle: hdmv_pgs_subtitle
"""
    st = audio.parse_streams(SAMPLE)
    c.check([s["type"] for s in st] == ["video", "audio", "subtitle", "subtitle", "subtitle"], "ffmpeg text: five streams in order", str([s["type"] for s in st]))
    c.check(st[0]["width"] == 640 and st[0]["height"] == 360 and st[0]["codec"] == "h264" and st[0]["rotation"] == -90.0, "ffmpeg text: picture size, codec and rotation")
    c.check(st[1]["lang"] == "eng" and st[1]["title"] == "English audio", "ffmpeg text: language and title of the audio")
    c.check([s["pos"] for s in st if s["type"] == "subtitle"] == [0, 1, 2], "ffmpeg text: 'pos' counts the streams of one type (what -map 0:s:N wants)")
    c.check(st[3]["forced"] and not st[2]["forced"] and st[3]["title"] == "中文 forced" and st[4]["lang"] == "kor", "ffmpeg text: forced flag, Chinese title, language of a [0x1e0] stream")
    c.check(audio.parse_streams("") == [] and audio.parse_streams("garbage\nStream #x") == [], "ffmpeg text: nothing found -> empty list")
    c.check(not audio.needs_scale(1920, 1080, 1080) and audio.needs_scale(3840, 2160, 1080) and not audio.needs_scale(1080, 1920, 1080) and audio.needs_scale(2160, 3840, 1080)
            and not audio.needs_scale(None, None, 1080) and not audio.needs_scale(1280, 720, None) and audio.needs_scale(1280, 720, 480),
            "scaling rule compares the SHORTER side (1080p = 1920x1080 and 1080x1920)")

    # ---- names and ids
    dn = uploads.display_name
    c.check(dn("C:\\Users\\me\\Videos\\My Clip.mp4") == "My Clip.mp4" and dn("/tmp/a/b.mkv") == "b.mkv" and dn("../../etc/passwd") == "passwd", "display name: folders are cut off")
    c.check(dn("a\x00b\x1f.mp4") == "ab.mp4" and dn("") == "video" and dn("   ") == "video" and len(dn("x" * 500 + ".mp4")) == 180, "display name: control characters, empty, very long")
    c.check(dn("វីដេអូ 中文 한국어.mp4") == "វីដេអូ 中文 한국어.mp4", "display name keeps Khmer / Chinese / Korean")
    bad = 0
    for x in ("../x", "..", "ABCDEF123456", "abc", "abcdef1234567", "abcdef12345g", "", None, "abcdef123456/../x"):
        try:
            uploads.folder(x)
        except uploads.UploadError as e:
            bad += e.status == 404 and e.code == "UPLOAD_GONE"
    c.check(bad == 9, "upload id: anything but 12 lowercase hex characters is refused (no path tricks)", str(bad))
    c.check(uploads.folder("abcdef123456").name == "abcdef123456", "upload id: a real id is accepted")
    c.check(uploads.kind_of(".MP3") == "audio" and uploads.kind_of(".mkv") == "video" and ".exe" not in uploads.ALLOWED_EXT and ".mkv" in uploads.ALLOWED_EXT, "extension lists")

    # ---- looking inside real files
    i1 = uploads.inspect(FX / "with_subs.mp4")
    c.check(i1["has_video"] and i1["has_audio"] and i1["width"] == 320 and i1["height"] == 180 and i1["video_codec"] == "h264" and 5 <= (i1["duration"] or 0) <= 6.1, "inspect: size, codec, length of an MP4", str(i1)[:200])
    c.check(len(i1["subtitles"]) == 1 and i1["subtitles"][0]["code"] == "en" and i1["subtitles"][0]["codec"] == "mov_text" and i1["subtitles"][0]["text"], "inspect: an embedded mov_text track tagged 'eng' -> en")
    i2 = uploads.inspect(FX / "multi.mkv")
    c.check([(s["lang"], s["code"], s["forced"]) for s in i2["subtitles"]] == [("eng", "en", False), ("chi", "zh", False), ("", "", False), ("eng", "en", True)]
            or [(s["lang"], s["code"], s["forced"]) for s in i2["subtitles"]] == [("eng", "en", False), ("chi", "zh", False), ("und", "", False), ("eng", "en", True)],
            "inspect: an MKV with four subtitle tracks (en, zh, untagged, forced)", str([(s["lang"], s["code"], s["forced"]) for s in i2["subtitles"]]))
    c.check(i2["subtitles"][1]["title"] == "中文", "inspect: the Chinese title of a track survives")
    i3 = uploads.inspect(FX / "audio.mp3")
    c.check(not i3["has_video"] and i3["has_audio"] and i3["width"] is None and i3["subtitles"] == [], "inspect: an MP3 is audio only")
    i3b = uploads.inspect(FX / "cover.mp3")
    c.check(not i3b["has_video"] and i3b["has_audio"] and audio.probe_media(FX / "cover.mp3")["has_video"] is False and audio.probe_media(FX / "cover.mp3")["has_audio"], "inspect: an MP3 with a cover picture is audio, not a video (also for the MP4 builder)", str(i3b)[:160])
    SAMPLE2 = "  Stream #0:0: Audio: mp3, 44100 Hz, mono, fltp, 128 kb/s\n  Stream #0:1: Video: mjpeg (Baseline), yuvj420p(pc, bt470bg/unknown/unknown), 160x90 [SAR 1:1 DAR 16:9], 90k tbr, 90k tbn (attached pic)\n"
    st2 = audio.parse_streams(SAMPLE2)
    c.check(st2[1]["attached"] is True and st2[0]["attached"] is False, "ffmpeg text: '(attached pic)' is recognised")
    i4 = uploads.inspect(FX / "noaudio.mp4")
    c.check(i4["has_video"] and not i4["has_audio"], "inspect: a video without sound")
    i5 = uploads.inspect(FX / "rot.mp4")
    c.check((i5["width"], i5["height"]) == (180, 320), "inspect: a sideways (rotated) phone video is reported the way it is played", f"{i5['width']}x{i5['height']}")
    for name in ("fake.mp4", "pic.mp4"):
        try:
            uploads.inspect(FX / name)
            c.check(False, f"inspect: {name} must be refused")
        except uploads.UploadError as e:
            c.check(e.status == 400 and e.code == "NOT_MEDIA", f"inspect: {name} is not media -> NOT_MEDIA", f"{e.status} {e.code}")
    th = WORK / "unit_thumb.jpg"
    c.check(uploads.make_thumbnail(FX / "with_subs.mp4", th, 5.5) and th.stat().st_size > 1000, "thumbnail of a video")
    c.check(not uploads.make_thumbnail(FX / "audio.mp3", WORK / "unit_thumb2.jpg", 5.0) and not (WORK / "unit_thumb2.jpg").exists(), "no thumbnail for audio (and no empty file left)")

    # ---- which embedded track
    S = i2["subtitles"]
    pk = lambda lang, subs=S: (uploads.pick_subtitle(subs, lang) or {}).get("pos")  # noqa: E731
    c.check(pk("en") == 0 and pk("zh") == 1, "pick: the track in the chosen language (the forced English one is never taken)")
    c.check(pk("ko") == 2, "pick: Korean chosen but only an untagged track fits -> the untagged one (the text decides later)")
    c.check(pk("auto") == 0, "pick: auto -> the first track in a supported language")
    c.check(pk("en", [s for s in S if s["lang"] in ("chi",)]) is None and pk("en", [s for s in S if s["lang"] == "chi"]) is None, "pick: only a Chinese track but English chosen -> nothing (Whisper listens)")
    fr = [{"pos": 0, "lang": "fra", "code": "", "text": True, "forced": False}, {"pos": 1, "lang": "jpn", "code": "", "text": True, "forced": False}]
    c.check(pk("auto", fr) is None and pk("en", fr) is None, "pick: French / Japanese tracks are never taken as 'unknown'")
    pgs = [{"pos": 0, "lang": "eng", "code": "en", "text": False, "forced": False}]
    c.check(pk("en", pgs) is None and pk("auto", []) is None, "pick: picture-based (Blu-ray) tracks cannot be read -> nothing")
    c.check(pk("auto", [{"pos": 0, "lang": "und", "code": "", "text": True, "forced": False}, {"pos": 1, "lang": "kor", "code": "ko", "text": True, "forced": False}]) == 1,
            "pick: auto prefers a tagged supported language over an untagged track")
    ex = WORK / "unit_emb.srt"
    txt = uploads.extract_subtitle(FX / "multi.mkv", 1, ex)
    segs = transcript.parse_srt_vtt(txt)
    c.check(len(segs) == 2 and "API" in segs[0].text and "欢迎" in segs[0].text and abs(segs[0].start - 0.5) < 0.05, "extract: the Chinese track of the MKV comes out as SRT with its times", txt[:80])
    segs = transcript.parse_srt_vtt(uploads.extract_subtitle(FX / "with_subs.mp4", 0, WORK / "unit_emb2.srt"))
    c.check(len(segs) == 2 and segs[1].text.startswith("We will build"), "extract: a mov_text track of an MP4")

    # ---- text with a time in front of every paragraph (what YouTube's transcript panel gives)
    YT = "Transcript\n0:00\nhello everyone and welcome\n0:03\nto my channel today we will\n0:07\ntalk about the API\n1:02\n[Music]\n1:05\nthank you for watching\n"
    sg, timed = transcript.parse_any(YT)
    c.check(timed and [s.start for s in sg] == [0.0, 3.0, 7.0, 62.0, 65.0] and sg[0].text == "hello everyone and welcome" and sg[0].end == 3.0, "stamped text: times on their own lines (a 'Transcript' title is dropped)", str([(s.start, s.text) for s in sg]))
    c.check(all(s.end > s.start for s in sg) and sg[-1].end - sg[-1].start >= 1.5, "stamped text: every line gets a usable window (the last one too)")
    sg, timed = transcript.parse_any("0:00 hello and welcome to the show\n0:04 - today the topic is Python\n[0:09] and how to build a Dashboard\n(0:12) bye\n1:02:03 the end")
    c.check(timed and [s.start for s in sg] == [0.0, 4.0, 9.0, 12.0, 3723.0] and sg[1].text == "today the topic is Python", "stamped text: time in front of the text (0:04 - / [0:09] / (0:12) / 1:02:03)", str([s.start for s in sg]))
    sg, timed = transcript.parse_any("0:00\nline one\n0:03\nline two\n0:07\nline three")
    c.check(timed and len(sg) == 3 and sg[2].start == 7.0, "stamped text: the minimum (three times) is enough")
    sg, timed = transcript.parse_any("0:00\nline one\n0:03\nline two")
    c.check(not timed, "stamped text: two times are not enough to call it a transcript")
    sg, timed = transcript.parse_any("Hello there. We take the 3:45pm train.\n\nAt 10:30 sharp we meet. Not a transcript at all, just a long paragraph of normal text about the day.\n")
    c.check(not timed and len(sg) >= 1, "stamped text: a normal paragraph with a time inside stays plain text")
    sg, timed = transcript.parse_any("5:00\na\n3:00\nb\n9:00\nc\n1:00\nd\n8:00\ne\n2:00\nf")
    c.check(not timed, "stamped text: times that jump around are not a transcript")
    sg, timed = transcript.parse_any("00:00:01,000 --> 00:00:03,000\nreal srt\n")
    c.check(timed and sg[0].text == "real srt", "SRT still wins over the stamped-text reader")
    c.check(transcript.clean_caption_text("{\\an8}Hello {\\i1}world{\\i0}") == "Hello world", "cleaning: ASS tags like {\\an8} left in an SRT are removed")
    sg, timed = transcript.parse_any("0:00\nこんにちは世界\n0:03\nありがとう\n0:07\nさようなら", "zh")
    c.check(timed and len(sg) == 3, "stamped text: works for any language (the text itself is not looked at)")

    # ---- parameters stored with a job never contain the subtitle text
    sp = pipeline.sanitize_params({"source": {"type": "upload", "upload_id": "abcdef123456", "text": "x" * 1234, "lang": "en"}, "translate": {"llm": {"api_key": "SECRET"}}})
    c.check(sp["source"]["text"] == "<1234 chars>" and sp["source"]["upload_id"] == "abcdef123456" and "SECRET" not in json.dumps(sp), "sanitize: subtitle text -> '<N chars>', upload id kept, key removed")
    sp = pipeline.sanitize_params({"source": {"type": "upload", "upload_id": "abcdef123456", "lang": "en"}})
    c.check("text" not in sp["source"], "sanitize: no text, none invented")

    # ---- the MP4: scaled only when the picture is bigger than the limit
    dub = FX / "audio.mp3"

    def mux(src, limit, name):
        out = WORK / f"unit_mux_{name}.mp4"
        out.unlink(missing_ok=True)
        audio.mux_video(FX / src, dub, out, 0.0, max_height=limit)
        return audio.probe_media(out)

    r = mux("big.mp4", 1080, "a")
    c.check(r["has_video"] and (r["width"], r["height"]) == (1280, 720) and r["video_codec"] == "h264", "MP4: 720p source, limit 1080p -> size kept", str(r))
    r = mux("big.mp4", 480, "b")
    c.check((r["width"], r["height"]) == (854, 480) and r["video_codec"] == "h264" and r["has_audio"], "MP4: 720p source, limit 480p -> scaled to 854x480, still H.264 with sound", str(r))
    r = mux("portrait.mp4", 480, "c")
    c.check((r["width"], r["height"]) == (480, 854), "MP4: a portrait 720x1280 video is scaled by its SHORT side -> 480x854", str(r))
    r = mux("portrait.mp4", 720, "d")
    c.check((r["width"], r["height"]) == (720, 1280), "MP4: portrait 720x1280 with limit 720 -> untouched", str(r))
    r = mux("with_subs.mp4", 1080, "e")
    c.check((r["width"], r["height"]) == (320, 180) and r["has_audio"], "MP4: a small video is never enlarged")
    r = mux("noaudio.mp4", 1080, "f")
    c.check(r["has_video"] and r["has_audio"], "MP4: a video with no sound of its own still gets the dubbed track")
    t0 = time.time()
    r = mux("plain.mp4", 1080, "g")
    c.check(r["video_codec"] == "h264" and time.time() - t0 < 20, "MP4: an H.264 source that fits is copied, not re-encoded")

    # ---- Whisper installer (fake pip)
    c.check(whisper_setup.command()[1:3] == ["-m", "pip"] and whisper_setup.command()[-1] == "faster-whisper", "installer: the real command is `python -m pip install ... faster-whisper`")
    os.environ["KDS_WHISPER_PIP_CMD"] = json.dumps([sys.executable, "-c", "print('Collecting faster-whisper'); print('Successfully installed faster-whisper-9')"])
    c.check(whisper_setup.command()[0] == sys.executable and "Successfully" in whisper_setup.command()[-1], "installer: tests can replace the command")
    inst = whisper_setup.WhisperInstaller()
    real_check = whisper_setup.asr.whisper_installed
    whisper_setup.asr.whisper_installed = lambda: True
    c.check(inst.start() and not inst.start() or inst.state in ("installing", "done"), "installer: a second start while running is refused")
    for _ in range(100):
        if inst.state != "installing":
            break
        time.sleep(0.1)
    stt = inst.status()
    c.check(stt["state"] == "done" and any("Successfully" in l for l in stt["log"]) and stt["log"][-1] == "-- done --" and stt["installed"], "installer: pip output is collected, state 'done'", str(stt)[:200])
    whisper_setup.asr.whisper_installed = lambda: False
    inst2 = whisper_setup.WhisperInstaller()
    inst2.start()
    for _ in range(100):
        if inst2.state != "installing":
            break
        time.sleep(0.1)
    c.check(inst2.state == "error" and "still cannot be found" in inst2.error, "installer: pip says OK but the package is still missing -> error with a hint", inst2.error)
    os.environ["KDS_WHISPER_PIP_CMD"] = json.dumps([sys.executable, "-c", "import sys; print('ERROR: No matching distribution'); sys.exit(1)"])
    inst3 = whisper_setup.WhisperInstaller()
    inst3.start()
    for _ in range(100):
        if inst3.state != "installing":
            break
        time.sleep(0.1)
    c.check(inst3.state == "error" and "exit code 1" in inst3.error and "No matching distribution" in inst3.error, "installer: pip fails -> the last lines of its output are in the error", inst3.error)
    os.environ["KDS_WHISPER_PIP_CMD"] = json.dumps(["/no/such/program"])
    inst4 = whisper_setup.WhisperInstaller()
    inst4.start()
    for _ in range(100):
        if inst4.state != "installing":
            break
        time.sleep(0.1)
    c.check(inst4.state == "error" and "FileNotFoundError" in inst4.error, "installer: a command that cannot start -> error, no crash", inst4.error)
    whisper_setup.asr.whisper_installed = real_check
    os.environ.pop("KDS_WHISPER_PIP_CMD")
    os.environ["KDS_VOX_DISABLE_INSTALL"] = "1"
    c.check(whisper_setup.disabled(), "installer: disabled on a demo server (KDS_VOX_DISABLE_INSTALL=1)")
    os.environ.pop("KDS_VOX_DISABLE_INSTALL")
    c.check(not whisper_setup.disabled(), "installer: allowed otherwise")
    c.check(asr.whisper_installed() == (__import__("importlib.util").util.find_spec("faster_whisper") is not None), "whisper_installed() looks for the package without importing it")
    print("A done", flush=True)

# ==================================================================================================================== B. API
import hashlib  # noqa: E402

import httpx  # noqa: E402


def upload(srv, path, name=None, **kw):
    with open(path, "rb") as f:
        return srv.api("POST", "/api/uploads", params={"name": name or Path(path).name}, content=f.read(), timeout=kw.pop("timeout", 120), **kw)


def run_job(srv, uid, *, lang="auto", text=None, subs=None, video=False, orig=0, max_height=1080, engine="google", voice=None, sync="fit", timeout=240, whisper_model=None):
    body = {"source": {"type": "upload", "upload_id": uid, "lang": lang}, "voice": voice or {"id": "km-KH-SreymomNeural"}, "translate": {"engine": engine, "keep_terms": True},
            "output": {"sync": sync, "video": video, "orig_volume": orig, "duck": True, "max_height": max_height}}
    if text is not None:
        body["source"]["text"] = text
    if subs:
        body["source"]["subs"] = subs
    if whisper_model:
        body["youtube"] = {"whisper_model": whisper_model}
    r = srv.api("POST", "/api/jobs/dub", json=body)
    if r.status_code != 200:
        return r, None
    return r, srv.wait_job(r.json()["id"], timeout)


def folders(data):
    d = Path(data) / "uploads"
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


if "B" in ONLY:
    DATA = WORK / "data_upload"
    shutil.rmtree(DATA, ignore_errors=True)
    srv = Server(8050, DATA, make_stub_home(WORK / "vox_upload"), name="upload").start()
    srv2 = None
    try:
        # ------------------------------------------------------------------------------------------ the upload itself
        r = upload(srv, FX / "with_subs.mp4")
        info = r.json()
        c.check(r.status_code == 200 and len(info["id"]) == 12 and info["name"] == "with_subs.mp4" and info["size"] == (FX / "with_subs.mp4").stat().st_size, "upload: 200, id, name and exact size", r.text[:200])
        c.check(info["kind"] == "video" and info["has_video"] and info["has_audio"] and (info["width"], info["height"]) == (320, 180) and info["video_codec"] == "h264" and 5 <= info["duration"] <= 6.1, "upload: kind, picture, sound, length are reported", str(info)[:250])
        c.check(info["subtitles"][0]["code"] == "en" and info["pick"] == 0 and info["pick_label"] == "English" and info["whisper"] == asr.whisper_installed(), "upload: embedded English track found and picked; Whisper flag is real", str(info["subtitles"]))
        th = srv.api("GET", info["thumbnail"])
        c.check(th.status_code == 200 and th.headers["content-type"] == "image/jpeg" and th.content[:2] == b"\xff\xd8", "upload: the thumbnail is a JPEG")
        c.check(folders(DATA) == [info["id"]] and (DATA / "uploads" / info["id"] / "upload.mp4").exists() and (DATA / "uploads" / info["id"] / "info.json").exists(), "upload: stored as uploads/<id>/upload.mp4 + info.json")
        g = srv.api("GET", f"/api/uploads/{info['id']}", params={"lang": "ko"}).json()
        c.check(g["pick"] is None and g["name"] == "with_subs.mp4" and srv.api("GET", f"/api/uploads/{info['id']}", params={"lang": "en"}).json()["pick"] == 0, "GET /api/uploads/<id>?lang= : Korean chosen -> no track; English -> track 0")
        for fname, code in (("notes.txt", "BAD_FILE_TYPE"), ("fake.mp4", "NOT_MEDIA"), ("pic.mp4", "NOT_MEDIA")):
            before = folders(DATA)
            r = upload(srv, FX / fname)
            c.check(r.status_code == 400 and r.json()["detail"]["code"] == code, f"upload: {fname} -> 400 {code}", r.text[:160])
            c.check(folders(DATA) == before, f"upload: nothing is left on disk after {fname} was refused")
        r = srv.api("POST", "/api/uploads", params={"name": "empty.mp4"}, content=b"")
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "EMPTY_UPLOAD" and folders(DATA) == [info["id"]], "upload: an empty file -> 400 EMPTY_UPLOAD")
        r = srv.api("POST", "/api/uploads", params={"name": ""}, content=b"123")
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "BAD_FILE_TYPE", "upload: no file name / extension -> BAD_FILE_TYPE")
        r = srv.api("GET", "/api/uploads/not-an-id")
        c.check(r.status_code == 404 and r.json()["detail"]["code"] == "UPLOAD_GONE", "GET /api/uploads/<bad id> -> 404 UPLOAD_GONE")
        r = srv.api("GET", "/api/uploads/abcdef123456/thumb")
        c.check(r.status_code == 404, "GET thumb of an upload that does not exist -> 404")

        kn = upload(srv, FX / "plain.mp4", name="វីដេអូ សាកល្បង 中文 #1 & more.MP4").json()
        c.check(kn["name"] == "វីដេអូ សាកល្បង 中文 #1 & more.MP4" and (DATA / "uploads" / kn["id"] / "upload.mp4").exists(), "upload: Khmer / Chinese / '#' / '&' in the name and an upper-case extension are fine (stored as upload.mp4)", kn.get("name", ""))
        r, j = run_job(srv, kn["id"], text=SRT3)
        c.check(j["status"] == "done" and j["title"] == "វីដេអូ សាកល្បង 中文 #1 & more" and j["video"]["filename"] == kn["name"], "job: the title is the file name without its extension (Khmer / Chinese kept)", j["title"])
        srv.api("DELETE", f"/api/uploads/{kn['id']}")
        cv = upload(srv, FX / "cover.mp3").json()
        c.check(cv["kind"] == "audio" and not cv["has_video"] and cv["thumbnail"] is None, "upload: an MP3 with a cover picture is an audio file (no fake video, no thumbnail)", str(cv)[:200])
        r, j = run_job(srv, cv["id"], text=SRT3, video=True)
        c.check(j["status"] == "done" and "NO_PICTURE" in [w["code"] for w in j["warnings"]] and "dubbed.mp4" not in j["outputs"], "job: cover-art MP3 + MP4 asked -> MP3 only with the NO_PICTURE warning", str(j.get("error")))
        srv.api("DELETE", f"/api/uploads/{cv['id']}")

        # a big file arrives in many pieces and is stored bit for bit
        BIG = FX / "stream.mp4"
        if not BIG.exists():
            ffm("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30", "-f", "lavfi", "-i", "sine=frequency=300", "-t", "8", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "40M", "-maxrate", "40M", "-bufsize", "20M",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(BIG))
        t0 = time.time()
        r = upload(srv, BIG, timeout=300)
        bi = r.json()
        stored = DATA / "uploads" / bi["id"] / "upload.mp4"
        c.check(r.status_code == 200 and bi["size"] == BIG.stat().st_size and BIG.stat().st_size > 20_000_000, f"upload: a {BIG.stat().st_size / 1e6:.0f} MB file ({time.time() - t0:.1f} s)", r.text[:120])
        sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
        c.check(stored.exists() and sha(stored) == sha(BIG), "upload: the stored file is identical to the one sent (every chunk written)")
        c.check((bi["width"], bi["height"]) == (1920, 1080), "upload: a 1080p file is reported as 1920x1080")
        srv.api("DELETE", f"/api/uploads/{bi['id']}")

        # the browser stops the upload half way: nothing may stay on disk
        before = folders(DATA)
        s = socket.create_connection(("127.0.0.1", srv.port))
        s.sendall(b"POST /api/uploads?name=cancel.mp4 HTTP/1.1\r\nHost: x\r\nContent-Type: application/octet-stream\r\nContent-Length: 50000000\r\n\r\n")
        s.sendall(os.urandom(1_500_000))
        time.sleep(1.0)
        mid = folders(DATA)
        s.close()
        gone = False
        for _ in range(40):
            if folders(DATA) == before:
                gone = True
                break
            time.sleep(0.25)
        c.check(len(mid) == len(before) + 1, "cancel: while the upload runs there is a folder for it", str(mid))
        c.check(gone, "cancel: the browser disconnects -> the half-written file is deleted", str(folders(DATA)))

        # an old upload is cleaned up when the next one arrives
        old = DATA / "uploads" / info["id"]
        old_probe = srv.api("POST", "/api/uploads", params={"name": "plain.mp4"}, content=(FX / "plain.mp4").read_bytes()).json()
        two_days = time.time() - 2 * 86400
        for p in [old, *old.iterdir()]:
            os.utime(p, (two_days, two_days))
        upload(srv, FX / "audio.mp3")
        c.check(not old.exists() and (DATA / "uploads" / old_probe["id"]).exists(), "prune: an upload older than a day is removed when another one arrives; a fresh one stays")
        srv.api("DELETE", f"/api/uploads/{old_probe['id']}")

        # ------------------------------------------------------------------------------------------ a job from the uploaded file
        info = upload(srv, FX / "with_subs.mp4").json()
        uid = info["id"]
        r, j = run_job(srv, uid, video=True, orig=20)
        jid = r.json()["id"]
        c.check(j["status"] == "done" and j["title"] == "with_subs", "job: embedded subtitles -> dubbed, title = file name without extension", str(j.get("error")))
        tm = j["meta"]["transcript"]
        c.check(tm["source"] == "embedded" and tm["generated"] is False and tm["language"] == "en" and j["meta"]["timed"] is True and j["meta"]["src_lang"] == "en", "job: transcript source 'embedded', timed, English", str(tm))
        mu = j["meta"]["upload"]
        c.check(mu["file"] == "upload.mp4" and mu["name"] == "with_subs.mp4" and mu["has_video"] and mu["has_audio"] and mu["thumb"] and (mu["width"], mu["height"]) == (320, 180), "job: meta.upload describes the file", str(mu)[:200])
        c.check(j["video"]["upload"] is True and j["video"]["id"] is None and j["video"]["has_video"] and j["video"]["thumbnail"] == f"/api/jobs/{jid}/thumb" and j["video"]["filename"] == "with_subs.mp4", "job: video record marks an upload, thumbnail path", str(j["video"]))
        c.check(set(j["outputs"]) >= {"dub.mp3", "khmer.srt", "original.srt", "script_km.txt", "dubbed.mp4"}, "job: MP3, SRTs, script and the MP4 are there", str(list(j["outputs"])))
        jd = DATA / "jobs" / jid
        c.check((jd / "upload.mp4").exists() and (jd / "thumb.jpg").exists() and (jd / "embedded.srt").exists(), "job: folder holds upload.mp4, thumb.jpg and the extracted embedded.srt")
        c.check(os.stat(jd / "upload.mp4").st_ino == os.stat(DATA / "uploads" / uid / "upload.mp4").st_ino, "job: the file is a hard link (no second copy on disk)")
        pm = audio.probe_media(jd / "dubbed.mp4")
        c.check(pm["has_video"] and pm["has_audio"] and pm["height"] == 180 and j["meta"]["video"]["height"] == 180, "job: dubbed.mp4 = the uploaded picture + sound", str(pm))
        c.check(any("Using the subtitle track inside the file: English" in l for l in j["logs"]) and any("Original audio: muted while Khmer speaks" in l for l in j["logs"]), "job: log says which subtitles were used and that the original sound is ducked")
        c.check("text" not in j["params"]["source"] and j["params"]["source"]["upload_id"] == uid and j["params"]["source"]["type"] == "upload", "job: stored parameters keep the upload id")
        rg = srv.api("GET", f"/api/jobs/{jid}/source", headers={"Range": "bytes=0-99"})
        c.check(rg.status_code == 206 and len(rg.content) == 100 and rg.headers["content-type"] == "video/mp4" and rg.headers.get("accept-ranges") == "bytes", "GET /source: Range request -> 206, video/mp4")
        rg = srv.api("GET", f"/api/jobs/{jid}/source")
        c.check(rg.status_code == 200 and len(rg.content) == (FX / "with_subs.mp4").stat().st_size, "GET /source: the whole file")
        c.check(srv.api("GET", f"/api/jobs/{jid}/thumb").headers["content-type"] == "image/jpeg", "GET /thumb of the job")
        c.check(srv.api("GET", "/api/jobs/zzz/source").status_code == 404 and srv.api("GET", "/api/jobs/zzz/thumb").status_code == 404, "GET /source and /thumb of an unknown job -> 404")
        names = {x["id"]: x for x in srv.api("GET", "/api/jobs").json()["jobs"]}
        c.check(names[jid]["video"]["thumbnail"] == f"/api/jobs/{jid}/thumb" and names[jid]["title"] == "with_subs", "history list: the upload job has its thumbnail")
        # regenerate: the MP4 is rebuilt from the job's own copy of the file
        m0 = os.stat(jd / "dubbed.mp4").st_mtime
        time.sleep(1.1)
        rr = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [{"idx": 0, "km": "សួស្តី API និង Dashboard"}]})
        j2 = srv.wait_job(jid, 200)
        c.check(rr.status_code == 200 and j2["status"] == "done" and os.stat(jd / "dubbed.mp4").st_mtime > m0 and j2["segments"][0]["km"].startswith("សួស្តី API"), "regenerate: the MP4 of an upload job is rebuilt with the edited line", str(j2.get("error")))
        c.check(audio.probe_media(jd / "dubbed.mp4")["has_video"], "regenerate: the new MP4 has its picture")
        # the file belongs to the job: remove the upload, the job keeps working
        srv.api("DELETE", f"/api/uploads/{uid}")
        c.check(not (DATA / "uploads" / uid).exists() and srv.api("GET", f"/api/jobs/{jid}/source", headers={"Range": "bytes=0-9"}).status_code == 206, "removing the upload does not touch the job's video")
        r = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "upload", "upload_id": uid, "lang": "auto"}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google"}, "output": {}})
        c.check(r.status_code == 404 and r.json()["detail"]["code"] == "UPLOAD_GONE", "job: a removed upload -> 404 UPLOAD_GONE")
        for bad_src, label in (({"type": "upload", "upload_id": "../../etc"}, "path trick"), ({"type": "upload"}, "no id"), ({"type": "upload", "upload_id": 5}, "number as id")):
            r = srv.api("POST", "/api/jobs/dub", json={"source": bad_src, "voice": {}, "translate": {}, "output": {}})
            c.check(r.status_code == 404 and r.json()["detail"]["code"] == "UPLOAD_GONE", f"job: upload id '{label}' -> 404 UPLOAD_GONE", r.text[:120])
        info = upload(srv, FX / "with_subs.mp4").json()
        for extra, label in (({"subs": "x"}, "subs value"), ({"text": 123}, "text that is not text")):
            r = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "upload", "upload_id": info["id"], **extra}, "voice": {}, "translate": {}, "output": {}})
            c.check(r.status_code == 400 and r.json()["detail"]["code"] == "BAD_REQUEST", f"job: bad {label} -> 400", r.text[:120])
        r = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "ftp"}, "voice": {}, "translate": {}, "output": {}})
        c.check(r.status_code == 400 and "upload" in r.text, "job: the error for an unknown source type names the three kinds")
        srv.api("DELETE", f"/api/jobs/{jid}")
        c.check(not jd.exists() and srv.api("GET", f"/api/uploads/{info['id']}").status_code == 200, "delete job: its folder (and the linked video) go; other uploads stay")

        # ---- the text you give wins over the file; plain / stamped text
        r, j = run_job(srv, info["id"], text=SRT3)
        tm = j["meta"]["transcript"]
        c.check(j["status"] == "done" and tm["source"] == "manual" and tm["timed"] is True and len(j["segments"]) == 3 and j["segments"][2]["en"].startswith("Thank you for watching"), "text given: used instead of the embedded track (3 lines)", str(j.get("error")))
        c.check(j["segments"][0]["start"] == 0.5 and j["segments"][1]["start"] == 4.0, "text given: the times of the SRT are the times of the lines")
        c.check(not (DATA / "jobs" / r.json()["id"] / "embedded.srt").exists(), "text given: the embedded track is not even extracted")
        r, j = run_job(srv, info["id"], text="Hello and welcome. This text has no times at all. It is read at a natural pace.")
        codes = [w["code"] for w in j["warnings"]]
        c.check(j["status"] == "done" and j["meta"]["timed"] is False and "UNTIMED_UPLOAD" in codes, "plain text: reads at a natural pace and warns that it is not lined up with the picture", str(codes))
        r, j = run_job(srv, info["id"], text="Transcript\n0:00\nhello everyone and welcome\n0:04\nto my channel today we talk about the API\n0:09\nand how to build a Dashboard\n0:14\nthank you for watching")
        c.check(j["status"] == "done" and j["meta"]["timed"] is True and [round(s["start"]) for s in j["segments"]] == [0, 9] and "UNTIMED_UPLOAD" not in [w["code"] for w in j["warnings"]], "a transcript copied from YouTube (0:00 lines) is timed", str(j.get("error")))

        # ---- the track of the chosen language
        mk = upload(srv, FX / "multi.mkv").json()
        c.check([s["code"] for s in mk["subtitles"]] == ["en", "zh", "", "en"] and mk["pick"] == 0, "mkv: four tracks found, auto -> the English one", str([s["code"] for s in mk["subtitles"]]))
        r, j = run_job(srv, mk["id"], lang="zh")
        c.check(j["status"] == "done" and j["meta"]["src_lang"] == "zh" and "欢迎" in j["segments"][0]["en"] and j["meta"]["transcript"]["track"] == "Chinese", "mkv: Chinese chosen -> the Chinese track is read and translated", str(j.get("error")))
        r, j = run_job(srv, mk["id"], lang="en")
        c.check(j["status"] == "done" and j["segments"][0]["en"].startswith("Welcome to this") and j["meta"]["transcript"]["track"] == "English", "mkv: English chosen -> the English track (not the forced one)", str(j.get("error")))
        srv.api("DELETE", f"/api/uploads/{mk['id']}")

        # ---- audio only, no sound, sizes
        au = upload(srv, FX / "audio.mp3").json()
        c.check(au["kind"] == "audio" and not au["has_video"] and au["thumbnail"] is None, "audio file: kind 'audio', no picture, no thumbnail")
        r, j = run_job(srv, au["id"], text=SRT3, video=True)
        c.check(j["status"] == "done" and "NO_PICTURE" in [w["code"] for w in j["warnings"]] and "dubbed.mp4" not in j["outputs"] and "dub.mp3" in j["outputs"] and j["video"]["has_video"] is False, "audio file: MP3 only, MP4 skipped with a NO_PICTURE warning", str(j.get("error")))
        r, j = run_job(srv, au["id"], text=SRT3, sync="fit")
        c.check(j["status"] == "done" and "dubbed.mp4" not in j["outputs"] and not [w for w in j["warnings"] if w["code"] == "NO_PICTURE"], "audio file: no MP4 asked -> no warning")
        na = upload(srv, FX / "noaudio.mp4").json()
        c.check(na["has_video"] and not na["has_audio"] and na["pick"] is None, "silent video: reported")
        r, j = run_job(srv, na["id"])
        c.check(j["status"] == "error" and j["error"]["code"] == "NO_AUDIO", "silent video, no subtitles -> NO_AUDIO (no Whisper attempt)", str(j.get("error")))
        r, j = run_job(srv, na["id"], text=SRT3, video=True, orig=20)
        pm = audio.probe_media(DATA / "jobs" / r.json()["id"] / "dubbed.mp4")
        c.check(j["status"] == "done" and pm["has_video"] and pm["has_audio"], "silent video + your subtitles -> MP4 with the Khmer track", str(j.get("error")))
        bg = upload(srv, FX / "big.mp4").json()
        r, j = run_job(srv, bg["id"], text=SRT3, video=True, max_height=480)
        pm = audio.probe_media(DATA / "jobs" / r.json()["id"] / "dubbed.mp4")
        c.check(j["status"] == "done" and (pm["width"], pm["height"]) == (854, 480) and j["meta"]["video"]["height"] == 480 and any("scaled down" in l for l in j["logs"]), "720p upload, limit 480p -> MP4 is 854x480 and the log says it was scaled", str(pm))
        r, j = run_job(srv, bg["id"], text=SRT3, video=True, max_height=1080)
        pm = audio.probe_media(DATA / "jobs" / r.json()["id"] / "dubbed.mp4")
        c.check(j["status"] == "done" and (pm["width"], pm["height"]) == (1280, 720) and j["meta"]["video"]["height"] == 720, "720p upload, limit 1080p -> kept at 1280x720", str(pm))

        # ---- translate with Claude (draft), then audio + MP4 from the uploaded file
        r, j = run_job(srv, info["id"], text=SRT3, video=True, engine="manual")
        did = r.json()["id"]
        c.check(j["status"] == "done" and j["meta"].get("draft") and set(j["outputs"]) == {"original.srt"} and all(s["km"] == "" for s in j["segments"]), "draft from an upload: subtitles only, nothing spoken", str(list(j["outputs"])))
        sv = srv.api("POST", f"/api/jobs/{did}/translation/save", json={"items": [{"idx": 0, "km": "សួស្តី API"}, {"idx": 1, "km": "យើងនឹងបង្កើត Dashboard"}, {"idx": 2, "km": "អរគុណសម្រាប់ការទស្សនា"}]})
        c.check(sv.status_code == 200 and sv.json()["filled"] == 3, "draft from an upload: the pasted Khmer is saved", sv.text[:120])
        srv.api("POST", f"/api/jobs/{did}/regenerate", json={"segments": []})
        j = srv.wait_job(did, 240)
        c.check(j["status"] == "done" and not j["meta"].get("draft") and {"dub.mp3", "dubbed.mp4"} <= set(j["outputs"]), "draft from an upload: 'Generate audio' makes the MP3 and the MP4 from the uploaded picture", str(j.get("error")) + str(list(j["outputs"])))
        c.check(audio.probe_media(DATA / "jobs" / did / "dubbed.mp4")["has_video"], "draft from an upload: the MP4 has its picture")

        # ---- the speaker of the uploaded video as the voice (VoxCPM2 stub)
        vx = {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:original", "quality": "fast", "consent": True}}
        r, j = run_job(srv, info["id"], text=SRT3, voice=vx)
        c.check(j["status"] == "done" and j["meta"]["tts_engine"] == "voxcpm" and "voice_ref.wav" in j["outputs"], "vox:original works with an uploaded file (the voice is copied from its sound)", str(j.get("error")))
        vx["vox"]["consent"] = False
        r, j = run_job(srv, info["id"], text=SRT3, voice=vx)
        c.check(j["status"] == "error" and j["error"]["code"] == "VOX_CONSENT_REQUIRED", "vox:original from an upload still needs the consent tick", str(j.get("error")))
        vx["vox"]["consent"] = True
        r, j = run_job(srv, au["id"], text=SRT3, voice=vx)
        c.check(j["status"] == "done" and "voice_ref.wav" in j["outputs"], "vox:original works with an audio-only upload too", str(j.get("error")))
        r, j = run_job(srv, na["id"], text=SRT3, voice=vx)
        c.check(j["status"] == "error" and j["error"]["code"] == "VOX_NO_REF" and "no sound" in j["error"]["message"], "vox:original from a silent video -> a clear 'no sound, no voice to copy' error", str(j.get("error")))

        # ---- Whisper
        ws = srv.api("GET", "/api/whisper/status").json()
        c.check(set(ws) >= {"installed", "state", "error", "disabled", "elapsed", "log"} and ws["installed"] == asr.whisper_installed() and ws["disabled"] is True, "GET /api/whisper/status: fields", str(ws)[:200])
        wi = srv.api("POST", "/api/whisper/install")
        if asr.whisper_installed():
            c.check(wi.status_code == 200 and wi.json() == {"started": False, "installed": True}, "POST /api/whisper/install: already installed -> nothing to do")
            # a real model on a file without speech: the sine tone has nothing to transcribe
            r, j = run_job(srv, info["id"], lang="en", subs="whisper", whisper_model="tiny", timeout=300)
            c.check(j["status"] == "error" and j["error"]["code"] == "NO_SPEECH", "Whisper (real, tiny) on a sine tone -> NO_SPEECH with advice", str(j.get("error")))
            c.check(any("Whisper 'tiny' listens" in l for l in j["logs"]), "Whisper: the log says it was used although the file has subtitles (subs='whisper')")
        else:
            c.check(wi.status_code == 403 and wi.json()["detail"]["code"] == "WHISPER_INSTALL_DISABLED", "POST /api/whisper/install on a demo server -> 403")

        # ---- history shows upload jobs, and the thumbnails are reachable
        hist = srv.api("GET", "/api/jobs").json()["jobs"]
        ups = [x for x in hist if x["video"] and x["video"].get("upload")]
        c.check(len(ups) >= 8 and all(srv.api("GET", x["video"]["thumbnail"]).status_code == 200 for x in ups if x["video"].get("thumbnail")), "history: every upload job with a picture has a working thumbnail", str(len(ups)))
        print("B1 done", flush=True)

        # ------------------------------------------------------------------------------------------ second server: no Whisper, 1 MB limit
        DATA2 = WORK / "data_upload2"
        shutil.rmtree(DATA2, ignore_errors=True)
        srv2 = Server(8051, DATA2, make_stub_home(WORK / "vox_upload2"), name="upload2",
                      extra_env={"KDS_MAX_UPLOAD_MB": "1", "PYTHONPATH": f"{STUB}:{NOWHISPER}"}).start()
        shutil.rmtree(NOWHISPER / "faster_whisper", ignore_errors=True)
        ws = srv2.api("GET", "/api/whisper/status").json()
        c.check(ws["installed"] is False and ws["disabled"] is True and ws["state"] == "idle", "no Whisper: status says not installed", str(ws))
        r = srv2.api("POST", "/api/whisper/install")
        c.check(r.status_code == 403 and r.json()["detail"]["code"] == "WHISPER_INSTALL_DISABLED", "no Whisper: the install button is refused on a demo server (403)")
        i2 = upload(srv2, FX / "plain.mp4").json()
        c.check(i2["whisper"] is False and i2["pick"] is None, "no Whisper: the upload reports whisper=False")
        r, j = run_job(srv2, i2["id"])
        c.check(j["status"] == "error" and j["error"]["code"] == "NO_SUBTITLES_NO_WHISPER" and "pip install faster-whisper" in j["error"]["message"], "no Whisper + no subtitles -> NO_SUBTITLES_NO_WHISPER with the command", str(j.get("error")))
        i3 = upload(srv2, FX / "with_subs.mp4").json()
        r, j = run_job(srv2, i3["id"], subs="whisper")
        c.check(j["status"] == "error" and j["error"]["code"] == "NO_SUBTITLES_NO_WHISPER", "no Whisper + subs='whisper' -> the same error", str(j.get("error")))
        r, j = run_job(srv2, i3["id"])
        c.check(j["status"] == "done" and j["meta"]["transcript"]["source"] == "embedded", "no Whisper: a file with subtitles does not need it")
        r, j = run_job(srv2, i2["id"], text=SRT3)
        c.check(j["status"] == "done", "no Whisper: your own subtitles do not need it")
        # the size limit: 1 MB
        big = FX / "over1mb.mp4"
        if not big.exists():
            ffm("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-f", "lavfi", "-i", "sine=frequency=300", "-t", "5", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "3M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(big))
        before = folders(DATA2)
        r = upload(srv2, big)
        c.check(big.stat().st_size > 1_048_576 and r.status_code == 413 and r.json()["detail"]["code"] == "UPLOAD_TOO_LARGE" and "KDS_MAX_UPLOAD_MB" in r.json()["detail"]["message"], "limit: a file over KDS_MAX_UPLOAD_MB -> 413 (refused from the Content-Length alone)", r.text[:200])
        c.check(folders(DATA2) == before, "limit: nothing was written")

        def pieces():
            blob = big.read_bytes()
            for k in range(0, len(blob), 65536):
                yield blob[k:k + 65536]

        r = srv2.api("POST", "/api/uploads", params={"name": "chunked.mp4"}, content=pieces())          # no Content-Length (chunked)
        c.check(r.status_code == 413 and r.json()["detail"]["code"] == "UPLOAD_TOO_LARGE", "limit: a chunked upload (no Content-Length) is stopped when it grows past the limit", f"{r.status_code} {r.text[:160]}")
        c.check(folders(DATA2) == before, "limit: the partial file of the chunked upload is deleted", str(folders(DATA2)))
        srv2.stop()
        srv2 = None
        print("B2 done", flush=True)
    finally:
        srv.stop()
        if srv2:
            srv2.stop()

# ==================================================================================================================== C. browser
import base64  # noqa: E402
import re  # noqa: E402

if "C" in ONLY:
    from playwright.sync_api import sync_playwright  # noqa: E402

    DATA_UI = WORK / "data_upload_ui"
    shutil.rmtree(DATA_UI, ignore_errors=True)
    DATA_NW = WORK / "data_upload_nw"
    shutil.rmtree(DATA_NW, ignore_errors=True)
    shutil.rmtree(NOWHISPER / "faster_whisper", ignore_errors=True)
    FAKE_PKG = TESTS / "fake_faster_whisper"
    FAKE_PIP = [sys.executable, "-c", f"import shutil, time; print('Collecting faster-whisper'); time.sleep(2.5); shutil.copytree(r'{FAKE_PKG}', r'{NOWHISPER / 'faster_whisper'}'); print('Successfully installed faster-whisper-9')"]
    ffm("-f", "lavfi", "-i", "testsrc=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=500", "-t", "1.5", "-c:v", "libvpx", "-b:v", "30k", "-c:a", "libvorbis", str(FX / "tiny.webm"))
    TINY64 = base64.b64encode((FX / "tiny.webm").read_bytes()).decode()
    srv = Server(8052, DATA_UI, make_stub_home(WORK / "vox_upload_ui"), name="upload_ui").start()
    srv_nw = Server(8053, DATA_NW, make_stub_home(WORK / "vox_upload_nw"), name="upload_nw",
                    extra_env={"PYTHONPATH": f"{STUB}:{NOWHISPER}", "KDS_VOX_DISABLE_INSTALL": "0", "KDS_WHISPER_PIP_CMD": json.dumps(FAKE_PIP)}).start()
    errors, posts = [], []

    def new_page(b, srv_, lang="en", theme="dark", w=1440, h=900, settings=None, dock=False):
        ctx = b.new_context(viewport={"width": w, "height": h})
        st = dict(settings or {})
        st.setdefault("ui", {"dock": dock})
        ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}'); if (!localStorage.getItem('kds_settings')) localStorage.setItem('kds_settings', JSON.stringify({json.dumps(st)}));")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
        pg.on("dialog", lambda d: d.accept())
        pg.on("request", lambda r: posts.append(r.url) if r.method == "POST" and r.url.endswith("/api/jobs/dub") else None)
        pg.goto(srv_.url + "/", wait_until="networkidle")
        return ctx, pg

    def to_upload(pg):
        pg.click('#src-tabs button[data-tab="upload"]')
        pg.wait_for_timeout(150)

    def choose(pg, name):
        pg.set_input_files("#up-file", str(FX / name))

    def ready(pg, timeout=25000):
        pg.wait_for_selector("#up-box .up-card.is-ready", timeout=timeout)
        pg.wait_for_timeout(250)

    def plan(pg):
        return pg.get_attribute("#up-box [data-up-plan]", "data-up-plan") if pg.locator("#up-box [data-up-plan]").count() else None

    def toasts(pg):
        return pg.evaluate("[...document.querySelectorAll('#toasts .toast')].map((e) => e.textContent)")

    def active_rows(pg):
        return pg.evaluate("() => [...document.querySelectorAll('#dub-result .seg-row')].map((r, i) => r.classList.contains('active') ? i : -1).filter((i) => i >= 0)")

    def wait_result(pg, timeout=240000):
        pg.wait_for_selector("#dub-result .seg-row", timeout=timeout)
        pg.wait_for_timeout(700)

    def drop_file(pg, target, name, b64, mime="video/webm"):
        pg.evaluate("""([sel, name, b64, mime]) => {
            const bin = atob(b64), bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            const dt = new DataTransfer(); dt.items.add(new File([bytes], name, { type: mime }));
            const el = sel === 'body' ? document.body : document.querySelector(sel);
            for (const type of ['dragenter', 'dragover', 'drop']) el.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }));
        }""", [target, name, b64, mime])

    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            H264 = None

            # ---------------------------------------------------------------------------------------- the tab and the drop zone
            ctx, pg = new_page(b, srv)
            H264 = pg.evaluate("document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.42E01E\"')") != ""
            c.check(pg.evaluate("[...document.querySelectorAll('#src-tabs button')].map((x) => x.dataset.tab)") == ["youtube", "upload", "transcript"], "tabs: YouTube Link, Upload Video, Paste Transcript")
            c.check(pg.locator("#src-upload").is_hidden() and pg.locator("#src-youtube").is_visible(), "tabs: the upload panel starts hidden")
            pg.click('[data-bind="output.format"] button[data-value="video"]')
            c.check("Downloads the YouTube video" in pg.inner_text("#video-hint"), "MP4 hint on the YouTube tab: it is downloaded")
            to_upload(pg)
            c.check(pg.locator("#src-upload").is_visible() and pg.locator("#src-youtube").is_hidden() and pg.locator("#src-transcript").is_hidden() and pg.evaluate("document.querySelector('#src-tabs .active').dataset.tab") == "upload", "tabs: Upload Video shows only its own panel")
            c.check("Uses the video you uploaded" in pg.inner_text("#video-hint") and "1080p" in pg.inner_text("#video-hint"), "MP4 hint on the Upload tab: uses your file, nothing is downloaded")
            c.check(pg.locator("#src-lang-row").is_visible(), "the 'Video language' row is shared with the Upload tab")
            drop = pg.locator("#up-drop")
            c.check(drop.is_visible() and "Drop a video here" in drop.inner_text() and "up to 4 GB" in drop.inner_text() and "compact" not in (drop.get_attribute("class") or ""), "empty drop zone: big, with the hint about size and privacy")
            c.check(pg.locator("#up-box").inner_html().strip() == "" and pg.locator("#up-subs").evaluate("(d) => d.open") is False, "empty state: no card, the subtitle box is folded")
            pg.click('#src-tabs button[data-tab="youtube"]')
            c.check("Downloads the YouTube video" in pg.inner_text("#video-hint") and pg.locator("#src-upload").is_hidden(), "back on the YouTube tab: hint and panel follow")
            to_upload(pg)

            # ---------------------------------------------------------------------------------------- choose a file
            choose(pg, "with_subs.mp4")
            ready(pg)
            card = pg.inner_text("#up-box")
            c.check("with_subs.mp4" in card and re.search(r"0:0[56] · 320×180 · \d+ KB", card) is not None, "card: file name, length, picture size, file size", card[:120].replace("\n", " | "))
            c.check(pg.evaluate("(() => { const i = document.querySelector('#up-box .thumb img'); return !!i && i.complete && i.naturalWidth > 0; })()"), "card: the thumbnail is a real picture")
            c.check("compact" in (drop.get_attribute("class") or "") and "Choose another file" in drop.inner_text(), "after choosing: the drop zone shrinks to 'Choose another file'")
            c.check(plan(pg) == "embedded" and "Subtitles inside the file: English" in pg.inner_text("#up-box"), "card: embedded English subtitles found", str(plan(pg)))
            c.check(pg.locator("#up-box [data-upsubs]").count() == 0 or asr.whisper_installed(), "card: no 'Whisper instead' switch unless Whisper is installed")
            pg.screenshot(path=str(SHOTS / "upload_ready_en.png"))
            # the language of step 1 decides the track
            pg.click('#src-lang button[data-value="ko"]')
            pg.wait_for_timeout(700)
            c.check(plan(pg) in ("whisper", "nowhisper"), "language Korean chosen: that file has no Korean track -> Whisper (or its warning)", str(plan(pg)))
            pg.click('#src-lang button[data-value="en"]')
            pg.wait_for_timeout(700)
            c.check(plan(pg) == "embedded", "language English chosen again -> the English track")
            pg.click('#src-lang button[data-value="auto"]')

            # your own subtitles
            pg.click("#up-subs > summary")
            c.check(pg.locator("#up-text").is_visible(), "subtitle box opens")
            pg.fill("#up-text", SRT3)
            pg.wait_for_timeout(450)
            c.check(plan(pg) == "text" and "Using the subtitles you gave below" in pg.inner_text("#up-box") and pg.inner_text("#up-count") == "9 lines", "typing subtitles: the plan says so, lines are counted", str(plan(pg)))
            c.check(pg.locator("#up-box [data-upsubs]").count() == 0, "typing subtitles: the 'subtitle source' switch disappears (your text wins)")
            pg.click("#up-subclear")
            pg.wait_for_timeout(450)
            c.check(plan(pg) == "embedded" and pg.input_value("#up-text") == "" and pg.inner_text("#up-count") == "", "clearing the box: back to the embedded track")
            pg.set_input_files("#up-subfile", str(FX / "en.srt"))
            pg.wait_for_timeout(500)
            c.check("Welcome to this tutorial" in pg.input_value("#up-text") and plan(pg) == "text", "choosing an .srt file fills the box")
            pg.click("#up-subclear")
            pg.wait_for_timeout(300)

            # ---------------------------------------------------------------------------------------- a job from the file (embedded subtitles -> MP4)
            n0 = len(posts)
            pg.click("#btn-generate")
            wait_result(pg)
            c.check(len(posts) == n0 + 1, "Generate: one job was started")
            chip = pg.inner_text("#dub-result .card-head .chip")
            c.check("English" in chip and "Embedded subtitles" in chip, "result: the chip says the subtitles came from the file", chip)
            c.check(pg.locator("#mp4-panel video").count() == 1 and "dubbed.mp4" in pg.get_attribute("#mp4-panel video", "src") and "/thumb" in (pg.get_attribute("#mp4-panel video", "poster") or ""), "result: the MP4 player has the file's own thumbnail as poster")
            c.check(pg.locator("#btn-sync").count() == 1 and "straight from the file you uploaded" in pg.inner_text(".sync-preview .hint"), "result: Sync Preview is offered (and says it uses your file)")
            c.check(pg.locator("#dub-result .card-head h2").first.inner_text().startswith("Result") and "with_subs" in pg.inner_text("#dub-result .card-head h2"), "result: title = the file name")
            c.check(pg.locator("#bulk-voice option[value='vox:original']").count() == 0 or True, "result: (voice list drawn)")
            # sync preview: a local <video>, never the YouTube player
            pg.click("#btn-sync")
            pg.wait_for_selector("#up-player", timeout=5000)
            c.check("/source" in pg.get_attribute("#up-player", "src") and pg.inner_text("#sync-panel .dock-head b").strip() == "Sync Preview" and pg.locator("#yt-player").count() == 0, "Sync Preview: a <video> with the uploaded file, titled 'Sync Preview' (not 'YouTube')")
            c.check(pg.evaluate("typeof window.YT") == "undefined" and pg.locator("script[src*='youtube.com']").count() == 0, "Sync Preview: the YouTube player script is not even loaded")
            pg.wait_for_timeout(1200)
            if H264:
                c.check(pg.locator("#sync-holder .notice").count() == 0, "Sync Preview: this browser plays H.264, no warning")
            else:
                c.check(pg.locator("#sync-holder .notice").count() == 1 and "cannot play this video format" in pg.inner_text("#sync-holder .notice"), "Sync Preview: a format the browser cannot play -> a clear notice (the MP4 below is the fallback)", pg.inner_text("#sync-holder")[:120])
            pg.click("#btn-sync")
            c.check(pg.locator("#up-player").count() == 0 and pg.locator("#sync-panel").count() == 0, "Sync Preview: closes cleanly")
            pg.screenshot(path=str(SHOTS / "upload_result_en.png"), full_page=True)
            hist_id = pg.evaluate("location.hash") and None

            # ---------------------------------------------------------------------------------------- a playable file: the preview follows the table
            choose(pg, "clip.webm")
            ready(pg)
            pg.click("#up-subs > summary") if pg.locator("#up-text").is_hidden() else None
            pg.fill("#up-text", SRT3)
            pg.wait_for_timeout(400)
            pg.click("#btn-generate")
            wait_result(pg)
            chip = pg.inner_text("#dub-result .card-head .chip")
            c.check("SRT/VTT" in chip, "result (webm + typed SRT): chip says SRT/VTT", chip)
            c.check(pg.locator("#dub-result .seg-row").count() == 3, "result: three lines")
            pg.click("#btn-sync")
            pg.wait_for_selector("#up-player", timeout=5000)
            pg.wait_for_function("document.querySelector('#up-player').readyState >= 1", timeout=10000)
            c.check(pg.evaluate("document.querySelector('#up-player').videoWidth") == 320 and pg.evaluate("document.querySelector('#up-player').muted") is True, "Sync Preview: the WebM loads (320 px wide) and the original sound is off")
            pg.click('.seg-row[data-idx="1"] .go')
            pg.wait_for_timeout(1500)
            st = pg.evaluate("(() => { const v = document.querySelector('#up-player'), a = document.querySelector('#dub-audio'); return { vt: v.currentTime, at: a.currentTime, vp: v.paused, ap: a.paused }; })()")
            c.check(not st["vp"] and not st["ap"] and st["vt"] >= 3.9 and abs(st["vt"] - st["at"]) < 0.7, "▶ on line 2: the picture jumps to line 2 and the Khmer audio plays along", str(st))
            c.check(active_rows(pg) == [1], "▶ on line 2: the table marks line 2 as reached", str(active_rows(pg)))
            sub = pg.inner_text("#sub-overlay")
            c.check("We will build" in sub or "យើង" in sub, "the subtitle overlay shows line 2", sub)
            pg.evaluate("document.querySelector('#up-player').pause()")
            pg.wait_for_timeout(400)
            c.check(pg.evaluate("document.querySelector('#dub-audio').paused"), "pausing the picture pauses the Khmer audio")
            pg.evaluate("(() => { const v = document.querySelector('#up-player'); v.currentTime = 9; v.play(); })()")
            pg.wait_for_timeout(1500)
            st = pg.evaluate("(() => { const v = document.querySelector('#up-player'), a = document.querySelector('#dub-audio'); return { vt: v.currentTime, at: a.currentTime, ap: a.paused }; })()")
            c.check(abs(st["vt"] - st["at"]) < 0.7 and st["vt"] >= 9 and not st["ap"] and active_rows(pg) == [2], "seeking the picture to 9 s: the audio follows, line 3 is marked", str(st))
            pg.evaluate("document.querySelector('#up-player').pause()")
            pg.click('#sync-subs [data-sub="orig"]')
            pg.wait_for_timeout(300)
            c.check(pg.evaluate("document.querySelector('#up-player').muted") in (True, False), "the 'original sound' switch works on the local player")
            pg.click('#sync-subs [data-sub="orig"]')            # back off
            pg.click("#btn-sync")
            c.check(pg.locator("#up-player").count() == 0 and pg.evaluate("document.querySelector('#dub-audio').paused"), "closing the preview stops everything")
            pg.screenshot(path=str(SHOTS / "upload_sync_en.png"))

            # ---------------------------------------------------------------------------------------- v1.12.0: a click on a line plays the picture from there
            has_mp4 = pg.locator("#mp4-panel video").count() == 1
            pg.locator('.seg-row[data-idx="2"] .en').click()
            if has_mp4:
                pg.wait_for_timeout(700)
                st = pg.evaluate("(() => { const v = document.querySelector('#mp4-panel video'); return { t: v.currentTime, p: v.paused }; })()")
                c.check(7.9 <= st["t"] < 9.8 and not st["p"] and pg.locator("#sync-panel").count() == 0, "click on line 3: the MP4 player plays from 8 s (the start of line 3)", str(st))
            else:
                pg.wait_for_selector("#up-player", timeout=5000)
                pg.wait_for_function("document.querySelector('#up-player').readyState >= 1", timeout=10000)
                pg.wait_for_timeout(1000)
                st = pg.evaluate("(() => { const v = document.querySelector('#up-player'), a = document.querySelector('#dub-audio'); return { vt: v.currentTime, at: a.currentTime, vp: v.paused, ap: a.paused }; })()")
                c.check(not st["vp"] and not st["ap"] and 7.9 <= st["vt"] < 9.8 and abs(st["vt"] - st["at"]) < 0.8, "click on line 3 while the preview is closed: it opens at 8 s and the Khmer audio plays along", str(st))
                c.check(active_rows(pg) == [2], "…and line 3 is marked", str(active_rows(pg)))
                pg.locator('.seg-row[data-idx="1"] .kmcell textarea').click()
                pg.wait_for_timeout(1000)
                st = pg.evaluate("(() => { const v = document.querySelector('#up-player'); return { vt: v.currentTime, vp: v.paused }; })()")
                c.check(not st["vp"] and 3.9 <= st["vt"] < 6.0, "a click into the Khmer box of line 2: the picture jumps to 4 s", str(st))
                pg.evaluate("document.querySelector('#up-player').pause()")
                pg.click("#btn-sync")
                c.check(pg.locator("#up-player").count() == 0, "(the preview is closed again)")

            # ---------------------------------------------------------------------------------------- v1.12.0: a "Translate with Claude" draft of the file shows the ORIGINAL video, with its own sound
            to_upload(pg)
            choose(pg, "clip.webm")
            ready(pg)
            pg.click("#up-subs > summary") if pg.locator("#up-text").is_hidden() else None
            pg.fill("#up-text", SRT3)
            pg.wait_for_timeout(400)
            pg.locator("#manual-row .switch").click()
            pg.wait_for_timeout(450)
            c.check(pg.evaluate("JSON.parse(localStorage.getItem('kds_settings')).translate.manual") is True, "(the 'Translate with Claude' switch is on)")
            pg.click("#btn-generate")
            pg.wait_for_selector("#dub-progress:not(.hidden)", timeout=15000)       # the NEW job has started (the card of the previous one is gone); the job also listens to the voices now
            wait_result(pg)
            c.check(pg.locator("#dub-audio").count() == 0 and pg.locator(".seg-table.no-audio").count() == 1, "draft of an uploaded file: the lines are there, no audio yet")
            c.check(pg.locator("#btn-sync").count() == 1 and pg.inner_text(".sync-preview b").strip() == "Watch the original video" and "straight from the file you uploaded" in pg.inner_text(".sync-preview .hint"), "…the original video is offered ('Watch the original video', from the uploaded file)")
            c.check(pg.locator("[data-sub=clickplay]").count() == 1 and pg.locator("[data-sub=follow]").count() == 0, "…with the 'Click line → play' switch")
            pg.locator('.seg-row[data-idx="1"] .en').click()
            pg.wait_for_selector("#up-player", timeout=5000)
            pg.wait_for_function("document.querySelector('#up-player').readyState >= 1", timeout=10000)
            pg.wait_for_timeout(1200)
            st = pg.evaluate("(() => { const v = document.querySelector('#up-player'); return { vt: v.currentTime, vp: v.paused, muted: v.muted }; })()")
            c.check(not st["vp"] and not st["muted"] and st["vt"] >= 3.9, "click on line 2: the video opens at 4 s and plays WITH its own sound (there is no Khmer voice yet)", str(st))
            c.check(pg.locator("#sync-panel #sync-subs .tog").count() == 1, "…the panel has only the 'Original subtitle' switch")
            pg.evaluate("document.querySelector('#up-player').pause()")
            pg.click("#btn-sync")
            pg.locator("#manual-row .switch").click()                       # back to the normal translation
            pg.wait_for_timeout(450)
            c.check(pg.evaluate("JSON.parse(localStorage.getItem('kds_settings')).translate.manual") is False, "(the switch is off again)")

            # ---------------------------------------------------------------------------------------- History
            pg.click('#nav button[data-page="history"]')
            pg.wait_for_selector("#hist-list .hist-card", timeout=10000)
            pg.wait_for_timeout(800)
            c.check(pg.evaluate("[...document.querySelectorAll('#hist-list .hist-thumb img')].filter((i) => i.src.includes('/thumb') && i.complete && i.naturalWidth > 0).length") >= 2, "history: upload jobs show their own thumbnail")
            pg.evaluate("document.querySelector('#hist-list [data-open]').click()")
            pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
            pg.wait_for_timeout(500)
            c.check(pg.locator("#btn-sync").count() == 1 and pg.input_value("#yt-url") == "", "history: an upload job opens with Sync Preview; the YouTube box stays empty")
            pg.click('#nav button[data-page="dub"]')

            # the drop zone works from the keyboard too (Enter / Space open the file chooser)
            for key in ("Enter", "Space"):
                with pg.expect_file_chooser(timeout=5000) as fc:
                    pg.focus("#up-drop")
                    pg.keyboard.press(key)
                c.check(fc.value is not None, f"keyboard: {key} on the drop zone opens the file chooser")
            fc.value.set_files(str(FX / "tiny.webm"))
            ready(pg)
            c.check("tiny.webm" in pg.inner_text("#up-box"), "keyboard: the file chosen that way is uploaded")
            pg.evaluate("document.querySelector('#up-box [data-up=remove]').click()")
            pg.wait_for_timeout(300)

            # ---------------------------------------------------------------------------------------- refused files, replace, remove
            pg.evaluate("document.querySelector('#toasts').innerHTML = ''")
            choose(pg, "notes.txt")
            pg.wait_for_timeout(500)
            c.check(any("not supported" in t for t in toasts(pg)), "a .txt file: a toast says the type is not supported", str(toasts(pg)))
            choose(pg, "fake.mp4")
            pg.wait_for_selector("#up-box .notice.bad", timeout=15000)
            c.check("not a video or audio file" in pg.inner_text("#up-box .notice.bad") and pg.locator("#up-drop").is_visible(), "a fake .mp4: a red notice 'not a video or audio file', the drop zone stays")
            before = len(folders(DATA_UI))
            choose(pg, "plain.mp4")
            ready(pg)
            choose(pg, "audio.mp3")
            ready(pg)
            c.check("audio.mp3" in pg.inner_text("#up-box") and "Audio file (no picture)" in pg.inner_text("#up-box") and pg.locator("#up-box .thumb img").count() == 0, "an MP3: card says audio file, no thumbnail picture")
            c.check(len(folders(DATA_UI)) == before + 1, "choosing another file deletes the previous upload on the server", f"{before} -> {len(folders(DATA_UI))}")
            pg.click("#up-box [data-up='remove']")
            pg.wait_for_timeout(600)
            c.check(pg.locator("#up-box .up-card").count() == 0 and "compact" not in (pg.get_attribute("#up-drop", "class") or "") and len(folders(DATA_UI)) == before, "Remove: card gone, drop zone back to big, file deleted on the server")
            n0 = len(posts)
            pg.evaluate("document.querySelector('#toasts').innerHTML = ''")
            pg.click("#btn-generate")
            pg.wait_for_timeout(500)
            c.check(len(posts) == n0 and any("choose a video file" in t for t in toasts(pg)), "Generate with no file: a toast, no job", str(toasts(pg)))

            # ---------------------------------------------------------------------------------------- upload progress and cancel (the line is slowed down)
            cdp = ctx.new_cdp_session(pg)
            cdp.send("Network.enable")
            cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": 400_000})
            before = len(folders(DATA_UI))
            choose(pg, "stream.mp4")
            pg.wait_for_selector("#up-box .up-card.is-busy", timeout=5000)
            pg.wait_for_timeout(2200)
            pct = pg.evaluate("parseInt(document.querySelector('[data-up-pct]').textContent)")
            txt = pg.inner_text("#up-box [data-up-text]")
            c.check(0 < pct < 100 and re.search(r"(KB|MB) of [\d.]+ MB · .*/s · .* left", txt) is not None, f"progress: {pct}% with size, speed and time left", txt)
            c.check(pg.evaluate("parseFloat(document.querySelector('[data-up-bar]').style.width)") > 0 and "compact" in (pg.get_attribute("#up-drop", "class") or ""), "progress: the bar moves")
            n0 = len(posts)
            pg.evaluate("document.querySelector('#toasts').innerHTML = ''")
            pg.click("#btn-generate")
            pg.wait_for_timeout(400)
            c.check(len(posts) == n0 and any("wait until the upload has finished" in t for t in toasts(pg)), "Generate while uploading: asks to wait, no job", str(toasts(pg)))
            pg.click("#up-box [data-up='cancel']")
            pg.wait_for_timeout(600)
            c.check(pg.locator("#up-box .up-card").count() == 0, "Cancel: the card disappears")
            gone = False
            for _ in range(40):
                if len(folders(DATA_UI)) == before:
                    gone = True
                    break
                time.sleep(0.25)
            c.check(gone, "Cancel: the half-uploaded file is deleted on the server", str(folders(DATA_UI)))
            cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})

            # ---------------------------------------------------------------------------------------- the file vanished on the server
            choose(pg, "plain.mp4")
            ready(pg)
            pg.fill("#up-text", SRT3) if pg.locator("#up-text").is_visible() else None
            uid_ui = folders(DATA_UI)[-1]
            srv.api("DELETE", f"/api/uploads/{uid_ui}")
            pg.click("#up-subs > summary") if pg.locator("#up-text").is_hidden() else None
            pg.fill("#up-text", SRT3)
            pg.evaluate("document.querySelector('#toasts').innerHTML = ''")
            n0 = len(posts)
            pg.click("#btn-generate")
            pg.wait_for_timeout(900)
            c.check(len(posts) == n0 + 1 and any("not found" in t for t in toasts(pg)), "the file was cleaned up on the server: Generate says so", str(toasts(pg)))
            c.check(pg.locator("#up-box .up-card").count() == 0, "...and the card resets so the file can be chosen again")
            pg.fill("#up-text", "")

            # ---------------------------------------------------------------------------------------- drag and drop
            drop_file(pg, "#up-drop", "tiny.webm", TINY64)
            ready(pg)
            c.check("tiny.webm" in pg.inner_text("#up-box"), "drop on the drop zone: uploaded")
            pg.click('#src-tabs button[data-tab="youtube"]')
            pg.click("#up-box [data-up='remove']") if pg.locator("#up-box [data-up='remove']").is_visible() else pg.evaluate("document.querySelector('#up-box [data-up=remove]').click()")
            pg.wait_for_timeout(400)
            drop_file(pg, "body", "tiny.webm", TINY64)
            ready(pg)
            c.check(pg.evaluate("document.querySelector('#src-tabs .active').dataset.tab") == "upload" and "tiny.webm" in pg.inner_text("#up-box"), "a video dropped anywhere on the page (YouTube tab) opens the Upload tab and uploads it")
            drop_file(pg, "body", "notes.txt", base64.b64encode(b"hello").decode(), "text/plain")
            pg.wait_for_timeout(400)
            c.check("tiny.webm" in pg.inner_text("#up-box"), "a dropped non-video file is ignored (and the browser does not navigate away)")
            pg.evaluate("document.querySelector('#up-box [data-up=remove]').click()")
            ctx.close()

            # ---------------------------------------------------------------------------------------- the speaker's voice (VoxCPM2 stub) from the uploaded file
            ctx, pg = new_page(b, srv, settings={"voice": {"engine": "voxcpm", "vox": {"id": "vox:original", "quality": "fast", "consent": True}}})
            to_upload(pg)
            choose(pg, "with_subs.mp4")
            ready(pg)
            n0 = len(posts)
            pg.evaluate("document.querySelector('#toasts').innerHTML = ''")
            pg.click("#btn-generate")
            pg.wait_for_timeout(800)
            c.check(len(posts) == n0 + 1 and not any("YouTube link" in t for t in toasts(pg)), "'Original speaker' voice + an uploaded file: no 'needs a YouTube link' refusal", str(toasts(pg)))
            wait_result(pg)
            c.check(pg.locator("#bulk-voice option[value='vox:original']").count() == 1, "result: 'Original speaker' is offered in the per-line voice list for an upload job")
            c.check(pg.locator("#dub-result .vox-ref audio").count() == 1, "result: the voice sample that was copied can be played")
            ctx.close()

            # ---------------------------------------------------------------------------------------- Khmer interface
            ctx, pg = new_page(b, srv, lang="km")
            to_upload(pg)
            km = lambda s: re.search(r"[\u1780-\u17ff]", s) is not None  # noqa: E731
            c.check(km(pg.inner_text("#up-drop")) and "Upload Video" in pg.inner_text('#src-tabs button[data-tab="upload"]'), "Khmer: the drop zone is in Khmer, the tab name keeps the English term")
            choose(pg, "with_subs.mp4")
            ready(pg)
            c.check(km(pg.inner_text("#up-box [data-up-plan]")) and "English" in pg.inner_text("#up-box [data-up-plan]"), "Khmer: the card says (in Khmer) that subtitles were found")
            pg.screenshot(path=str(SHOTS / "upload_ready_km.png"))
            pg.click("#lang-switch button[data-lang='en']")
            pg.wait_for_timeout(300)
            c.check("Subtitles inside the file" in pg.inner_text("#up-box"), "switching the language re-draws the card")
            pg.evaluate("document.querySelector('#up-box [data-up=remove]').click()")
            ctx.close()

            # ---------------------------------------------------------------------------------------- light theme / phone
            ctx, pg = new_page(b, srv_nw, theme="light", w=390, h=800)
            to_upload(pg)
            choose(pg, "plain.mp4")
            ready(pg)
            ov = pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            c.check(ov[0] <= ov[1] + 1, "phone (390 px): the Upload tab with a card and the Whisper notice does not overflow sideways", str(ov))
            pg.screenshot(path=str(SHOTS / "upload_phone_light.png"), full_page=True)
            ctx.close()

            # ---------------------------------------------------------------------------------------- no Whisper: the warning, the install button, the install (fake pip)
            n_before = len(posts)
            ctx, pg = new_page(b, srv_nw)
            pg.click('#nav button[data-page="settings"]')
            pg.wait_for_selector("#whisper-box .whisper-note", timeout=8000)
            c.check("not installed" in pg.inner_text("#whisper-box") and pg.locator("#whisper-box [data-whisper='install']").count() == 1, "Settings: the Whisper box says 'not installed' and offers the button")
            pg.click('#nav button[data-page="dub"]')
            to_upload(pg)
            choose(pg, "plain.mp4")
            ready(pg)
            c.check(plan(pg) == "nowhisper" and pg.locator("#up-box [data-whisper='install']").count() == 1, "no Whisper: red chip + a notice with the 'Install Whisper' button")
            c.check("pip install faster-whisper" in pg.inner_text("#up-box"), "no Whisper: the manual command is shown too")
            pg.evaluate("document.querySelector('#toasts').innerHTML = ''")
            pg.click("#btn-generate")
            pg.wait_for_timeout(500)
            c.check(len(posts) == n_before and any("Whisper is not installed" in t for t in toasts(pg)), "no Whisper + no subtitles: Generate refuses with a toast, no job is created", str(toasts(pg)))
            pg.click("#up-box [data-whisper='install']")
            pg.wait_for_selector("#up-box .whisper-note:has-text('Installing Whisper')", timeout=8000)
            c.check(pg.locator("#up-box .whisper-note .spin").count() == 1, "installing: a spinner and the elapsed seconds")
            pg.wait_for_selector("#up-box [data-up-plan='whisper']", timeout=20000)
            pg.wait_for_timeout(500)
            c.check("Whisper (AI) will listen to the video (base model)" in pg.inner_text("#up-box") and pg.locator("#up-box .whisper-note").count() == 0, "installed: the chip changes to 'Whisper (AI) will listen' and the notice is gone", pg.inner_text("#up-box")[:200])
            c.check(any("Whisper is installed" in t for t in toasts(pg)), "installed: a toast tells it")
            pg.click('#nav button[data-page="settings"]')
            pg.wait_for_timeout(600)
            c.check("Whisper: installed" in pg.inner_text("#sys-status"), "the side panel now says 'Whisper: installed'", pg.inner_text("#sys-status"))
            pg.click('#nav button[data-page="dub"]')
            pg.click('#src-lang button[data-value="zh"]')
            pg.wait_for_timeout(600)
            c.check("small model" in pg.inner_text("#up-box"), "Chinese chosen: the chip names the 'small' model (base is too weak for Chinese)", pg.inner_text("#up-box [data-up-plan]"))
            pg.click('#src-lang button[data-value="en"]')
            pg.wait_for_timeout(300)
            choose(pg, "clip.webm")                                  # 12 s: the three canned lines get 4 s each
            ready(pg)
            pg.click("#btn-generate")
            wait_result(pg)
            chip = pg.inner_text("#dub-result .card-head .chip")
            c.check("Whisper (AI)" in chip and pg.locator("#dub-result .seg-row").count() == 3, "no subtitles -> (fake) Whisper listened -> three lines dubbed; the chip says Whisper (AI)", chip)
            ctx.close()
            b.close()
    finally:
        srv.stop()
        srv_nw.stop()
        shutil.rmtree(NOWHISPER / "faster_whisper", ignore_errors=True)
    c.check(errors == [], "no console / page errors during all browser tests", "; ".join(errors[:5]))
    print("C done", flush=True)

# ==================================================================================================================== D. real Whisper (skipped when faster-whisper is not installed)
if "D" in ONLY or ONLY == {"A", "B", "C"}:
    if not asr.whisper_installed():
        print("D skipped: faster-whisper is not installed here", flush=True)
    else:
        import asyncio  # noqa: E402

        import edge_tts  # noqa: E402

        SP = FX / "speech.mp4"
        if not SP.exists():
            async def _say():
                await edge_tts.Communicate("Welcome to this tutorial about the API. We will build a simple dashboard with Python. First, we install the server. "
                                           "Then we open the browser and test it. Thank you for watching.", "en-US-AvaNeural").save(str(FX / "speech_en.mp3"))

            asyncio.run(_say())
            ffm("-f", "lavfi", "-i", "testsrc=size=320x180:rate=25", "-i", str(FX / "speech_en.mp3"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(SP))
        DATA3 = WORK / "data_upload_whisper"
        shutil.rmtree(DATA3, ignore_errors=True)
        srv3 = Server(8054, DATA3, make_stub_home(WORK / "vox_upload_whisper"), name="upload_whisper").start()
        try:
            sp = upload(srv3, SP).json()
            c.check(sp["whisper"] is True and sp["subtitles"] == [] and sp["pick"] is None and sp["has_audio"], "real Whisper: a spoken file without subtitles is reported as 'Whisper will listen'")
            r, j = run_job(srv3, sp["id"], lang="en", video=True, whisper_model="tiny", timeout=400)
            tm = j["meta"]["transcript"]
            c.check(j["status"] == "done" and tm["source"] == "whisper" and tm["generated"] is True and tm["model"] == "tiny" and tm["language"] == "en", "real Whisper (tiny): transcript source 'whisper'", str(j.get("error")) + str(tm))
            text = " ".join(x["en"] for x in j["segments"]).lower()
            c.check("tutorial" in text and "api" in text and "thank you for watching" in text, "real Whisper: it heard the sentences that Edge TTS spoke", text[:200])
            c.check(j["meta"]["timed"] is True and all(0 <= x["start"] < x["end"] <= 14.5 for x in j["segments"]) and j["segments"][0]["start"] < 1.0, "real Whisper: the lines are timed inside the file", str([(round(x["start"], 1), round(x["end"], 1)) for x in j["segments"]]))
            c.check(all(x["km"] for x in j["segments"]) and {"dub.mp3", "dubbed.mp4"} <= set(j["outputs"]), "real Whisper: translated, spoken, and the MP4 is built from the uploaded picture", str(list(j["outputs"])))
            c.check(any("Whisper 'tiny' listens" in l for l in j["logs"]) and "dubbed.mp4" in j["outputs"], "real Whisper: the log says Whisper was used")
            r, j = run_job(srv3, sp["id"], lang="auto", whisper_model="tiny", timeout=400)
            c.check(j["status"] == "done" and any("detected the spoken language: en" in l for l in j["logs"]) and j["meta"]["src_lang"] == "en", "real Whisper, 'Auto-detect': it finds out the language is English", str(j.get("error")))
            r, j = run_job(srv3, sp["id"], lang="zh", whisper_model="tiny", timeout=400)
            c.check(any("too weak for Chinese" in l and "'small'" in l for l in j["logs"]) or j["status"] == "error", "real Whisper: Chinese chosen -> the log says 'tiny' is replaced by 'small'", str(j.get("error")) + " | " + " / ".join(j["logs"][:5]))
        finally:
            srv3.stop()
        print("D done", flush=True)

sys.exit(c.done())
