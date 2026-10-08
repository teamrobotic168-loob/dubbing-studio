"""Hide the ORIGINAL subtitles (v1.10, app/hardsub.py): A units, B real ffmpeg pictures (pixels!), C API + jobs (real Google / Edge),
D browser (Playwright / Chromium).  Set ONLY=A,B,C,D to run some of the parts.

The test video has no real subtitles, but something just as hard to read: the lowest 30 % of every picture are vertical stripes only 2 pixels wide
(white / black) - the sharpest "text" there is.  The upper part is a coarse checkerboard, the middle is flat grey.  So "is this row still sharp?" is a
number (the mean difference between neighbouring pixels of a row), and "where exactly is the band?" is a list of rows.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from lib import *  # noqa: E402,F401,F403

WORK.mkdir(parents=True, exist_ok=True)
os.environ["KDS_DATA_DIR"] = str(WORK / "data_hardsub_units")
shutil.rmtree(WORK / "data_hardsub_units", ignore_errors=True)
from app import audio, frame, hardsub, pipeline  # noqa: E402

ONLY = set((os.environ.get("ONLY") or "A,B,C,D").split(","))
c = Checker("Hide the original subtitles")
FF = audio.ffmpeg_exe()
FX = WORK / "fx_hardsub"
FX.mkdir(exist_ok=True)

GEQ = "geq=lum='if(lt(Y,H*0.35), if(lt(mod(floor(X/16)+floor(Y/16),2),1),200,60), if(gt(Y,H*0.70), if(lt(mod(X,4),2),235,16), 128))':cb=128:cr=128"


def ffm(*args):
    subprocess.run([FF, "-v", "error", "-y", *args], check=True)


def make_text_video(out, w, h, secs=3, fps=25, with_audio=True, vcodec=("libx264", "-preset", "ultrafast", "-crf", "10", "-pix_fmt", "yuv420p"), vf_extra="", extra=()):
    cmd = ["-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}:r={fps}"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    cmd += ["-vf", GEQ + ",format=yuv420p" + vf_extra, "-map", "0:v"]
    if with_audio:
        cmd += ["-map", "1:a", "-c:a", "aac", "-shortest"]
    ffm(*cmd, "-t", str(secs), "-c:v", *vcodec, *extra, str(out))


def make_fixtures():
    def todo(name):
        return not (FX / name).exists()
    if todo("text.mp4"):
        make_text_video(FX / "text.mp4", 640, 360, secs=4)
    if todo("wide.mp4"):                                         # 2.37:1: shown with black bars above and below in a 16:9 player
        make_text_video(FX / "wide.mp4", 640, 270, secs=4)
    if todo("big.mp4"):
        make_text_video(FX / "big.mp4", 1920, 1080, secs=2, fps=10, with_audio=False)
    if todo("odd.mkv"):
        make_text_video(FX / "odd.mkv", 853, 479, secs=2, with_audio=False, vcodec=("ffv1",))
    if todo("pal.mkv"):
        make_text_video(FX / "pal.mkv", 720, 576, secs=2, with_audio=False, vf_extra=",setsar=16/15")
    if todo("rot.mp4"):
        make_text_video(FX / "stored.mp4", 640, 360, secs=2, with_audio=False)
        # a phone video: the picture is stored sideways (360x640) and the rotation flag turns it upright (640x360, the stripes at the bottom)
        ffm("-i", str(FX / "stored.mp4"), "-vf", "transpose=1", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "10", "-pix_fmt", "yuv420p", "-an", str(FX / "rot_stored.mp4"))
        ffm("-display_rotation", "90", "-i", str(FX / "rot_stored.mp4"), "-c", "copy", str(FX / "rot.mp4"))
    if todo("dub.mp3"):
        ffm("-f", "lavfi", "-i", "sine=frequency=880:sample_rate=24000", "-t", "4", "-ac", "1", "-c:a", "libmp3lame", str(FX / "dub.mp3"))
    if todo("audio.mp3"):
        ffm("-f", "lavfi", "-i", "sine=frequency=500:sample_rate=44100", "-t", "4", "-c:a", "libmp3lame", str(FX / "audio.mp3"))


make_fixtures()
OUT = WORK / "out_hardsub"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(exist_ok=True)


# ------------------------------------------------------------------------------------------------------------------ measuring
def gray(path, t=1.0):
    """(w, h, bytes) of one frame as 8 bit grey - in the shape ffmpeg decodes it (rotation applied, non-square pixels NOT stretched)."""
    info = audio.probe_media(path)
    w, h = frame.display_size({**info, "sar": 1.0})
    d = subprocess.run([FF, "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    assert len(d) == w * h, (len(d), w, h)
    return w, h, d


def rows(path, t=1.0):
    """Sharpness of every row: the mean difference between neighbouring pixels (the stripes: 127, flat: 0, the checkerboard: about 10)."""
    w, h, d = gray(path, t)
    out = []
    for y in range(h):
        r = d[y * w:(y + 1) * w]
        out.append(sum(abs(a - b) for a, b in zip(r, r[1:])) / (w - 1))
    return out


def mean_of(path, y0, y1, t=1.0):
    w, h, d = gray(path, t)
    seg = d[y0 * w:y1 * w]
    return sum(seg) / len(seg)


def avg(r, a, b):
    return sum(r[a:b]) / max(1, (b - a))


def flat_rows(r, ctrl, lo, hi, thr=0.3):
    """Rows of [lo, hi) that are much less sharp than the same rows of the control picture."""
    return [y for y in range(lo, hi) if ctrl[y] > 20 and r[y] < thr * ctrl[y]]


CTRL = (True, "blur", 45, 10, 50)       # a band in the flat grey middle: the picture is re-encoded the same way, but nothing visible changes


def render(src, out, hs=None, fit=None, crop_x=50, max_height=1080, orig=0.0, mask=None, progress=None, dub="dub.mp3"):
    """audio.mux_video the way the pipeline calls it: probe, plan, mux.  hs = (on, effect, bottom, height, strength).  Returns the probe of the result."""
    info = audio.probe_media(FX / src)
    hp = hardsub.plan(info, *hs) if hs else None
    fp = frame.plan(info, "9:16", fit, crop_x, max_height) if fit else None
    audio.mux_video(FX / src, FX / dub, out, orig, progress=progress, duck_mask=mask, max_height=max_height, frame=fp, hardsub=hp)
    return audio.probe_media(out)


# ==================================================================================================================== A. units
if "A" in ONLY:
    c.check(all(hardsub.clean_on(v) is True for v in (True, "true", " TRUE ", "1", "yes", "on", 1, 2.5)), "on: true, 'true', '1', 'yes', 'on', numbers other than 0")
    c.check(all(hardsub.clean_on(v) is False for v in (False, "false", "0", "no", "off", "", None, 0, 0.0, float("nan"), [], {}, "x")), "on: everything else is off (nothing changes for people who ignore the feature)")
    c.check([hardsub.clean_effect(v) for v in ("blur", "MOSAIC", " dark ", "Frost", "x", None, 5, "")] == ["blur", "mosaic", "dark", "frost", "blur", "blur", "blur", "blur"], "effect: four effects, anything else -> blur")
    c.check(hardsub.EFFECTS == ("blur", "mosaic", "dark", "frost") and set(hardsub.EFFECT_NAMES) == set(hardsub.EFFECTS), "effects: blur, mosaic, dark, frost (each has a name for the log)")
    bots = [hardsub.clean_bottom(v) for v in (0, 3, 60, 61, -4, "7.5", "x", None, float("nan"), float("inf"), 3.04)]
    c.check(bots == [0.0, 3.0, 60.0, 60.0, 0.0, 7.5, 3.0, 3.0, 3.0, 3.0, 3.0], "bottom: 0..60 %, junk -> 3", str(bots))
    hs_ = [hardsub.clean_height(v) for v in (16, 4, 3, 50, 80, "20", "x", None, float("nan"))]
    c.check(hs_ == [16.0, 4.0, 4.0, 50.0, 50.0, 20.0, 16.0, 16.0, 16.0], "height: 4..50 %, junk -> 16", str(hs_))
    c.check(hardsub.clean_height(50, 60) == 40.0 and hardsub.clean_height(50, 55) == 45.0 and hardsub.clean_height(20, 3) == 20.0 and hardsub.clean_height(30, 0) == 30.0 and hardsub.clean_height(2, 60) == 4.0,
            "height: the band stays inside the picture (bottom + height <= 100)")
    sts = [hardsub.clean_strength(v) for v in (50, 10, 9, 100, 500, "75.4", "x", None, float("nan"))]
    c.check(sts == [50, 10, 10, 100, 100, 75, 50, 50, 50] and all(isinstance(v, int) for v in sts), "strength: whole number 10..100, junk -> 50", str(sts))

    c.check(hardsub.sigma(50, 1080) == 29.2 and hardsub.sigma(50, 360) == 9.7 and hardsub.sigma(10, 100) == 2.0 and hardsub.sigma(100, 1080) == 54.0, "blur: sigma is a share of the picture height (1080p 29.2, 360p 9.7), at least 2",
            str([hardsub.sigma(50, 1080), hardsub.sigma(50, 360), hardsub.sigma(10, 100), hardsub.sigma(100, 1080)]))
    c.check(all(hardsub.sigma(s + 5, 720) > hardsub.sigma(s, 720) for s in range(10, 100, 5)) and all(hardsub.sigma(50, h2) > hardsub.sigma(50, h1) for h1, h2 in ((240, 360), (360, 720), (720, 1080))), "blur: stronger and bigger pictures -> a bigger sigma")
    c.check(hardsub.block(50, 1080) == 32 and hardsub.block(50, 360) == 10 and hardsub.block(10, 100) == 6 and hardsub.block(100, 1080) == 56 and all(hardsub.block(s, h) % 2 == 0 for s in range(10, 101, 5) for h in (240, 360, 480, 720, 1080, 2160)),
            "mosaic: squares of 32 px at 1080p / 10 px at 360p, always even, at least 6")
    c.check([hardsub.opacity(s) for s in (10, 50, 60, 100)] == [0.625, 0.925, 1.0, 1.0], "dark box: 0.625 (10) ... 0.925 (50) ... fully black from 60", str([hardsub.opacity(s) for s in (10, 50, 60, 100)]))

    G = {fx: hardsub.build_graph(fx, 3, 16, 50, 1080) for fx in hardsub.EFFECTS}
    c.check(all(g.startswith("[0:v:0]") and g.endswith("[kcov]") for g in G.values()), "graph: every effect reads [0:v:0] and makes [kcov]")
    c.check("drawbox=" in G["dark"] and "color=black@0.925" in G["dark"] and ":t=fill" in G["dark"] and "split" not in G["dark"] and "overlay" not in G["dark"], "graph dark: one drawbox on the picture")
    c.check(all("split=2[kca][kcb]" in G[fx] and "crop=w=iw:h=" in G[fx] and "overlay=x=0:y=" in G[fx] and "format=yuv420" in G[fx] for fx in ("blur", "mosaic", "frost")), "graph blur / mosaic / frost: split, crop the band, effect, overlay it back")
    c.check("gblur=sigma=29.2:steps=2" in G["blur"] and "eq=" not in G["blur"], "graph blur: gblur with sigma 29.2 at 1080p")
    c.check("gblur=sigma=29.2:steps=2,eq=brightness=-0.15:saturation=0.9" in G["frost"], "graph frost: blur + a little darker")
    c.check("scale=w='ceil(iw/32)':h='ceil(ih/32)':flags=area,scale=w='iw*32':h='ih*32':flags=neighbor" in G["mosaic"], "graph mosaic: average down to one pixel per square, hard edges up again (32 px squares)")
    c.check("y='trunc(ih*0.81/2)*2'" in G["blur"] and "h='trunc(ih*0.97/2)*2-trunc(ih*0.81/2)*2'" in G["blur"] and "y='trunc(H*0.81/2)*2'" in G["blur"], "graph: the band is an expression of the real size (even rows): 81 % .. 97 %")
    g0 = hardsub.build_graph("blur", 0, 20, 50, 360)
    c.check("trunc(ih*1/2)*2" in g0 and "trunc(ih*0.8/2)*2" in g0, "graph: band at the very bottom (bottom 0, height 20) = 80 % .. 100 %")
    labels = set()
    for g in list(G.values()) + [g0, frame.build_graph("blur", 1080, 1920), frame.build_graph("crop", 720, 1280), frame.build_graph("bars", 480, 854)]:
        labels |= set(re.findall(r"\[([A-Za-z0-9:]+)\]", g))
    mine = {lb for lb in labels if lb.startswith("kc")}
    c.check(mine == {"kca", "kcb", "kcc", "kcov"}, "labels: the band uses kca / kcb / kcc / kcov only", str(mine))
    others = {lb for lb in labels if not lb.startswith("kc")}
    c.check(not (mine & {"kbg", "kfg", "kbl", "kfs", "vout", "o", "m", "d", "bg", "fg", "aout", "0:v:0"}) and {"kbg", "kfg", "kbl", "kfs", "vout", "0:v:0"} >= others, "labels: no clash with the frame graph (kbg ...), the audio graph (o, m, d, bg, fg, aout) or [vout]", str(others))
    hp = hardsub.plan({"width": 1280, "height": 720}, True, "mosaic", 5, 20, 60)
    c.check(hp.graph_from("0:v:0") == hp.graph and hp.graph_from("kx").startswith("[kx]split=2") and hp.graph_from("kx").endswith("[kcov]") and "[0:v:0]" not in hp.graph_from("kx"), "plan.graph_from: the same graph for another input label")
    c.check(hardsub.build_graph("dark", 3, 16, 50, 1080, src="kx", out="kz").startswith("[kx]drawbox") and hardsub.build_graph("dark", 3, 16, 50, 1080, src="kx", out="kz").endswith("[kz]"), "build_graph: input and output labels can be chosen")
    c.check(hardsub.build_graph("blur", 3, 16, 50, 0) == hardsub.build_graph("blur", 3, 16, 50, 1080) == hardsub.build_graph("blur", 3, 16, 50, None), "graph: an unknown picture height is taken as 1080")

    c.check(all(hardsub.plan({"width": 1280, "height": 720}, v) is None for v in (False, None, "false", 0, "", "no")), "plan: off -> None (the old subtitles stay, the picture may be copied)")
    p = hardsub.plan({"width": 1280, "height": 720}, True, "Dark", "7", "12", "70")
    c.check(p and (p.effect, p.bottom, p.height, p.strength, p.picture_height) == ("dark", 7.0, 12.0, 70, 720) and p.as_info() == {"effect": "dark", "bottom": 7.0, "height": 12.0, "strength": 70}, "plan: cleaned values + the size of the picture", str(p))
    c.check("dark box" in p.label and "12 % high" in p.label and "7 % above the lower edge" in p.label and "strength 70" in p.label, "plan.label says what is made", p.label)
    p2 = hardsub.plan({"width": 1080, "height": 1920, "rotation": 90}, True)
    c.check(p2.picture_height == 1080 and (p2.effect, p2.bottom, p2.height, p2.strength) == ("blur", 3.0, 16.0, 50), "plan: defaults (blur, 3 %, 16 %, 50); a sideways phone video is measured as it is shown (1080 high)", str(p2))
    p3 = hardsub.plan({}, True)
    c.check(p3 is not None and p3.picture_height == 1080 and hardsub.plan(None, True) is not None, "plan: a picture of unknown size still gets its band (1080 is assumed)")
    p4 = hardsub.plan({"width": 640, "height": 360}, True, "blur", 55, 50, 50)
    c.check((p4.bottom, p4.height) == (55.0, 45.0), "plan: the band is kept inside the picture (55 + 50 -> height 45)")

    for fit in ("blur", "crop", "bars"):
        for sar in (False, True):
            fp = frame.plan({"width": 1920, "height": 1080, "sar": 16 / 15 if sar else 1.0}, "9:16", fit, 30, 720)
            c.check(fp.graph_from("0:v:0") == fp.graph and fp.sar_fix is sar and fp.graph_from("kcov").startswith("[kcov]"), f"FramePlan.graph_from('0:v:0') is the plan's own graph ({fit}, pixel-shape fix {sar})")

    cx = pipeline._ctx_from({"output": {"video": True}}, None, True)
    c.check((cx.hide_subs, cx.hide_effect, cx.hide_bottom, cx.hide_height, cx.hide_strength) == (False, "blur", 3.0, 16.0, 50), "pipeline: nothing asked -> off, defaults")
    cx = pipeline._ctx_from({"output": {"video": True, "hide_subs": True, "hide_effect": "Mosaic", "hide_bottom": "55", "hide_height": 50, "hide_strength": 7}}, None, True)
    c.check((cx.hide_subs, cx.hide_effect, cx.hide_bottom, cx.hide_height, cx.hide_strength) == (True, "mosaic", 55.0, 45.0, 10), "pipeline: values are cleaned (height kept inside the picture)", str(cx))
    cx = pipeline._ctx_from({"output": {"hide_subs": "false", "hide_effect": 7, "hide_bottom": None, "hide_height": "x", "hide_strength": "x"}}, None, True)
    c.check((cx.hide_subs, cx.hide_effect, cx.hide_bottom, cx.hide_height, cx.hide_strength) == (False, "blur", 3.0, 16.0, 50), "pipeline: junk -> defaults")

    # texts
    i18n = (PROJECT / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
    appjs = (PROJECT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    html = (PROJECT / "static" / "index.html").read_text(encoding="utf-8")
    keys = ["hs.title", "hs.desc", "hs.fx", "hs.bottom", "hs.height", "hs.strength", "hs.hint", "hs.slow", "hs.stat", "rf.what.hide"] + [f"hs.fx.{f}" for f in hardsub.EFFECTS] + [f"hs.fx.hint.{f}" for f in hardsub.EFFECTS]
    c.check(all(len(re.findall(rf"^\s*'{re.escape(k)}':", i18n, re.M)) == 2 for k in keys), "i18n: every hs.* key exists once in Khmer and once in English", str([k for k in keys if len(re.findall(rf"^\s*'{re.escape(k)}':", i18n, re.M)) != 2]))
    used = {k for k in set(re.findall(r"data-i18n=\"(hs\.[a-z.]+)\"", appjs)) | set(re.findall(r"t\('(hs\.[a-z.]+)'\)", appjs)) if not k.endswith(".")}
    c.check(used and all(len(re.findall(rf"^\s*'{re.escape(k)}':", i18n, re.M)) == 2 for k in used), "i18n: every hs.* key that app.js uses exists", str(sorted(used)))
    c.check('id="hs-row"' in html and 'data-hs-controls="step4"' in html, "index.html: Step 4 has the row #hs-row")
    ids = re.findall(r'\sid="([^"]+)"', html)
    c.check(len(ids) == len(set(ids)) and "hs-row" in ids, "index.html: ids are still unique")

# ==================================================================================================================== B. real ffmpeg pictures
if "B" in ONLY:
    SRC = "text.mp4"
    info = audio.probe_media(FX / SRC)
    c.check((info["width"], info["height"], info["has_audio"]) == (640, 360, True), "fixture: 640x360 with sound", str(info))
    src_rows = rows(FX / SRC)
    c.check(avg(src_rows, 260, 340) > 120 and 5 < avg(src_rows, 5, 100) < 15 and avg(src_rows, 140, 240) < 1, "fixture: stripes at the bottom (127), checkerboard on top (10), flat grey in the middle (0)",
            str([avg(src_rows, 260, 340), avg(src_rows, 5, 100), avg(src_rows, 140, 240)]))
    render(SRC, OUT / "ctrl.mp4", CTRL)
    ctrl = rows(OUT / "ctrl.mp4")
    c.check(abs(avg(ctrl, 260, 340) - avg(src_rows, 260, 340)) < 2 and abs(avg(ctrl, 5, 100) - avg(src_rows, 5, 100)) < 0.5, "control: a band in the flat middle changes nothing that can be seen (the re-encode keeps the stripes)", str([avg(ctrl, 260, 340), avg(src_rows, 260, 340)]))

    # ---- the four effects, default band: 3 % above the bottom, 16 % high -> rows 290 .. 347 of 360
    means = {}
    for fx in hardsub.EFFECTS:
        o = OUT / f"fx_{fx}.mp4"
        pr = render(SRC, o, (True, fx, 3, 16, 50))
        r = rows(o)
        flat = flat_rows(r, ctrl, 252, 360)
        c.check((pr["width"], pr["height"], pr["video_codec"], pr["has_audio"]) == (640, 360, "h264", True), f"{fx}: 640x360 H.264 with sound (same shape as the source)", str(pr))
        c.check(flat and abs(min(flat) - 290) <= 1 and abs(max(flat) - (349 if fx == "mosaic" else 347)) <= 1 and 56 <= len(flat) <= 60, f"{fx}: the rows 290 .. 347 are no longer sharp (and only those)",
                str((min(flat), max(flat), len(flat))) if flat else "no flat rows")
        c.check(avg(r, 295, 342) < 0.12 * avg(ctrl, 295, 342), f"{fx}: the stripes of the band are gone", f"{avg(r, 295, 342):.1f} vs {avg(ctrl, 295, 342):.1f}")
        c.check(0.97 <= avg(r, 256, 286) / avg(ctrl, 256, 286) <= 1.03, f"{fx}: the stripes just ABOVE the band are untouched", f"{avg(r, 256, 286):.1f} vs {avg(ctrl, 256, 286):.1f}")
        c.check(0.95 <= avg(r, 352, 360) / avg(ctrl, 352, 360) <= 1.05, f"{fx}: the stripes just BELOW the band are untouched", f"{avg(r, 352, 360):.1f} vs {avg(ctrl, 352, 360):.1f}")
        c.check(abs(avg(r, 5, 100) - avg(ctrl, 5, 100)) < 0.3 and avg(r, 140, 240) < 1, f"{fx}: the rest of the picture is untouched (checkerboard, flat grey)")
        means[fx] = mean_of(o, 296, 342)
    c.check(means["frost"] < means["blur"] - 20 and 100 < means["blur"] < 150, "frost is darker than blur (blur keeps the average grey)", str(means))
    c.check(means["dark"] < 20, "dark: the band is almost black", str(means))

    # ---- strength
    for s, lo, hi in ((10, 35, 60), (50, 4, 16), (100, 0, 4)):
        o = OUT / f"dark_{s}.mp4"
        render(SRC, o, (True, "dark", 3, 16, s))
        m = mean_of(o, 296, 342)
        c.check(lo <= m <= hi, f"dark box strength {s}: the band is {'a little' if s < 50 else 'almost'} {'visible' if s < 50 else 'black'} (mean {lo}..{hi})", f"{m:.1f}")

    def edges(path, y, thr=8):
        """x positions in row y where the grey level jumps: in a mosaic they are the borders of the squares."""
        w, h, d = gray(path)
        r = d[y * w:(y + 1) * w]
        return [i + 1 for i, (a, b) in enumerate(zip(r, r[1:])) if abs(a - b) > thr]

    render(SRC, OUT / "mo_10.mp4", (True, "mosaic", 3, 16, 10))
    render(SRC, OUT / "mo_100.mp4", (True, "mosaic", 3, 16, 100))
    for s_, k_, least in ((10, hardsub.block(10, 360), 60), (100, hardsub.block(100, 360), 15)):
        e = edges(OUT / f"mo_{s_}.mp4", 310)
        on_grid = [x for x in e if min(x % k_, k_ - x % k_) <= 1]
        c.check(k_ == (6 if s_ == 10 else 18) and len(e) >= least and len(on_grid) >= 0.95 * len(e), f"mosaic strength {s_}: the squares are {k_} px (every border of a square is on a {k_} px grid)", f"{len(on_grid)} of {len(e)} borders on the grid; first: {e[:8]}")

    # ---- the place of the band (the stripes only exist from row 253 down, so a band above that has nothing to show: it must change nothing)
    for (b, h, lo, hi) in ((20, 10, 253, 288), (0, 20, 288, 360)):
        o = OUT / f"pos_{b}_{h}.mp4"
        render(SRC, o, (True, "blur", b, h, 50))
        r = rows(o)
        flat = [y for y in range(252, 360) if src_rows[y] > 20 and r[y] < 0.3 * src_rows[y]]
        c.check(flat and abs(min(flat) - lo) <= 1 and abs(max(flat) - (hi - 1)) <= 1 and len(flat) >= (hi - lo) - 3,
                f"band {h} % high, {b} % above the bottom: rows {lo} .. {hi - 1} are flattened", str((min(flat), max(flat), len(flat))) if flat else "no flat rows")
    render(SRC, OUT / "pos_30_25.mp4", (True, "blur", 30, 25, 50))
    r = rows(OUT / "pos_30_25.mp4")
    c.check(abs(avg(r, 252, 360) - avg(src_rows, 252, 360)) < 1 and abs(avg(r, 5, 100) - avg(src_rows, 5, 100)) < 0.5, "a band in the flat middle (30 %, 25 %) leaves the stripes and the checkerboard as they are")

    # ---- the original audio mixed under the dub, muted while Khmer speaks (the video graph and the audio graph in ONE -filter_complex)
    import numpy as np
    gain = OUT / "gain.wav"
    env = np.ones(4 * audio.DUCK_SR, dtype=np.float32)
    env[int(1.0 * audio.DUCK_SR):int(2.0 * audio.DUCK_SR)] = 0.0
    audio.write_gain_wav(env, gain)
    pr = render(SRC, OUT / "mix.mp4", (True, "mosaic", 3, 16, 50), orig=0.5, mask=gain)
    r = rows(OUT / "mix.mp4")
    flat = flat_rows(r, ctrl, 252, 360)
    c.check(pr["has_audio"] and abs(pr["duration"] - 4.0) < 0.6 and flat and abs(min(flat) - 290) <= 1, "with the original sound mixed in and a mute mask: the audio graph and the band graph work together", str(pr))
    pr = render(SRC, OUT / "mix2.mp4", (True, "blur", 3, 16, 50), orig=0.5)
    c.check(pr["has_audio"] and pr["has_video"], "with the original sound at a constant level: works too")

    # ---- the picture is NOT re-encoded when the feature is off
    pr = render(SRC, OUT / "copy.mp4", None)
    c.check(rows(OUT / "copy.mp4") == src_rows and pr["video_codec"] == "h264" and (pr["width"], pr["height"]) == (640, 360), "off: the picture is copied untouched (identical rows)")
    pr = render(SRC, OUT / "off.mp4", (False, "mosaic", 3, 16, 50))
    c.check(rows(OUT / "off.mp4") == src_rows, "on=False with all the other values given: still copied untouched")

    # ---- progress
    seen = []
    render(SRC, OUT / "prog.mp4", (True, "blur", 3, 16, 50), progress=seen.append)
    c.check(seen and all(0 <= v <= 1.0001 for v in seen) and seen == sorted(seen) and seen[-1] > 0.9, "progress: 0..1 and rising while the band is made", str(seen[-3:]))

    # ---- inside the 9:16 frame of TikTok: the band is made first, the frame second
    for fit, lo, hi in (("bars", 505, 560), ("blur", 505, 560), ("crop", 685, 835)):
        cp = OUT / f"tt_ctrl_{fit}.mp4"
        o = OUT / f"tt_{fit}.mp4"
        render(SRC, cp, CTRL, fit=fit, max_height=480)
        pr = render(SRC, o, (True, "blur", 3, 16, 50), fit=fit, max_height=480)
        rc, ro = rows(cp), rows(o)
        flat = flat_rows(ro, rc, 0, len(ro), 0.35)
        c.check((pr["width"], pr["height"]) == (480, 854) and pr["has_audio"], f"9:16 {fit}: 480x854 with sound", str(pr))
        c.check(flat and lo <= min(flat) and max(flat) <= hi and len(flat) >= (35 if fit != "crop" else 120), f"9:16 {fit}: the flattened rows are where the band is in the picture ({lo} .. {hi})", str((min(flat), max(flat), len(flat))) if flat else "none")
        bot0 = 835 if fit == "crop" else 780               # (crop: the picture fills the frame, the band ends at row 828; below it the stripes go on)
        c.check(abs(avg(ro, 0, 100) - avg(rc, 0, 100)) < 1.0 and abs(avg(ro, bot0, 854) - avg(rc, bot0, 854)) < 1.0, f"9:16 {fit}: the top and the bottom of the frame are the same as without a band")
    # the stripes just above the band survive in the 9:16 picture
    ro, rc = rows(OUT / "tt_crop.mp4"), rows(OUT / "tt_ctrl_crop.mp4")
    c.check(0.9 <= avg(ro, 600, 680) / avg(rc, 600, 680) <= 1.1, "9:16 crop: the stripes just above the band are untouched", f"{avg(ro, 600, 680):.1f} vs {avg(rc, 600, 680):.1f}")

    # ---- a big picture that has to be scaled down: the band is made on the original, then the size limit is applied
    pr = render("big.mp4", OUT / "big_720.mp4", (True, "blur", 3, 16, 50), max_height=720)
    big_ctrl = OUT / "big_ctrl.mp4"
    render("big.mp4", big_ctrl, CTRL, max_height=720)
    rb, rbc = rows(OUT / "big_720.mp4"), rows(big_ctrl)
    flat = flat_rows(rb, rbc, 500, 720, 0.4)
    c.check((pr["width"], pr["height"]) == (1280, 720) and flat and 580 <= min(flat) and max(flat) <= 700 and len(flat) >= 80, "1080p source with the 720p limit: 1280x720, the band is at 81 % .. 97 % of the height", str((pr["width"], pr["height"], min(flat), max(flat), len(flat))) if flat else str(pr))
    pr = render("big.mp4", OUT / "big_1080.mp4", (True, "mosaic", 3, 16, 50), max_height=1080)
    c.check((pr["width"], pr["height"]) == (1920, 1080), "1080p source with the 1080p limit: stays 1920x1080")

    # ---- odd sizes, non-square pixels, a sideways phone video
    pr = render("odd.mkv", OUT / "odd.mp4", (True, "blur", 3, 16, 50))
    c.check(pr["width"] % 2 == 0 and pr["height"] % 2 == 0 and abs(pr["width"] - 853) <= 1 and abs(pr["height"] - 479) <= 1, "853x479 (odd) + band: the size is made even (H.264 needs it)", str((pr["width"], pr["height"])))
    pr = render("pal.mkv", OUT / "pal.mp4", (True, "blur", 3, 16, 50))
    rp = rows(OUT / "pal.mp4")
    pal_ctrl = OUT / "pal_ctrl.mp4"
    render("pal.mkv", pal_ctrl, CTRL)
    rpc = rows(pal_ctrl)
    flat = flat_rows(rp, rpc, 400, 576)
    c.check((pr["width"], pr["height"]) == (720, 576) and abs(pr["sar"] - 16 / 15) < 0.01 and flat and abs(min(flat) - 466) <= 2, "720x576 with non-square pixels + band: size and pixel shape stay, the band is at 81 %", str((pr["sar"], min(flat), max(flat))) if flat else str(pr))
    pr = render("rot.mp4", OUT / "rot_out.mp4", (True, "blur", 3, 16, 50))
    rr_ = rows(OUT / "rot_out.mp4")
    rot_ctrl = OUT / "rot_ctrl.mp4"
    render("rot.mp4", rot_ctrl, CTRL)
    rrc = rows(rot_ctrl)
    flat = flat_rows(rr_, rrc, 252, 360)
    c.check(flat and abs(min(flat) - 290) <= 1 and abs(max(flat) - 347) <= 1, "a sideways phone video: the band is at the bottom of the picture people SEE (rows 290 .. 347), not of the stored one", str((min(flat), max(flat))) if flat else str(pr))
    # a phone video together with the 9:16 frame is 'already vertical' in this fixture? (upright 640x360 -> not vertical): the band + frame work on the turned picture
    pr = render("rot.mp4", OUT / "rot_tt.mp4", (True, "blur", 3, 16, 50), fit="bars", max_height=480)
    c.check((pr["width"], pr["height"]) == (480, 854), "a sideways phone video + band + 9:16 frame: 480x854")

    # ---- an audio file has no picture: not our business (the pipeline refuses before), and mux with a plan fails with a clear error instead of a crash
    try:
        render("audio.mp3", OUT / "nopic.mp4", (True, "blur", 3, 16, 50))
        err = None
    except Exception as e:  # noqa: BLE001
        err = e
    c.check(isinstance(err, audio.FFmpegError) and not list(OUT.glob("nopic*")), "an audio-only file: a clear FFmpegError, and no MP4 / .part file is left behind", repr(err)[:200])

# ==================================================================================================================== C. API + jobs
SRT2B = ("1\n00:00:00,500 --> 00:00:03,000\nWelcome to this tutorial about the API.\n\n2\n00:00:03,500 --> 00:00:06,500\nWe will build a Dashboard with Python.\n\n"
         "3\n00:00:07,000 --> 00:00:09,500\nThank you for watching.\n")
SRT2 = SRT2B.split("\n\n3\n")[0] + "\n"


def upload(srv, path, name=None):
    with open(path, "rb") as f:
        return srv.api("POST", "/api/uploads", params={"name": name or Path(path).name}, content=f.read(), timeout=120)


def make_job(srv, uid, *, text=SRT2B, video=True, max_height=720, orig=0, extra_out=None):
    out = {"sync": "fit", "video": video, "orig_volume": orig, "duck": True, "max_height": max_height}
    out.update(extra_out or {})
    body = {"source": {"type": "upload", "upload_id": uid, "lang": "en", "text": text}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google", "keep_terms": True}, "output": out}
    r = srv.api("POST", "/api/jobs/dub", json=body)
    return r, (srv.wait_job(r.json()["id"], 300) if r.status_code == 200 else None)


def dl_rows(srv, jid, name="dubbed.mp4", t=1.0):
    p = OUT / f"dl_{jid}.mp4"
    p.write_bytes(srv.api("GET", f"/api/jobs/{jid}/file/{name}").content)
    return p, rows(p, t)


HS_JOB = {}
if "C" in ONLY or "D" in ONLY:
    DATA = WORK / "data_hardsub"
    shutil.rmtree(DATA, ignore_errors=True)
    srv = Server(8064, DATA, make_stub_home(WORK / "vox_hardsub"), name="hardsub").start()

if "C" in ONLY:
    try:
        src_rows = rows(FX / "text.mp4")
        render("text.mp4", OUT / "ctrl.mp4", CTRL)
        ctrl = rows(OUT / "ctrl.mp4")
        up = upload(srv, FX / "text.mp4").json()
        # ---- nothing asked: as before (the picture is copied)
        r, j0 = make_job(srv, up["id"])
        jid0 = r.json()["id"]
        c.check(j0["status"] == "done" and "dubbed.mp4" in j0["outputs"], "job without the feature: done, MP4 made", str(j0.get("error")) + str(j0.get("warnings")))
        c.check(j0["meta"]["video"].get("hide") is None and not any("Original subtitles hidden" in l for l in j0["logs"]), "job without the feature: meta.video.hide is null, nothing in the log")
        p0, r0 = dl_rows(srv, jid0)
        c.check(abs(avg(r0, 260, 340) - avg(src_rows, 260, 340)) < 1 and abs(avg(r0, 256, 286) - avg(src_rows, 256, 286)) < 1, "job without the feature: the stripes of the picture are untouched")
        c.check(j0["params"]["output"].get("hide_subs") in (None, False), "job without the feature: nothing is stored for the band")

        # ---- a job that hides the subtitles at once
        r, j1 = make_job(srv, up["id"], extra_out={"hide_subs": True, "hide_effect": "mosaic", "hide_bottom": 3, "hide_height": 16, "hide_strength": 60})
        jid = r.json()["id"]
        HS_JOB["id"] = jid
        c.check(j1["status"] == "done" and "dubbed.mp4" in j1["outputs"], "job with the band: done, MP4 made", str(j1.get("error")) + str(j1.get("warnings")))
        mv = j1["meta"]["video"]
        c.check(mv.get("hide") == {"effect": "mosaic", "bottom": 3.0, "height": 16.0, "strength": 60} and mv["aspect"] == "original" and (mv["out_width"], mv["out_height"]) == (640, 360), "job with the band: meta.video.hide says what was made", str(mv))
        o = j1["params"]["output"]
        c.check((o["hide_subs"], o["hide_effect"], o["hide_bottom"], o["hide_height"], o["hide_strength"]) == (True, "mosaic", 3, 16, 60), "job with the band: the settings are stored in the parameters", str(o))
        c.check(any("Original subtitles hidden: mosaic, band 16 % high, 3 % above the lower edge, strength 60" in l for l in j1["logs"]), "job with the band: the log says what was made", str([l for l in j1["logs"] if "ubtitle" in l]))
        vstep = next(s for s in j1["steps"] if s["key"] == "video")
        c.check(vstep["status"] == "done" and vstep["progress"] == 1.0, "job with the band: the video step is done")
        p1, r1 = dl_rows(srv, jid)
        flat = flat_rows(r1, ctrl, 252, 360)
        c.check(flat and abs(min(flat) - 290) <= 1 and abs(avg(r1, 256, 286) - avg(ctrl, 256, 286)) < 3 and avg(r1, 295, 342) < 0.12 * avg(ctrl, 295, 342), "job with the band: the MP4 the browser downloads has the band at rows 290 .. 349", str((min(flat), max(flat))) if flat else "no flat rows")
        c.check(not list((DATA / "jobs" / jid).glob("*.part*")), "job with the band: no .part file is left")

        # ---- the same job, only the video again
        dub0 = (DATA / "jobs" / jid / "dub.mp3").read_bytes()
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"hide_subs": False})
        j2 = srv.wait_job(jid, 200)
        c.check(rr.status_code == 200 and j2["status"] == "done" and j2["meta"]["video"].get("hide") is None, "POST /video hide_subs=false: the band is gone from meta.video", rr.text[:150] + str(j2.get("error")))
        p2, r2 = dl_rows(srv, jid)
        c.check(abs(avg(r2, 260, 340) - avg(src_rows, 260, 340)) < 1, "POST /video hide_subs=false: the old subtitles (stripes) are back in the MP4")
        o2 = j2["params"]["output"]
        c.check(o2["hide_subs"] is False and o2["hide_effect"] == "mosaic" and o2["hide_strength"] == 60 and o2["max_height"] == 720 and (DATA / "jobs" / jid / "dub.mp3").read_bytes() == dub0,
                "POST /video: the other settings (effect, strength, size) and the Khmer audio stay", str(o2))

        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"hide_subs": True})
        j3 = srv.wait_job(jid, 200)
        c.check(rr.status_code == 200 and j3["meta"]["video"].get("hide") == {"effect": "mosaic", "bottom": 3.0, "height": 16.0, "strength": 60}, "POST /video hide_subs=true only: the effect and the band of the job are used again", str(j3["meta"]["video"]))

        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"hide_subs": True, "hide_effect": "frost", "hide_bottom": 20, "hide_height": 10, "hide_strength": 30})
        j4 = srv.wait_job(jid, 200)
        c.check(rr.status_code == 200 and j4["meta"]["video"]["hide"] == {"effect": "frost", "bottom": 20.0, "height": 10.0, "strength": 30}, "POST /video: a new effect, place and strength", str(j4["meta"]["video"]))
        p4, r4 = dl_rows(srv, jid)
        flat = flat_rows(r4, ctrl, 252, 360)
        c.check(flat and abs(min(flat) - 252) <= 2 and abs(max(flat) - 287) <= 2, "POST /video: the band moved to 20 % .. 30 % above the bottom (rows 252 .. 287)", str((min(flat), max(flat))) if flat else "no flat rows")

        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"hide_subs": "yes", "hide_effect": "zzz", "hide_bottom": 999, "hide_height": -5, "hide_strength": "x"})
        j5 = srv.wait_job(jid, 200)
        o5 = j5["params"]["output"]
        c.check(rr.status_code == 200 and j5["status"] == "done" and (o5["hide_subs"], o5["hide_effect"], o5["hide_bottom"], o5["hide_height"], o5["hide_strength"]) == (True, "blur", 60.0, 4.0, 50)
                and j5["meta"]["video"]["hide"] == {"effect": "blur", "bottom": 60.0, "height": 4.0, "strength": 50}, "POST /video: junk values are cleaned (effect blur, bottom 60, height 4, strength 50)", str(o5))

        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"hide_subs": True, "hide_effect": "blur", "hide_bottom": 3, "hide_height": 16, "hide_strength": 50, "aspect": "9:16", "fit": "bars", "max_height": 720})
        j6 = srv.wait_job(jid, 200)
        mv6 = j6["meta"]["video"]
        c.check(j6["status"] == "done" and (mv6["out_width"], mv6["out_height"]) == (720, 1280) and mv6["aspect"] == "9:16" and mv6["hide"]["effect"] == "blur", "POST /video: the band together with the TikTok 9:16 frame -> 720x1280", str(mv6))
        c.check(any("Original subtitles hidden" in l for l in j6["logs"]) and any("TikTok / Reels / Shorts: 720x1280" in l for l in j6["logs"]), "both are in the log")
        p6, r6 = dl_rows(srv, jid)
        render("text.mp4", OUT / "tt_ctrl_api.mp4", CTRL, fit="bars", max_height=720)
        rc6 = rows(OUT / "tt_ctrl_api.mp4")
        flat = flat_rows(r6, rc6, 0, len(r6), 0.35)
        c.check(flat and len(flat) >= 40 and 740 <= min(flat) and max(flat) <= 850, "9:16 + band in a job: the flattened rows are in the picture, not in the bars", str((min(flat), max(flat), len(flat))) if flat else "none")

        # the log line when only the band is made and the video is not vertical
        rr = srv.api("POST", f"/api/jobs/{jid}/video", json={"aspect": "original", "hide_subs": True, "hide_effect": "dark", "hide_strength": 100})
        j7 = srv.wait_job(jid, 200)
        vs7 = next(s for s in j7["steps"] if s["key"] == "video")
        c.check(j7["status"] == "done" and j7["meta"]["video"]["hide"]["effect"] == "dark" and j7["meta"]["video"]["aspect"] == "original" and vs7["status"] == "done", "POST /video: the band without the 9:16 frame again", str(j7["meta"]["video"]))

        # ---- the progress text says what is going on
        up2 = upload(srv, FX / "text.mp4").json()
        r = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "upload", "upload_id": up2["id"], "lang": "en", "text": SRT2B}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google"},
                                                    "output": {"video": True, "max_height": 720, "hide_subs": True}})
        jidp = r.json()["id"]
        seen_detail = set()
        for _ in range(400):
            jp = srv.api("GET", f"/api/jobs/{jidp}").json()
            seen_detail.add(next(s for s in jp["steps"] if s["key"] == "video").get("detail") or "")
            if jp["status"] in ("done", "error", "cancelled"):
                break
            time.sleep(0.15)
        c.check(any("hiding the original subtitles" in d for d in seen_detail) or jp["status"] == "done", "progress: the video step says 'hiding the original subtitles …' (when it was seen while polling)", str(sorted(seen_detail))[:300])
        c.check(jp["status"] == "done" and jp["meta"]["video"]["hide"]["effect"] == "blur" and jp["meta"]["video"]["hide"]["bottom"] == 3.0, "the defaults of the band (blur, 3 %, 16 %, 50) are used when only hide_subs is sent", str(jp["meta"]["video"]))

        # ---- no picture: a pasted transcript has no video, the request must not break anything
        rt = srv.api("POST", "/api/jobs/dub", json={"source": {"type": "transcript", "text": SRT2, "lang": "en"}, "voice": {"id": "km-KH-SreymomNeural"}, "translate": {"engine": "google"},
                                                     "output": {"video": True, "hide_subs": True}}).json()["id"]
        jt = srv.wait_job(rt, 200)
        c.check(jt["status"] == "done" and any(w["code"] == "NO_VIDEO_SOURCE" for w in jt["warnings"]) and "dubbed.mp4" not in jt["outputs"], "a pasted transcript with hide_subs: done, the usual 'no video source' warning, no MP4", str(jt.get("error")) + str(jt["warnings"]))
        r = srv.api("POST", f"/api/jobs/{rt}/video", json={"hide_subs": True})
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NO_VIDEO_SOURCE", "POST /video with hide_subs for a job without a video -> 400 NO_VIDEO_SOURCE", r.text[:150])
        mp3 = upload(srv, FX / "audio.mp3").json()
        r_, ja = make_job(srv, mp3["id"], video=False)
        r = srv.api("POST", f"/api/jobs/{ja['id']}/video", json={"hide_subs": True})
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NO_PICTURE", "POST /video with hide_subs for an audio file -> 400 NO_PICTURE", r.text[:150])
        r = srv.api("POST", "/api/jobs/nope/video", json={"hide_subs": True})
        c.check(r.status_code == 404, "POST /video with hide_subs for an unknown job -> 404")

        # ---- the job in the list / history still has everything
        full = srv.api("GET", f"/api/jobs/{jid}").json()
        c.check(full["meta"]["video"]["hide"]["effect"] == "dark" and full["params"]["output"]["hide_strength"] == 100, "GET /api/jobs/{id}: meta.video.hide and params.output are there")
    finally:
        pass

# ==================================================================================================================== D. browser
if "D" in ONLY:
    from playwright.sync_api import sync_playwright  # noqa: E402
    errors, posts = [], []
    RAW_KEYS = """() => [...document.querySelectorAll('[data-i18n]')].map((e) => e.textContent.trim()).filter((t) => /^[a-z0-9]+(\\.[a-z0-9]+)+$/i.test(t)).slice(0, 5)"""
    OLD_SETTINGS = {"output": {"format": "video", "aspect": "original", "fit": "blur", "crop_x": 50, "max_height": 1080, "sync": "fit", "orig_volume": 0, "duck": True, "max_speedup": 1.4}}

    def new_page(b, lang="en", theme="dark", w=1440, h=900, settings=None, dock=False):
        ctx = b.new_context(viewport={"width": w, "height": h})
        st = dict(settings or {})
        st.setdefault("ui", {"dock": dock})
        ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}'); if (!localStorage.getItem('kds_settings')) localStorage.setItem('kds_settings', JSON.stringify({json.dumps(st)}));")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
        pg.on("request", lambda r: posts.append((r.url.split("/api/")[-1], r.post_data)) if r.method == "POST" and "/api/jobs/" in r.url else None)
        pg.on("dialog", lambda d: d.accept())
        pg.goto(srv.url + "/", wait_until="networkidle")
        return ctx, pg

    def band(pg, root_sel):
        """Where the band is inside its little picture / frame (shares of the picture), the effect and what the CSS made of it."""
        return pg.evaluate("""(sel) => {
            const m = document.querySelector(sel); const b = m.querySelector('.hs-fx'); const cs = getComputedStyle(b);
            const mr = m.getBoundingClientRect(), br = b.getBoundingClientRect();
            const top = mr.top + m.clientTop, H = m.clientHeight;
            return { fx: b.dataset.fx, bottom: (top + H - br.bottom) / H, height: br.height / H, H, bf: cs.backdropFilter || cs.webkitBackdropFilter || '', bg: cs.backgroundColor, outline: cs.outlineStyle, pe: cs.pointerEvents, z: getComputedStyle(m).zIndex };
        }""", root_sel)

    def blur_px(s):
        m = re.search(r"blur\(([\d.]+)px\)", s or "")
        return float(m.group(1)) if m else None

    def alpha(s):
        m = re.search(r"rgba?\(([^)]*)\)", s or "")
        if not m:
            return None
        parts = [p.strip() for p in m.group(1).split(",")]
        return float(parts[3]) if len(parts) > 3 else 1.0

    def set_range(pg, root_sel, bind, value):
        pg.evaluate("([r, b, v]) => { const e = document.querySelector(`${r} input[data-bind='${b}']`); e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); }", [root_sel, bind, value])
        pg.wait_for_timeout(350)                                   # the settings are saved 200 ms after the last change

    def settings_of(pg):
        return pg.evaluate("() => JSON.parse(localStorage.getItem('kds_settings') || '{}')")

    def active(pg, root, bind):
        return pg.evaluate("([r, b]) => { const e = document.querySelector(`${r} .seg[data-bind='${b}'] button.active`); return e ? e.dataset.value : null; }", [root, bind])

    def open_job(pg, jid):
        pg.goto(srv.url + "/#history")
        pg.wait_for_selector("[data-open]")
        pg.wait_for_timeout(400)
        pg.evaluate("(id) => { [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id).click(); }", jid)
        pg.wait_for_selector("#dub-result .seg-row", timeout=20000)
        pg.wait_for_timeout(700)

    try:
        if not HS_JOB.get("id"):                                    # part C was not run: make the job for the result card now
            up = upload(srv, FX / "text.mp4").json()
            r, j = make_job(srv, up["id"], extra_out={"hide_subs": True, "hide_effect": "mosaic", "hide_bottom": 3, "hide_height": 16, "hide_strength": 60})
            HS_JOB["id"] = r.json()["id"]
        else:                                                       # (C left it with other values: make it the way the browser tests expect)
            srv.api("POST", f"/api/jobs/{HS_JOB['id']}/video", json={"aspect": "original", "hide_subs": True, "hide_effect": "mosaic", "hide_bottom": 3, "hide_height": 16, "hide_strength": 60})
            srv.wait_job(HS_JOB["id"], 200)
        JV = HS_JOB["id"]
        up_ = upload(srv, FX / "text.mp4").json()
        r, jn = make_job(srv, up_["id"])                            # a job whose MP4 keeps the old subtitles
        JN = r.json()["id"]
        upw = upload(srv, FX / "wide.mp4").json()
        r, jw = make_job(srv, upw["id"], extra_out={"hide_subs": True, "hide_effect": "dark", "hide_bottom": 3, "hide_height": 16, "hide_strength": 60})   # 2.37:1
        JW = r.json()["id"]
        with sync_playwright() as pw:
            b = pw.chromium.launch()

            # ================================================================== Step 4
            ctx, pg = new_page(b)
            c.check(not pg.is_visible("#hs-row"), "Step 4: 'audio only' (default) -> no row for the original subtitles")
            pg.click('.seg[data-bind="output.format"] button[data-value="video"]')
            pg.wait_for_timeout(150)
            c.check(pg.is_visible("#hs-row") and pg.is_visible("#hs-row .hs-switch") and not pg.is_visible("#hs-row [data-hs-body]"), "Step 4: MP4 -> the row shows, only the switch (off): nothing else")
            c.check(pg.inner_text("#hs-row .hs-switch b") == "Hide the original subtitles" and "Khmer subtitles are not touched" in pg.inner_text("#hs-row .hs-switch span"), "Step 4: title and explanation (English)")
            c.check(not pg.is_checked("#hs-row input[data-bind='output.hide_subs']"), "Step 4: the switch is off by default")
            pg.click("#hs-row label.switch")
            pg.wait_for_timeout(200)
            c.check(pg.is_checked("#hs-row input[data-bind='output.hide_subs']") and pg.is_visible("#hs-row [data-hs-body]"), "Step 4: the switch opens the controls")
            c.check(active(pg, "#hs-row", "output.hide_effect") == "blur" and [pg.inner_text(f"#hs-row output[data-out='output.hide_{k}']") for k in ("bottom", "height", "strength")] == ["3%", "16%", "50%"], "Step 4: blur, 3 %, 16 %, 50 % are the defaults")
            c.check([pg.inner_text(f"#hs-row .seg[data-bind='output.hide_effect'] button:nth-child({i})") for i in (1, 2, 3, 4)] == ["Blur", "Mosaic", "Dark box", "Frosted"], "Step 4: four effects: Blur, Mosaic, Dark box, Frosted")
            c.check(pg.is_visible("#hs-row [data-hs-mock]") and pg.is_visible("#hs-row .hs-fake") and pg.locator("#hs-row [data-hs-mock] .hs-img").count() == 1, "Step 4: the little picture with a pretend subtitle is there")
            bd = band(pg, "#hs-row [data-hs-mock]")
            c.check(bd["fx"] == "blur" and abs(bd["bottom"] - 0.03) < 0.012 and abs(bd["height"] - 0.16) < 0.012 and bd["outline"] == "dashed" and bd["pe"] == "none", "little picture: the band sits 3 % above the bottom, 16 % high, dashed frame, no mouse events", str(bd))
            c.check(blur_px(bd["bf"]) is not None and abs(blur_px(bd["bf"]) - bd["H"] * 0.027) < 0.5, "little picture: blur = 2.7 % of the picture height (the same share as the video)", str(bd))
            c.check("Blurred" in pg.inner_text("#hs-row [data-hs-hint]") or "blurred" in pg.inner_text("#hs-row [data-hs-hint]"), "Step 4: the hint explains the effect", pg.inner_text("#hs-row [data-hs-hint]"))
            c.check(pg.locator("#hs-row .hs-hints .hint").count() == 3 and "re-encoded" in pg.inner_text("#hs-row .hs-hints"), "Step 4: hints: effect, how to place the band, 'the MP4 takes longer'")

            for fx, hint in (("mosaic", "squares"), ("dark", "dark box"), ("frost", "frosted glass"), ("blur", "blurred")):
                pg.click(f"#hs-row .seg[data-bind='output.hide_effect'] button[data-value='{fx}']")
                pg.wait_for_timeout(120)
                bd = band(pg, "#hs-row [data-hs-mock]")
                ok = bd["fx"] == fx and hint in pg.inner_text("#hs-row [data-hs-hint]").lower() and active(pg, "#hs-row", "output.hide_effect") == fx
                if fx == "dark":
                    ok = ok and abs(alpha(bd["bg"]) - 0.925) < 0.02 and "blur" not in bd["bf"]
                elif fx == "mosaic":
                    ok = ok and "gradient" in pg.evaluate("(s) => getComputedStyle(document.querySelector(s + ' .hs-fx')).backgroundImage", "#hs-row [data-hs-mock]") and blur_px(bd["bf"]) is not None
                else:
                    ok = ok and blur_px(bd["bf"]) is not None
                c.check(ok, f"effect {fx}: the little picture shows it, the hint changes, the button is active", str(bd))

            set_range(pg, "#hs-row", "output.hide_bottom", 10)
            set_range(pg, "#hs-row", "output.hide_height", 30)
            set_range(pg, "#hs-row", "output.hide_strength", 80)
            c.check([pg.inner_text(f"#hs-row output[data-out='output.hide_{k}']") for k in ("bottom", "height", "strength")] == ["10%", "30%", "80%"], "sliders: the numbers beside them follow (10 %, 30 %, 80 %)")
            bd = band(pg, "#hs-row [data-hs-mock]")
            c.check(abs(bd["bottom"] - 0.10) < 0.012 and abs(bd["height"] - 0.30) < 0.012, "sliders: the band in the little picture moves (10 % above the bottom, 30 % high)", str(bd))
            pg.click("#hs-row .seg[data-bind='output.hide_effect'] button[data-value='blur']")
            pg.wait_for_timeout(150)
            bd = band(pg, "#hs-row [data-hs-mock]")
            c.check(abs(blur_px(bd["bf"]) - bd["H"] * (0.004 + 80 * 0.00046)) < 0.5, "sliders: strength 80 -> blur 4.1 % of the height", str(bd))
            st = settings_of(pg)["output"]
            c.check((st["hide_subs"], st["hide_effect"], st["hide_bottom"], st["hide_height"], st["hide_strength"]) == (True, "blur", 10, 30, 80), "the choices are saved in the browser settings", str(st))
            ctx.close()

            # ---- the settings come back after a reload; an older settings object (no hide_* keys) gets the defaults
            ctx, pg = new_page(b, settings={"output": {**OLD_SETTINGS["output"], "hide_subs": True, "hide_effect": "frost", "hide_bottom": 7, "hide_height": 22, "hide_strength": 35}})
            c.check(pg.is_visible("#hs-row [data-hs-body]") and active(pg, "#hs-row", "output.hide_effect") == "frost" and pg.inner_text("#hs-row output[data-out='output.hide_height']") == "22%", "reload: the saved choices are shown again")
            ctx.close()
            ctx, pg = new_page(b, settings=OLD_SETTINGS)
            c.check(pg.is_visible("#hs-row") and not pg.is_checked("#hs-row input[data-bind='output.hide_subs']") and not pg.is_visible("#hs-row [data-hs-body]"), "settings of an older version (no hide_* keys): the row is there, off")
            pg.click("#hs-row label.switch")
            pg.wait_for_timeout(200)
            c.check(active(pg, "#hs-row", "output.hide_effect") == "blur" and pg.inner_text("#hs-row output[data-out='output.hide_bottom']") == "3%" and pg.inner_text("#hs-row output[data-out='output.hide_strength']") == "50%", "settings of an older version: switched on -> the defaults (blur, 3 %, 50 %)")
            ctx.close()

            # ---- what is sent to the server (a pasted transcript: the request is captured, no job is made)
            captured = {}

            def fake_dub(route):
                captured["body"] = json.loads(route.request.post_data)
                route.fulfill(status=200, content_type="application/json", body='{"id":"zzzzzzzzzz"}')

            ctx, pg = new_page(b, settings={"output": {**OLD_SETTINGS["output"], "hide_subs": True, "hide_effect": "dark", "hide_bottom": 12, "hide_height": 25, "hide_strength": 90}})
            pg.route("**/api/jobs/dub", fake_dub)
            pg.click('#src-tabs button[data-tab="transcript"]')
            pg.fill("#tr-text", SRT2)
            pg.click("#btn-generate")
            pg.wait_for_timeout(600)
            ob = (captured.get("body") or {}).get("output") or {}
            c.check((ob.get("hide_subs"), ob.get("hide_effect"), ob.get("hide_bottom"), ob.get("hide_height"), ob.get("hide_strength")) == (True, "dark", 12, 25, 90) and ob.get("video") is True, "Generate: the request carries hide_subs / effect / bottom / height / strength", str(ob))
            ctx.close()
            ctx, pg = new_page(b)
            captured.clear()
            pg.route("**/api/jobs/dub", fake_dub)
            pg.click('#src-tabs button[data-tab="transcript"]')
            pg.fill("#tr-text", SRT2)
            pg.click("#btn-generate")
            pg.wait_for_timeout(600)
            ob = (captured.get("body") or {}).get("output") or {}
            c.check(ob.get("hide_subs") is False and ob.get("hide_effect") == "blur" and (ob.get("hide_bottom"), ob.get("hide_height"), ob.get("hide_strength")) == (3, 16, 50), "Generate with the defaults: hide_subs false (nothing changes for people who ignore the row)", str(ob))
            ctx.close()

            # ---- Khmer, no raw keys, a narrow screen
            ctx, pg = new_page(b, lang="km", settings={"output": {**OLD_SETTINGS["output"], "hide_subs": True}}, w=360, h=800)
            c.check(pg.inner_text("#hs-row .hs-switch b") == "បិទបាំង Subtitle ដើម" and pg.inner_text("#hs-row .seg[data-bind='output.hide_effect'] button:nth-child(3)") == "ប្រអប់ងងឹត", "Khmer: title and effect names")
            c.check(pg.evaluate(RAW_KEYS) == [], "Khmer: no raw translation keys on the screen", str(pg.evaluate(RAW_KEYS)))
            c.check(pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), "360 px wide: no sideways scrolling with the controls open", str(pg.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")))
            c.check(pg.evaluate("() => { const m = document.querySelector('#hs-row [data-hs-mock]').getBoundingClientRect(); return m.width > 100 && m.right <= window.innerWidth; }"), "360 px wide: the little picture fits on the screen")
            pg.click("#lang-switch button[data-lang='en']")
            pg.wait_for_timeout(200)
            c.check(pg.inner_text("#hs-row .hs-switch b") == "Hide the original subtitles" and "blurred" in pg.inner_text("#hs-row [data-hs-hint]").lower(), "back to English: the texts change at once")
            ctx.close()

            # ================================================================== the result card
            ctx, pg = new_page(b, w=1440, h=900, dock=True)
            open_job(pg, JV)
            summ = pg.inner_text("#reframe-box > summary")
            c.check("Video shape (TikTok) · original subtitles" in summ and "original subtitles hidden (Mosaic)" in summ, "result: the panel title mentions the subtitles, the summary says what the MP4 has", summ)
            stats = pg.inner_text("#dub-result .player-box .stats")
            c.check("Original subtitles Mosaic" in stats.replace("\n", " "), "result: the numbers line says 'Original subtitles Mosaic'", stats)
            pg.click("#reframe-box > summary")
            pg.wait_for_timeout(200)
            c.check(pg.is_checked("#reframe-box input[data-bind='remake.hide_subs']") and active(pg, "#reframe-box", "remake.hide_effect") == "mosaic" and pg.is_visible("#reframe-box [data-hs-body]")
                    and [pg.inner_text(f"#reframe-box output[data-out='remake.hide_{k}']") for k in ("bottom", "height", "strength")] == ["3%", "16%", "60%"], "result panel: starts from what the MP4 has (on, Mosaic, 3 %, 16 %, 60 %)")
            mock_src = pg.get_attribute("#reframe-box [data-hs-mock] .hs-img", "src") or ""
            c.check("/api/jobs/" in mock_src and mock_src.endswith("/thumb"), "result panel: the little picture shows the picture of this job", mock_src[:80])

            # the same band over the real video in the Sync Preview
            pg.click("#btn-sync")
            pg.wait_for_selector("#sync-panel #up-player", timeout=20000)
            pg.wait_for_timeout(500)
            live = "#sync-panel [data-hs-live]"
            c.check(pg.locator(live).count() == 1 and pg.is_visible(live + " .hs-fx"), "Sync Preview: the band is drawn over the real video")
            bd = band(pg, live)
            c.check(bd["fx"] == "mosaic" and abs(bd["bottom"] - 0.03) < 0.012 and abs(bd["height"] - 0.16) < 0.012 and bd["pe"] == "none", "Sync Preview: same place (3 % / 16 %), same effect, the mouse goes through it", str(bd))
            z = pg.evaluate("() => [getComputedStyle(document.querySelector('#sync-panel [data-hs-live]')).zIndex, getComputedStyle(document.querySelector('#sync-panel .sub-overlay')).zIndex]")
            c.check(int(z[0]) < int(z[1]), "Sync Preview: the Khmer / English captions are drawn ABOVE the band", str(z))
            frame_box = pg.evaluate("() => { const f = document.querySelector('#sync-panel .yt-frame'), v = document.querySelector('#sync-panel #up-player').getBoundingClientRect(), l = document.querySelector('#sync-panel [data-hs-live]').getBoundingClientRect(); return [Math.abs(f.clientWidth - l.width) < 1, Math.abs(f.clientHeight - l.height) < 1, Math.abs(v.width - l.width) < 1, Math.abs(v.height - l.height) < 1, Math.abs(v.top - l.top) < 1]; }")
            c.check(frame_box == [True] * 5, "Sync Preview: the layer covers exactly the video (the inside of the frame, the same box as the <video>)", str(frame_box))
            set_range(pg, "#reframe-box", "remake.hide_bottom", 12)
            set_range(pg, "#reframe-box", "remake.hide_height", 24)
            bd = band(pg, live)
            c.check(abs(bd["bottom"] - 0.12) < 0.012 and abs(bd["height"] - 0.24) < 0.012, "Sync Preview: moving the sliders of the panel moves the band over the video at once", str(bd))
            pg.click("#reframe-box .seg[data-bind='remake.hide_effect'] button[data-value='dark']")
            pg.wait_for_timeout(150)
            bd = band(pg, live)
            c.check(bd["fx"] == "dark" and alpha(bd["bg"]) is not None and abs(alpha(bd["bg"]) - min(1, 0.55 + 60 * 0.0075)) < 0.02, "Sync Preview: another effect shows at once (dark box, strength 60 = fully black)", str(bd))
            pg.click("#reframe-box .hs-switch label.switch")
            pg.wait_for_timeout(200)
            c.check(not pg.is_visible(live + " .hs-fx") and not pg.is_visible("#reframe-box [data-hs-body]"), "Sync Preview: switching the band off hides it (and the controls)")
            pg.click("#reframe-box .hs-switch label.switch")
            pg.wait_for_timeout(200)
            c.check(pg.is_visible(live + " .hs-fx"), "Sync Preview: and on again")
            # Step 4 keeps its own settings
            pg.click("#reframe-box .hs-switch label.switch")
            pg.wait_for_timeout(200)

            # make the video again WITHOUT the band (the real thing)
            n_posts = len(posts)
            pg.click("#btn-reframe")
            pg.wait_for_timeout(800)
            sent = [json.loads(p[1]) for p in posts[n_posts:] if p[0].endswith("/video") and p[1]]
            c.check(sent and sent[-1].get("hide_subs") is False and sent[-1].get("hide_effect") == "dark" and (sent[-1].get("hide_bottom"), sent[-1].get("hide_height"), sent[-1].get("hide_strength")) == (12, 24, 60) and sent[-1].get("aspect") == "original",
                    "make the video again: the request carries hide_subs false and the rest of the panel", str(sent[-1:] if sent else posts[-2:]))
            j_after = srv.wait_job(JV, 200)
            c.check(j_after["status"] == "done" and j_after["meta"]["video"].get("hide") is None, "make the video again: the new MP4 has no band", str(j_after["meta"]["video"]))
            ctx.close()

            # a job whose MP4 keeps the old subtitles: the panel starts 'off'; switching on and making the video again sends the band
            ctx, pg = new_page(b, w=1440, h=900, dock=True)
            open_job(pg, JN)
            c.check("hidden" not in pg.inner_text("#reframe-box > summary") and "original subtitles hidden" not in pg.inner_text("#reframe-box > summary"), "result (old subtitles visible): the summary does not mention a band", pg.inner_text("#reframe-box > summary"))
            c.check("Original subtitles" not in pg.inner_text("#dub-result .player-box .stats"), "result (old subtitles visible): the numbers line has no 'Original subtitles'")
            pg.click("#reframe-box > summary")
            pg.wait_for_timeout(200)
            c.check(not pg.is_checked("#reframe-box input[data-bind='remake.hide_subs']") and not pg.is_visible("#reframe-box [data-hs-body]"), "result (old subtitles visible): the panel starts off")
            pg.click("#reframe-box .hs-switch label.switch")
            pg.wait_for_timeout(150)
            pg.click("#reframe-box .seg[data-bind='remake.hide_effect'] button[data-value='frost']")
            pg.wait_for_timeout(100)
            n_posts = len(posts)
            pg.click("#btn-reframe")
            pg.wait_for_timeout(800)
            sent = [json.loads(p[1]) for p in posts[n_posts:] if p[0].endswith("/video") and p[1]]
            c.check(sent and sent[-1].get("hide_subs") is True and sent[-1].get("hide_effect") == "frost", "make the video again with the band: the request carries hide_subs true + frost", str(sent[-1:] if sent else "no request"))
            j_n = srv.wait_job(JN, 200)
            c.check(j_n["status"] == "done" and (j_n["meta"]["video"].get("hide") or {}).get("effect") == "frost", "make the video again with the band: the new MP4 has the band (frost)", str(j_n["meta"]["video"]))
            pg.wait_for_selector("#dub-result .seg-row", timeout=60000)
            pg.wait_for_timeout(800)
            c.check("original subtitles hidden (Frosted)" in pg.inner_text("#reframe-box > summary") and "Original subtitles Frosted" in pg.inner_text("#dub-result .player-box .stats").replace("\n", " "), "result: after the new MP4 the summary and the numbers line show the band (Frosted)", pg.inner_text("#reframe-box > summary"))
            ctx.close()

            # a picture wider than the 16:9 player (2.37:1): the layer only covers the picture, so the band is where ffmpeg puts it
            ctx, pg = new_page(b, w=1440, h=1000, dock=True)
            open_job(pg, JW)
            pg.click("#btn-sync")
            pg.wait_for_selector("#sync-panel #up-player", timeout=20000)
            pg.wait_for_timeout(500)
            geo = pg.evaluate("""() => {
                const f = document.querySelector('#sync-panel .yt-frame'), l = document.querySelector('#sync-panel [data-hs-live]'), fr = f.getBoundingClientRect(), lr = l.getBoundingClientRect();
                return { keep: lr.height / f.clientHeight, top: (lr.top - fr.top - f.clientTop) / f.clientHeight, w: Math.abs(lr.width - f.clientWidth) < 1 };
            }""")
            want = (16 / 9) / (640 / 270)
            c.check(geo["w"] and abs(geo["keep"] - want) < 0.02 and abs(geo["top"] - (1 - want) / 2) < 0.02, "Sync Preview of a 2.37:1 picture: the layer covers only the picture (not the black bars above and below)", str(geo) + f" want {want:.3f}")
            bd = band(pg, "#sync-panel [data-hs-live]")
            c.check(bd["fx"] == "dark" and abs(bd["bottom"] - 0.03) < 0.012 and abs(bd["height"] - 0.16) < 0.012, "Sync Preview of a 2.37:1 picture: the band is 3 % / 16 % of the PICTURE", str(bd))
            ctx.close()
            ctx, pg = new_page(b, w=1440, h=1000, dock=True)
            open_job(pg, JN)
            pg.click("#btn-sync")
            pg.wait_for_selector("#sync-panel #up-player", timeout=20000)
            pg.wait_for_timeout(400)
            keep = pg.evaluate("() => { const f = document.querySelector('#sync-panel .yt-frame'), l = document.querySelector('#sync-panel [data-hs-live]'); return l.getBoundingClientRect().height / f.clientHeight; }")
            c.check(abs(keep - 1.0) < 0.01, "Sync Preview of a 16:9 picture: the layer covers the whole frame", str(keep))
            ctx.close()

            c.check(not errors, "no JavaScript errors in the whole run", "; ".join(errors[:4]))
            b.close()
    finally:
        pass

if "C" in ONLY or "D" in ONLY:
    srv.stop()
sys.exit(c.done())
