"""Translate by copy / paste with a chat AI (Claude, ChatGPT, Gemini ...) - no API key, no cost.

The editor offers the numbered source lines of a job together with the instructions (``build_prompt``).  The user pastes that
into the chat, copies the numbered Khmer answer and pastes it back.  ``parse_reply`` reads the Khmer lines out of whatever the
chat produced (inside a code block or not, ``1.`` / ``1)`` / ``**1.**``, lines that were wrapped, Khmer digits ...) and says
exactly which lines were found, which are missing and which look wrong.  Nothing in this module touches the network.

Numbers are the numbers of the editor table (1-based = segment ``idx`` + 1), so a part of a long video can be translated
in a separate chat message and pasted back in any order: every paste only fills the lines it contains.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .glossary import build_matcher
from .langs import LANGS
from .textutil import has_khmer, normalize_ws, strip_zero_width

PART_SIZES = (20, 40, 80, 0)          # lines per part offered by the editor (0 = everything in one message)
DEFAULT_SIZE = 40
NAMES_MODES = ("latin", "khmer")
MAX_REPLY_CHARS = 400_000
MAX_TERMS = 60


# --------------------------------------------------------------------------- #
# parts
# --------------------------------------------------------------------------- #
def clean_size(size) -> int:
    """Lines per part: 0 = all, otherwise 5 .. 300 (the editor offers 20 / 40 / 80 / all)."""
    try:
        n = int(size)
    except (TypeError, ValueError):
        return DEFAULT_SIZE
    if n <= 0:
        return 0
    return max(5, min(n, 300))


def plan(total: int, size) -> tuple:
    """(size, parts) for `total` lines."""
    size = clean_size(size)
    if total <= 0 or size == 0:
        return size, 1
    return size, (total + size - 1) // size


def part_range(total: int, size, part: int) -> tuple:
    """0-based [a, b) of the lines of a part (1-based `part`)."""
    size, parts = plan(total, size)
    if size == 0:
        return 0, total
    part = max(1, min(int(part or 1), parts))
    a = (part - 1) * size
    return a, min(total, a + size)


# --------------------------------------------------------------------------- #
# the text that is copied to the chat
# --------------------------------------------------------------------------- #
def _one_line(text: str) -> str:
    return normalize_ws(strip_zero_width(text or ""))


def good_title(title: str) -> str:
    """A title worth telling the chat about (a pasted SRT without a title would otherwise be called "1")."""
    t = _one_line(title)[:120]
    if len(t) < 3 or re.fullmatch(r"[\d\s:;,.>\-]+", t):
        return ""
    return t


def find_terms(texts: List[str], *, keep_terms: bool = True, auto_detect: bool = True, glossary_text: Optional[str] = None,
               lang: str = "en", limit: int = MAX_TERMS) -> List[str]:
    """The pieces of these lines that must stay in English (glossary terms, acronyms, product names ...).  Chinese / Korean source
    words come as "服务器 → server" (the English form that stays in the Khmer text)."""
    matcher, _ = build_matcher(keep_terms, auto_detect, glossary_text, lang)
    if matcher is None:
        return []
    out: List[str] = []
    seen = set()
    for text in texts:
        for sp in matcher.find_spans(text):
            word = text[sp.start:sp.end].strip()
            if not word:
                continue
            shown = f"{word} → {sp.repl}" if sp.kind == "map" and sp.repl else word
            key = shown.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(shown)
            if len(out) >= limit:
                return out
    return out


def build_prompt(segments: List[dict], lang: str = "en", title: str = "", *, part: int = 1, size=DEFAULT_SIZE, names: str = "latin",
                 keep_terms: bool = True, auto_detect: bool = True, glossary_text: Optional[str] = None) -> dict:
    """Instructions + the numbered source lines of one part, ready to paste into a chat AI."""
    total = len(segments)
    size, parts = plan(total, size)
    try:
        part = int(part or 1)
    except (TypeError, ValueError):
        part = 1
    part = max(1, min(part, parts))
    a, b = part_range(total, size, part)
    names = names if names in NAMES_MODES else "latin"
    lang = lang if lang in LANGS else "en"
    lang_name = LANGS[lang].name
    lines = [(i + 1, _one_line(segments[i].get("en", ""))) for i in range(a, b)]
    terms = find_terms([t for _, t in lines], keep_terms=keep_terms, auto_detect=auto_detect, glossary_text=glossary_text, lang=lang) if keep_terms else []
    plain = [x for x in terms if " → " not in x]
    mapped = [x for x in terms if " → " in x]
    first, last = (lines[0][0], lines[-1][0]) if lines else (0, 0)
    ex1 = first or 1
    ex2 = ex1 + 1

    head = [
        "You are an expert subtitle translator and Khmer voice-over scriptwriter.",
        f"Translate the numbered {lang_name} subtitle lines below into natural, spoken Khmer (ភាសាខ្មែរ). "
        "A text-to-speech voice will read the Khmer aloud to dub the video, so the text must sound natural when spoken.",
    ]
    ttl = good_title(title)
    if ttl:
        head.append(f"Video title: {ttl}")
    if parts > 1:
        head.append(f"This is part {part} of {parts} of the same video (lines {first}-{last} of {total}). "
                    "Keep the wording and terminology consistent with the other parts.")

    rules = [
        "Keep exactly the same line numbers. Give one Khmer line for every numbered line, in the same order. "
        "Never merge, split, skip or add lines.",
    ]
    if keep_terms:
        rules.append(
            "Keep professional and technical terms, product and brand names, programming terms, acronyms, code, file names, URLs and numbers "
            "in English (Latin letters), exactly as written. Do not translate them and do not write them in Khmer letters "
            "(for example: API, Dashboard, Machine Learning, Python, GPT-4, YouTube)."
        )
        if plain:
            rules.append("These pieces appear in this part and must stay exactly as written: " + ", ".join(plain) + ".")
        if mapped:
            rules.append("Write these source words in English (Latin letters) inside the Khmer sentence: " + ", ".join(mapped) + ".")
    else:
        rules.append("Translate everything into Khmer. Only code, file names, URLs and numbers stay as they are.")
    if names == "khmer":
        rules.append("Write people's and character names in Khmer letters (transliterated). Brand and product names stay in Latin letters.")
    else:
        rules.append("Keep people's, character's and place names in Latin letters, as written in the source.")
    rules += [
        "Write natural, fluent, conversational Khmer that sounds good when spoken - not a word-for-word translation. "
        "Use clear everyday words and a neutral, polite tone, and keep the meaning, tone and emotion of the speaker.",
        "Keep each Khmer line about as short as the original line: it has to be spoken in the same amount of time. "
        "Leave out filler words if needed, but never drop information.",
        "The subtitles may come from automatic captions: if a line looks like a speech-recognition mistake or has no punctuation, "
        "translate what the speaker most likely meant. A sentence can continue in the next line - use the neighbouring lines as context.",
        "Use ordinary digits (0-9) for numbers and for the line numbers. Translate sound cues such as [Music] or [Applause] and keep the square brackets. "
        "Plain text only: no bold, italics or other formatting.",
    ]
    out_fmt = [
        "Reply with ONE code block that contains only the numbered Khmer lines, in exactly this form, and nothing else "
        "(no explanation, no notes, no text before or after the block):",
        "```text",
        f"{ex1}. <Khmer translation of line {ex1}>",
        f"{ex2}. <Khmer translation of line {ex2}>",
        "```",
    ]
    where = f"part {part} of {parts}, lines {first}-{last} of {total}" if parts > 1 else f"{total} lines"
    lines_text = "\n".join(f"{n}. {t}" for n, t in lines)
    body = [f"Subtitle lines ({where}):", lines_text, "", "(End of the lines. Reply now with the code block only.)"]

    instructions = "\n".join(head) + "\n\nRules\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1)) + "\n\nOutput format\n" + "\n".join(out_fmt) + "\n"
    text = instructions + "\n" + "\n".join(body) + "\n"
    # text = everything for one paste; `instructions` and `lines_text` are the two halves (a chat project can keep the instructions once)
    return {"text": text, "instructions": instructions, "lines_text": lines_text + "\n", "part": part, "parts": parts, "size": size, "first": first, "last": last,
            "total": total, "chars": len(text), "terms": terms, "lang": lang, "names": names}


# --------------------------------------------------------------------------- #
# reading the answer
# --------------------------------------------------------------------------- #
_DIGITS = {ord(c): str(i) for i, c in enumerate("០១២៣៤៥៦៧៨៩")}
_DIGITS.update({ord(c): str(i) for i, c in enumerate("０１２３４５６７８９")})
_FENCE_RE = re.compile(r"^\s*(?:`{3,}|~{3,})")
_ITEM_RE = re.compile(
    r"""^\s*
        (?:[-*•·▪‣]\s+)?                                      # list bullet
        (?:\*{1,2}|_{1,2}|`)?\s*                              # bold / italic / code opener
        (?:(?:line|ln|no\.?|nr\.?|\#|ជួរទី|ជួរលេខ|ជួរ)\s*)?          # "Line 5", "#5", "ជួរទី 5"
        [\[(<{]?\s*
        (?P<num>[0-9០-៩０-９]{1,5})
        \s*[\])>}]?
        (?:\*{1,2}|_{1,2}|`)?
        [ \t]*
        (?:\\?[.．)\]:：។|\-–—]+|\t|[ ]{2,})                     # separator  (1.  1)  1:  1 -  1|  or a tab / two spaces)
        (?![0-9០-៩０-９])                                      # "1.5 million" is not item 1
        [ \t]*
        (?P<text>.*)$""",
    re.I | re.X)


def _num(s: str) -> int:
    return int(s.translate(_DIGITS))


def _clean(s: str) -> str:
    """One answer line: no markdown emphasis (**bold**, a stray ** left over from "**1.** text"), no `code` ticks, no zero-width marks,
    one space between words.  (Underscores are kept: a term such as __init__ is real text.)"""
    s = strip_zero_width(s or "").replace("**", "").replace("`", "")
    return normalize_ws(s)


def _blocks(raw: str) -> List[str]:
    """Contents of the fenced code blocks (a block that was never closed - the chat was cut off - counts as well)."""
    blocks, cur, inside = [], [], False
    for line in raw.split("\n"):
        if _FENCE_RE.match(line):
            if inside:
                blocks.append("\n".join(cur))
                cur, inside = [], False
            else:
                inside, cur = True, []
            continue
        if inside:
            cur.append(line)
    if inside and cur:
        blocks.append("\n".join(cur))
    return blocks


def parse_reply(text: str, total: int, first: Optional[int] = None, last: Optional[int] = None) -> dict:
    """Read the numbered Khmer lines of an answer.

    `total` = number of lines of the job; `first` / `last` (1-based, optional) = the lines that were asked for (used to report
    what is missing and for the fallback when the answer has no numbers at all).
    """
    if not isinstance(text, str):
        raise ValueError("The answer must be text.")
    if len(text) > MAX_REPLY_CHARS:
        raise ValueError("The answer is too long (more than 400,000 characters).")
    raw = text.replace("\ufeff", "").replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    blocks = _blocks(raw)
    good = [b for b in blocks if any(_ITEM_RE.match(ln) for ln in b.split("\n"))]
    if good:
        body_lines = "\n".join(good).split("\n")                        # the chat followed the instructions: only the code block counts
    else:
        body_lines = [ln for ln in raw.split("\n") if not _FENCE_RE.match(ln)]

    items: Dict[int, str] = {}
    dupes: List[int] = []
    unknown: List[int] = []
    ignored = 0
    cur: Optional[int] = None
    open_ = False
    for line in body_lines:
        if not line.strip():
            open_ = False                                                   # a blank line ends the item (comments after it are not glued on)
            continue
        m = _ITEM_RE.match(line)
        if m:
            n = _num(m.group("num"))
            if 1 <= n <= total:
                if n in items:
                    dupes.append(n)
                items[n] = _clean(m.group("text"))
                cur, open_ = n, True
            else:
                unknown.append(n)
                cur, open_ = None, False
            continue
        if cur is not None and open_:
            items[cur] = (items[cur] + " " + _clean(line)).strip()          # a long line the chat wrapped
        else:
            ignored += 1

    positional = False
    want = (last - first + 1) if (isinstance(first, int) and isinstance(last, int) and 1 <= first <= last <= total) else 0
    if not items and want:                                                  # no line numbers at all: same number of lines as asked -> by order
        cands = [[_clean(x) for x in b.split("\n") if x.strip()] for b in blocks] + [[_clean(x) for x in body_lines if x.strip()]]
        for lines in cands:
            if len(lines) == want:
                items = {first + k: v for k, v in enumerate(lines)}
                positional = True
                break

    for n in [n for n, v in items.items() if not v]:
        del items[n]                                                         # "7." with nothing after it = missing
    nums = sorted(items)
    lo, hi = (first, last) if want else ((nums[0], nums[-1]) if nums else (None, None))
    missing = sorted(set(range(lo, hi + 1)) - set(items)) if lo else []
    no_khmer = [n for n in nums if not has_khmer(items[n]) and re.search(r"[^\W\d_]", items[n])]
    return {
        "items": [{"idx": n - 1, "km": items[n]} for n in nums],
        "count": len(nums),
        "range": [nums[0], nums[-1]] if nums else None,
        "expected": [first, last] if want else None,
        "missing": missing,
        "unknown": sorted(set(unknown)),
        "duplicates": sorted(set(dupes)),
        "no_khmer": no_khmer,
        "ignored": ignored,
        "positional": positional,
    }
