"""Text helpers: script detection, Khmer/English run splitting, sentence splitting (Khmer, English, Chinese, Korean)."""
from __future__ import annotations

import re
from typing import List, Tuple

KHMER_CHARS = "\u1780-\u17FF\u19E0-\u19FF"
_KHMER_RE = re.compile(f"[{KHMER_CHARS}]")
_SPEAKABLE_RE = re.compile(f"[{KHMER_CHARS}A-Za-z0-9]")
_ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\ufeff]")

# A "Latin token": English word, acronym, product name, GPT-4, Node.js, C++, 4K ...
_LATIN_TOKEN = (
    r"(?:[A-Za-z][A-Za-z0-9]*(?:[-./'’&][A-Za-z0-9]+)*[+#]*"
    r"|\d+[A-Za-z][A-Za-z0-9]*(?:[-./][A-Za-z0-9]+)*)"
)
LATIN_RUN_RE = re.compile(rf"{_LATIN_TOKEN}(?:[ \u00a0]+{_LATIN_TOKEN})*")

PAUSE_LONG = set("។៕.!?…\n")
PAUSE_SHORT = set(",;:៖،、")

# Chinese / Japanese kanji + kana, CJK and full-width punctuation: written WITHOUT spaces between words
_CJK_JOIN_RE = re.compile("[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")


def has_khmer(text: str) -> bool:
    return bool(_KHMER_RE.search(text or ""))


def is_speakable(text: str) -> bool:
    return bool(_SPEAKABLE_RE.search(text or ""))


def strip_zero_width(text: str) -> str:
    return _ZERO_WIDTH_RE.sub("", text or "")


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ")).strip()


def khmer_ratio(text: str) -> float:
    letters = re.findall(f"[{KHMER_CHARS}A-Za-z]", text or "")
    if not letters:
        return 0.0
    k = sum(1 for c in letters if _KHMER_RE.match(c))
    return k / len(letters)


def split_runs(text: str) -> List[Tuple[str, str]]:
    """Split mixed text into ordered ("km" | "en", chunk) pairs.

    "en" chunks are runs of Latin words (technical terms, brands, acronyms).
    Everything else (Khmer, digits, punctuation) is "km".
    """
    text = strip_zero_width(text)
    out: List[Tuple[str, str]] = []
    pos = 0
    for m in LATIN_RUN_RE.finditer(text):
        if m.start() > pos:
            out.append(("km", text[pos:m.start()]))
        out.append(("en", m.group(0)))
        pos = m.end()
    if pos < len(text):
        out.append(("km", text[pos:]))
    return out


def join_caption(a: str, b: str) -> str:
    """Join two caption fragments: with a space, except between two Chinese characters (no spaces there)."""
    if not a:
        return b
    if not b:
        return a
    if _CJK_JOIN_RE.match(a[-1]) and _CJK_JOIN_RE.match(b[0]):
        return a + b
    return a + " " + b


def pause_after(chunk: str) -> float:
    """Pause (seconds) implied by punctuation-only text."""
    s = chunk.strip()
    if not s:
        return 0.0
    if any(c in PAUSE_LONG for c in s):
        return 0.28
    if any(c in PAUSE_SHORT for c in s):
        return 0.14
    return 0.0


# sentence ends: Khmer ។ ៕ · ! ? … · Chinese 。！？ (a closing quote after the mark stays with its sentence)
_SENT_SPLIT_RE = re.compile(
    r"(?<=[។៕!?…。！？])(?![!?！？…”’」』）)\"'])\s*"
    r"|(?<=[។៕!?…。！？][”’」』）)\"'])\s*"
    r"|(?<=[.!?])\s+(?=[\"'“”A-Z0-9\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3\u3400-\u9fff])"      # also before Korean / Chinese text
    r"|\n+"
)
_SOFT_BREAKS = (" ", ",", "、", "，", "；", ";", "：")


def split_sentences(text: str, max_chars: int = 320, min_chunk: int = 40) -> List[str]:
    """Split long text into speakable chunks (<= max_chars) at sentence boundaries.

    `min_chunk`: chunks shorter than this are merged with the next one (40 for English; Chinese needs ~14).
    """
    text = (text or "").replace("\r", "")
    parts: List[str] = []
    for para in re.split(r"\n+", text):
        para = para.strip()
        if not para:
            continue
        for s in _SENT_SPLIT_RE.split(para):
            s = (s or "").strip()
            if s:
                parts.append(s)

    chunks: List[str] = []
    for s in parts:
        while len(s) > max_chars:
            # try to cut at a space (Khmer uses spaces between phrases) or comma
            cut = max(s.rfind(b, 0, max_chars) for b in _SOFT_BREAKS)
            if cut < max_chars * 0.4:
                cut = max_chars
            chunks.append(s[:cut].strip())
            s = s[cut:].strip()
        if s:
            chunks.append(s)

    # merge tiny neighbours so we do not make 1-word requests
    merged: List[str] = []
    for c in chunks:
        if merged and len(merged[-1]) < min_chunk and len(merged[-1]) + 1 + len(c) <= max_chars:
            merged[-1] = join_caption(merged[-1], c)
        else:
            merged.append(c)
    return merged


def ensure_khmer_terminal(text: str) -> str:
    """Make sure a Khmer sentence ends with a terminal mark (helps TTS prosody)."""
    t = (text or "").rstrip()
    if not t:
        return t
    if t[-1] in "។៕.!?…":
        return t
    if has_khmer(t[-12:]) or not t[-1].isascii():
        return t + "។"
    return t


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"
