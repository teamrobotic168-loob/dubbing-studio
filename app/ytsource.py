"""YouTube access: link parsing, video info, transcript (English / Chinese / Korean), video/audio download.

Transcript strategy (first success wins):
  1. youtube-transcript-api  (fast, no download)
  2. yt-dlp subtitles        (json3)
  3. (pipeline) Whisper on downloaded audio – only if enabled and installed

Which caption track is used: the language chosen in the dashboard (English / 中文 / 한국어) or, with "Auto",
the language of the video (automatic captions are always in the spoken language; see langs.pick_caption_lang).
Machine-TRANSLATED tracks (e.g. English captions made from Korean speech) are never used as a source.

YouTube often blocks data-centre IPs ("Sign in to confirm you're not a bot"). On a normal home
connection this works; otherwise use browser cookies (Settings) or paste the transcript manually.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import httpx

from .audio import ffmpeg_exe, probe_media
from .langs import AUTO, LANGS, base_lang, caption_summary, lang_list_text, normalize_lang, pick_caption_lang, track_sort_key
from .transcript import Seg, from_snippets, parse_json3, parse_srt_vtt


class SourceError(Exception):
    """Error with a stable `code` the UI can translate."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def extract_video_id(text: str) -> Optional[str]:
    s = (text or "").strip()
    if _ID_RE.match(s):
        return s
    if not s:
        return None
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I):
        s = "https://" + s
    try:
        u = urlparse(s)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    host = re.sub(r"^(www\.|m\.)", "", host)
    vid = None
    if host == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com", "gaming.youtube.com", "youtube-nocookie.com"):
        if u.path.rstrip("/") == "/watch":
            vid = (parse_qs(u.query).get("v") or [None])[0]
        else:
            m = re.match(r"^/(?:shorts|live|embed|v|e)/([A-Za-z0-9_-]{11})", u.path)
            vid = m.group(1) if m else None
    return vid if vid and _ID_RE.match(vid) else None


def canonical_url(vid: str) -> str:
    return f"https://www.youtube.com/watch?v={vid}"


def _is_block_message(msg: str) -> bool:
    m = (msg or "").lower()
    return any(k in m for k in ("sign in to confirm", "not a bot", "blocking requests", "ip has been blocked", "requestblocked", "ipblocked", "http error 429", "too many requests"))


# --------------------------------------------------------------------------- #
# yt-dlp helpers
# --------------------------------------------------------------------------- #
def _ydl_opts(cookies_browser: str = "", proxy: str = "", **extra) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 3,
        "ffmpeg_location": ffmpeg_exe(),
    }
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    if proxy:
        opts["proxy"] = proxy
    opts.update(extra)
    return opts


def _ytdlp_info(url: str, cookies_browser: str = "", proxy: str = "") -> dict:
    import yt_dlp

    with yt_dlp.YoutubeDL(_ydl_opts(cookies_browser, proxy, skip_download=True)) as ydl:
        return ydl.extract_info(url, download=False)


# --------------------------------------------------------------------------- #
# video info (for the preview card)
# --------------------------------------------------------------------------- #
def _oembed(vid: str) -> dict:
    r = httpx.get(
        "https://www.youtube.com/oembed",
        params={"url": canonical_url(vid), "format": "json"},
        headers={"User-Agent": _UA},
        timeout=10,
        follow_redirects=True,
    )
    if r.status_code == 200:
        j = r.json()
        return {"title": j.get("title"), "channel": j.get("author_name"), "thumbnail": j.get("thumbnail_url")}
    if r.status_code in (400, 404):
        raise SourceError("VIDEO_UNAVAILABLE", "This video does not exist or is private.")
    return {}


def _api(proxy: str = ""):
    from youtube_transcript_api import YouTubeTranscriptApi

    if proxy:
        try:
            from youtube_transcript_api.proxies import GenericProxyConfig

            return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy))
        except Exception:
            pass
    return YouTubeTranscriptApi()


