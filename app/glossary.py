"""Technical-terms glossary: keep professional words in English.

Glossary file format (one entry per line):

    # comment
    API                      <- keep "API" in English
    machine learning         <- multi-word term
    nginx = អេនជីនអិច        <- keep "nginx" in English text, but read it with this Khmer pronunciation
    机器学习 => machine learning   <- (Chinese / Korean videos) write this source word in English

How it works with machine translation
-------------------------------------
1. `TermMatcher.protect()` replaces every protected term in the source text with
   a placeholder (X1X, X2X, …) so the translator cannot translate it.  For Chinese and Korean sources the
   built-in tables in `cjkterms.py` (and your `=>` lines) also find native words ("服务器", "서버") and
   protect the ENGLISH form ("server") instead of the source word.
2. After translation `restore()` puts the original English term back (with spacing
   fixed for Khmer text).
3. At speech time the English terms are spoken by an English neural voice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .cjkterms import builtin_terms
from .config import GLOSSARY_FILE

DEFAULT_GLOSSARY_TEXT = """\
# ─────────────────────────────────────────────────────────────
#  Technical terms that stay in English (one per line).
#  Optional Khmer pronunciation:   term = ការអានជាខ្មែរ
#  Chinese / Korean videos:        机器学习 => machine learning
#                                  (your own source word => the English word that stays)
#  Lines starting with # are comments.
# ─────────────────────────────────────────────────────────────

# ── AI & Data ──
AI
artificial intelligence
machine learning
deep learning
neural network
LLM
large language model
GPT
ChatGPT
OpenAI
Gemini
Claude
Copilot
prompt
prompt engineering
fine-tuning
training data
dataset
algorithm
chatbot
computer vision
NLP
natural language processing
data science
data scientist
data analyst
big data
analytics
data pipeline
ETL
Jupyter
TensorFlow
PyTorch
scikit-learn
pandas
NumPy
Hugging Face
reinforcement learning
vector database
embedding
RAG
text-to-speech
speech-to-text

# ── Software & Web ──
API
REST API
GraphQL
SDK
CLI
GUI
UI
UX
UI/UX
front-end
frontend
back-end
backend
full-stack
full stack
framework
plugin
widget
dashboard
web app
mobile app
webhook
endpoint
server
database
SQL
NoSQL
MySQL
PostgreSQL
MongoDB
Redis
JSON
XML
YAML
CSV
HTML
CSS
JavaScript
TypeScript
Python
Java
PHP
Kotlin
React
Vue
Angular
Next.js
Node.js
Django
Flask
FastAPI
Laravel
WordPress
Docker
Kubernetes
microservices
DevOps
CI/CD
Git
GitHub
GitLab
repository
repo
commit
pull request
deploy
deployment
hosting
domain name
DNS
SSL
HTTPS
HTTP
URL
localhost
IDE
VS Code
Visual Studio Code
terminal
command line
bash
npm
pip
yarn
SSH
FTP
PowerShell
script
debug
debugging
bug
compiler
runtime
open source
open-source
source code
version control
cloud
AWS
Azure
Google Cloud
serverless
CDN
load balancer
scalability
latency
bandwidth
browser
cookie
cookies
cache
login
log in
sign up
username
no-code
low-code
SaaS
PaaS
IaaS
Excel
Google Sheets
PowerPoint
Notion
Slack
Zoom
Figma
Photoshop
Illustrator
Canva
Android
iOS
macOS
Linux
Ubuntu
Windows
Chrome
Firefox
Safari
Wi-Fi
Bluetooth
USB
HDMI
CPU
GPU
RAM
SSD
HDD
firmware
hardware
software
IoT
Raspberry Pi
Arduino
5G
4G
LTE

# ── Security ──
cybersecurity
encryption
authentication
authorization
OAuth
JWT
password
firewall
VPN
phishing
malware
ransomware
hacker
two-factor authentication
2FA

