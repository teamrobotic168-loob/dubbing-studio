"""Vertical video for TikTok (9:16): A units, B real ffmpeg pictures (pixels!), C API + jobs (real Google / Edge),
D browser (Playwright / Chromium).  Set ONLY=A,B,C,D to run some of the parts."""
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from lib import *  # noqa: E402,F401,F403

WORK.mkdir(parents=True, exist_ok=True)
os.environ["KDS_DATA_DIR"] = str(WORK / "data_tiktok_units")
shutil.rmtree(WORK / "data_tiktok_units", ignore_errors=True)
from app import audio, frame  # noqa: E402

ONLY = set((os.environ.get("ONLY") or "A,B,C,D").split(","))
c = Checker("TikTok vertical video")
FF = audio.ffmpeg_exe()
FX = WORK / "fx_tiktok"
SHOTS = WORK / "shots"
SHOTS.mkdir(exist_ok=True)


# ------------------------------------------------------------------------------------------------------------------ fixtures
def ffm(*args):
    subprocess.run([FF, "-v", "error", "-y", *args], check=True)


def halves(out, w, h, left="red", right="blue", secs=4, audio_=True, vcodec=("libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"), vf="", extra=()):
    """A picture whose left half is `left` and right half `right` (so every crop / bar / rotation can be seen in the pixels)."""
    lw = w // 2
    fc = f"[0:v][1:v]hstack{(',' + vf) if vf else ''}[v]"
    cmd = ["-f", "lavfi", "-i", f"color=c={left}:s={lw}x{h}:r=25", "-f", "lavfi", "-i", f"color=c={right}:s={w - lw}x{h}:r=25"]
    if audio_:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    cmd += ["-filter_complex", fc, "-map", "[v]"]
    if audio_:
        cmd += ["-map", "2:a", "-c:a", "aac", "-shortest"]
    cmd += ["-t", str(secs), "-c:v", *vcodec, *extra, str(out)]
    ffm(*cmd)


def make_fixtures():
    FX.mkdir(exist_ok=True)
    if (FX / "done.flag").exists():
        return
    halves(FX / "wide.mp4", 1920, 1080)
    halves(FX / "wide_silent.mp4", 1920, 1080, secs=3, audio_=False)
    halves(FX / "four3.mp4", 1440, 1080, "red", "blue", secs=3)
    halves(FX / "square.mp4", 1080, 1080, secs=3)
    halves(FX / "ultra.mp4", 2560, 1080, secs=3)
    halves(FX / "tall.mp4", 1080, 2400, secs=3)
    halves(FX / "vert_mpeg4.mp4", 1080, 1920, secs=3, vcodec=("mpeg4", "-q:v", "3"))
    halves(FX / "vert.mp4", 1080, 1920, secs=3)
    halves(FX / "small.mp4", 320, 180, secs=3)
    halves(FX / "odd.mkv", 853, 479, secs=3, vcodec=("ffv1",))
    halves(FX / "pal.mkv", 720, 576, secs=3, vf="setsar=16/15")
    ffm("-display_rotation", "90", "-i", str(FX / "vert.mp4"), "-c", "copy", str(FX / "rot_land.mp4"))
    ffm("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25", "-f", "lavfi", "-i", "sine=frequency=300", "-t", "50", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(FX / "long.mp4"))
    ffm("-f", "lavfi", "-i", "sine=frequency=500:sample_rate=44100", "-t", "4", "-c:a", "libmp3lame", str(FX / "audio.mp3"))
    ffm("-f", "lavfi", "-i", "sine=frequency=880:sample_rate=24000", "-t", "5", "-ac", "1", "-c:a", "libmp3lame", str(FX / "dub.mp3"))
    (FX / "done.flag").write_text("1")


make_fixtures()