def _captions_overview(vid: str, proxy: str = "") -> dict:
    """Caption tracks the video really has: {"entries": [(code, auto_generated), …]}."""
    tl = _api(proxy).list(vid)
    return {"entries": [(t.language_code, bool(t.is_generated)) for t in tl]}


def _finish_captions(entries: List[Tuple[str, bool]], title: str) -> dict:
    """Shape of info["captions"] for the dashboard:
    {"langs": {"en": "manual"|"auto"|None, "zh": …, "ko": …}, "detected": "en"|"zh"|"ko"|None,
     "english": …(older field), "languages": ["ko (auto)", …]}"""
    summ = caption_summary(entries, title)
    return {
        "langs": summ["langs"],
        "detected": summ["detected"],
        "english": summ["langs"]["en"],
        "languages": lang_list_text(entries).split(", ") if entries else [],
    }


def get_video_info(url: str, cookies_browser: str = "", proxy: str = "") -> dict:
    vid = extract_video_id(url)
    if not vid:
        raise SourceError("INVALID_URL", "That does not look like a YouTube link.")
    info = {
        "id": vid,
        "url": canonical_url(vid),
        "title": None,
        "channel": None,
        "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "duration": None,
        "captions": None,   # {"langs": {"en": "manual"|"auto"|None, "zh": …, "ko": …}, "detected": "ko"|None, "languages": [...]}
        "blocked": False,
    }
    errors: List[str] = []
    unavailable: Optional[SourceError] = None

    def run_oembed():
        return _oembed(vid)

    def run_caps():
        return _captions_overview(vid, proxy)

    def run_ytdlp():
        d = _ytdlp_info(canonical_url(vid), cookies_browser, proxy)
        return {
            "title": d.get("title"),
            "channel": d.get("uploader") or d.get("channel"),
            "thumbnail": d.get("thumbnail"),
            "duration": d.get("duration"),
            "entries": [(code, gen) for code, gen, _k, _src in _ytdlp_tracks(d)],
        }

    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {"oembed": ex.submit(run_oembed), "caps": ex.submit(run_caps), "ytdlp": ex.submit(run_ytdlp)}
        results: Dict[str, dict] = {}
        for name, f in futs.items():
            try:
                results[name] = f.result(timeout=35)
            except SourceError as e:
                unavailable = unavailable or e
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                errors.append(f"{name}: {msg[:200]}")
                if _is_block_message(msg):
                    info["blocked"] = True

    if "oembed" in results:
        for k in ("title", "channel", "thumbnail"):
            if results["oembed"].get(k):
                info[k] = results["oembed"][k]
    if "ytdlp" in results:
        y = results["ytdlp"]
        for k in ("title", "channel", "duration"):
            if y.get(k):
                info[k] = y[k]
        if y.get("thumbnail") and not results.get("oembed"):
            info["thumbnail"] = y["thumbnail"]
        if "caps" not in results:
            info["captions"] = _finish_captions(y.get("entries") or [], info.get("title") or "")
    if "caps" in results:
        info["captions"] = _finish_captions(results["caps"]["entries"], info.get("title") or "")

    if not results:
        if unavailable:
            raise unavailable
        raise SourceError("YT_BLOCKED" if info["blocked"] else "INFO_FAILED", "; ".join(errors) or "Could not reach YouTube.")
    info["notes"] = errors
    return info


# --------------------------------------------------------------------------- #
# transcript
# --------------------------------------------------------------------------- #
def _no_captions(lang: str, entries: List[Tuple[str, bool]]) -> SourceError:
    want = "English, Chinese or Korean" if lang == AUTO else LANGS[lang].name
    return SourceError("NO_CAPTIONS", f"No {want} captions on this video (available: {lang_list_text(entries)}).")