# ── Business & Marketing ──
SEO
SEM
KPI
OKR
ROI
B2B
B2C
CRM
ERP
CEO
CFO
CTO
COO
startup
branding
sales funnel
funnel
conversion rate
landing page
call to action
CTA
A/B testing
content marketing
influencer
engagement
impressions
CTR
CPC
CPM
retargeting
newsletter
e-commerce
dropshipping
stakeholder
workflow
MVP
pitch deck
venture capital
Agile
Scrum
Kanban
sprint
product manager
project management
Six Sigma

# ── Finance & Crypto ──
blockchain
cryptocurrency
crypto
Bitcoin
Ethereum
NFT
DeFi
Web3
fintech
ETF
forex
IPO
EBITDA
cash flow
KHQR
Bakong

# ── Social & Media ──
YouTube
Facebook
Instagram
TikTok
Telegram
WhatsApp
LinkedIn
Twitter
Google
Gmail
Microsoft
Apple
Netflix
Spotify
Messenger
WeChat
podcast
livestream
live stream
vlog
subscribe
subscriber
subscribers
thumbnail
playlist
hashtag
monetization
watch time
CapCut
OBS
Premiere Pro
DaVinci Resolve
4K
HD
1080p
MP4
MP3
WAV
GIF
PDF
PNG
JPEG
SVG
codec
frame rate
fps
bitrate

