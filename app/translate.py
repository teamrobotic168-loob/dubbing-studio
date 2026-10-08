"""English / Chinese / Korean → Khmer translation with professional terms kept in English.

Engines
-------
* ``google`` – the free Google Translate web endpoints (no API key). Terms are protected with
  placeholders (X1X …) and restored afterwards. Lines are sent in batches (one request carries up
  to 16 lines), several endpoints are tried in turn, and the engine stops with a clear message
  instead of retrying silently for minutes when Google is not answering.
* ``llm``    – any OpenAI-compatible chat API (OpenAI, Gemini, OpenRouter, Groq …).
  The model is instructed to keep technical/professional terms in English.

The source language ('en' | 'zh' | 'ko') only changes three things: the Google ``sl`` code, the sentence the
LLM is told, and the term table (Chinese / Korean words such as 服务器 / 서버 are found and kept as "server").
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import httpx

from .config import CACHE_DIR
from .cjkterms import builtin_terms
from .glossary import TermMatcher, build_matcher, parse_glossary_text, load_glossary_text
from .langs import LANGS, normalize_lang
from .textutil import ensure_khmer_terminal, normalize_ws, split_sentences, strip_zero_width

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
TR_CACHE_DIR = CACHE_DIR / "translate"
TR_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class TranslationError(RuntimeError):
    pass


class _Stop(Exception):
    """Raised inside worker threads when the job was cancelled."""


class _RouteError(Exception):
    """One Google endpoint failed. kind: rate | net | http | parse."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


# --------------------------------------------------------------------------- #
# Google web endpoints (tried in order; the one that works is remembered)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GoogleRoute:
    name: str
    url: str
    kind: str                          # "batch": many `q` in one POST · "single": one `q` per request
    params: Tuple[Tuple[str, str], ...]


_LLM_EXAMPLES = {
    "zh": ("服务器", "机器学习", "数据库", "谷歌"),
    "ko": ("서버", "머신러닝", "데이터베이스", "유튜브", "파이썬"),
}

GT_ROUTES: List[GoogleRoute] = [
    GoogleRoute("gtx-batch", "https://translate.googleapis.com/translate_a/t", "batch",
                (("client", "gtx"), ("dt", "t"))),
    GoogleRoute("chrome-batch", "https://clients5.google.com/translate_a/t", "batch",
                (("client", "dict-chrome-ex"),)),
    GoogleRoute("gtx-single", "https://translate.googleapis.com/translate_a/single", "single",
                (("client", "gtx"), ("dt", "t"))),
    GoogleRoute("web-single", "https://translate.google.com/translate_a/single", "single",
                (("client", "gtx"), ("dt", "t"))),
]


def system_proxies() -> Dict[str, str]:
    """Proxies picked up from the environment / OS settings (credentials removed)."""
    try:
        raw = urllib.request.getproxies()
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for scheme in ("http", "https", "all"):
        v = raw.get(scheme)
        if not v:
            continue
        try:
            u = urlsplit(v if "://" in v else "http://" + v)
            out[scheme] = f"{u.scheme}://{u.hostname}{':' + str(u.port) if u.port else ''}"
        except Exception:
            out[scheme] = "(configured)"
    return out


def _parse_batch(data, n: int) -> Optional[List[str]]:
    if isinstance(data, str):
        data = [data]
    if not isinstance(data, list) or len(data) != n:
        return None
    out: List[str] = []
    for x in data:
        if isinstance(x, list) and x and isinstance(x[0], str):
            x = x[0]
        if not isinstance(x, str):
            return None
        out.append(x)
    return out


@dataclass
class TranslateConfig:
    engine: str = "google"           # "google" | "llm"  ("manual" = copy / paste with a chat AI: the pipeline stops before translating, see pipeline._make_draft)
    keep_terms: bool = True
    auto_detect: bool = True
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    glossary_text: Optional[str] = None
    src_lang: str = "en"             # source language: "en" | "zh" | "ko"

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "TranslateConfig":
        d = d or {}
        llm = d.get("llm") or {}
        return cls(
            engine=(d.get("engine") or "google").lower(),
            keep_terms=bool(d.get("keep_terms", True)),
            auto_detect=bool(d.get("auto_detect", True)),
            llm_base_url=(llm.get("base_url") or "").strip(),
            llm_api_key=(llm.get("api_key") or "").strip(),
            llm_model=(llm.get("model") or "").strip(),
            glossary_text=d.get("glossary_text"),
            src_lang=normalize_lang(d.get("src_lang"), "en"),
        )


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _clean_khmer(text: str) -> str:
    text = strip_zero_width(text or "")
    text = normalize_ws(text)
    text = text.replace(" ។", "។").replace(" ៕", "៕")
    return text