def rgb(path, t=1.0):
    info = audio.probe_media(path)
    data = subprocess.run([FF, "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return info["width"], info["height"], data


class Img:
    def __init__(self, path, t=1.0):
        self.w, self.h, self.d = rgb(path, t)

    def at(self, x, y):
        i = (y * self.w + x) * 3
        return tuple(self.d[i:i + 3])


red = lambda p: p[0] > 150 and p[1] < 80 and p[2] < 80          # noqa: E731
blue = lambda p: p[2] > 150 and p[0] < 80 and p[1] < 80         # noqa: E731
pure_red = lambda p: p[0] > 235 and p[1] < 40 and p[2] < 40     # noqa: E731  (the sharp picture; a blurred mix of red and blue fails this)
pure_blue = lambda p: p[2] > 235 and p[0] < 40 and p[1] < 40    # noqa: E731
black = lambda p: max(p) < 26                                   # noqa: E731


def ffinfo(path):
    return subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr


def render(src, fit, out, crop_x=50, max_height=1080, orig=0.0, progress=None, mask=None, dub="dub.mp3"):
    """audio.mux_video the way the pipeline calls it: probe, plan, mux.  Returns the probe of the result."""
    info = audio.probe_media(FX / src)
    plan = frame.plan(info, "9:16", fit, crop_x, max_height)
    audio.mux_video(FX / src, FX / dub, out, orig, progress=progress, duck_mask=mask, max_height=max_height, frame=plan)
    return audio.probe_media(out), plan


# ==================================================================================================================== A. units
if "A" in ONLY:
    c.check([frame.clean_aspect(v) for v in ("9:16", " 9:16 ", "9x16", "TikTok", "vertical")] == ["9:16"] * 5, "aspect: 9:16 and its nicknames")
    c.check([frame.clean_aspect(v) for v in ("original", "16:9", "", None, 5, "x")] == ["original"] * 6, "aspect: anything else = original")
    c.check([frame.clean_fit(v) for v in ("blur", "CROP", " bars ", "x", None, 3)] == ["blur", "crop", "bars", "blur", "blur", "blur"], "fit: three styles, unknown -> blur")
    c.check([frame.clean_crop_x(v) for v in (0, 100, 50, 33.33, -5, 250, "70", "x", None, float("nan"), float("inf"))] == [0.0, 100.0, 50.0, 33.3, 0.0, 100.0, 70.0, 50.0, 50.0, 50.0, 100.0],
            "crop position: 0..100, junk -> middle", str([frame.clean_crop_x(v) for v in (0, 100, 50, 33.33, -5, 250, "70", "x", None, float("nan"), float("inf"))]))
    c.check([frame.canvas(s) for s in (1080, 720, 480)] == [(1080, 1920), (720, 1280), (480, 854)] and frame.canvas("x") == (1080, 1920) and frame.canvas(None) == (1080, 1920),
            "canvas: 1080 -> 1080x1920, 720 -> 720x1280, 480 -> 480x854 (even), junk -> 1080p")
    c.check(all(w % 2 == 0 and h % 2 == 0 for w, h in (frame.canvas(s) for s in range(240, 2161, 7))), "canvas: every size is even (H.264 needs it)")
    c.check(frame.canvas(1) == (240, 427 + 1) or frame.canvas(1)[0] == 240, "canvas: tiny / huge limits are clamped", str(frame.canvas(1)))
    c.check(frame.display_size({"width": 1920, "height": 1080}) == (1920, 1080) and frame.display_size({"width": 1080, "height": 1920, "rotation": 90}) == (1920, 1080)
            and frame.display_size({"width": 1080, "height": 1920, "rotation": -90.0}) == (1920, 1080) and frame.display_size({"width": 1080, "height": 1920, "rotation": 180}) == (1080, 1920)
            and frame.display_size({"width": 720, "height": 576, "sar": 16 / 15}) == (768, 576) and frame.display_size({"width": None, "height": 5}) == (None, None),
            "display size: rotation flag (90 / -90 swap, 180 not) and non-square pixels")
    c.check(frame.is_vertical(1080, 1920) and frame.is_vertical(720, 1280) and frame.is_vertical(1080, 1919) and frame.is_vertical(2160, 3840) and frame.is_vertical(1088, 1920)
            and not frame.is_vertical(1080, 2400) and not frame.is_vertical(1080, 1350) and not frame.is_vertical(1920, 1080) and not frame.is_vertical(None, None) and not frame.is_vertical(1080, 0),
            "is_vertical: 9:16 within 1.5 %, but not 20:9 / 4:5 / landscape")
    wide = {"width": 1920, "height": 1080}
    c.check(frame.plan(wide, "original") is None and frame.plan(wide, "x") is None and frame.plan({"width": 1080, "height": 1920}, "9:16") is None
            and frame.plan({"width": 1920, "height": 1080, "rotation": 90}, "9:16") is None, "plan: original shape / already 9:16 (also sideways) -> nothing to do")
    p = frame.plan(wide, "9:16", "blur", 50, 1080)
    c.check(p and (p.width, p.height, p.fit, p.crop_x) == (1080, 1920, "blur", 50.0) and "overlay" in p.graph and "gblur" in p.graph and p.graph.endswith("[vout]") and "split=2" in p.graph, "plan: blur = split + small blurred copy + overlay")
    p = frame.plan(wide, "9:16", "crop", 30, 720)
    c.check(p and (p.width, p.height, p.fit) == (720, 1280, "crop") and "crop=" in p.graph and "(iw-ow)*0.3" in p.graph and "overlay" not in p.graph and "scale=720:1280" in p.graph, "plan: crop uses the position (30 % -> 0.3) and the 720p frame", p.graph if p else "")
    p = frame.plan(wide, "9:16", "bars", 50, 480)
    c.check(p and (p.width, p.height) == (480, 854) and "pad=480:854" in p.graph and "color=black" in p.graph and "overlay" not in p.graph, "plan: bars = scale + pad on black (480p frame is 480x854)", p.graph if p else "")
    c.check(frame.plan(wide, "9:16", "zzz", "junk", "junk").fit == "blur" and frame.plan(wide, "9:16", "crop", 999, 1080).crop_x == 100.0, "plan: junk values are cleaned")
    c.check("iw*sar" not in frame.plan(wide, "9:16", "bars").graph and "iw*sar" in frame.plan({"width": 720, "height": 576, "sar": 16 / 15}, "9:16", "bars").graph, "plan: the pixel-shape fix is only added for non-square pixels")
    g = frame.build_graph("blur", 1080, 1920)
    c.check(all(x in g for x in ("scale=134:240", "crop=134:240", "scale=1080:1920")) and frame.build_graph("blur", 720, 1280).count("90:160") == 2 and "scale=60:106" in frame.build_graph("blur", 480, 854),
            "blur graph: the background is made at 1/8 size with even numbers", g)
    c.check(frame.build_graph("crop", 1080, 1920, 0).count("(iw-ow)*0'") == 1 and "(iw-ow)*1'" in frame.build_graph("crop", 1080, 1920, 100) and "(iw-ow)*0.333'" in frame.build_graph("crop", 1080, 1920, 33.33333),
            "crop graph: 0 % / 100 % / fraction")
    c.check(all(("[" + lab + "]") not in frame.build_graph(f, 1080, 1920) for f in frame.FITS for lab in ("bg", "fg", "o", "m", "d", "aout")), "graph labels never clash with the audio graph (bg fg o m d aout)")
    def commas_ok(graph):
        """Every comma inside brackets of an expression must be in single quotes (otherwise ffmpeg reads it as the next filter)."""
        depth, quoted = 0, False
        for ch_ in graph:
            if ch_ == "'":
                quoted = not quoted
            elif not quoted:
                depth += (ch_ == "(") - (ch_ == ")")
                if ch_ == "," and depth > 0:
                    return False
        return depth == 0 and not quoted
    c.check(all(commas_ok(frame.build_graph(f, cw_, ch_, 40, sar)) for f in frame.FITS for cw_, ch_ in ((1080, 1920), (720, 1280), (480, 854)) for sar in (False, True)),
            "graph: every expression with a comma is in single quotes; quotes and brackets are balanced")
    pl = frame.plan(wide, "9:16", "crop", 50, 1080)
    c.check("1080x1920" in pl.label and "cropped" in pl.label and "blurred" in frame.plan(wide, "9:16", "blur").label and "black" in frame.plan(wide, "9:16", "bars").label, "plan: readable label for the log")

    # ---- ffmpeg text: SAR and rotation
    SAMPLE = """Input #0, matroska,webm, from 'x.mkv':
  Duration: 00:00:03.00, start: 0.000000, bitrate: 1013 kb/s
  Stream #0:0: Video: h264 (High), yuv420p(progressive), 720x576 [SAR 16:15 DAR 4:3], 25 fps, 25 tbr, 1k tbn (default)
  Side data:
    displaymatrix: rotation of -90.00 degrees
"""
    # (probe_media reads a file, so test the two regexes through a real file below; here the parser of streams)
    st = audio.parse_streams(SAMPLE)
    c.check(st[0]["rotation"] == -90.0 and (st[0]["width"], st[0]["height"]) == (720, 576), "ffmpeg text: rotation and size of the picture")
    pi = audio.probe_media(FX / "pal.mkv")
    c.check(abs(pi["sar"] - 16 / 15) < 0.002 and (pi["width"], pi["height"]) == (720, 576) and pi["rotation"] == 0.0, "probe_media: SAR 16:15 of a PAL picture", str(pi))
    pr = audio.probe_media(FX / "rot_land.mp4")
    c.check(abs(abs(pr["rotation"]) - 90) < 0.1 and (pr["width"], pr["height"]) == (1080, 1920) and frame.display_size(pr) == (1920, 1080), "probe_media: a sideways phone video -> rotation, stored 1080x1920, shown 1920x1080", str(pr))
    pw = audio.probe_media(FX / "wide.mp4")
    c.check(pw["sar"] == 1.0 and pw["rotation"] == 0.0 and pw["has_audio"] and pw["has_video"] and (pw["width"], pw["height"]) == (1920, 1080), "probe_media: an ordinary picture has SAR 1 and no rotation")
    pa = audio.probe_media(FX / "audio.mp3")
    c.check(not pa["has_video"] and pa["sar"] == 1.0 and pa["rotation"] == 0.0, "probe_media: audio file -> neutral values")

    # ---- progress lines of `ffmpeg -progress`
    po = audio.parse_out_time
    c.check(po("out_time=00:00:05.120000") == 5.12 and po("out_time=01:02:03.5\n") == 3723.5 and po("out_time=N/A") is None and po("out_time_ms=5120000") is None and po("progress=end") is None and po("") is None,
            "progress: out_time=HH:MM:SS.micro is understood, N/A and other lines are ignored")

    # ---- the runner (a fake 'ffmpeg' that prints progress)
    FAKE = WORK / "fake_ffmpeg.py"
    FAKE.write_text("""import sys, time
mode = sys.argv[-1]
if mode == 'ok':
    for i in range(1, 5):
        print('out_time=00:00:0%d.000000' % i, flush=True); print('progress=continue', flush=True); time.sleep(0.15)
    print('out_time=00:00:09.000000', flush=True); print('progress=end', flush=True)
elif mode == 'fail':
    sys.stderr.write('Unrecognized option vf_oops\\nError opening filters!\\n'); sys.exit(1)
elif mode == 'noenc':
    sys.stderr.write("[vost#0:0 @ 0x1] Unknown encoder 'libx264'\\n[vost#0:0 @ 0x1] Error selecting an encoder\\n"); sys.exit(1)
elif mode == 'slow':
    for i in range(1, 200):
        print('out_time=00:00:01.000000', flush=True); time.sleep(0.2)
""", encoding="utf-8")
    SH = WORK / "fake_ffmpeg.sh"
    SH.write_text(f"#!/bin/sh\nexec {sys.executable} {FAKE} \"$@\"\n")
    SH.chmod(0o755)
    FAKE_CMD = lambda mode: [str(SH), mode]            # noqa: E731
    seen = []
    audio.run_with_progress(FAKE_CMD("ok"), 10.0, seen.append)
    c.check(len(seen) == 5 and seen == sorted(seen) and abs(seen[0] - 0.1) < 1e-6 and seen[-1] == 0.9 and max(seen) <= 0.99, "runner: progress 0..1 follows out_time and never reaches 1", str(seen))
    seen = []
    audio.run_with_progress(FAKE_CMD("ok"), 5.0, seen.append)
    c.check(max(seen) == 0.99, "runner: capped at 0.99 (the caller marks the step done)", str(seen))
    seen = []
    audio.run_with_progress(FAKE_CMD("ok"), None, seen.append)
    audio.run_with_progress(FAKE_CMD("ok"), 0, seen.append)
    audio.run_with_progress(FAKE_CMD("ok"), 10.0, None)
    c.check(seen == [], "runner: no length / no callback -> silent, no crash")

    def boom(_):
        raise RuntimeError("callback bug")
    audio.run_with_progress(FAKE_CMD("ok"), 10.0, boom)
    c.check(True, "runner: a broken progress callback does not break the run")
    try:
        audio.run_with_progress(FAKE_CMD("fail"), 10.0, None)
        c.check(False, "runner: a failing ffmpeg raises")
    except audio.FFmpegError as e:
        c.check("ffmpeg failed (1)" in str(e) and "Error opening filters" in str(e), "runner: failure -> FFmpegError with the error text", str(e)[:200])
    try:
        audio.run_with_progress(FAKE_CMD("noenc"), 10.0, None)
        c.check(False, "runner: a missing encoder raises")
    except audio.FFmpegError as e:
        c.check("Unknown encoder 'libx264'" in str(e) and "no 'libx264' encoder" in str(e) and "brew install ffmpeg" in str(e) and "winget install ffmpeg" in str(e), "runner: a missing encoder -> a plain hint (brew / winget) after the ffmpeg text", str(e)[:300])
    try:
        audio._run([str(SH), "noenc"])
        c.check(False, "_run: a missing encoder raises")
    except audio.FFmpegError as e:
        c.check("no 'libx264' encoder" in str(e), "_run: the same hint for the short ffmpeg calls (MP3 / probe)")
    c.check("no '" not in str(audio.ffmpeg_failure(1, "Error opening filters!")) and "ffmpeg failed (1): Error opening filters!" == str(audio.ffmpeg_failure(1, " Error opening filters! ")), "another failure gets no encoder hint")
    t0 = time.time()
    flag = {"n": 0}

    def want_cancel():
        flag["n"] += 1
        return flag["n"] > 3
    try:
        audio.run_with_progress(FAKE_CMD("slow"), 10.0, None, want_cancel)
        c.check(False, "runner: cancel stops it")
    except audio.FFmpegError as e:
        c.check(str(e) == "cancelled" and time.time() - t0 < 5, "runner: cancel() -> the process is stopped quickly -> FFmpegError('cancelled')", f"{time.time() - t0:.1f}s {e}")

    # ---- mux_video: nothing half-written
    out = WORK / "fx_mux_fail.mp4"
    out.unlink(missing_ok=True)
    try:
        audio.mux_video(FX / "audio.mp3", FX / "dub.mp3", out, 0.0)         # not a video -> ffmpeg fails
        c.check(False, "mux: audio as 'video' fails")
    except audio.FFmpegError:
        c.check(not out.exists() and not list(WORK.glob("fx_mux_fail*.part*")), "mux: a failure leaves neither a result nor a .part file")
    keep = WORK / "fx_mux_keep.mp4"
    shutil.copy(FX / "wide.mp4", keep)
    before = keep.read_bytes()
    try:
        audio.mux_video(FX / "audio.mp3", FX / "dub.mp3", keep, 0.0)
    except audio.FFmpegError:
        pass
    c.check(keep.read_bytes() == before, "mux: an older MP4 is untouched when the new one fails")

    # ---- Windows may still hold the old MP4 for a moment (the browser that played it, an antivirus scan)
    calls = {"n": 0}
    real_replace, real_sleep = audio.os.replace, audio.time.sleep

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(13, "The process cannot access the file because it is being used by another process")
        return real_replace(src, dst)
    src_f, dst_f = WORK / "fx_rep_src.txt", WORK / "fx_rep_dst.txt"
    src_f.write_text("new")
    dst_f.write_text("old")
    audio.os.replace, audio.time.sleep = flaky, lambda *_: None
    try:
        audio.replace_file(src_f, dst_f)
        c.check(dst_f.read_text() == "new" and calls["n"] == 3 and not src_f.exists(), "replace_file: a file that Windows still holds is retried (3rd try works) and replaced")
        src_f.write_text("new2")
        audio.os.replace = lambda a, b: (_ for _ in ()).throw(PermissionError(13, "locked"))
        try:
            audio.replace_file(src_f, dst_f, tries=3)
            c.check(False, "replace_file: a file that stays locked raises")
        except audio.FFmpegError as e:
            c.check("in use by another program" in str(e) and "fx_rep_dst.txt" in str(e) and "make the video again" in str(e) and dst_f.read_text() == "new", "replace_file: still locked after the last try -> a plain-language FFmpegError, the old file untouched", str(e)[:200])
        out_l = WORK / "fx_mux_locked.mp4"
        shutil.copy(FX / "wide.mp4", out_l)
        before_l = out_l.read_bytes()
        try:
            audio.mux_video(FX / "wide.mp4", FX / "dub.mp3", out_l, 0.0, max_height=720)
            c.check(False, "mux: a locked target raises")
        except audio.FFmpegError as e:
            c.check("in use by another program" in str(e) and out_l.read_bytes() == before_l and not list(WORK.glob("fx_mux_locked*.part*")), "mux: the old MP4 is locked -> FFmpegError, old file intact, no .part file left")
    finally:
        audio.os.replace, audio.time.sleep = real_replace, real_sleep

# ==================================================================================================================== B. real pictures
if "B" in ONLY:
    OUT = WORK / "tt_out"
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()

    def size_of(path):
        i = audio.probe_media(path)
        return i["width"], i["height"]

    # ---- blur / bars / crop of a 16:9 picture
    seen = []
    o = OUT / "wide_blur.mp4"
    pi, plan = render("wide.mp4", "blur", o, progress=seen.append)
    c.check(size_of(o) == (1080, 1920) and pi["video_codec"] == "h264" and abs(pi["duration"] - 5.0) < 0.3, "blur 16:9 -> 1080x1920 H.264, as long as the longer of picture (4 s) and Khmer audio (5 s)", str(pi))
    ft = ffinfo(o)
    c.check("yuv420p" in ft and "SAR 1:1" in ft and "DAR 9:16" in ft and "48000 Hz, stereo" in ft and "aac" in ft, "blur: yuv420p, square pixels, 9:16, AAC stereo 48 kHz", ft[-500:])
    # (ffmpeg reports every 0.5 s: a fast computer finishes this 4 s picture in under a second = only 1-2 reports; the runner unit test above checks the many-values case)
    c.check(len(seen) >= 1 and seen == sorted(seen) and 0 < seen[0] <= 0.99, "blur: progress was reported while rendering", str(seen))
    c.check(not list(OUT.glob("*.part*")), "blur: no temporary file is left")
    im = Img(o)
    c.check(red(im.at(10, 100)) and blue(im.at(1069, 100)) and red(im.at(10, 1900)) and blue(im.at(1069, 1900)), "blur: the corners show a blurred copy of the picture (red left, blue right)", str([im.at(10, 100), im.at(1069, 100)]))
    c.check(red(im.at(200, 960)) and blue(im.at(900, 960)) and not black(im.at(10, 100)), "blur: the picture is in the middle, the background is not black")
    c.check(pure_red(im.at(530, 960)) and pure_blue(im.at(552, 960)), "blur: the middle picture is sharp (the red/blue edge is crisp)", str([im.at(530, 960), im.at(552, 960)]))
    c.check(not pure_red(im.at(530, 300)) and not pure_blue(im.at(552, 300)) and not pure_red(im.at(530, 1700)), "blur: the background edge is soft (no pure red / blue next to the middle)", str([im.at(530, 300), im.at(552, 300)]))
    c.check(red(im.at(200, 700)) and red(im.at(200, 1220)), "blur: the picture is centred (rows ~656-1264)")

    o = OUT / "wide_bars.mp4"
    render("wide.mp4", "bars", o)
    im = Img(o)
    c.check(size_of(o) == (1080, 1920) and black(im.at(10, 100)) and black(im.at(1069, 1900)) and black(im.at(540, 640)) and black(im.at(540, 1280)), "bars 16:9: black above and below", str([im.at(10, 100), im.at(540, 640), im.at(540, 1280)]))
    c.check(red(im.at(200, 960)) and blue(im.at(900, 960)) and red(im.at(200, 670)) and blue(im.at(900, 1250)), "bars: the whole picture in the middle (rows 656-1264)")

    for cx, left_color, right_color, label in ((0, "r", "r", "left"), (25, "r", "r", "25 %"), (50, "r", "b", "middle"), (75, "b", "b", "75 %"), (100, "b", "b", "right")):
        o = OUT / f"wide_crop{cx}.mp4"
        render("wide.mp4", "crop", o, crop_x=cx)
        im = Img(o)
        want = {"r": red, "b": blue}
        c.check(size_of(o) == (1080, 1920) and want[left_color](im.at(100, 960)) and want[right_color](im.at(1000, 960)) and want[left_color](im.at(100, 100)) and want[right_color](im.at(1000, 1800)),
                f"crop position {label}: the part of the picture that is kept", str([im.at(100, 960), im.at(1000, 960)]))
    im = Img(OUT / "wide_crop50.mp4")
    c.check(pure_red(im.at(530, 960)) and pure_blue(im.at(552, 960)), "crop middle: the red/blue edge is exactly in the middle of the frame", str([im.at(530, 960), im.at(552, 960)]))

    # ---- other shapes of picture
    cases = [("four3.mp4", 555, 1365, "4:3 (1440x1080) -> picture 1080x810"), ("square.mp4", 420, 1500, "1:1 -> picture 1080x1080"), ("ultra.mp4", 733, 1187, "21:9 (2560x1080) -> picture 1080x454")]
    for src, top, bottom, label in cases:
        o = OUT / f"{src[:-4]}_bars.mp4"
        render(src, "bars", o)
        im = Img(o)
        c.check(size_of(o) == (1080, 1920) and black(im.at(200, top - 12)) and not black(im.at(200, top + 12)) and not black(im.at(200, bottom - 12)) and black(im.at(200, bottom + 12)), f"bars {label}: the black bars are as tall as they must be", str([im.at(200, top - 12), im.at(200, top + 12)]))
        o = OUT / f"{src[:-4]}_blur.mp4"
        render(src, "blur", o)
        im = Img(o)
        c.check(size_of(o) == (1080, 1920) and not black(im.at(200, top - 30)) and red(im.at(200, top - 30)), f"blur {label}: the space around is filled", str(im.at(200, top - 30)))
    o = OUT / "tall_bars.mp4"
    render("tall.mp4", "bars", o)
    im = Img(o)
    c.check(size_of(o) == (1080, 1920) and black(im.at(50, 960)) and black(im.at(1030, 960)) and red(im.at(300, 960)) and blue(im.at(800, 960)), "bars 20:9 phone picture (1080x2400): side bars, picture 864x1920")
    o = OUT / "tall_crop.mp4"
    render("tall.mp4", "crop", o)
    im = Img(o)
    c.check(size_of(o) == (1080, 1920) and red(im.at(200, 960)) and blue(im.at(900, 960)) and red(im.at(200, 10)), "crop 20:9: the top and bottom are cut, the frame is full")
    o = OUT / "tall_blur.mp4"
    render("tall.mp4", "blur", o)
    im = Img(o)
    c.check(size_of(o) == (1080, 1920) and not black(im.at(20, 960)) and red(im.at(20, 960)) and blue(im.at(1060, 960)), "blur 20:9: thin blurred sides")

    o = OUT / "small_blur.mp4"
    render("small.mp4", "blur", o)
    c.check(size_of(o) == (1080, 1920), "a tiny 320x180 picture is enlarged into the 1080x1920 frame")
    o = OUT / "odd.mp4"
    pi, _ = render("odd.mkv", "blur", o)
    c.check(size_of(o) == (1080, 1920) and pi["video_codec"] == "h264", "odd picture size (853x479, FFV1 in MKV) -> even 1080x1920 H.264")
    o = OUT / "odd_bars.mp4"
    render("odd.mkv", "bars", o)
    c.check(size_of(o) == (1080, 1920), "odd picture size with bars")
    o = OUT / "odd_crop.mp4"
    render("odd.mkv", "crop", o, crop_x=100)
    c.check(size_of(o) == (1080, 1920), "odd picture size with crop")

    o = OUT / "pal_bars.mp4"
    render("pal.mkv", "bars", o)
    im = Img(o)
    c.check(size_of(o) == (1080, 1920) and black(im.at(200, 545)) and not black(im.at(200, 570)), "non-square pixels (PAL 720x576, SAR 16:15) are shown as 4:3: bars 555 px tall", str([im.at(200, 545), im.at(200, 570)]))
    o = OUT / "pal_blur.mp4"
    render("pal.mkv", "blur", o)
    c.check(size_of(o) == (1080, 1920), "non-square pixels with blur")

    o = OUT / "rot_bars.mp4"
    pi, plan = render("rot_land.mp4", "bars", o)
    im = Img(o)
    c.check(plan is not None and size_of(o) == (1080, 1920), "sideways phone video (stored 1080x1920 + rotate flag = shown landscape) is fitted as landscape")
    top_c, bot_c = im.at(540, 700), im.at(540, 1220)
    c.check(((red(top_c) and blue(bot_c)) or (blue(top_c) and red(bot_c))) and black(im.at(540, 600)) and red(im.at(200, 700)) == red(im.at(900, 700)),
            "rotation: the picture is turned upright first (the two colours are one above the other now)", str([top_c, bot_c, im.at(200, 700), im.at(900, 700)]))

    # ---- already vertical: nothing is re-encoded
    o = OUT / "vert_copy.mp4"
    pi, plan = render("vert_mpeg4.mp4", "blur", o)
    c.check(plan is None and size_of(o) == (1080, 1920) and pi["video_codec"] == "mpeg4", "already 9:16 (MPEG-4): the picture is copied, not re-encoded (codec stays mpeg4)", str(pi))
    o = OUT / "vert_720.mp4"
    pi, plan = render("vert.mp4", "blur", o, max_height=720)
    c.check(plan is None and size_of(o) == (720, 1280), "already 9:16 but bigger than the 720p limit -> scaled to 720x1280 (the normal size rule)")
    o = OUT / "wide_720.mp4"
    render("wide.mp4", "blur", o, max_height=720)
    c.check(size_of(o) == (720, 1280), "720p limit -> a 720x1280 frame")
    o = OUT / "wide_480.mp4"
    render("wide.mp4", "bars", o, max_height=480)
    c.check(size_of(o) == (480, 854), "480p limit -> a 480x854 frame")

    # ---- audio: the original sound mixed under the Khmer voice + the 'mute while Khmer speaks' envelope
    env = audio.duck_envelope(audio.duck_intervals([(0.5, 2.0)]), 6.0)
    mask = WORK / "tt_mask.wav"
    audio.write_gain_wav(env, mask)
    for fit in ("blur", "crop", "bars"):
        o = OUT / f"wide_mix_{fit}.mp4"
        pi, _ = render("wide.mp4", fit, o, orig=0.3, mask=mask)
        ft = ffinfo(o)
        c.check(size_of(o) == (1080, 1920) and "48000 Hz, stereo" in ft and pi["has_audio"], f"{fit}: video graph + 'original sound under the Khmer voice' graph work together")
    o = OUT / "silent_mix.mp4"
    pi, _ = render("wide_silent.mp4", "blur", o, orig=0.3)
    c.check(size_of(o) == (1080, 1920) and pi["has_audio"], "a video without sound: only the Khmer voice (original level ignored)")
    o = OUT / "silent_mix_mask.mp4"
    pi, _ = render("wide_silent.mp4", "bars", o, orig=0.3, mask=mask)
    c.check(size_of(o) == (1080, 1920) and pi["has_audio"], "a video without sound + a mute envelope")

    # ---- the original shape keeps working exactly as before
    o = OUT / "orig_copy.mp4"
    audio.mux_video(FX / "wide.mp4", FX / "dub.mp3", o, 0.0, max_height=1080)
    ft = ffinfo(o)
    c.check(size_of(o) == (1920, 1080) and "24000 Hz, mono" in ft, "original shape (no frame): the picture is copied, audio as before (24 kHz mono)", ft[-400:])
    o = OUT / "orig_progress.mp4"
    seen = []
    audio.mux_video(FX / "wide.mp4", FX / "dub.mp3", o, 0.0, max_height=720, progress=seen.append)
    c.check(size_of(o) == (1280, 720) and len(seen) >= 1, "original shape + 720p limit: scaled, progress reported", str(seen))

    # ---- stopping a long render: ffmpeg is stopped, nothing is left
    o = OUT / "cancelled.mp4"
    info = audio.probe_media(FX / "long.mp4")
    plan = frame.plan(info, "9:16", "blur", 50, 1080)
    res = {}
    stop = threading.Event()

    def worker():
        try:
            audio.mux_video(FX / "long.mp4", FX / "dub.mp3", o, 0.0, max_height=1080, frame=plan, cancel=stop.is_set)
            res["r"] = "finished"
        except audio.FFmpegError as e:
            res["r"] = str(e)
    th = threading.Thread(target=worker)
    th.start()
    time.sleep(2.5)
    t0 = time.time()
    stop.set()
    th.join(30)
    c.check(res.get("r") == "cancelled" and time.time() - t0 < 8, "cancel: a long render stops quickly", str(res) + f" {time.time() - t0:.1f}s")
    c.check(not o.exists() and not list(OUT.glob("cancelled*")), "cancel: no result and no .part file")
    alive = "?"
    for _ in range(12):                                    # the killed process may need a moment to disappear
        time.sleep(0.25)
        alive = subprocess.run(["sh", "-c", "pgrep -af 'ffmpeg.*long[.]mp4' || true"], capture_output=True, text=True).stdout.strip()
        if not alive:
            break
    c.check(alive == "", "cancel: no ffmpeg keeps running", alive)

# ==================================================================================================================== C. API + jobs
SRT2 = ("1\n00:00:00,500 --> 00:00:03,000\nWelcome to this tutorial about the API.\n\n2\n00:00:03,500 --> 00:00:06,500\nWe will build a Dashboard with Python.\n")
SRT2B = SRT2 + "\n3\n00:00:07,000 --> 00:00:09,500\nThank you for watching.\n"


def upload(srv, path, name=None):
    with open(path, "rb") as f:
        return srv.api("POST", "/api/uploads", params={"name": name or Path(path).name}, content=f.read(), timeout=120)


def make_job(srv, uid, *, text=SRT2B, video=True, aspect=None, fit=None, crop_x=None, max_height=720, orig=0, engine="google", extra_out=None):
    out = {"sync": "fit", "video": video, "orig_volume": orig, "duck": True, "max_height": max_height}
    for k, v in (("aspect", aspect), ("fit", fit), ("crop_x", crop_x)):
        if v is not None:
            out[k] = v
    out.update(extra_out or {})
    body = {"source": {"type": "upload", "upload_id": uid, "lang": "en", "text": text}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": engine, "keep_terms": True}, "output": out}
    r = srv.api("POST", "/api/jobs/dub", json=body)
    return r, (srv.wait_job(r.json()["id"], 300) if r.status_code == 200 else None)


if "C" in ONLY:
    DATA = WORK / "data_tiktok"
    shutil.rmtree(DATA, ignore_errors=True)
    srv = Server(8060, DATA, make_stub_home(WORK / "vox_tiktok"), name="tiktok").start()
    try:
        up = upload(srv, FX / "wide.mp4").json()
        # ---- a job that makes the vertical video at once
        r, j = make_job(srv, up["id"], aspect="9:16", fit="blur", max_height=720, orig=20)
        jid = r.json()["id"]
        jd = DATA / "jobs" / jid
        c.check(j["status"] == "done" and "dubbed.mp4" in j["outputs"], "job: TikTok vertical video made together with the dub", str(j.get("error")) + str(j.get("warnings")))
        mv = j["meta"]["video"]
        c.check(mv["aspect"] == "9:16" and mv["fit"] == "blur" and (mv["out_width"], mv["out_height"]) == (720, 1280) and mv["size"] == (jd / "dubbed.mp4").stat().st_size and mv["crop_x"] == 50.0,
                "job: meta.video says 9:16 / blur / 720x1280 / size", str(mv))
        c.check(j["params"]["output"]["aspect"] == "9:16" and j["params"]["output"]["fit"] == "blur" and j["params"]["output"]["max_height"] == 720, "job: the shape is stored in the parameters")
        c.check(size := audio.probe_media(jd / "dubbed.mp4"), "job: dubbed.mp4 can be probed")
        c.check((size["width"], size["height"]) == (720, 1280) and size["has_audio"], "job: the MP4 is 720x1280 with sound", str(size))
        c.check(any("TikTok / Reels / Shorts: 720x1280" in l for l in j["logs"]) and any("Original audio: muted while Khmer speaks" in l for l in j["logs"]), "job: the log says what was made (and that the original voice is muted)")
        vstep = next(s for s in j["steps"] if s["key"] == "video")
        c.check(vstep["status"] == "done" and vstep["progress"] == 1.0, "job: the video step is done")
        dl = srv.api("GET", f"/api/jobs/{jid}/file/dubbed.mp4", params={"download": 1})
        c.check(dl.status_code == 200 and "_khmer_tiktok_9x16.mp4" in dl.headers.get("content-disposition", "") and dl.headers["content-type"] == "video/mp4", "download name of a vertical video ends with _khmer_tiktok_9x16.mp4", dl.headers.get("content-disposition", ""))
        c.check(not j["warnings"] or all(w["code"] not in ("TIKTOK_LONG", "TIKTOK_BIG") for w in j["warnings"]), "job: a short small video gets no TikTok warning", str(j["warnings"]))

        # ---- the same job, only the video again: original shape
        t0m = (jd / "dubbed.mp4").stat().st_mtime
        dub0 = (jd / "dub.mp3").read_bytes()
        time.sleep(1.1)
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "original"})
        j2 = srv.wait_job(jid, 200)
        c.check(rr.status_code == 200 and rr.json() == {"id": jid} and j2["status"] == "done", "POST /video aspect=original -> done", rr.text[:200] + str(j2.get("error")))
        pm = audio.probe_media(jd / "dubbed.mp4")
        c.check((pm["width"], pm["height"]) == (1280, 720) and not audio.needs_scale(pm["width"], pm["height"], 720), "original shape again (landscape, 720p limit of the job)", str(pm))
        c.check(j2["meta"]["video"]["aspect"] == "original" and j2["meta"]["video"]["fit"] is None and (jd / "dubbed.mp4").stat().st_mtime > t0m, "meta.video back to 'original', the MP4 was replaced", str(j2["meta"]["video"]))
        c.check((jd / "dub.mp3").read_bytes() == dub0, "POST /video: the Khmer audio file is not touched")
        c.check(j2["params"]["output"]["aspect"] == "original" and j2["params"]["output"]["orig_volume"] == 20 and j2["params"]["output"]["duck"] is True, "POST /video: other output settings (original volume, mute) stay")
        dl = srv.api("GET", f"/api/jobs/{jid}/file/dubbed.mp4", params={"download": 1})
        c.check("_khmer_dubbed.mp4" in dl.headers.get("content-disposition", ""), "download name of the normal video is as before")

        # ---- crop, left edge
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "9:16", "fit": "crop", "crop_x": 0, "max_height": 720})
        j3 = srv.wait_job(jid, 200)
        c.check(rr.status_code == 200 and j3["status"] == "done" and j3["meta"]["video"]["fit"] == "crop" and j3["meta"]["video"]["crop_x"] == 0.0 and j3["params"]["output"]["crop_x"] == 0.0, "POST /video crop at the left edge", str(j3.get("error")) + str(j3["meta"]["video"]))
        # the file the browser would download: red on the left half = the left part of the picture is kept
        dlp = WORK / "tt_dl.mp4"
        dlp.write_bytes(srv.api("GET", f"/api/jobs/{jid}/file/dubbed.mp4").content)
        im = Img(dlp)
        c.check((im.w, im.h) == (720, 1280) and red(im.at(60, 640)) and red(im.at(660, 640)), "POST /video: crop_x=0 really keeps the left (red) part", str([im.at(60, 640), im.at(660, 640)]))
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "9:16", "fit": "crop", "crop_x": 100})
        srv.wait_job(jid, 200)
        dlp.write_bytes(srv.api("GET", f"/api/jobs/{jid}/file/dubbed.mp4").content)
        im = Img(dlp)
        c.check(blue(im.at(60, 640)) and blue(im.at(660, 640)), "POST /video: crop_x=100 keeps the right (blue) part")

        # ---- junk values are cleaned, missing values keep the job's settings
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "foo", "fit": "zzz", "crop_x": 999, "max_height": 999})
        j4 = srv.wait_job(jid, 200)
        o4 = j4["params"]["output"]
        c.check(rr.status_code == 200 and (o4["aspect"], o4["fit"], o4["crop_x"], o4["max_height"]) == ("original", "blur", 100.0, 1080) and j4["status"] == "done", "POST /video: junk values -> aspect original, fit blur, crop_x 100, 1080p", str(o4))
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "9:16"})
        j5 = srv.wait_job(jid, 200)
        o5 = j5["params"]["output"]
        c.check(o5["aspect"] == "9:16" and o5["fit"] == "blur" and o5["max_height"] == 1080 and j5["meta"]["video"]["fit"] == "blur" and (j5["meta"]["video"]["out_width"], j5["meta"]["video"]["out_height"]) == (1080, 1920),
                "POST /video: only the aspect given -> the other settings of the job stay; 1080p -> 1080x1920", str(o5))

        # ---- refusals
        c.check(srv.api("POST", "/api/jobs/nope/video", json={}).status_code == 404, "POST /video of an unknown job -> 404")
        tt = srv.api("POST", "/api/jobs/tts", json={"text": "សួស្តី", "voice": {"id": "km-KH-SreymomNeural"}}).json()["id"]
        srv.wait_job(tt, 120)
        r = srv.api("POST", f"/api/jobs/{tt}/video", json={})
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NOT_DUB", "POST /video of a text-to-speech job -> 400 NOT_DUB", r.text[:120])
        rt = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "transcript", "text": SRT2, "lang": "en"}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google"}, "output": {"video": False}}).json()["id"]
        srv.wait_job(rt, 200)
        r = srv.api("POST", f"/api/jobs/{rt}/video", json={"aspect": "9:16"})
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NO_VIDEO_SOURCE", "POST /video of a pasted-transcript job (no video) -> 400 NO_VIDEO_SOURCE", r.text[:120])
        mp3 = upload(srv, FX / "audio.mp3").json()
        r, ja = make_job(srv, mp3["id"], video=False)
        r2 = srv.api("POST", f"/api/jobs/{ja['id']}/video", json={"aspect": "9:16"})
        c.check(r2.status_code == 400 and r2.json()["detail"]["code"] == "NO_PICTURE", "POST /video of an audio-file job -> 400 NO_PICTURE", r2.text[:120])
        up2 = upload(srv, FX / "wide.mp4").json()
        rd = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "upload", "upload_id": up2["id"], "lang": "en", "text": SRT2}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "manual"}, "output": {"video": True}}).json()["id"]
        jdr = srv.wait_job(rd, 100)
        r = srv.api("POST", f"/api/jobs/{rd}/video", json={"aspect": "9:16"})
        c.check(jdr["meta"].get("draft") and r.status_code == 400 and r.json()["detail"]["code"] == "NO_AUDIO_YET", "POST /video of a copy/paste draft (no audio yet) -> 400 NO_AUDIO_YET", r.text[:120])

        # ---- a job that is busy: 409
        up3 = upload(srv, FX / "long.mp4").json()
        r, j6 = make_job(srv, up3["id"], text=SRT2B, video=False)
        id6 = r.json()["id"]
        rr = srv.api("POST", f"/api/jobs/{id6}/video", json={"aspect": "9:16", "fit": "blur", "max_height": 1080})
        jp, vs = None, {}
        for _ in range(40):
            time.sleep(0.4)
            jp = srv.api("GET", f"/api/jobs/{id6}").json()
            vs = next(s for s in jp["steps"] if s["key"] == "video")
            if "%" in (vs.get("detail") or ""):
                break
        r409 = srv.api("POST", f"/api/jobs/{id6}/video", json={"aspect": "9:16"})
        c.check(rr.status_code == 200 and r409.status_code == 409 and r409.json()["detail"]["code"] == "BUSY", "POST /video while the video is being made -> 409 BUSY", r409.text[:120])
        # the progress shows how far the video is, and the old MP4 would be kept: cancel it now
        c.check(vs["status"] == "running" and "making the vertical video" in vs["detail"] and 0.85 <= vs["progress"] < 1, "progress: the video step says 'making the vertical video … N%'", str(vs))
        rc = srv.api("POST", f"/api/jobs/{id6}/cancel")
        j7 = srv.wait_job(id6, 60)
        d6 = DATA / "jobs" / id6
        c.check(rc.status_code == 200 and j7["status"] == "done" and not (d6 / "dubbed.mp4").exists() and not list(d6.glob("*.part*")), "cancel while the video is made (no MP4 before): the dub stays 'done', no MP4, no .part file",
                f"{j7['status']} {list(d6.iterdir())}")
        vs = next(s for s in j7["steps"] if s["key"] == "video")
        c.check(vs["status"] == "skipped" and j7["params"]["output"].get("aspect") in (None, "original"), "cancel: the video step is 'skipped' and the settings are back as they were", str(vs) + str(j7["params"]["output"]))

        # a first MP4 exists, then a cancelled remake keeps it
        rr = srv.api("POST", f"/api/jobs/{id6}/video", json={"aspect": "original", "max_height": 720})
        j8 = srv.wait_job(id6, 120)
        d6mp4 = d6 / "dubbed.mp4"
        keep_bytes = d6mp4.read_bytes()
        rr = srv.api("POST", f"/api/jobs/{id6}/video", json={"aspect": "9:16", "fit": "blur", "max_height": 1080})
        time.sleep(2.0)
        srv.api("POST", f"/api/jobs/{id6}/cancel")
        j9 = srv.wait_job(id6, 60)
        c.check(j8["status"] == "done" and j9["status"] == "done" and d6mp4.read_bytes() == keep_bytes and not list(d6.glob("*.part*")), "cancelled remake: the earlier MP4 is untouched, job stays 'done'", str(j9["status"]))
        c.check(j9["params"]["output"]["aspect"] == "original" and j9["meta"]["video"]["aspect"] == "original" and next(s for s in j9["steps"] if s["key"] == "video")["status"] == "done", "cancelled remake: the settings and the info of the earlier MP4 stay")

        # a failing remake keeps the old MP4 as well (the file is damaged -> no picture)
        up_bad = DATA / "jobs" / jid / "upload.mp4"
        shutil.copy(up_bad, WORK / "tt_backup_upload.mp4")
        old = (DATA / "jobs" / jid / "dubbed.mp4").read_bytes()
        os.remove(up_bad)
        up_bad.write_bytes(os.urandom(5000))
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "9:16", "fit": "bars"})
        j10 = srv.wait_job(jid, 100)
        c.check(rr.status_code == 200 and j10["status"] == "done" and (DATA / "jobs" / jid / "dubbed.mp4").read_bytes() == old, "failing remake (damaged source): the old MP4 stays", str(j10.get("error")))
        c.check(any(w["code"] == "NO_PICTURE" for w in j10["warnings"]) and next(s for s in j10["steps"] if s["key"] == "video")["status"] == "error" and j10["params"]["output"]["fit"] == "blur", "failing remake: a warning is shown, the step is 'error', the settings of the old MP4 stay", str(j10["warnings"]))
        os.remove(up_bad)
        shutil.copy(WORK / "tt_backup_upload.mp4", up_bad)
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "9:16", "fit": "bars"})
        j11 = srv.wait_job(jid, 100)
        c.check(j11["status"] == "done" and not [w for w in j11["warnings"] if w["code"] == "NO_PICTURE"] and j11["meta"]["video"]["fit"] == "bars", "after the file is back, the next remake works and the old warning is gone", str(j11["warnings"]))

        # ---- regenerate (edit a line) uses the shape that is sent with it
        rr = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [{"idx": 0, "km": "សួស្តី API និង Dashboard"}], "output": {"video": True, "aspect": "9:16", "fit": "crop", "crop_x": 20, "max_height": 720, "orig_volume": 20, "duck": True, "sync": "fit"}})
        j12 = srv.wait_job(jid, 200)
        c.check(rr.status_code == 200 and j12["status"] == "done" and j12["meta"]["video"]["fit"] == "crop" and (j12["meta"]["video"]["out_width"], j12["meta"]["video"]["out_height"]) == (720, 1280) and j12["segments"][0]["km"].startswith("សួស្តី API"),
                "regenerate with output.aspect=9:16 / crop 20 % -> dub + vertical video", str(j12.get("error")) + str(j12["meta"]["video"]))
        # a regenerate that does not send `output` keeps the job's shape
        rr = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [{"idx": 1, "km": "យើងនឹងបង្កើត Dashboard"}]})
        j13 = srv.wait_job(jid, 200)
        c.check(j13["status"] == "done" and j13["meta"]["video"]["aspect"] == "9:16" and j13["meta"]["video"]["fit"] == "crop" and j13["params"]["output"]["crop_x"] == 20.0, "regenerate without `output`: the job keeps its vertical settings", str(j13["meta"]["video"]))

        # ---- the source is already vertical -> nothing to fit, no warning, the normal rules
        upv = upload(srv, FX / "vert.mp4").json()
        r, jv = make_job(srv, upv["id"], aspect="9:16", fit="blur", max_height=1080)
        mvv = jv["meta"]["video"]
        c.check(jv["status"] == "done" and mvv["aspect"] == "9:16" and mvv["fit"] is None and (mvv["out_width"], mvv["out_height"]) == (1080, 1920) and any("already is 9:16" in l for l in jv["logs"]),
                "an already vertical upload: 'nothing to fit', output stays 1080x1920", str(mvv))

        # ---- TikTok warnings (a 12-minute / 300 MB video is too slow to make here: check the rule with fake numbers)
        from app import pipeline  # noqa: E402
        c.check(frame.TIKTOK_MAX_MINUTES == 10 and frame.TIKTOK_APP_MAX_MB == 287 and "TIKTOK_LONG" in pipeline.VIDEO_WARNINGS and "TIKTOK_BIG" in pipeline.VIDEO_WARNINGS, "TikTok limits and the warning codes are defined")
    finally:
        srv.stop()

# ==================================================================================================================== D. browser (added with the user interface)
if "D" in ONLY and (TESTS / "test_tiktok_ui.py").exists():
    exec(compile(open(TESTS / "test_tiktok_ui.py", encoding="utf-8").read(), "test_tiktok_ui.py", "exec"))

sys.exit(c.done())