# ── Science & Engineering ──
CO2
DNA
RNA
mRNA
PCR
MRI
CT scan
ECG
NASA
LED
LCD
OLED
CAD
CNC
PLC
PCB
3D printing
3D printer
"""

_COMMENT_RE = re.compile(r"^\s*#")


def parse_glossary_text(text: str) -> Tuple[List[str], Dict[str, str]]:
    """Return (terms, readings) from glossary text. (`source => English` lines are not terms: see parse_glossary_maps.)"""
    terms: List[str] = []
    readings: Dict[str, str] = {}
    seen = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or _COMMENT_RE.match(line) or "=>" in line:
            continue
        reading = None
        if "=" in line:
            left, _, right = line.partition("=")
            line, reading = left.strip(), right.strip()
        if not line:
            continue
        key = line.lower()
        if key not in seen:
            seen.add(key)
            terms.append(line)
        if reading:
            readings[key] = reading
    return terms, readings


def parse_glossary_maps(text: str) -> Dict[str, str]:
    """`源词 => English` lines → {source word: English form} (the English form is what stays in the Khmer text)."""
    out: Dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or _COMMENT_RE.match(line) or "=>" not in line:
            continue
        left, _, right = line.partition("=>")
        right = right.strip()
        for src in left.split("|"):
            src = src.strip()
            if src and right:
                out[src] = right
    return out


def load_glossary_text() -> str:
    try:
        if GLOSSARY_FILE.exists():
            return GLOSSARY_FILE.read_text(encoding="utf-8")
    except Exception:
        pass
    return DEFAULT_GLOSSARY_TEXT


def save_glossary_text(text: str) -> None:
    GLOSSARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    GLOSSARY_FILE.write_text(text or "", encoding="utf-8")


def reset_glossary() -> str:
    try:
        if GLOSSARY_FILE.exists():
            GLOSSARY_FILE.unlink()
    except Exception:
        pass
    return DEFAULT_GLOSSARY_TEXT


# --------------------------------------------------------------------------- #
# Heuristic detection (acronyms, CamelCase, version numbers, file names …)
# --------------------------------------------------------------------------- #
_CAPS_STOP = {"I", "A", "OK", "US", "USA", "UK", "EU", "UN", "AM", "PM", "TV", "II", "III", "IV", "VI", "AD", "BC", "OH", "NO", "SO"}
_ORDINAL_RE = re.compile(r"^\d+(?:st|nd|rd|th|s|am|pm|x)$", re.I)

_HEURISTICS = [
    # URLs / e-mails
    re.compile(
        r"(?:https?://|www\.)[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]*[A-Za-z0-9\-_~/#=%]"
        r"|(?<![A-Za-z0-9._+-])[A-Za-z0-9._+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?![A-Za-z0-9])"
    ),
    # file names & dotted tech tokens: Node.js, package.json, openai.com
    re.compile(
        r"(?<![A-Za-z0-9])[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.(?:js|ts|tsx|jsx|py|io|ai|com|org|net|dev|app|exe|json|html|css|md|txt|csv|xml|yml|yaml|sql|php|sh|bat|zip|pdf|mp4|mp3)(?![A-Za-z0-9])",
        re.I,
    ),
    # C++, C#, F#, .NET
    re.compile(r"(?<![A-Za-z0-9])(?:[CF]\+\+|[CF]#)|\.NET(?![A-Za-z0-9])"),
    # CamelCase / mixed case: iPhone, JavaScript, YouTube, OpenAI, GitHub
    re.compile(r"(?<![A-Za-z0-9])(?:[a-z]+[A-Z][A-Za-z0-9]*|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*)(?![A-Za-z0-9])"),
    # letters + digits: GPT-4, H264, Python3, 4K, 5G, COVID-19
    re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z0-9.\-]*\d)(?=[A-Za-z0-9.\-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9](?![A-Za-z0-9])"),
    # ALL-CAPS acronyms (2-8 chars): API, CPU, SEO
    re.compile(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{1,7}(?![A-Za-z0-9])"),
]


def _is_mostly_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 8:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) > 0.8


@dataclass
class _Span:
    start: int
    end: int
    kind: str                    # "term" | "map" | "auto"
    repl: Optional[str] = None   # "map": the English form that stays in the Khmer text (instead of the source word)


# --- Chinese / Korean source words -------------------------------------------------
_HANGUL_SYL = "\uac00-\ud7a3"
# Korean glues particles to nouns (서버를, 서버에서는, 서버입니다). They may follow a term; another noun or
# a longer word may not ("서버리스" is not "서버" + "리스").
_KO_PARTICLES = (
    "에서는|에서도|으로는|으로도|으로써|으로서|이라고|이라는|에게서|한테서|에서|에게|한테|으로|로는|로도|로써|로서|까지|부터|"
    "처럼|보다|마다|라고|라는|이란|이나|이랑|이다|입니다|이에요|예요|이며|이고|이면|인데|이라|에는|에도|와|과|은|는|이|가|을|를|"
    "의|에|로|도|만|나|랑|란|들|인"
)
_KO_VERB_START = "하해합했한할됩됐되된될"        # 디버깅합니다, 배포했다 …


def _is_hangul(ch: str) -> bool:
    return bool(ch) and ("\uac00" <= ch <= "\ud7a3" or "\u1100" <= ch <= "\u11ff" or "\u3130" <= ch <= "\u318f")


def _norm_src(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def _src_alt(key: str) -> str:
    """Regex for one source word. Spaces inside a Korean term are optional (머신 러닝 = 머신러닝)."""
    pieces = [p for p in re.split(r"\s+", key.strip()) if p]
    return r"\s*".join(re.escape(p) for p in pieces)


class TermMatcher:
    """Finds protected terms in English text and swaps them for placeholders."""

    # placeholder styles tried in order when the translator mangles one: X1X, then QQ1QQ
    STYLES = (("X", "X"), ("QQ", "QQ"))

    def __init__(self, terms: Optional[List[str]] = None, auto_detect: bool = True, src_map: Optional[Dict[str, str]] = None):
        self.terms = [t for t in (terms or []) if t.strip()]
        self.auto_detect = auto_detect
        self._rx = self._compile(self.terms)
        # source word (Chinese / Korean / anything) → English form
        self.src_map = {k.strip(): v.strip() for k, v in (src_map or {}).items() if k.strip() and v.strip()}
        self._src_lookup = {_norm_src(k): v for k, v in self.src_map.items()}
        self._src_rx = self._compile_src(self.src_map)

    @staticmethod
    def _compile_src(src_map: Dict[str, str]) -> List["re.Pattern"]:
        """Three expressions, tried in this order: Han / other scripts, Hangul, Latin keys."""
        han, hangul, latin = [], [], []
        for k in sorted(src_map, key=lambda x: (-len(x), x)):
            alt = _src_alt(k)
            if not alt:
                continue
            if re.search(f"[{_HANGUL_SYL}\u1100-\u11ff\u3130-\u318f]", k):
                hangul.append(alt)
            elif re.fullmatch(r"[\x00-\x7f\s]+", k):
                latin.append(alt)
            else:
                han.append(alt)
        rxs: List["re.Pattern"] = []
        if han:
            rxs.append(re.compile("|".join(han)))
        if hangul:
            rxs.append(re.compile(
                rf"(?<![{_HANGUL_SYL}])(?:{'|'.join(hangul)})"
                rf"(?=(?:{_KO_PARTICLES}){{0,3}}(?:[^{_HANGUL_SYL}]|$|[{_KO_VERB_START}]))"
            ))
        if latin:
            rxs.append(re.compile(rf"(?<![A-Za-z0-9])(?:{'|'.join(latin)})(?![A-Za-z0-9])", re.I))
        return rxs

    @staticmethod
    def _compile(terms: List[str]):
        if not terms:
            return None
        parts = []
        for t in sorted(set(terms), key=lambda s: (-len(s), s.lower())):
            # "front-end" also matches "front end"; "machine learning" also matches "machine-learning"
            pieces = [p for p in re.split(r"[\s\-]+", t.strip()) if p]
            if not pieces:
                continue
            parts.append(r"[\s\-]+".join(re.escape(p) for p in pieces))
        body = "|".join(parts)
        return re.compile(
            rf"(?<![A-Za-z0-9])(?:{body})(?:['’]s|s|es)?(?:-?\d+(?:\.\d+)*[A-Za-z]?)?(?![A-Za-z0-9])", re.I
        )

    # -- detection ---------------------------------------------------------- #
    def find_spans(self, text: str) -> List[_Span]:
        """Where the protected pieces are. Earlier steps win: a later match may not overlap an earlier one."""
        spans: List[_Span] = []

        def overlaps(a: int, b: int) -> bool:
            return any(not (b <= s.start or a >= s.end) for s in spans)

        def add(start: int, end: int, kind: str, repl: Optional[str] = None) -> None:
            if not overlaps(start, end):
                spans.append(_Span(start, end, kind, repl))

        # 1. URLs and e-mail addresses are one piece (not "https" + "example.com")
        if self.auto_detect:
            for m in _HEURISTICS[0].finditer(text):
                add(m.start(), m.end(), "auto")

        # 2. Chinese / Korean words → their English form ("챗GPT" is ChatGPT, not "챗" + GPT)
        for rx in self._src_rx:
            for m in rx.finditer(text):
                repl = self._src_lookup.get(_norm_src(m.group(0)))
                if repl:
                    add(m.start(), m.end(), "map", repl)

        # 3. glossary terms
        if self._rx is not None:
            for m in self._rx.finditer(text):
                add(m.start(), m.end(), "term")

        # 4. acronyms, CamelCase, version numbers, file names …
        if self.auto_detect:
            upper_text = _is_mostly_upper(text)
            for rx in _HEURISTICS[1:]:
                for m in rx.finditer(text):
                    tok = m.group(0)
                    if overlaps(m.start(), m.end()):
                        continue
                    if rx is _HEURISTICS[-1]:  # ALL-CAPS
                        if upper_text or tok in _CAPS_STOP or tok.isdigit():
                            continue
                    if rx is _HEURISTICS[-2]:  # letters+digits
                        if _ORDINAL_RE.match(tok) or tok.isdigit():
                            continue
                        if re.fullmatch(r"[\d.\-]+", tok):
                            continue
                    spans.append(_Span(m.start(), m.end(), "auto"))
        spans.sort(key=lambda s: s.start)

        # merge spans that are separated only by a single space ("VS" "Code", "Open" "AI")
        merged: List[_Span] = []
        for s in spans:
            if merged and text[merged[-1].end:s.start] in (" ", "\u00a0") and (s.start - merged[-1].end) == 1:
                a = merged[-1]
                repl = None
                if a.repl or s.repl:   # "구글 클라우드" → "Google cloud"
                    repl = f"{a.repl or text[a.start:a.end]} {s.repl or text[s.start:s.end]}"
                merged[-1] = _Span(a.start, s.end, a.kind if not repl else "map", repl)
            else:
                merged.append(s)
        return merged

    # -- protect / restore -------------------------------------------------- #
    def protect(self, text: str, style: Tuple[str, str] = ("X", "X")) -> Tuple[str, Dict[int, str]]:
        spans = self.find_spans(text)
        if not spans:
            return text, {}
        out, mapping, pos = [], {}, 0
        for i, s in enumerate(spans, start=1):
            out.append(text[pos:s.start])
            # pad with spaces so the placeholder is its own token for the translator
            # (not before a Korean particle: "X1X를" – the translator needs to see that it is a noun)
            tail = "" if (s.end < len(text) and _is_hangul(text[s.end])) else " "
            out.append(f" {style[0]}{i}{style[1]}{tail}")
            mapping[i] = s.repl or text[s.start:s.end]
            pos = s.end
        out.append(text[pos:])
        protected = re.sub(r"[ \t]{2,}", " ", "".join(out)).strip()
        return protected, mapping

    @classmethod
    def restore(cls, translated: str, mapping: Dict[int, str], style: Tuple[str, str] = ("X", "X")) -> Tuple[str, bool]:
        """Put English terms back. Returns (text, all_placeholders_found_exactly_once)."""
        if not mapping:
            return translated, True
        seen: Dict[int, int] = {}
        ph_re = re.compile(
            re.escape(style[0]) + r"\s*([0-9\u17E0-\u17E9]{1,3})\s*" + re.escape(style[1]), re.I
        )

        def _digits(s: str) -> int:
            return int("".join(str(ord(c) - 0x17E0) if "\u17E0" <= c <= "\u17E9" else c for c in s))

        def _sub(m: "re.Match") -> str:
            try:
                idx = _digits(m.group(1))
            except ValueError:
                return m.group(0)
            if idx not in mapping:
                return m.group(0)
            seen[idx] = seen.get(idx, 0) + 1
            return f"\u0000{mapping[idx]}\u0001"

        text = ph_re.sub(_sub, translated)
        ok = set(seen) == set(mapping) and all(v == 1 for v in seen.values())

        # spacing: a Latin term must be separated from neighbouring Khmer text by a space
        text = re.sub("(?<=[^\\s(\\[“‘\"'])\u0000", " \u0000", text)
        text = re.sub("\u0001(?=[^\\s\u0000.,;:!?។៕)\\]”’\"'])", "\u0001 ", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\s+([។៕.,;:!?])", r"\1", text)  # markers still present → ".NET" is safe
        text = re.sub(r"([(\[“‘]) +", r"\1", text)
        text = re.sub(r" +([)\]”’])", r"\1", text)
        text = text.replace("\u0000", "").replace("\u0001", "")
        return text.strip(), ok


def apply_readings(text: str, readings: Dict[str, str]) -> str:
    """Swap terms that have a custom Khmer reading (used only for speech)."""
    if not readings or not text:
        return text
    keys = sorted(readings, key=len, reverse=True)
    rx = re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(k) for k in keys) + r")(?:['’]s|s|es)?(?![A-Za-z0-9])", re.I
    )

    def _sub(m: "re.Match") -> str:
        return f" {readings.get(m.group(1).lower(), m.group(0))} "

    return re.sub(r"[ \t]{2,}", " ", rx.sub(_sub, text)).strip()


def build_matcher(
    keep_terms: bool = True,
    auto_detect: bool = True,
    glossary_text: Optional[str] = None,
    lang: str = "en",
) -> Tuple[Optional[TermMatcher], Dict[str, str]]:
    """Return (matcher or None, readings). `lang` is the source language ('en' | 'zh' | 'ko')."""
    text = glossary_text if glossary_text is not None else load_glossary_text()
    terms, readings = parse_glossary_text(text)
    if not keep_terms:
        return None, readings
    src_map = dict(builtin_terms(lang))
    src_map.update(parse_glossary_maps(text))      # your own lines win over the built-in table
    return TermMatcher(terms, auto_detect=auto_detect, src_map=src_map), readings