def _extract_json(text: str):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}|\[.*\]", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


# --------------------------------------------------------------------------- #
# Translator
# --------------------------------------------------------------------------- #
class Translator:
    # -- Google engine tuning ------------------------------------------------ #
    CONNECT_TIMEOUT = 6.0            # seconds to open a connection
    READ_TIMEOUT = 15.0              # seconds to wait for an answer
    ROUNDS = 4                       # full passes over all routes before giving up
    BACKOFF = (3.0, 8.0, 15.0)       # pause between passes (seconds)
    STALL_LIMIT = 50.0               # no successful answer for this long → stop with an error
    BATCH_MAX_ITEMS = 16
    BATCH_MAX_CHARS = 3200
    WORKERS = 3                      # parallel Google requests
    LLM_WORKERS = 3                  # parallel LLM requests

    def __init__(self, cfg: TranslateConfig, log: Callable[[str], None] = lambda m: None):
        self.cfg = cfg
        self.log = log
        self.lang = normalize_lang(cfg.src_lang, "en")
        if self.lang not in LANGS:
            self.lang = "en"
        self.sl = LANGS[self.lang].google
        gl_text = cfg.glossary_text if cfg.glossary_text is not None else load_glossary_text()
        self.matcher, self.readings = build_matcher(cfg.keep_terms, cfg.auto_detect, gl_text, lang=self.lang)
        self.glossary_terms, _ = parse_glossary_text(gl_text)
        self._gl_hash = hashlib.sha1((gl_text if cfg.keep_terms else "").encode("utf-8")).hexdigest()[:12]

        timeout = httpx.Timeout(self.READ_TIMEOUT, connect=self.CONNECT_TIMEOUT)
        base = dict(headers={"User-Agent": _UA}, timeout=timeout, follow_redirects=True)
        self._client = httpx.Client(**base)
        self._clients: List[Tuple[str, httpx.Client]] = [("default", self._client)]
        if system_proxies():
            # a broken VPN / system proxy must not make translation impossible → also try a direct connection
            self._clients.append(("direct", httpx.Client(trust_env=False, **base)))

        self._lock = threading.Lock()
        self.stats = {"fallback_unprotected": 0, "retries": 0, "requests": 0, "failed_requests": 0}
        self._pref = 0                                   # index of the last working (route, client) pair
        self._route_used = ""
        self._last_ok = time.monotonic()
        self._fatal: Optional[Exception] = None
        self._last_errors: Dict[str, _RouteError] = {}
        self._status: Callable[[str], None] = lambda m: None
        self._cancelled: Callable[[], bool] = lambda: False
        self._last_note: Dict[str, float] = {}

    # -- cache (a retry after a TTS hiccup must not re-translate hundreds of lines) -- #
    def _ckey(self, text: str) -> str:
        c = self.cfg
        key = [c.engine, c.keep_terms, c.auto_detect, self._gl_hash, c.llm_model if c.engine == "llm" else "", text]
        if self.lang != "en":      # English keys stay as they were, so the existing cache keeps working
            key.insert(5, self.lang)
        raw = json.dumps(key, ensure_ascii=False)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _cget(key: str) -> Optional[str]:
        f = TR_CACHE_DIR / f"{key}.txt"
        try:
            return f.read_text(encoding="utf-8") if f.exists() else None
        except OSError:
            return None

    @staticmethod
    def _cput(key: str, value: str) -> None:
        if not value:
            return
        tmp = TR_CACHE_DIR / f"{key}.{os.getpid()}-{threading.get_ident()}.tmp"
        try:
            tmp.write_text(value, encoding="utf-8")
            os.replace(tmp, TR_CACHE_DIR / f"{key}.txt")
        except OSError:
            pass

    def close(self) -> None:
        for _, c in self._clients:
            try:
                c.close()
            except Exception:
                pass

    # -- shared plumbing ------------------------------------------------------ #
    def _note(self, msg: str, short: Optional[str] = None) -> None:
        """Log a problem (at most once every 4 s per message) and show it next to the progress bar."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_note.get(msg, -99.0) < 4.0:
                return
            self._last_note[msg] = now
        self.log(msg)
        try:
            self._status(short or msg)
        except Exception:
            pass

    def _guard(self, stall: bool = True) -> None:
        if self._fatal is not None:
            raise self._fatal
        if self._cancelled():
            raise _Stop()
        if stall and time.monotonic() - self._last_ok > self.STALL_LIMIT:
            self._fatal = self._summarize(self._last_errors, stalled=True)
            raise self._fatal

    def _sleep(self, seconds: float, stall: bool = True) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self._guard(stall)
            time.sleep(min(0.2, max(0.0, end - time.monotonic())))

    def _summarize(self, errors: Dict[str, _RouteError], stalled: bool = False) -> TranslationError:
        kinds = {e.kind for e in errors.values()}
        detail = "; ".join(f"{k} → {e.detail}" for k, e in errors.items()) or "no reply"
        if kinds == {"rate"}:
            why = "Google is rate-limiting this internet connection right now (HTTP 429)."
        elif kinds == {"net"}:
            why = "This computer cannot reach Google Translate (network, VPN/proxy or firewall)."
        elif stalled and not errors:
            why = f"Google Translate did not answer for {int(self.STALL_LIMIT)} seconds."
        else:
            why = "Google Translate keeps returning errors."
        return TranslationError(
            f"{why} Details: {detail}. Wait a few minutes, change network / VPN, or switch to the "
            f"AI / LLM engine (Settings → AI Translation). Settings → “Test Google Translate” shows which route works."
        )

    # -- public ------------------------------------------------------------- #
    def translate_many(
        self,
        texts: List[str],
        progress: Optional[Callable[[int, int], None]] = None,
        cancelled: Callable[[], bool] = lambda: False,
        status: Optional[Callable[[str], None]] = None,
    ) -> List[str]:
        self._cancelled = cancelled
        if self.cfg.engine == "llm":
            return self._translate_llm(texts, progress, cancelled, status)
        return self._translate_google(texts, progress, cancelled, status)

    def translate_text(
        self,
        text: str,
        progress: Optional[Callable[[int, int], None]] = None,
        cancelled: Callable[[], bool] = lambda: False,
        status: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Translate arbitrary (multi-paragraph) text, preserving paragraph breaks."""
        paragraphs = [p for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]
        pieces: List[str] = []
        owners: List[int] = []
        li = LANGS[self.lang]
        for pi, para in enumerate(paragraphs):
            # 280 characters of English ≈ 90 Chinese / 150 Korean characters of speech
            for s in split_sentences(para, max_chars=round(280 * li.cps / 14.0), min_chunk=round(40 * li.cps / 14.0)):
                pieces.append(s)
                owners.append(pi)
        if not pieces:
            return ""
        out = self.translate_many(pieces, progress=progress, cancelled=cancelled, status=status)
        joined: Dict[int, List[str]] = {}
        for o, t in zip(owners, out):
            joined.setdefault(o, []).append(t)
        return "\n".join(" ".join(v) for _, v in sorted(joined.items()))

    # -- Google: one HTTP request ------------------------------------------------ #
    def _combos(self) -> List[Tuple[GoogleRoute, str, httpx.Client]]:
        return [(r, cname, client) for r in GT_ROUTES for cname, client in self._clients]

    @staticmethod
    def _http(fn, url: str, **kw) -> httpx.Response:
        try:
            r = fn(url, **kw)
        except (httpx.HTTPError, OSError) as exc:
            raise _RouteError("net", f"{type(exc).__name__}: {str(exc)[:100] or 'no details'}") from exc
        if r.status_code != 200:
            raise _RouteError("rate" if r.status_code in (429, 403) else "http", f"HTTP {r.status_code}")
        return r

    @staticmethod
    def _json(r: httpx.Response):
        try:
            return r.json()
        except ValueError as exc:
            raise _RouteError("parse", "the reply is not JSON (captcha page?)") from exc

    def _call_route(self, client: httpx.Client, route: GoogleRoute, texts: List[str], timeout=None) -> List[str]:
        kw = {"timeout": timeout} if timeout is not None else {}
        params = {"sl": self.sl, "tl": "km", **dict(route.params)}
        if route.kind == "batch":
            r = self._http(client.post, route.url, params=params, data={"q": texts}, **kw)
            out = _parse_batch(self._json(r), len(texts))
            if out is None:
                raise _RouteError("parse", "unexpected reply shape")
            return out
        out = []
        for text in texts:
            if len(text) > 1500:
                r = self._http(client.post, route.url, params=params, data={"q": text}, **kw)
            else:
                r = self._http(client.get, route.url, params={**params, "q": text}, **kw)
            data = self._json(r)
            try:
                out.append("".join(seg[0] for seg in (data[0] or []) if seg and seg[0]))
            except Exception as exc:
                raise _RouteError("parse", "unexpected reply shape") from exc
        return out

    def _google_batch_raw(self, texts: List[str]) -> List[str]:
        """Translate already-protected lines; rotates over routes, remembers the one that works."""
        last: Dict[str, _RouteError] = {}
        for rnd in range(self.ROUNDS):
            combos = self._combos()
            n = len(combos)
            start = self._pref % n
            for k in range(n):
                self._guard()
                idx = (start + k) % n
                route, cname, client = combos[idx]
                label = route.name if len(self._clients) == 1 else f"{route.name}/{cname}"
                try:
                    try:
                        out = self._call_route(client, route, texts)
                    except _RouteError:
                        raise
                    except Exception as exc:  # a bug / odd reply on one route must not kill the whole job
                        raise _RouteError("parse", f"{type(exc).__name__}: {str(exc)[:100]}") from exc
                except _RouteError as e:
                    last[label] = e
                    self._last_errors = dict(last)
                    with self._lock:
                        self.stats["failed_requests"] += 1
                    self._note(
                        f"Google Translate · {label}: {e.detail}" + ("  (rate-limited)" if e.kind == "rate" else ""),
                        short=f"{label}: {e.detail}",
                    )
                    continue
                with self._lock:
                    self._pref = idx
                    self._last_ok = time.monotonic()
                    self._route_used = label
                    self.stats["requests"] += 1
                return out
            with self._lock:
                self.stats["retries"] += 1
            if rnd + 1 < self.ROUNDS:
                delay = self.BACKOFF[min(rnd, len(self.BACKOFF) - 1)] + random.random() * 1.5
                self._note(
                    f"Every Google Translate route failed – waiting {delay:.0f}s, then trying again ({rnd + 1}/{self.ROUNDS - 1})",
                    short=f"retrying in {delay:.0f}s",
                )
                self._sleep(delay)
        err = self._fatal or self._summarize(last)
        self._fatal = err
        raise err

    # -- Google: whole job -------------------------------------------------------- #
    def _chunks(self, prepared: List[tuple]) -> List[List[tuple]]:
        chunks, cur, chars = [], [], 0
        for item in prepared:
            ln = len(item[1])
            if cur and (len(cur) >= self.BATCH_MAX_ITEMS or chars + ln > self.BATCH_MAX_CHARS):
                chunks.append(cur)
                cur, chars = [], 0
            cur.append(item)
            chars += ln
        if cur:
            chunks.append(cur)
        return chunks

    def _run_pool(self, jobs: List[Callable[[], None]], workers: int) -> None:
        """Run callables in parallel; the first error stops everything immediately (no silent waiting)."""
        if not jobs:
            return
        pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(jobs))))
        futs = [pool.submit(fn) for fn in jobs]
        try:
            for f in futs:
                f.result()
        except BaseException as exc:
            if self._fatal is None and not isinstance(exc, _Stop):
                self._fatal = exc if isinstance(exc, Exception) else TranslationError(str(exc))
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        pool.shutdown(wait=True)

    def _google_stage(self, prepared, style, results, srcs, st, lock, progress) -> List[int]:
        """Translate one stage (placeholder style, or None = unprotected). Returns indices that failed."""
        failed: List[int] = []
        protected_ok = self.matcher is None or style is not None   # False only for the last-resort stage

        def make_job(chunk):
            def run():
                try:
                    raws = self._google_batch_raw([p for _, p, _ in chunk])
                except _Stop:
                    return
                local_fail, finished = [], 0
                for (i, _payload, mapping), raw in zip(chunk, raws):
                    if mapping is None:
                        out = ensure_khmer_terminal(_clean_khmer(raw))
                    else:
                        restored, ok = TermMatcher.restore(raw, mapping, style)
                        if not ok:
                            local_fail.append(i)
                            continue
                        out = ensure_khmer_terminal(_clean_khmer(restored))
                    results[i] = out
                    finished += 1
                    if protected_ok:
                        self._cput(self._ckey(srcs[i]), out)
                    else:
                        with self._lock:
                            self.stats["fallback_unprotected"] += 1
                with lock:
                    st["done"] += finished
                    failed.extend(local_fail)
                    if progress:
                        progress(st["done"], st["total"])
            return run

        self._run_pool([make_job(c) for c in self._chunks(prepared)], self.WORKERS)
        return failed

    def _translate_google(self, texts, progress, cancelled, status) -> List[str]:
        n = len(texts)
        results: List[Optional[str]] = [None] * n
        srcs = [normalize_ws(t) for t in texts]
        st = {"done": 0, "total": n}
        lock = threading.Lock()
        pending: List[int] = []
        for i, s in enumerate(srcs):
            if not s:
                results[i] = ""
                st["done"] += 1
                continue
            hit = self._cget(self._ckey(s))
            if hit:
                results[i] = hit
                st["done"] += 1
            else:
                pending.append(i)

        self._fatal = None
        self._last_ok = time.monotonic()
        self._last_errors = {}
        self._status = (lambda m: status(f"{st['done']}/{n} · {m}")) if status else (lambda m: None)
        if progress:
            progress(st["done"], n)
        if not pending:
            return [r or "" for r in results]

        t0 = time.monotonic()
        cached = n - len(pending)
        self.log(
            f"Google Translate: {len(pending)} line(s) to translate"
            + (f" ({cached} already in the cache)" if cached else "")
            + f" – up to {self.BATCH_MAX_ITEMS} lines per request."
        )

        stages: List[Optional[Tuple[str, str]]] = list(TermMatcher.STYLES) if self.matcher is not None else []
        stages.append(None)
        for si, style in enumerate(stages):
            if not pending or cancelled():
                break
            prepared = []
            for i in pending:
                payload, mapping = srcs[i], None
                if style is not None:
                    protected, m = self.matcher.protect(srcs[i], style)
                    if m:
                        payload, mapping = protected, m
                prepared.append((i, payload, mapping))
            pending = self._google_stage(prepared, style, results, srcs, st, lock, progress)
            if pending and si < len(stages) - 1:
                self.log(f"{len(pending)} line(s) lost their term placeholders – trying again with a different marker …")

        if self.stats["fallback_unprotected"]:
            self.log(f"⚠ {self.stats['fallback_unprotected']} segment(s) could not keep placeholders; translated without term protection.")
        if not cancelled():
            self.log(
                f"Google Translate finished in {time.monotonic() - t0:.1f}s "
                f"({self.stats['requests']} request(s) via {self._route_used or '—'}, "
                f"{self.stats['failed_requests']} failed attempt(s))."
            )
        return [r or "" for r in results]

    def _google_one(self, text: str) -> str:
        """Translate a single line (used to fill gaps left by the LLM engine)."""
        return self._translate_google([text], None, lambda: False, None)[0]

    # -- connection test (Settings → Test Google Translate) ------------------------ #
    def diagnose(self, timeout: float = 7.0) -> dict:
        sample = "Hello! This dashboard uses an API and a Python server."
        combos = self._combos()
        rows: List[Optional[dict]] = [None] * len(combos)
        tmo = httpx.Timeout(timeout, connect=min(5.0, timeout))

        def probe(k: int) -> None:
            route, cname, client = combos[k]
            t0 = time.monotonic()
            row = {"route": route.name, "mode": cname, "ok": False, "ms": None, "status": None,
                   "kind": None, "error": None, "sample": None}
            try:
                out = self._call_route(client, route, [sample], timeout=tmo)
                row.update(ok=True, status=200, sample=(out[0] or "")[:80])
            except _RouteError as e:
                row.update(kind=e.kind, error=e.detail)
                m = re.match(r"HTTP (\d{3})", e.detail)
                row["status"] = int(m.group(1)) if m else None
            except Exception as e:  # never let the test itself crash
                row.update(kind="net", error=f"{type(e).__name__}: {str(e)[:100]}")
            row["ms"] = int((time.monotonic() - t0) * 1000)
            rows[k] = row

        with ThreadPoolExecutor(max_workers=max(1, len(combos))) as pool:
            list(pool.map(probe, range(len(combos))))
        results = [r for r in rows if r]
        ok = sum(1 for r in results if r["ok"])
        if ok == len(results):
            verdict = "ok"
        elif ok:
            verdict = "partial"
        else:
            kinds = {r["kind"] for r in results}
            verdict = "rate_limited" if kinds == {"rate"} else "network" if kinds == {"net"} else "failed"
        return {"verdict": verdict, "ok_count": ok, "total": len(results), "results": results,
                "proxies": system_proxies()}

    # -- LLM (OpenAI-compatible) -------------------------------------------- #
    def _llm_system_prompt(self) -> str:
        terms = ", ".join(self.glossary_terms[:400]) if self.cfg.keep_terms else ""
        keep = (
            "Keep ALL technical, professional, scientific, business, brand, product, programming and software terms in "
            "English using Latin script (never transliterate them into Khmer script). Examples: API, dashboard, server, "
            "machine learning, Python, YouTube, SEO, startup. Also keep acronyms, code identifiers, file names and URLs "
            "exactly as written. "
            + (f"Always keep these terms in English: {terms}. " if terms else "")
            if self.cfg.keep_terms
            else "Translate everything into Khmer. "
        )
        name = LANGS[self.lang].name
        if self.lang != "en" and self.cfg.keep_terms:
            table = builtin_terms(self.lang)
            shown = [f"{w}→{table[w]}" for w in _LLM_EXAMPLES.get(self.lang, ()) if w in table]
            keep += (
                f"The source is {name}: technical, product and brand words that are written in {name} "
                f"({', '.join(shown)}) must ALSO be written in English with Latin script. "
            )
        return (
            f"You are a professional {name}→Khmer dubbing translator. You receive consecutive lines of one video "
            f"transcript (JSON items with an id and the {name} text in the field \"{self.lang}\") and translate each line "
            "into natural, fluent SPOKEN Khmer (ភាសាខ្មែរ) suitable for a narrator. "
            + keep
            + "Keep numbers as digits. Do not add or omit information. Keep each translation about the same length as the "
            "source so the dubbing fits the timing. Reply with JSON only, in the form "
            '{"translations":[{"id":<number>,"km":"<Khmer text>"}]} and include every id.'
        )

    def _llm_call(self, batch: List[tuple]) -> Dict[int, str]:
        base = self.cfg.llm_base_url.rstrip("/")
        if not base or not self.cfg.llm_model:
            raise TranslationError("AI / LLM engine needs a Base URL and a Model name (Settings → AI Translation).")
        payload = json.dumps([{"id": i, self.lang: t} for i, t in batch], ensure_ascii=False)
        body = {
            "model": self.cfg.llm_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": self._llm_system_prompt()},
                {"role": "user", "content": payload},
            ],
            "response_format": {"type": "json_object"},
        }
        host = urlsplit(base).hostname or ""
        if host.endswith("generativelanguage.googleapis.com") and self.cfg.llm_model.lower().startswith("gemini-3"):
            body["reasoning_effort"] = "minimal"  # Gemini 3 "thinks" by default – translation does not need it
        headers = {"Authorization": f"Bearer {self.cfg.llm_api_key}", "Content-Type": "application/json"}
        url = f"{base}/chat/completions"
        last = None
        for attempt in range(4):
            self._guard(stall=False)
            try:
                r = self._client.post(url, headers=headers, json=body, timeout=120)
                if r.status_code in (400, 404, 422):
                    txt = r.text.lower()
                    order = ("response_format", "reasoning_effort") if ("response_format" in txt or "json" in txt) else ("reasoning_effort", "response_format")
                    dropped = next((k for k in order if k in body), None)
                    if dropped:  # this provider may not know that optional parameter → try again without it
                        body.pop(dropped, None)
                        continue
                    raise TranslationError(
                        f"The LLM API rejected the request (HTTP {r.status_code}): {r.text[:200].strip()} "
                        "– check Base URL and Model in Settings → AI Translation."
                    )
                if r.status_code in (429, 500, 502, 503, 504):
                    last = f"HTTP {r.status_code}"
                    delay = 2 * (attempt + 1)
                    self._note(f"LLM request failed ({last}) – trying again in {delay}s ({attempt + 1}/4)", short=f"{last}, retrying")
                    self._sleep(delay, stall=False)
                    continue
                if r.status_code in (401, 403):
                    raise TranslationError("The LLM API rejected the API key (HTTP %d). Check Settings → AI Translation." % r.status_code)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                data = _extract_json(content)
                if isinstance(data, dict) and "translations" in data:
                    data = data["translations"]
                out: Dict[int, str] = {}
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "id" in item:
                            out[int(item["id"])] = str(item.get("km") or item.get("text") or "")
                elif isinstance(data, dict):
                    for k, v in data.items():
                        if str(k).isdigit():
                            out[int(k)] = str(v)
                return out
            except (TranslationError, _Stop):
                raise
            except Exception as exc:  # network / parse errors → retry
                last = f"{type(exc).__name__}: {exc}"
                delay = 1.5 * (attempt + 1)
                self._note(f"LLM request failed ({last[:120]}) – trying again in {delay:.0f}s ({attempt + 1}/4)", short="retrying")
                self._sleep(delay, stall=False)
        raise TranslationError(f"LLM translation failed ({last}).")

    def _translate_llm(self, texts, progress, cancelled, status) -> List[str]:
        n = len(texts)
        results: List[str] = [""] * n
        items = []
        st = {"done": 0}
        for i, t in enumerate(texts):
            src = normalize_ws(t)
            hit = self._cget(self._ckey(src)) if src else None
            if hit:
                results[i] = hit
                st["done"] += 1
            elif src:
                items.append((i, src))
        self._fatal = None
        self._last_ok = time.monotonic()
        self._status = (lambda m: status(f"{st['done']}/{n} · {m}")) if status else (lambda m: None)
        if progress and st["done"]:
            progress(st["done"], n)

        batches, cur, cur_chars = [], [], 0
        for it in items:
            if cur and (len(cur) >= 12 or cur_chars + len(it[1]) > 3500):
                batches.append(cur)
                cur, cur_chars = [], 0
            cur.append(it)
            cur_chars += len(it[1])
        if cur:
            batches.append(cur)

        lock = threading.Lock()
        gaps: List[tuple] = []

        def make_job(b):
            def run():
                try:
                    self._guard(stall=False)
                    got = self._llm_call(b)
                except _Stop:
                    return
                with lock:
                    for i, src in b:
                        km = got.get(i)
                        if km and km.strip():
                            results[i] = ensure_khmer_terminal(_clean_khmer(km))
                            self._cput(self._ckey(src), results[i])
                        else:
                            gaps.append((i, src))
                    st["done"] += len(b)
                    if progress:
                        progress(st["done"], n)
            return run

        self._run_pool([make_job(b) for b in batches], self.LLM_WORKERS)
        for i, src in gaps:  # fill any gap with Google so the dub is never silent
            if cancelled():
                break
            try:
                results[i] = self._google_one(src)
            except Exception:
                results[i] = src
        return results

    def test_llm(self) -> str:
        self._fatal = None
        self._last_ok = time.monotonic()
        out = self._llm_call([(1, "Hello! This dashboard uses an API and a Python server.")])
        if 1 not in out:
            raise TranslationError("The model replied, but not in the expected JSON format.")
        return out[1]
