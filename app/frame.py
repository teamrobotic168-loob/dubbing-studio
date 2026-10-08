"""Vertical video for TikTok / Instagram Reels / YouTube Shorts (9:16).

A horizontal (or any other) picture is put into a 9:16 frame in one of three ways ("fit"):

* ``blur``  - the whole picture in the middle; a blurred, enlarged copy of it fills the rest (the look most TikTok videos use)
* ``crop``  - the picture is enlarged until it fills the frame and the sides are cut off (``crop_x`` says which part is kept)
* ``bars``  - the whole picture in the middle, on black

This module is plain text / number logic: it never starts ffmpeg, so every decision can be tested without a video.
``audio.mux_video`` runs the ffmpeg filter graph that ``plan()`` builds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

ASPECTS = ("original", "9:16")
FITS = ("blur", "crop", "bars")
DEFAULT_ASPECT = "original"
DEFAULT_FIT = "blur"
DEFAULT_CROP_X = 50.0          # 0 = the left edge of the picture is kept, 50 = the middle, 100 = the right edge
TARGET = 9 / 16                # width / height of the frame
TOLERANCE = 0.015              # a picture within 1.5 % of 9:16 is "already vertical" (1080x1920, 1080x1919, 720x1280 ...)

# What TikTok says about uploads (checked Oct 2026; the phone app is stricter than the website).
TIKTOK_MAX_MINUTES = 10        # most accounts (a few have 60)
TIKTOK_APP_MAX_MB = 287        # iPhone app (Android: about 72 MB)


def clean_aspect(v) -> str:
    return "9:16" if str(v or "").strip().lower() in ("9:16", "9x16", "tiktok", "vertical") else DEFAULT_ASPECT


def clean_fit(v) -> str:
    v = str(v or "").strip().lower()
    return v if v in FITS else DEFAULT_FIT


def clean_crop_x(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return DEFAULT_CROP_X
    if f != f:                                   # NaN
        return DEFAULT_CROP_X
    return round(max(0.0, min(100.0, f)), 1)


def canvas(short_side) -> Tuple[int, int]:
    """(width, height) of the 9:16 frame whose SHORTER side is `short_side`: 1080 -> 1080x1920, 720 -> 720x1280, 480 -> 480x854."""
    try:
        s = int(short_side)
    except (TypeError, ValueError):
        s = 1080
    s = max(240, min(2160, s))
    s -= s % 2
    h = int(round(s * 16 / 9))
    h += h % 2
    return s, h


def display_size(info: dict) -> Tuple[Optional[int], Optional[int]]:
    """The size a player shows: the stored size turned by the rotation flag of phone videos and widened by a non-square pixel shape."""
    w, h = info.get("width"), info.get("height")
    if not (w and h):
        return None, None
    try:
        rot = abs(float(info.get("rotation") or 0.0)) % 180.0
    except (TypeError, ValueError):
        rot = 0.0
    if 45.0 < rot < 135.0:
        w, h = h, w
    try:
        sar = float(info.get("sar") or 1.0)
    except (TypeError, ValueError):
        sar = 1.0
    if sar > 0 and abs(sar - 1.0) > 0.005:
        w = int(round(w * sar))
    return int(w), int(h)


def is_vertical(dw: Optional[int], dh: Optional[int]) -> bool:
    return bool(dw and dh and abs(dw / dh - TARGET) <= TARGET * TOLERANCE)


def _num(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s or "0"


def build_graph(fit: str, cw: int, ch: int, crop_x: float = DEFAULT_CROP_X, sar_fix: bool = False,
                src: str = "0:v:0", out: str = "vout") -> str:
    """The ffmpeg filter graph (text for -filter_complex) that turns stream `src` into a cw x ch picture named [out].

    Every size is an expression of the real input size (iw / ih), so it is right for any shape of picture and
    every number it produces is even (H.264 needs that).  Labels start with "k" so they never clash with the audio graph.
    """
    head = f"[{src}]"
    pre = "scale=w='trunc(iw*sar/2)*2':h=ih,setsar=1," if sar_fix else ""       # non-square pixels -> the shape people see
    tail = "setsar=1,format=yuv420p"
    inside = f"scale=w='trunc(min({cw},{ch}*a)/2)*2':h='trunc(min({ch},{cw}/a)/2)*2':flags=bicubic"   # as big as fits in the frame
    fit = clean_fit(fit)
    if fit == "crop":
        px = _num(clean_crop_x(crop_x) / 100.0)
        return (f"{head}{pre}crop=w='trunc(min(iw,ih*{cw}/{ch})/2)*2':h='trunc(min(ih,iw*{ch}/{cw})/2)*2'"
                f":x='(iw-ow)*{px}':y='(ih-oh)/2',scale={cw}:{ch}:flags=bicubic,{tail}[{out}]")
    if fit == "bars":
        return f"{head}{pre}{inside},pad={cw}:{ch}:x='(ow-iw)/2':y='(oh-ih)/2':color=black,{tail}[{out}]"
    # blur: the background is made on a tiny copy (1/8 size) - cheap - and enlarged again, which also makes it smooth
    sw, sh = (cw // 16) * 2, (ch // 16) * 2
    return (f"{head}{pre}split=2[kbg][kfg];"
            f"[kbg]scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=bilinear,crop={sw}:{sh},gblur=sigma=3:steps=2,"
            f"eq=brightness=-0.06:saturation=1.1,scale={cw}:{ch}:flags=bilinear[kbl];"
            f"[kfg]{inside}[kfs];"
            f"[kbl][kfs]overlay=x='(W-w)/2':y='(H-h)/2':format=yuv420,{tail}[{out}]")


@dataclass
class FramePlan:
    width: int
    height: int
    fit: str
    crop_x: float
    graph: str
    sar_fix: bool = False

    def graph_from(self, src: str) -> str:
        """The same graph for another input label - e.g. the picture after hardsub.py has hidden the old subtitles."""
        return build_graph(self.fit, self.width, self.height, self.crop_x, sar_fix=self.sar_fix, src=src)

    @property
    def label(self) -> str:
        return f"{self.width}x{self.height} (9:16, {dict(blur='blurred background', crop='cropped to fill', bars='black bars')[self.fit]})"


def plan(info: dict, aspect, fit=DEFAULT_FIT, crop_x=DEFAULT_CROP_X, max_height=1080) -> Optional[FramePlan]:
    """What to do with the picture of `info` (see audio.probe_media).  None = leave the shape alone (the user wants the original shape,
    or the picture already is 9:16 - the normal size limit of the MP4 still applies then)."""
    if clean_aspect(aspect) != "9:16":
        return None
    if is_vertical(*display_size(info)):
        return None
    cw, ch = canvas(max_height)
    fit, px = clean_fit(fit), clean_crop_x(crop_x)
    try:
        sar = float(info.get("sar") or 1.0)
    except (TypeError, ValueError):
        sar = 1.0
    fix = sar > 0 and abs(sar - 1.0) > 0.005
    return FramePlan(cw, ch, fit, px, build_graph(fit, cw, ch, px, sar_fix=fix), sar_fix=fix)
