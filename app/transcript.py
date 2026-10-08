"""Transcript parsing, cleaning and sentence-level merging (English, Chinese and Korean sources)."""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .langs import LANGS, info as lang_info
from .textutil import join_caption, normalize_ws


@dataclass
class Seg:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "text": self.text}


# --------------------------------------------------------------------------- #
# cleaning
# --------------------------------------------------------------------------- #
_CUE_WORDS = (
    r"music|applause|laughter|laughs|laughing|sighs|cheering|cheers|crowd|silence|noise|beep|singing|"
    r"inaudible|speaking|foreign|blank_audio|upbeat|dramatic|clears throat|coughs|sound"
)
_PAREN_CUE_RE = re.compile(rf"\(([^)]*\b(?:{_CUE_WORDS})\b[^)]*)\)", re.I)
# sound descriptions in Chinese / Korean subtitles:  （音乐） (掌声) (박수) (웃음소리)  – at the start of a short parenthesis
_CJK_CUE_WORDS = (
    "背景音乐|背景音樂|音乐|音樂|配乐|配樂|音效|掌声|掌聲|鼓掌|笑声|笑聲|欢呼|歡呼|歌声|歌聲|旁白|无声|無聲|静音|靜音|"
    "听不清|聽不清|外语|外語|空白|笑|"
    "배경음악|효과음|음악|박수|웃음|환호|함성|노래|침묵|잡음|무음|내레이션|한숨|기침|소리"
)
_PAREN_CJK_CUE_RE = re.compile(rf"[(（]\s*(?:{_CJK_CUE_WORDS})[^()（）]{{0,6}}[)）]")
_BRACKET_RE = re.compile(r"\[[^\]]*\]|【[^】]*】")
_MUSIC_RE = re.compile(r"[♪♫♬🎵🎶]+")
_TAG_RE = re.compile(r"<[^>]+>")
_ASS_RE = re.compile(r"\{\\[^}]*\}")                  # {\an8} {\i1} ... (positions / styles of ASS subtitles converted to SRT)


def _sentence_case(t: str) -> str:
    t = t.lower()
    return re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)


def clean_caption_text(text: str) -> str:
    t = html.unescape(html.unescape(text or ""))  # YouTube sometimes double-encodes (&amp;#39;)
    t = _TAG_RE.sub("", t)
    t = _ASS_RE.sub("", t)
    t = _BRACKET_RE.sub(" ", t)
    t = _PAREN_CUE_RE.sub(" ", t)
    t = _PAREN_CJK_CUE_RE.sub(" ", t)
    t = _MUSIC_RE.sub(" ", t)
    t = re.sub(r"(^|\s)>>+\s*", " ", t)          # speaker-change markers
    t = re.sub(r"^\s*[-–—]\s+", "", t)           # dialogue dash
    t = t.replace("\u200b", "")
    t = normalize_ws(t)
    letters = [c for c in t if c.isalpha()]
    if len(letters) >= 12 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.85:
        t = _sentence_case(t)
    return t


# something worth speaking: Latin letters, digits, Khmer, Chinese / Japanese characters, Hangul
_HAS_CONTENT_RE = re.compile(
    "[A-Za-z0-9\u1780-\u17FF\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]"
)


def clean_segments(segs: Iterable[Seg]) -> List[Seg]:
    out: List[Seg] = []
    for s in segs:
        t = clean_caption_text(s.text)
        if not t or not _HAS_CONTENT_RE.search(t):
            continue
        out.append(Seg(float(s.start), float(s.end), t))
    return out


def fix_overlaps(segs: List[Seg], min_len: float = 0.4) -> List[Seg]:
    segs = sorted(segs, key=lambda s: (s.start, s.end))
    for i, s in enumerate(segs):
        nxt = segs[i + 1].start if i + 1 < len(segs) else None
        if s.end <= s.start:
            s.end = s.start + min_len
        if nxt is not None and s.end > nxt:
            s.end = max(s.start + 0.2, nxt)
    return segs