def _transcript_via_api(vid: str, proxy: str, log: Callable[[str], None], lang: str = AUTO, title: str = "") -> Tuple[List[Seg], dict]:
    from youtube_transcript_api import _errors as yte

    api = _api(proxy)
    try:
        tl = api.list(vid)
    except Exception as exc:
        raise _wrap_api_error(exc, yte) from exc

    tracks = [(t.language_code, bool(t.is_generated), t) for t in tl]
    entries = [(c, g) for c, g, _t in tracks]
    chosen_lang = pick_caption_lang(entries, lang, title)
    if chosen_lang is None:
        raise _no_captions(lang, entries)
    cands = sorted((x for x in tracks if base_lang(x[0]) == chosen_lang), key=lambda x: track_sort_key(x[0], x[1]))
    code, generated, chosen = cands[0]
    meta = {"source": "youtube-transcript-api", "generated": generated, "language": chosen_lang, "track": code}
    try:
        fetched = chosen.fetch()
    except Exception as exc:
        raise _wrap_api_error(exc, yte) from exc
    segs = from_snippets(list(fetched))
    log(f"Transcript: {len(segs)} caption lines ({'auto-generated' if generated else 'manual'} {LANGS[chosen_lang].name}, track {code})")
    return segs, meta


def _wrap_api_error(exc: Exception, yte) -> SourceError:
    name = type(exc).__name__
    msg = str(exc)
    if name in ("RequestBlocked", "IpBlocked") or _is_block_message(msg):
        return SourceError("YT_BLOCKED", "YouTube is blocking requests from this IP address.")
    if name in ("TranscriptsDisabled",):
        return SourceError("NO_CAPTIONS", "Captions are disabled for this video.")
    if name in ("NoTranscriptFound",):
        return SourceError("NO_CAPTIONS", "No captions found for this video.")
    if name in ("VideoUnavailable", "VideoUnplayable", "InvalidVideoId"):
        return SourceError("VIDEO_UNAVAILABLE", "This video is unavailable or private.")
    if name == "AgeRestricted":
        return SourceError("AGE_RESTRICTED", "This video is age-restricted; use browser cookies in Settings.")
    return SourceError("TRANSCRIPT_FAILED", f"{name}: {msg[:300]}")


_PLAIN_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-(?:Hans|Hant|CN|TW|HK|SG|US|GB))?$")


def _ytdlp_tracks(info: dict) -> List[Tuple[str, bool, str, str]]:
    """Caption tracks of a yt-dlp info dict → [(language code, auto_generated, key, "subtitles"|"automatic_captions")].

    yt-dlp lists an automatic translation of the captions into EVERY language under `automatic_captions`
    (and "en-ko" = English made from manual Korean subtitles). Those are not the video's language, so only the
    original-language track ("ko-orig") counts. Older yt-dlp versions have no "-orig": then the video's
    `language` decides, and without it every plain code is taken (the old behaviour).
    """
    out: List[Tuple[str, bool, str, str]] = []
    for k in (info.get("subtitles") or {}):
        out.append((k, False, k, "subtitles"))
    auto = info.get("automatic_captions") or {}
    orig = [k for k in auto if k.endswith("-orig")]
    if orig:
        out += [(k[:-5], True, k, "automatic_captions") for k in orig]
    else:
        hint = base_lang(info.get("language"))
        for k in auto:
            if not _PLAIN_CODE_RE.match(k):
                continue
            if hint and base_lang(k) != hint:
                continue
            out.append((k, True, k, "automatic_captions"))
    return out


