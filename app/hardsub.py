"""Hide the ORIGINAL subtitles of the video - the ones that are burned into the picture ("hard subtitles") - in the MP4.

A band across the whole picture (by default the lowest 16 %, starting 3 % above the lower edge) is made unreadable in one of four ways ("effect"):

* ``blur``    - the band is blurred (Gaussian) until the letters cannot be read
* ``mosaic``  - the band is turned into big squares (pixelated)
* ``dark``    - a dark box lies over the band (the stronger, the less shines through)
* ``frost``   - blurred and a little darker, like frosted glass

Only the original picture changes.  The Khmer audio, the Khmer / English subtitle tracks and everything outside the band stay as they are.
The band is measured on the ORIGINAL picture (percent of its height), so it follows the picture when the video is also put into a vertical
9:16 frame (frame.py): the band is made first, the 9:16 frame second.

This module is plain text / number logic: it never starts ffmpeg, so every decision can be tested without a video.
``audio.mux_video`` runs the ffmpeg filter graph that ``plan()`` builds (a picture with a band always has to be re-encoded).
The dashboard shows the same effect with CSS (static/js/app.js, ``hsBlurSigma`` / ``hsDark``): keep the strength formulas below in sync with it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .frame import display_size

EFFECTS = ("blur", "mosaic", "dark", "frost")
EFFECT_NAMES = {"blur": "blur", "mosaic": "mosaic", "dark": "dark box", "frost": "frosted glass"}
DEFAULT_EFFECT = "blur"
DEFAULT_BOTTOM = 3.0                   # % of the picture height between the lower edge and the band
DEFAULT_HEIGHT = 16.0                  # % of the picture height the band covers
DEFAULT_STRENGTH = 50                  # 10 (light) .. 100 (very strong)
BOTTOM_MAX = 60.0
HEIGHT_MIN, HEIGHT_MAX = 4.0, 50.0
STRENGTH_MIN, STRENGTH_MAX = 10, 100
OUT_LABEL = "kcov"                     # the picture after the band; labels of this module start with "kc" (frame.py: "kbg" / "kfg" ..., audio: "o" / "m" ...)
FALLBACK_HEIGHT = 1080                 # when the size of the picture is not known (the sizes of the effects depend on it)


# ------------------------------------------------------------------------------------------------------------------ cleaning
def clean_on(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == v and v != 0
    return False


def clean_effect(v) -> str:
    v = str(v or "").strip().lower()
    return v if v in EFFECTS else DEFAULT_EFFECT


def _float(v, default: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def clean_bottom(v) -> float:
    return round(max(0.0, min(BOTTOM_MAX, _float(v, DEFAULT_BOTTOM))), 1)


def clean_height(v, bottom=None) -> float:
    """The height of the band; with `bottom` given the band is also kept inside the picture (bottom + height <= 100)."""
    h = round(max(HEIGHT_MIN, min(HEIGHT_MAX, _float(v, DEFAULT_HEIGHT))), 1)
    if bottom is not None:
        h = min(h, round(100.0 - clean_bottom(bottom), 1))
    return h


def clean_strength(v) -> int:
    return int(round(max(STRENGTH_MIN, min(STRENGTH_MAX, _float(v, DEFAULT_STRENGTH)))))


# ------------------------------------------------------------------------------------------------------------------ sizes
def sigma(strength, picture_height) -> float:
    """Blur radius (a Gaussian sigma, in pixels) of 'blur' and 'frost': a share of the picture height, so a 360p and a 1080p picture look alike."""
    return round(max(2.0, picture_height * (0.004 + clean_strength(strength) * 0.00046)), 1)


def block(strength, picture_height) -> int:
    """Side of a 'mosaic' square in pixels (always even)."""
    b = int(round(picture_height * (0.008 + clean_strength(strength) * 0.00044)))
    return max(6, b - b % 2)


def opacity(strength) -> float:
    """How black the 'dark' box is: 0.625 (strength 10) ... 0.925 (50) ... 1.0 (60 and more)."""
    return round(min(1.0, 0.55 + clean_strength(strength) * 0.0075), 3)


def _num(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s or "0"


# ------------------------------------------------------------------------------------------------------------------ ffmpeg graph
def build_graph(effect, bottom, height, strength, picture_height, src: str = "0:v:0", out: str = OUT_LABEL) -> str:
    """The ffmpeg filter graph (text for -filter_complex) that hides the band in stream `src` and calls the result [out].

    The place of the band is an expression of the real input size (ih), so it is right for any picture and every row number is even
    (the chroma of yuv420 has half the rows).  Only the strength of the effect uses a number measured on the picture (`picture_height`).
    """
    effect = clean_effect(effect)
    b = clean_bottom(bottom)
    h = clean_height(height, b)
    s = clean_strength(strength)
    ph = int(picture_height) if picture_height and picture_height > 0 else FALLBACK_HEIGHT
    top_f, bot_f = _num(1 - (b + h) / 100.0), _num(1 - b / 100.0)
    ty = f"trunc(ih*{top_f}/2)*2"                  # first row of the band
    by = f"trunc(ih*{bot_f}/2)*2"                  # first row below the band
    if effect == "dark":
        return f"[{src}]drawbox=x=0:y='{ty}':w=iw:h='{by}-{ty}':color=black@{_num(opacity(s))}:t=fill[{out}]"
    if effect == "mosaic":
        k = block(s, ph)
        # down to one pixel per square (area = average), up again with hard edges; ceil: the squares may stick out a little, the overlay cuts them off
        fx = f"scale=w='ceil(iw/{k})':h='ceil(ih/{k})':flags=area,scale=w='iw*{k}':h='ih*{k}':flags=neighbor"
    elif effect == "frost":
        fx = f"gblur=sigma={_num(sigma(s, ph))}:steps=2,eq=brightness=-0.15:saturation=0.9"
    else:
        fx = f"gblur=sigma={_num(sigma(s, ph))}:steps=2"
    return (f"[{src}]split=2[kca][kcb];"
            f"[kcb]crop=w=iw:h='{by}-{ty}':x=0:y='{ty}',{fx}[kcc];"
            f"[kca][kcc]overlay=x=0:y='trunc(H*{top_f}/2)*2':format=yuv420[{out}]")


@dataclass
class HardsubPlan:
    effect: str
    bottom: float
    height: float
    strength: int
    picture_height: int
    graph: str                       # for the stream "0:v:0"; graph_from() makes it for another label

    out: str = OUT_LABEL

    def graph_from(self, src: str) -> str:
        return build_graph(self.effect, self.bottom, self.height, self.strength, self.picture_height, src=src, out=self.out)

    @property
    def label(self) -> str:
        return (f"{EFFECT_NAMES[self.effect]}, band {self.height:g} % high, {self.bottom:g} % above the lower edge, strength {self.strength}")

    def as_info(self) -> dict:
        """What is stored in job.meta['video']['hide'] (and shown by the dashboard)."""
        return {"effect": self.effect, "bottom": self.bottom, "height": self.height, "strength": self.strength}


def plan(info: dict, on, effect=DEFAULT_EFFECT, bottom=DEFAULT_BOTTOM, height=DEFAULT_HEIGHT, strength=DEFAULT_STRENGTH) -> Optional[HardsubPlan]:
    """What to do with the picture of `info` (see audio.probe_media).  None = the original subtitles stay (the user did not ask for this)."""
    if not clean_on(on):
        return None
    ph = display_size(info or {})[1] or FALLBACK_HEIGHT
    e, b, s = clean_effect(effect), clean_bottom(bottom), clean_strength(strength)
    h = clean_height(height, b)
    return HardsubPlan(e, b, h, s, int(ph), build_graph(e, b, h, s, ph))