# --------------------------------------------------------------------------- #
# parsers
# --------------------------------------------------------------------------- #
_TS_RE = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
)


def _ts(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int((ms + "00")[:3]) / 1000.0


def parse_srt_vtt(text: str) -> List[Seg]:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    segs: List[Seg] = []
    prev_lines: List[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.split("\n") if l.strip()]
        ts_idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if ts_idx is None:
            continue
        m = _TS_RE.search(lines[ts_idx])
        if not m:
            continue
        start = _ts(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _ts(m.group(5), m.group(6), m.group(7), m.group(8))
        body = lines[ts_idx + 1:]
        # rolling auto-captions repeat the previous cue's last line(s): drop repeats
        fresh = [l for l in body if _TAG_RE.sub("", l).strip() not in prev_lines]
        prev_lines = [_TAG_RE.sub("", l).strip() for l in body]
        if not fresh:
            continue
        segs.append(Seg(start, end, " ".join(fresh)))
    return segs


def parse_json3(data) -> List[Seg]:
    if isinstance(data, (str, bytes)):
        data = json.loads(data)
    segs: List[Seg] = []
    for ev in data.get("events", []):
        if "segs" not in ev:
            continue
        text = "".join(s.get("utf8", "") for s in ev["segs"]).replace("\n", " ").strip()
        if not text:
            continue
        start = ev.get("tStartMs", 0) / 1000.0
        dur = ev.get("dDurationMs", 2000) / 1000.0
        segs.append(Seg(start, start + dur, text))
    return segs


def from_snippets(snippets: Iterable) -> List[Seg]:
    """youtube-transcript-api snippets (objects or dicts)."""
    segs: List[Seg] = []
    for sn in snippets:
        if isinstance(sn, dict):
            text, start, dur = sn.get("text", ""), sn.get("start", 0.0), sn.get("duration", 2.0)
        else:
            text, start, dur = sn.text, sn.start, sn.duration
        segs.append(Seg(float(start), float(start) + float(dur), text))
    return segs


def parse_plain_text(text: str, lang: str = "en") -> List[Seg]:
    """Plain text without timing: one segment per sentence with estimated timing (speaking speed of the language)."""
    from .textutil import split_sentences

    li = lang_info(lang)
    segs: List[Seg] = []
    t = 0.0
    for sent in split_sentences(text, max_chars=li.max_sentence, min_chunk=round(40 * li.cps / 14.0)):
        dur = max(1.5, len(sent) / li.cps)
        segs.append(Seg(t, t + dur, sent))
        t += dur + 0.2
    return segs


# "0:03", "1:02:03", "[0:03] hello", "0:03 - hello", "(0:03.5) hello"  -> h, m, s, fraction, the text after the time
_STAMP_RE = re.compile(r"^[\[(]?(?:(\d{1,2}):)?(\d{1,3}):(\d{2})(?:[.,](\d{1,3}))?[\])]?(?:\s*[-–—:]\s*|\s+|$)(.*)$")


def parse_stamped_text(text: str, lang: str = "en") -> List[Seg]:
    """Text that has a time in front of every paragraph - for example what you get by copying the transcript panel of a YouTube video:

        0:00 / hello and welcome / 0:03 / to my channel     (the time on its own line, or in front of the text)

    Returns [] unless the text really looks like that (at least 3 times, going forward, and a good share of the lines)."""
    lines = [l.strip() for l in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n") if l.strip()]
    items: List[list] = []
    header: List[str] = []
    for line in lines:
        m = _STAMP_RE.match(line)
        if m:
            t = int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + (int((m.group(4) + "00")[:3]) / 1000.0 if m.group(4) else 0.0)
            rest = m.group(5).strip()
            items.append([t, [rest] if rest else []])
        elif items:
            items[-1][1].append(line)
        else:
            header.append(line)                                   # "Transcript" ... before the first time
    if len(items) < 3 or len(items) * 5 < len(lines) or len(header) > 3 or any(len(h) > 60 for h in header):
        return []
    if sum(1 for a, b in zip(items, items[1:]) if b[0] < a[0]) > len(items) * 0.1:
        return []                                                 # the times do not run forward: not a transcript
    li = lang_info(lang)
    segs: List[Seg] = []
    for i, (t, parts) in enumerate(items):
        body = " ".join(parts).strip()
        if not body:
            continue
        est = max(1.5, len(body) / li.cps)
        nxt = items[i + 1][0] if i + 1 < len(items) and items[i + 1][0] > t else None
        end = min(nxt, t + est * 1.5 + 1.0) if nxt is not None else t + est + 0.5
        segs.append(Seg(t, end, body))
    return segs if len(segs) >= 3 else []


def parse_any(text: str, lang: str = "en") -> Tuple[List[Seg], bool]:
    """Detect SRT/VTT, text with times in front of the paragraphs, or plain text. Returns (segments, has_real_timing)."""
    if "-->" in (text or ""):
        segs = parse_srt_vtt(text)
        if segs:
            return segs, True
    segs = parse_stamped_text(text, lang)
    if segs:
        return segs, True
    return parse_plain_text(text, lang), False


# --------------------------------------------------------------------------- #
# merging fragments into dubbing-friendly sentences
# --------------------------------------------------------------------------- #
_SENT_END_RE = re.compile(r"[.!?…。！？][\"”’')\]」』）]*$")


def merge_segments(
    segs: List[Seg],
    max_chars: Optional[int] = None,
    max_dur: float = 12.0,
    min_dur: float = 2.2,
    gap_break: float = 1.0,
    lang: str = "en",
) -> List[Seg]:
    """Glue caption fragments into sentence-sized dubbing segments. Length limits depend on the language
    (230 characters of English are ~15 s of speech, but 80 Chinese characters are already ~17 s)."""
    li = lang_info(lang)
    if max_chars is None:
        max_chars = li.max_chars
    out: List[Seg] = []
    cur: Optional[Seg] = None
    for s in segs:
        if cur is None:
            cur = Seg(s.start, s.end, s.text)
            continue
        gap = s.start - cur.end
        would_len = len(cur.text) + 1 + len(s.text)
        would_dur = s.end - cur.start
        sentence_done = bool(_SENT_END_RE.search(cur.text))
        if gap > gap_break or would_len > max_chars or would_dur > max_dur or (sentence_done and (cur.end - cur.start) >= min_dur):
            out.append(cur)
            cur = Seg(s.start, s.end, s.text)
        else:
            cur.text = join_caption(cur.text, s.text)
            cur.end = max(cur.end, s.end)
    if cur is not None:
        out.append(cur)

    # absorb tiny fragments into a neighbour when they are close together
    merged: List[Seg] = []
    for s in out:
        if merged and (len(s.text) < li.min_chars or (s.end - s.start) < 0.9):
            prev = merged[-1]
            if s.start - prev.end < 0.8 and len(prev.text) + len(s.text) < max_chars + 40 * li.cps / 14.0:
                prev.text = join_caption(prev.text, s.text)
                prev.end = max(prev.end, s.end)
                continue
        merged.append(s)
    return merged


# --------------------------------------------------------------------------- #
# writers
# --------------------------------------------------------------------------- #
def _srt_time(t: float) -> str:
    t = max(0.0, t)
    ms = int(round((t - int(t)) * 1000))
    s = int(t) % 60
    m = (int(t) // 60) % 60
    h = int(t) // 3600
    if ms == 1000:
        ms, s = 0, s + 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(items: List[dict], text_key: str = "km", start_key: str = "start", end_key: str = "end") -> str:
    lines = []
    n = 0
    for it in items:
        txt = (it.get(text_key) or "").strip()
        if not txt:
            continue
        n += 1
        lines.append(f"{n}\n{_srt_time(it[start_key])} --> {_srt_time(max(it[end_key], it[start_key] + 0.3))}\n{txt}\n")
    return "\n".join(lines)