def _transcript_via_ytdlp(
    vid: str, cookies_browser: str, proxy: str, log: Callable[[str], None], lang: str = AUTO, title: str = ""
) -> Tuple[List[Seg], dict]:
    try:
        info = _ytdlp_info(canonical_url(vid), cookies_browser, proxy)
    except Exception as exc:
        msg = str(exc)
        if _is_block_message(msg):
            raise SourceError("YT_BLOCKED", "YouTube asked yt-dlp to sign in (bot check).") from exc
        if "private" in msg.lower() or "unavailable" in msg.lower():
            raise SourceError("VIDEO_UNAVAILABLE", "This video is unavailable or private.") from exc
        raise SourceError("TRANSCRIPT_FAILED", msg[:300]) from exc

    tracks = _ytdlp_tracks(info)
    entries = [(c, g) for c, g, _k, _src in tracks]
    chosen_lang = pick_caption_lang(entries, lang, title or info.get("title") or "")
    if chosen_lang is None:
        raise _no_captions(lang, entries)

    def pick_format(formats: list) -> Optional[Tuple[str, dict]]:
        for want in ("json3", "srv3", "vtt", "srt"):
            for f in formats or []:
                if f.get("ext") == want and f.get("url"):
                    return want, f
        return None

    cands = sorted((x for x in tracks if base_lang(x[0]) == chosen_lang), key=lambda x: track_sort_key(x[0], x[1]))
    for code, generated, key, source in cands:
        got = pick_format((info.get(source) or {}).get(key) or [])
        if not got:
            continue
        ext, f = got
        r = httpx.get(f["url"], headers={"User-Agent": _UA}, timeout=30, follow_redirects=True)
        if r.status_code != 200 or not r.text.strip():
            continue
        if ext == "json3":
            segs = parse_json3(r.text)
        elif ext in ("vtt", "srt"):
            segs = parse_srt_vtt(r.text)
        else:
            continue
        if segs:
            log(f"Transcript via yt-dlp: {len(segs)} caption lines ({'auto' if generated else 'manual'} {LANGS[chosen_lang].name}, track {code})")
            return segs, {"source": "yt-dlp", "generated": generated, "language": chosen_lang, "track": code, "duration": info.get("duration")}
    raise _no_captions(lang, entries)


def fetch_transcript(
    vid: str,
    cookies_browser: str = "",
    proxy: str = "",
    log: Callable[[str], None] = lambda m: None,
    lang: str = AUTO,
    title: str = "",
) -> Tuple[List[Seg], dict]:
    """Captions of the video in `lang` ('auto' | 'en' | 'zh' | 'ko'). meta["language"] is the language used."""
    lang = normalize_lang(lang)
    errors: List[SourceError] = []
    for fn in (
        lambda: _transcript_via_api(vid, proxy, log, lang, title),
        lambda: _transcript_via_ytdlp(vid, cookies_browser, proxy, log, lang, title),
    ):
        try:
            return fn()
        except SourceError as e:
            errors.append(e)
            log(f"  · transcript strategy failed: [{e.code}] {e.message}")
            if e.code in ("VIDEO_UNAVAILABLE",):
                raise
        except Exception as exc:  # unexpected
            errors.append(SourceError("TRANSCRIPT_FAILED", f"{type(exc).__name__}: {exc}"))
    # classify: a strategy that *reached* YouTube and found nothing is the most informative answer
    for code in ("NO_CAPTIONS", "AGE_RESTRICTED", "YT_BLOCKED"):
        for e in errors:
            if e.code == code:
                raise e
    raise errors[-1] if errors else SourceError("TRANSCRIPT_FAILED", "Unknown error")


# --------------------------------------------------------------------------- #
# downloads (video for MP4 export, audio for Whisper)
# --------------------------------------------------------------------------- #
def _find_download(out_dir: Path, stem: str) -> Optional[Path]:
    for p in sorted(out_dir.glob(f"{stem}.*")):
        if p.suffix.lower() not in (".part", ".ytdl", ".json"):
            return p
    return None


VIDEO_HEIGHTS = (480, 720, 1080)
DEFAULT_VIDEO_HEIGHT = 1080          # v1.4: up to 1080p (v1.3 and older: 720p)
LEGACY_VIDEO_HEIGHT = 720            # what a download without a marker file (made by v1.3 or older) was limited to


def clean_video_height(v) -> int:
    """The tallest picture the MP4 export may download: 480 / 720 / 1080 (anything else -> 1080)."""
    try:
        h = int(v)
    except (TypeError, ValueError):
        return DEFAULT_VIDEO_HEIGHT
    return h if h in VIDEO_HEIGHTS else DEFAULT_VIDEO_HEIGHT


def _marker_path(out_dir: Path) -> Path:
    return out_dir / "source.json"            # ('.json' files are never mistaken for the video by _find_download)


