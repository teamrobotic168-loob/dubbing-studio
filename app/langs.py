"""Source languages (English, Chinese, Korean → Khmer).

Everything that differs between the languages lives in this one file:

* names and codes (UI, Google Translate, Whisper, YouTube caption tracks),
* script detection (Hangul → Korean, Han → Chinese, Latin → English),
* how long one dubbing segment may be, and how fast people speak (needed for text without timestamps),
* which YouTube caption track belongs to which language.

The internal segment field is still called ``en`` for historic reasons; it simply means "source text".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

AUTO = "auto"
SUPPORTED: Tuple[str, ...] = ("en", "zh", "ko")


@dataclass(frozen=True)
class LangInfo:
    code: str
    name: str          # English name
    native: str        # name in its own script (UI buttons)
    short: str         # label used inside toggles
    google: str        # Google Translate source code
    whisper: str       # faster-whisper language code
    cps: float         # normal speaking speed in characters per second (text without timing)
    max_chars: int     # longest dubbing segment (characters)
    min_chars: int     # shorter fragments are glued to a neighbour
    max_sentence: int  # sentence chunk size when a text has no punctuation at all


LANGS: Dict[str, LangInfo] = {
    "en": LangInfo("en", "English", "English", "EN", "en", "en", 14.0, 230, 14, 230),
    "zh": LangInfo("zh", "Chinese", "中文", "中文", "zh-CN", "zh", 4.6, 80, 5, 90),
    "ko": LangInfo("ko", "Korean", "한국어", "한국어", "ko", "ko", 7.5, 125, 8, 140),
}

_ALIASES = {
    "en": "en", "eng": "en", "english": "en",
    "zh": "zh", "cmn": "zh", "chi": "zh", "zho": "zh", "chinese": "zh", "mandarin": "zh", "yue": "zh",
    "ko": "ko", "kor": "ko", "korean": "ko", "kr": "ko",
}


def normalize_lang(value: Optional[str], default: str = AUTO) -> str:
    """'auto' | 'en' | 'zh' | 'ko'. Unknown / empty values mean `default` (auto-detect)."""
    v = str(value or "").strip().lower().replace("_", "-")
    if not v or v == AUTO:
        return default
    return _ALIASES.get(v) or _ALIASES.get(v.split("-")[0]) or default


def info(lang: Optional[str]) -> LangInfo:
    return LANGS.get(normalize_lang(lang, "en"), LANGS["en"])


# --------------------------------------------------------------------------- #
# script detection
# --------------------------------------------------------------------------- #
HANGUL = "\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3\ua960-\ua97f\ud7b0-\ud7ff"
HAN = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
KANA = "\u3040-\u30ff\u31f0-\u31ff"
_HANGUL_RE = re.compile(f"[{HANGUL}]")
_HAN_RE = re.compile(f"[{HAN}]")
_KANA_RE = re.compile(f"[{KANA}]")
_LATIN_RE = re.compile(r"[A-Za-z\u00c0-\u024f]")


def script_counts(text: str) -> Dict[str, int]:
    s = (text or "")[:40000]
    return {
        "hangul": len(_HANGUL_RE.findall(s)),
        "han": len(_HAN_RE.findall(s)),
        "kana": len(_KANA_RE.findall(s)),
        "latin": len(_LATIN_RE.findall(s)),
    }


_OTHER_NAMES = {"ja": "Japanese"}


def lang_name(code: str) -> str:
    return LANGS[code].name if code in LANGS else _OTHER_NAMES.get(code, code)


def detect_lang(text: str) -> Optional[str]:
    """Language of a text from its writing system, or None when there are no letters at all.
    Returns 'en' | 'zh' | 'ko' – or 'ja' (kana found), which is NOT supported and must be refused by the caller.

    A Chinese or Korean sentence is full of English product names ("我们用 Docker 和 Kubernetes 部署"), and an
    English word has many letters but a Chinese character carries a whole syllable – so a small share of
    CJK / Hangul characters is already enough to call the text Chinese / Korean.
    """
    c = script_counts(text)
    cjk = c["hangul"] + c["han"] + c["kana"]
    total = cjk + c["latin"]
    if total == 0:
        return None
    if cjk >= 3 and cjk / total >= 0.08:
        if c["hangul"] > c["han"] + c["kana"]:
            return "ko"
        if c["kana"] >= 3 and c["kana"] >= 0.2 * (c["han"] + c["kana"]):
            return "ja"          # Japanese sentences always contain hiragana / katakana; Chinese ones never do
        return "zh"
    return "en" if c["latin"] else None


def resolve_lang(selected: Optional[str], text: str, hint: Optional[str] = None) -> Tuple[str, str]:
    """Final language of a transcript → (code, note). The code is 'en' | 'zh' | 'ko' (or 'ja' = refuse, see detect_lang).

    The script of the text wins over the user's choice (English selected but Chinese text arrived → Chinese),
    because translating text with the wrong source language gives nonsense. `note` is non-empty when the
    selection was overridden.
    """
    sel = normalize_lang(selected)
    det = detect_lang(text)
    hint = normalize_lang(hint)
    if det is None:
        lang = sel if sel != AUTO else (hint if hint != AUTO else "en")
        return lang, ""
    note = ""
    if sel != AUTO and sel != det:
        note = f"You selected {lang_name(sel)}, but the text is written in {lang_name(det)} – using {lang_name(det)}."
    return det, note


# --------------------------------------------------------------------------- #
# YouTube caption tracks
# --------------------------------------------------------------------------- #
def base_lang(code: Optional[str]) -> Optional[str]:
    """YouTube track code ('ko', 'zh-Hans', 'en-GB', 'ko-orig', 'a.en') → 'ko' | 'zh' | 'en' | None."""
    c = str(code or "").strip().lower().replace("_", "-")
    if c.startswith("a."):                      # old style auto-generated marker
        c = c[2:]
    first = c.split("-")[0]
    got = _ALIASES.get(first)
    return got if got in SUPPORTED else None


def _zh_rank(code: str) -> int:
    c = (code or "").lower()
    if c in ("zh", "zh-hans", "zh-cn", "zh-sg"):
        return 0
    if c.startswith("zh-hans"):
        return 1
    return 2


def track_sort_key(code: str, generated: bool) -> Tuple[int, int]:
    """Manual tracks first; for Chinese Simplified before Traditional (both translate equally well)."""
    return (1 if generated else 0, _zh_rank(code) if base_lang(code) == "zh" else 0)


def title_lang(title: Optional[str]) -> Optional[str]:
    """Tie-breaker: the language of a video title – but only when it is not plain English."""
    d = detect_lang(title or "")
    return d if d in ("zh", "ko") else None


def pick_caption_lang(entries: Sequence[Tuple[str, bool]], requested: Optional[str], title: str = "") -> Optional[str]:
    """Which language to use from the caption tracks a video offers.

    `entries` = [(track code, is_auto_generated), …]. Returns 'en' | 'zh' | 'ko' or None.
    With an explicit language the answer is that language when a track exists. With 'auto':

    1. automatic captions are always spoken in the language of the video → that language wins,
    2. otherwise (manual subtitles only) a title written in Chinese / Korean decides,
    3. otherwise English, then Chinese, then Korean.
    """
    req = normalize_lang(requested)
    have: Dict[str, List[bool]] = {}
    for code, gen in entries:
        lg = base_lang(code)
        if lg:
            have.setdefault(lg, []).append(bool(gen))
    if req != AUTO:
        return req if req in have else None
    if not have:
        return None
    generated = [lg for lg in SUPPORTED if any(have.get(lg, []))]
    if len(generated) == 1:
        return generated[0]
    if len(generated) > 1:
        tl = title_lang(title)
        return tl if tl in generated else generated[0]
    tl = title_lang(title)
    if tl in have:
        return tl
    for lg in SUPPORTED:
        if lg in have:
            return lg
    return None


def caption_summary(entries: Sequence[Tuple[str, bool]], title: str = "") -> Dict[str, object]:
    """For the video card: {"langs": {"en": "manual"|"auto"|None, …}, "detected": 'ko'|None}."""
    langs: Dict[str, Optional[str]] = {lg: None for lg in SUPPORTED}
    for code, gen in entries:
        lg = base_lang(code)
        if not lg:
            continue
        kind = "auto" if gen else "manual"
        if langs[lg] is None or kind == "manual":
            langs[lg] = kind
    return {"langs": langs, "detected": pick_caption_lang(entries, AUTO, title)}


def lang_list_text(entries: Iterable[Tuple[str, bool]]) -> str:
    seen = []
    for code, gen in entries:
        s = f"{code}{' (auto)' if gen else ''}"
        if s not in seen:
            seen.append(s)
    return ", ".join(seen[:12]) or "none"