def _read_marker(out_dir: Path) -> dict:
    try:
        import json
        d = json.loads(_marker_path(out_dir).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _reusable(existing: Path, out_dir: Path, with_audio: bool, max_height: int) -> bool:
    """Is the video that is already on disk what is wanted now?  It must have been downloaded with the SAME height limit
    (the user chose 720p or 1080p for the MP4: a 720p file is replaced when 1080p is wanted, and the other way round, so the MP4
    has the quality that was chosen) and, when the original sound is needed, it must have sound."""
    marker = _read_marker(out_dir)
    try:
        have_h = int(marker.get("max_height") or LEGACY_VIDEO_HEIGHT)
    except (TypeError, ValueError):
        have_h = LEGACY_VIDEO_HEIGHT
    if have_h != max_height:
        return False
    if with_audio:
        have_audio = marker.get("with_audio")
        if have_audio is None:                  # downloaded by an older version: look inside the file
            try:
                have_audio = bool(probe_media(existing).get("has_audio"))
            except Exception:
                have_audio = False
        if not have_audio:
            return False
    return True


def download_video(
    vid: str,
    out_dir: Path,
    cookies_browser: str = "",
    proxy: str = "",
    with_audio: bool = False,
    max_height: int = DEFAULT_VIDEO_HEIGHT,
    progress: Optional[Callable[[float], None]] = None,
) -> Path:
    import json

    import yt_dlp

    max_height = clean_video_height(max_height)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = _find_download(out_dir, "source")
    if existing and existing.stat().st_size > 10_000:
        if _reusable(existing, out_dir, with_audio, max_height):
            return existing
        for f in out_dir.glob("source.*"):          # smaller than wanted / no sound: download it again
            try:
                f.unlink()
            except OSError:
                pass

    if with_audio:
        fmt = f"bv*[height<={max_height}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={max_height}]+ba/b[height<={max_height}]/b"
    else:
        fmt = f"bv*[height<={max_height}][vcodec^=avc1]/bv*[height<={max_height}]/b[height<={max_height}]/bv*/b"

    def hook(d):
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                progress(min(0.99, d.get("downloaded_bytes", 0) / total))

    opts = _ydl_opts(
        cookies_browser, proxy,
        format=fmt,
        merge_output_format="mp4",
        outtmpl=str(out_dir / "source.%(ext)s"),
        noprogress=True,
        progress_hooks=[hook],
        concurrent_fragment_downloads=4,
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([canonical_url(vid)])
    except Exception as exc:
        msg = str(exc)
        if _is_block_message(msg):
            raise SourceError("YT_BLOCKED", "YouTube blocked the video download (bot check).") from exc
        raise SourceError("DOWNLOAD_FAILED", msg[:400]) from exc
    p = _find_download(out_dir, "source")
    if not p:
        raise SourceError("DOWNLOAD_FAILED", "yt-dlp finished but no video file was found.")
    try:
        _marker_path(out_dir).write_text(json.dumps({"max_height": max_height, "with_audio": bool(with_audio)}), encoding="utf-8")
    except OSError:
        pass
    return p


def download_audio(
    vid: str,
    out_dir: Path,
    cookies_browser: str = "",
    proxy: str = "",
    progress: Optional[Callable[[float], None]] = None,
) -> Path:
    import yt_dlp

    out_dir.mkdir(parents=True, exist_ok=True)
    existing = _find_download(out_dir, "audio")
    if existing and existing.stat().st_size > 10_000:
        return existing

    def hook(d):
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                progress(min(0.99, d.get("downloaded_bytes", 0) / total))

    opts = _ydl_opts(
        cookies_browser, proxy,
        format="bestaudio[ext=m4a]/bestaudio/best",
        outtmpl=str(out_dir / "audio.%(ext)s"),
        noprogress=True,
        progress_hooks=[hook],
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([canonical_url(vid)])
    except Exception as exc:
        msg = str(exc)
        if _is_block_message(msg):
            raise SourceError("YT_BLOCKED", "YouTube blocked the audio download (bot check).") from exc
        raise SourceError("DOWNLOAD_FAILED", msg[:400]) from exc
    p = _find_download(out_dir, "audio")
    if not p:
        raise SourceError("DOWNLOAD_FAILED", "yt-dlp finished but no audio file was found.")
    return p
