"""FastAPI application: REST API + static dashboard."""
from __future__ import annotations

import asyncio
import base64
import errno
import hashlib
import json
import mimetypes
import os
import platform
import re
import shutil
import sys
import threading
import time
import uuid
from importlib import metadata
from pathlib import Path
from typing import Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.requests import ClientDisconnect

from . import __version__, asr, audio, autovoice, frame, hardsub
from .config import (
    CACHE_DIR,
    DATA_DIR,
    DOWNLOADABLE_FILES,
    EN_VOICES,
    KHMER_VOICES,
    STATIC_DIR,
    UPLOADS_DIR,
)
from .glossary import (
    DEFAULT_GLOSSARY_TEXT,
    load_glossary_text,
    parse_glossary_maps,
    parse_glossary_text,
    reset_glossary,
    save_glossary_text,
)
from .langs import LANGS, normalize_lang
from .jobs import JobManager
from .manualtr import DEFAULT_SIZE, build_prompt, parse_reply
from .mediafile import MediaFile
from .pipeline import clean_segment_edits, local_media_of, run_detect_speakers, run_dub_job, run_regenerate, run_remake_video, run_tts_job, sanitize_params
from .translate import TranslateConfig, Translator, TranslationError
from . import uploads, voxpresets, voxvoices, whisper_setup
from .tts import TTSError, VoiceSettings, preview_audio
from .vox import VoxError, manager as vox_manager
from .ytsource import SourceError, clean_video_height, extract_video_id, get_video_info

app = FastAPI(title="V_Heang Studio", version=__version__)
MANAGER = JobManager(workers=2)
PREVIEW_DIR = CACHE_DIR / "preview"
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
uploads.prune()            # uploads nobody turned into a job (or used more than a day ago)


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _ver(pkg: str) -> Optional[str]:
    try:
        return metadata.version(pkg)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
_BOOT_STAMP = str(int(time.time()))
_UI_MARKERS = (
    ("js/app.js", r"KDS_UI_VERSION\s*=\s*'([^']+)'"),
    ("js/i18n.js", r"I18N_VERSION\s*=\s*'([^']+)'"),
    ("index.html", r'name="kds-ui"\s+content="([^"]+)"'),
)
_ui_memo: dict = {"sig": None, "ver": None, "bad": []}


def _ui_state() -> dict:
    """Fingerprint of the UI files (their content + the app version) and the list of UI files that belong to another version.

    The fingerprint goes into every asset URL (?v=...), so a browser can never keep using an old app.js / i18n.js /
    app.css.  (The first scheme used the newest file time.  That value can repeat between versions - and then the
    browser silently kept the old scripts and showed raw keys such as "set.vox.install" with dead buttons.)
    """
    try:
        files = sorted(p for p in STATIC_DIR.rglob("*") if p.is_file() and p.suffix in (".js", ".css", ".html"))
        sig = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files)
        if _ui_memo["sig"] != sig:
            h = hashlib.sha1(__version__.encode())
            for p in files:
                h.update(p.name.encode("utf-8"))
                h.update(p.read_bytes())
            bad = []
            for rel, rx in _UI_MARKERS:
                try:
                    m = re.search(rx, (STATIC_DIR / rel).read_text(encoding="utf-8", errors="ignore")[:6000])
                    found = m.group(1) if m else "?"
                except OSError:
                    found = "missing"
                if found != __version__:
                    bad.append(f"{rel}={found}")
            _ui_memo.update(sig=sig, ver=f"{__version__}-{h.hexdigest()[:10]}", bad=bad)
        return _ui_memo
    except Exception:
        return {"ver": f"{__version__}-{_BOOT_STAMP}", "bad": []}


def _asset_version() -> str:
    return str(_ui_state()["ver"])


def _page_banner(bad: list) -> str:
    """Shown on top of the page (server-side, so it works even when the scripts are wrong) for a mixed / partial extraction."""
    if not bad:
        return ""
    return (
        '<div style="position:sticky;top:0;z-index:99999;background:#b42318;color:#fff;padding:10px 16px;'
        'font:600 14px/1.55 system-ui,sans-serif">'
        f"⚠ ឯកសារ UI មិនត្រូវនឹង server (server {__version__} · {', '.join(bad)})។ "
        "សូម extract ZIP ទាំងមូលពីលើ folder ចាស់ (Replace all) រួចបិទ-បើក start.bat ម្តងទៀត ហើយចុច Ctrl+Shift+R។"
        '<br><span style="font-weight:400">The UI files do not match the server. Extract the whole ZIP over the old folder '
        "(Replace all), restart start.bat and press Ctrl+Shift+R.</span></div>"
    )


@app.get("/", response_class=HTMLResponse)
def index():
    st = _ui_state()
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("{{v}}", str(st["ver"])).replace("{{ver}}", __version__).replace("<!--KDS_BANNER-->", _page_banner(st["bad"]))
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


# ---- installable app (PWA, v1.11): the manifest, the service worker and the page for "the server is not running" are served from the ROOT
#      (a service worker can only control the addresses below its own path).  They work the same when the dashboard is hosted online one day (https).
@app.get("/manifest.webmanifest")
def pwa_manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def pwa_service_worker():
    js = (STATIC_DIR / "sw.js").read_text(encoding="utf-8").replace("{{ver}}", __version__)       # a new version = a new file = the browser updates it
    return Response(js, media_type="text/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/offline.html", response_class=HTMLResponse)
def pwa_offline_page():
    html = (STATIC_DIR / "offline.html").read_text(encoding="utf-8")
    font = STATIC_DIR / "fonts" / "kantumruy-pro-khmer-wght-normal.woff2"
    face = ""
    if font.is_file():          # this page is shown when the server is OFF (the browser keeps its own copy), so the Khmer font travels INSIDE the page
        face = ('@font-face{font-family:"KDS Khmer";font-style:normal;font-weight:100 700;src:url(data:font/woff2;base64,' + base64.b64encode(font.read_bytes()).decode("ascii")
                + ') format("woff2-variations");unicode-range:U+1780-17FF,U+19E0-19FF,U+200C-200D,U+25CC}')
    return HTMLResponse(html.replace("/*{{khmer-font}}*/", face), headers={"Cache-Control": "no-cache"})


class _UiStatic(StaticFiles):
    """The dashboard is local, so UI files are always revalidated (fonts excepted): an updated file can never stay hidden."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if not path.lower().endswith((".woff", ".woff2", ".ttf", ".otf")):
            resp.headers["Cache-Control"] = "no-cache"
        return resp


app.mount("/static", _UiStatic(directory=str(STATIC_DIR)), name="static")

_bad_ui = _ui_state()["bad"]
if _bad_ui:
    print("\n  WARNING: the UI files do not match this version (" + ", ".join(_bad_ui) + ").\n"
          "  Extract the whole ZIP over the old folder (Replace all) and start again.\n", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# system / voices
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    st = _ui_state()
    return {"ok": True, "version": __version__, "assets": st["ver"], "ui_ok": not st["bad"]}


@app.get("/api/system")
def system():
    try:
        ff = {"ok": True, "path": audio.ffmpeg_exe(), "version": audio.ffmpeg_version()}
    except Exception as exc:
        ff = {"ok": False, "error": str(exc)}
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "ffmpeg": ff,
        "edge_tts": _ver("edge-tts"),
        "yt_dlp": _ver("yt-dlp"),
        "youtube_transcript_api": _ver("youtube-transcript-api"),
        "whisper": asr.whisper_installed(),
        "data_dir": str(DATA_DIR),
        "vox": _vox_brief(),
    }


def _vox_brief() -> dict:
    try:
        m = vox_manager()
        ws = m.worker_state() if m.installed() else {"state": "stopped"}
        return {"installed": m.installed(), "state": ws.get("state"), "device": ws.get("device"), "gpu": ws.get("gpu")}
    except Exception:
        return {"installed": False, "state": "stopped", "device": None, "gpu": None}


@app.get("/api/voices")
def voices():
    return {"khmer": KHMER_VOICES, "english": EN_VOICES,
            "vox": {"custom": voxvoices.list_custom(), "presets": voxpresets.list_presets(vox_manager().home)}}


PREVIEW_TEXT = {
    "km-KH-SreymomNeural": "សួស្តី! ខ្ញុំឈ្មោះ ស្រីមុំ។ ខ្ញុំអាចបកប្រែវីដេអូពីភាសាអង់គ្លេស ទៅជាភាសាខ្មែរ ដោយរក្សាពាក្យដូចជា API និង Machine Learning ជា English។",
    "km-KH-PisethNeural": "សួស្តី! ខ្ញុំឈ្មោះ ពិសិដ្ឋ។ ខ្ញុំអាចបកប្រែវីដេអូពីភាសាអង់គ្លេស ទៅជាភាសាខ្មែរ ដោយរក្សាពាក្យដូចជា API និង Machine Learning ជា English។",
}


@app.get("/api/voices/preview")
def voice_preview(
    voice: str = Query("km-KH-SreymomNeural"),
    rate: int = Query(0),
    pitch: int = Query(0),
    volume: int = Query(0),
    term_mode: str = Query("english_voice"),
    en_voice: str = Query(""),
    text: str = Query("", max_length=600),
):
    vs = VoiceSettings(voice=voice, rate=rate, pitch=pitch, volume=volume, term_mode=term_mode, en_voice=en_voice)
    text = (text or "").strip() or PREVIEW_TEXT.get(vs.voice, PREVIEW_TEXT["km-KH-SreymomNeural"])   # a line of the user's own text, or the sample
    key = hashlib.sha1(json.dumps([vs.voice, vs.rate, vs.pitch, vs.volume, vs.term_mode, vs.en_voice, text]).encode()).hexdigest()
    path = PREVIEW_DIR / f"{key}.mp3"
    if not path.exists():
        try:
            _, readings = parse_glossary_text(load_glossary_text())
            arr = asyncio.run(preview_audio(vs, text, readings))
            audio.encode_array(arr, path)
        except TTSError as exc:
            raise _err(502, "TTS_FAILED", str(exc))
    return MediaFile(path, media_type="audio/mpeg", headers={"Cache-Control": "max-age=3600"})


# --------------------------------------------------------------------------- #
# YouTube video info
# --------------------------------------------------------------------------- #
@app.post("/api/video/info")
def video_info(body: dict = Body(...)):
    url = (body.get("url") or "").strip()
    if not extract_video_id(url):
        raise _err(400, "INVALID_URL", "That does not look like a YouTube link.")
    yt = body.get("youtube") or {}
    try:
        return get_video_info(url, yt.get("cookies_browser") or "", yt.get("proxy") or "")
    except SourceError as e:
        status = 404 if e.code == "VIDEO_UNAVAILABLE" else 502
        raise _err(status, e.code, e.message)


# --------------------------------------------------------------------------- #
# uploaded video / audio files
# --------------------------------------------------------------------------- #
_UPLOAD_CHUNK = 4 * 1024 * 1024


def _finish_upload(uid: str, path: Path, name: str, size: int) -> dict:
    info = uploads.inspect(path)
    thumb = uploads.make_thumbnail(path, path.parent / "thumb.jpg", info["duration"]) if info["has_video"] else False
    info.update(id=uid, file=path.name, name=name, size=size, kind="video" if info["has_video"] else "audio", created=time.time(), thumb=thumb)
    uploads.save_info(uid, info)
    return info


@app.post("/api/uploads")
async def upload_media(request: Request, name: str = Query("", max_length=600)):
    """The raw bytes of a video / audio file (not a form: any size, nothing is held in memory) -> what is inside it.
    The browser sends the file as the request body and the file name in ?name=."""
    shown = uploads.display_name(name)
    ext = Path(shown).suffix.lower()
    if ext not in uploads.ALLOWED_EXT:
        raise _err(400, "BAD_FILE_TYPE", "This file type is not supported. Use a video (MP4, MKV, MOV, WEBM, AVI ...) or an audio file (MP3, WAV, M4A ...).")
    limit = uploads.max_upload_bytes()
    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        declared = 0
    if limit and declared > limit:
        raise _err(413, "UPLOAD_TOO_LARGE", f"This file is bigger than the limit of {limit / 2**30:.1f} GB (set KDS_MAX_UPLOAD_MB to change it).")
    await asyncio.to_thread(uploads.prune)
    try:
        free = shutil.disk_usage(UPLOADS_DIR).free
    except OSError:
        free = None
    if declared and free is not None and declared + 256 * 2**20 > free:
        raise _err(507, "DISK_FULL", f"There is not enough free disk space for this file ({declared / 2**30:.1f} GB needed, {free / 2**30:.1f} GB free).")
    uid = uploads.new_id()
    folder = uploads.folder(uid)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"upload{ext}"
    written = 0
    try:
        with open(path, "wb") as f:
            buf = bytearray()
            async for chunk in request.stream():
                if not chunk:
                    continue
                written += len(chunk)
                if limit and written > limit:
                    raise _err(413, "UPLOAD_TOO_LARGE", f"This file is bigger than the limit of {limit / 2**30:.1f} GB (set KDS_MAX_UPLOAD_MB to change it).")
                buf += chunk
                if len(buf) >= _UPLOAD_CHUNK:
                    await asyncio.to_thread(f.write, bytes(buf))
                    buf.clear()
            if buf:
                await asyncio.to_thread(f.write, bytes(buf))
        if written == 0:
            raise _err(400, "EMPTY_UPLOAD", "The file is empty.")
        info = await asyncio.to_thread(_finish_upload, uid, path, shown, written)
    except ClientDisconnect:                     # the browser cancelled the upload
        shutil.rmtree(folder, ignore_errors=True)
        return Response(status_code=499)
    except BaseException as exc:
        shutil.rmtree(folder, ignore_errors=True)
        if isinstance(exc, uploads.UploadError):
            raise _err(exc.status, exc.code, exc.message)
        if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            raise _err(507, "DISK_FULL", "The disk is full - the file could not be saved.")
        raise
    return uploads.public(uid, info)


@app.get("/api/uploads/{uid}")
def upload_info(uid: str, lang: str = Query("auto")):
    """Look at an upload again (e.g. after the language changed: which subtitle track would be used)."""
    try:
        return uploads.public(uid, uploads.load(uid), lang)
    except uploads.UploadError as e:
        raise _err(e.status, e.code, e.message)


@app.get("/api/uploads/{uid}/thumb")
def upload_thumb(uid: str):
    try:
        p = uploads.thumb_path(uid)
    except uploads.UploadError as e:
        raise _err(e.status, e.code, e.message)
    if not p:
        raise _err(404, "NOT_FOUND", "No thumbnail.")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.delete("/api/uploads/{uid}")
def upload_delete(uid: str):
    try:
        uploads.remove(uid)
    except uploads.UploadError as e:
        raise _err(e.status, e.code, e.message)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Whisper (speech recognition for videos without subtitles): one-click install
# --------------------------------------------------------------------------- #
@app.get("/api/whisper/status")
def whisper_status():
    return whisper_setup.installer.status()


@app.post("/api/whisper/install")
def whisper_install():
    if asr.whisper_installed():
        return {"started": False, "installed": True}
    if whisper_setup.disabled():
        raise _err(403, "WHISPER_INSTALL_DISABLED", "Installing is disabled on this server. Install Whisper on your own computer:  pip install faster-whisper")
    if not whisper_setup.installer.start():
        raise _err(409, "BUSY", "The installation is already running.")
    return {"started": True, "installed": False}


# --------------------------------------------------------------------------- #
# jobs
# --------------------------------------------------------------------------- #
@app.post("/api/jobs/dub")
def create_dub_job(body: dict = Body(...)):
    src = body.get("source") or {}
    if src.get("type") == "youtube":
        if not extract_video_id(src.get("url", "")):
            raise _err(400, "INVALID_URL", "That does not look like a YouTube link.")
    elif src.get("type") == "transcript":
        if not (src.get("text") or "").strip():
            raise _err(400, "EMPTY_TRANSCRIPT", "Please paste a transcript first.")
    elif src.get("type") == "upload":
        try:
            up_info = uploads.load(src.get("upload_id"))
        except uploads.UploadError as e:
            raise _err(e.status, e.code, e.message)
        if not isinstance(src.get("text", ""), str) or src.get("subs", "auto") not in ("auto", "whisper"):
            raise _err(400, "BAD_REQUEST", "source.text must be text and source.subs 'auto' or 'whisper'.")
    else:
        raise _err(400, "BAD_REQUEST", "source.type must be 'youtube', 'upload' or 'transcript'.")
    body.setdefault("translate", {})["glossary_text"] = load_glossary_text()
    title = (body.get("video") or {}).get("title") or ""
    if src.get("type") == "upload":
        title = str(src.get("title") or "").strip()[:120] or Path(up_info["name"]).stem[:120]
        body["video"] = None
    job = MANAGER.create("dub", sanitize_params(body), title=title)
    if src.get("type") == "upload":
        try:
            job.meta["upload"] = uploads.adopt(src["upload_id"], job.dir)
        except (uploads.UploadError, OSError) as e:
            MANAGER.delete(job.id)
            if isinstance(e, uploads.UploadError):
                raise _err(e.status, e.code, e.message)
            raise _err(500, "UPLOAD_FAILED", f"The uploaded file could not be attached to the job: {e}")
        mu = job.meta["upload"]
        job.video = {"id": None, "upload": True, "title": title, "filename": mu["name"], "duration": mu.get("duration"),
                     "width": mu.get("width"), "height": mu.get("height"), "has_video": mu["has_video"],
                     "thumbnail": f"/api/jobs/{job.id}/thumb" if mu.get("thumb") else None}
        job.save()
    MANAGER.submit(job, lambda j: run_dub_job(j, body))
    return {"id": job.id}


@app.post("/api/jobs/tts")
def create_tts_job(body: dict = Body(...)):
    text = (body.get("text") or "").strip()
    if not text:
        raise _err(400, "EMPTY_TEXT", "Please enter some text.")
    body.setdefault("translate", {})["glossary_text"] = load_glossary_text()
    job = MANAGER.create("tts", sanitize_params(body), title=text[:60])
    MANAGER.submit(job, lambda j: run_tts_job(j, body))
    return {"id": job.id}


@app.get("/api/jobs")
def list_jobs():
    return {"jobs": [j.to_dict(with_segments=False, with_logs=False) for j in MANAGER.list()]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    return job.to_dict()


@app.post("/api/jobs/{job_id}/regenerate")
def regenerate(job_id: str, body: dict = Body(default={})):
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    if job.status in ("queued", "running"):
        raise _err(409, "BUSY", "This job is still running.")
    if job.kind != "tts" and body.get("segments") is not None:
        try:
            body["segments"] = clean_segment_edits(job.segments, body.get("segments"))
        except ValueError as exc:
            raise _err(400, "BAD_REQUEST", str(exc))
    if job.kind != "tts" and body.get("characters") is not None:
        try:
            body["characters"] = autovoice.clean_character_edits((job.meta or {}).get("characters") or [], body.get("characters"))
        except ValueError as exc:
            raise _err(400, "BAD_REQUEST", str(exc))
    if job.kind == "dub" and (job.meta or {}).get("draft"):          # copy / paste draft: there must be some Khmer text to read aloud
        edits = body.get("segments") or []
        has_text = any((s.get("km") or "").strip() for s in job.segments) or any(isinstance(e, dict) and (e.get("km") or "").strip() for e in edits)
        if not has_text:
            raise _err(400, "NO_KHMER_TEXT", "There is no Khmer text yet - paste the translation first.")
    job.cancel_flag.clear()
    job.status = "queued"
    MANAGER.submit(job, lambda j: run_regenerate(j, body))
    return {"id": job.id}


@app.post("/api/jobs/{job_id}/speakers")
def detect_speakers(job_id: str, body: dict = Body(default={})):
    """Listen to the video of a finished job again and find its characters (who speaks which line, man or woman).
    The lines, the Khmer text and the audio are not touched; the new characters are used the next time the audio is generated."""
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    if job.kind != "dub":
        raise _err(400, "NOT_DUB", "Only a dubbing job has characters.")
    if job.status in ("queued", "running"):
        raise _err(409, "BUSY", "This job is still running.")
    if (job.meta or {}).get("timed") is False:
        raise _err(400, "NO_TIMING", "This text has no timestamps, so the voices cannot be matched to the lines.")
    up = (job.meta or {}).get("upload") or {}
    if not ((job.video or {}).get("id") or local_media_of(job)):
        raise _err(400, "NO_AUDIO_SOURCE", "This job has no sound to listen to: use a YouTube link or an uploaded video as the source.")
    if local_media_of(job) and up.get("has_audio") is False:
        raise _err(400, "NO_AUDIO", "The file you uploaded has no sound.")
    req = {"youtube": {k: str(v or "") for k, v in (body.get("youtube") or {}).items() if k in ("cookies_browser", "proxy")}}
    job.cancel_flag.clear()
    job.status = "queued"
    MANAGER.submit(job, lambda j: run_detect_speakers(j, req))
    return {"id": job.id}


@app.post("/api/jobs/{job_id}/video")
def remake_video(job_id: str, body: dict = Body(default={})):
    """Make only the MP4 again - e.g. as a vertical 9:16 video for TikTok - without touching the Khmer audio or the edits.
    Body (all optional): aspect "original" | "9:16", fit "blur" | "crop" | "bars", crop_x 0..100, max_height 480 | 720 | 1080,
    and the hidden original subtitles (hardsub.py): hide_subs true | false, hide_effect "blur" | "mosaic" | "dark" | "frost",
    hide_bottom 0..60 and hide_height 4..50 (percent of the picture height), hide_strength 10..100."""
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    if job.kind != "dub":
        raise _err(400, "NOT_DUB", "Only a dubbing job has a video.")
    if job.status in ("queued", "running"):
        raise _err(409, "BUSY", "This job is still running.")
    if (job.meta or {}).get("draft") or "dub.mp3" not in (job.outputs or {}) or not (job.dir / "dub.mp3").exists():
        raise _err(400, "NO_AUDIO_YET", "The Khmer audio has to be made first.")
    local = local_media_of(job)
    if not ((job.video or {}).get("id") or local):
        raise _err(400, "NO_VIDEO_SOURCE", "This job has no video: use a YouTube link or an uploaded video as the source.")
    if local and not (job.video or {}).get("has_video", True):
        raise _err(400, "NO_PICTURE", "The file you uploaded has no picture (it is audio only).")
    req: dict = {}
    if "aspect" in body:
        req["aspect"] = frame.clean_aspect(body.get("aspect"))
    if "fit" in body:
        req["fit"] = frame.clean_fit(body.get("fit"))
    if "crop_x" in body:
        req["crop_x"] = frame.clean_crop_x(body.get("crop_x"))
    if "max_height" in body:
        req["max_height"] = clean_video_height(body.get("max_height"))
    if "hide_subs" in body:
        req["hide_subs"] = hardsub.clean_on(body.get("hide_subs"))
    if "hide_effect" in body:
        req["hide_effect"] = hardsub.clean_effect(body.get("hide_effect"))
    if "hide_bottom" in body:
        req["hide_bottom"] = hardsub.clean_bottom(body.get("hide_bottom"))
    if "hide_height" in body:
        req["hide_height"] = hardsub.clean_height(body.get("hide_height"), body.get("hide_bottom", (job.params.get("output") or {}).get("hide_bottom")))
    if "hide_strength" in body:
        req["hide_strength"] = hardsub.clean_strength(body.get("hide_strength"))
    job.cancel_flag.clear()
    job.status = "queued"
    MANAGER.submit(job, lambda j: run_remake_video(j, req))
    return {"id": job.id}


def _translatable_job(job_id: str):
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    if job.kind != "dub" or not job.segments:
        raise _err(400, "BAD_REQUEST", "This job has no subtitle lines to translate.")
    return job


@app.post("/api/jobs/{job_id}/translation/prompt")
def translation_prompt(job_id: str, body: dict = Body(default={})):
    """Copy / paste translation (Claude, ChatGPT ...): the instructions + the numbered source lines of one part of the job."""
    job = _translatable_job(job_id)
    tr = (job.params or {}).get("translate") or {}
    return build_prompt(
        job.segments, (job.meta or {}).get("src_lang") or "en", job.title or "",
        part=body.get("part", 1), size=body.get("size", DEFAULT_SIZE), names=body.get("names", "latin"),
        keep_terms=bool(tr.get("keep_terms", True)), auto_detect=bool(tr.get("auto_detect", True)), glossary_text=load_glossary_text(),
    )


@app.post("/api/jobs/{job_id}/translation/parse")
def translation_parse(job_id: str, body: dict = Body(default={})):
    """Read the numbered Khmer lines out of the answer of a chat AI. Nothing is saved: the editor puts them in the table."""
    job = _translatable_job(job_id)
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise _err(400, "EMPTY_REPLY", "Paste the answer of the chat AI first.")
    first, last = body.get("first"), body.get("last")
    try:
        return parse_reply(text, len(job.segments), first if isinstance(first, int) else None, last if isinstance(last, int) else None)
    except ValueError as exc:
        raise _err(400, "BAD_REQUEST", str(exc))


@app.post("/api/jobs/{job_id}/translation/save")
def translation_save(job_id: str, body: dict = Body(default={})):
    """Copy / paste draft: keep the pasted Khmer lines in the job right away.  There is no audio yet, so nothing becomes out of date,
    and a reload or a crash cannot lose a long translation.  (A finished dub keeps edits in the editor until "Regenerate".)"""
    job = _translatable_job(job_id)
    if not (job.meta or {}).get("draft"):
        raise _err(409, "NOT_DRAFT", "Only a copy / paste draft keeps pasted lines before the audio exists - edit the lines in the table and press Regenerate.")
    if job.status in ("queued", "running"):
        raise _err(409, "BUSY", "This job is still running.")
    items = body.get("items")
    if not isinstance(items, list) or len(items) > len(job.segments):
        raise _err(400, "BAD_REQUEST", "items must be a list of {idx, km} (at most one per line).")
    by_idx = {s.get("idx"): s for s in job.segments}
    clean = {}
    for it in items:
        idx = it.get("idx") if isinstance(it, dict) else None
        km = it.get("km") if isinstance(it, dict) else None
        if not isinstance(idx, int) or isinstance(idx, bool) or idx not in by_idx or not isinstance(km, str):
            raise _err(400, "BAD_REQUEST", "Every item needs the integer idx of a line of this job and its text km.")
        clean[idx] = km.strip()[:4000]
    with job.lock:
        for idx, km in clean.items():
            by_idx[idx]["km"] = km
        job.updated = time.time()
    job.save()
    return {"saved": len(clean), "filled": sum(1 for s in job.segments if (s.get("km") or "").strip())}


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: str):
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    job.cancel_flag.set()
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    if not MANAGER.delete(job_id):
        raise _err(404, "NOT_FOUND", "Job not found.")
    return {"ok": True}


def _slug(text: str) -> str:
    # keep Khmer letters AND vowel signs (combining marks are not matched by \w)
    s = re.sub(r"[^\w\- \u1780-\u17FF]+", "", text or "", flags=re.UNICODE).strip().replace(" ", "_")
    return (s[:60] or "khmer_dub")


@app.get("/api/jobs/{job_id}/source")
def job_source(job_id: str):
    """The video the user uploaded (the Sync Preview plays it; Range requests work, so the player can jump)."""
    job = MANAGER.get(job_id)
    p = local_media_of(job) if job else None
    if not p:
        raise _err(404, "NOT_FOUND", "This job has no uploaded video.")
    return MediaFile(p, media_type=_MEDIA_TYPES.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0] or "application/octet-stream")


@app.get("/api/jobs/{job_id}/thumb")
def job_thumb(job_id: str):
    job = MANAGER.get(job_id)
    p = (job.dir / "thumb.jpg") if job else None
    if not p or not p.is_file():
        raise _err(404, "NOT_FOUND", "No thumbnail.")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


_MEDIA_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska", ".webm": "video/webm",
                ".ogv": "video/ogg", ".ts": "video/mp2t", ".mts": "video/mp2t", ".m2ts": "video/mp2t", ".avi": "video/x-msvideo",
                ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".flac": "audio/flac",
                ".aac": "audio/aac"}


@app.get("/api/jobs/{job_id}/file/{name}")
def job_file(job_id: str, name: str, download: int = 0):
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    ref_clip = re.fullmatch(r"voice_ref_c[1-9][0-9]?\.wav", name) is not None          # the voice sample of one character (voices by character)
    if not (name in DOWNLOADABLE_FILES or ref_clip) or name not in job.outputs:
        raise _err(404, "NOT_FOUND", "File not available.")
    path = job.dir / name
    if not path.exists():
        raise _err(404, "NOT_FOUND", "File is missing on disk.")
    kwargs = {}
    if download:
        src_name = LANGS[normalize_lang((job.meta or {}).get("src_lang"), "en")].name.lower()     # english | chinese | korean
        suffix = {"dub.mp3": "_khmer_dub.mp3", "speech.mp3": "_khmer_speech.mp3", "khmer.srt": "_khmer.srt",
                  "original.srt": f"_{src_name}.srt", "english.srt": "_english.srt", "script_km.txt": "_khmer_script.txt",
                  "dubbed.mp4": "_khmer_dubbed.mp4", "voice_ref.wav": "_voice_ref.wav"}.get(name, f"_{name}")
        if name == "dubbed.mp4" and ((job.meta or {}).get("video") or {}).get("aspect") == "9:16":
            suffix = "_khmer_tiktok_9x16.mp4"
        kwargs["filename"] = _slug(job.title) + suffix
    return MediaFile(path, media_type=DOWNLOADABLE_FILES.get(name, "audio/wav"), **kwargs)


# --------------------------------------------------------------------------- #
# glossary
# --------------------------------------------------------------------------- #
def _glossary_payload(text: str) -> dict:
    terms, readings = parse_glossary_text(text)
    maps = parse_glossary_maps(text)
    return {"text": text, "count": len(terms), "readings": len(readings), "maps": len(maps),
            "is_default": text.strip() == DEFAULT_GLOSSARY_TEXT.strip()}


@app.get("/api/glossary")
def get_glossary():
    return _glossary_payload(load_glossary_text())


@app.put("/api/glossary")
def put_glossary(body: dict = Body(...)):
    text = body.get("text") or ""
    if len(text) > 400_000:
        raise _err(400, "TOO_LARGE", "Glossary is too large.")
    save_glossary_text(text)
    return _glossary_payload(text)


@app.post("/api/glossary/reset")
def post_glossary_reset():
    return _glossary_payload(reset_glossary())


# --------------------------------------------------------------------------- #
# translation utilities
# --------------------------------------------------------------------------- #
@app.post("/api/translate")
def translate_text(body: dict = Body(...)):
    text = (body.get("text") or "").strip()
    if not text:
        raise _err(400, "EMPTY_TEXT", "Please enter some text.")
    cfg = TranslateConfig.from_dict(body.get("translate"))
    if body.get("lang"):
        cfg.src_lang = normalize_lang(body.get("lang"), cfg.src_lang)    # "en" | "zh" | "ko"
    tr = Translator(cfg)
    try:
        return {"km": tr.translate_text(text)}
    except TranslationError as exc:
        raise _err(502, "TRANSLATE_FAILED", str(exc))
    finally:
        tr.close()


@app.get("/api/translate/diagnose")
def translate_diagnose():
    """Connection test for the free Google Translate engine (Settings → Test Google Translate)."""
    tr = Translator(TranslateConfig(engine="google", keep_terms=False))
    try:
        return tr.diagnose()
    finally:
        tr.close()


@app.post("/api/llm/test")
def llm_test(body: dict = Body(...)):
    cfg = TranslateConfig(engine="llm", llm_base_url=body.get("base_url", ""), llm_api_key=body.get("api_key", ""), llm_model=body.get("model", ""))
    tr = Translator(cfg)
    try:
        return {"ok": True, "sample": tr.test_llm()}
    except TranslationError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=200)
    finally:
        tr.close()


# --------------------------------------------------------------------------- #
# subtitles (WebVTT, generated on the fly from the job's segments)
# --------------------------------------------------------------------------- #
def _vtt_time(t: float) -> str:
    t = max(0.0, float(t))
    h, rem = divmod(int(t), 3600)
    m, sec = divmod(rem, 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        ms, sec = 0, sec + 1
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"


@app.get("/api/jobs/{job_id}/subtitle/{name}")
def job_subtitle(job_id: str, name: str):
    job = MANAGER.get(job_id)
    if not job:
        raise _err(404, "NOT_FOUND", "Job not found.")
    if name not in ("en.vtt", "km.vtt"):
        raise _err(404, "NOT_FOUND", "Subtitle not found.")
    en = name == "en.vtt"
    lines = ["WEBVTT", ""]
    n = 0
    for sg in job.segments:
        text = (sg.get("en") if en else sg.get("km")) or ""
        a = sg.get("start") if en else sg.get("out_start")
        b = sg.get("end") if en else sg.get("out_end")
        if not text.strip() or a is None or b is None or b <= a:
            continue
        n += 1
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("-->", "- ->")
        lines += [str(n), f"{_vtt_time(a)} --> {_vtt_time(b)}", text.strip(), ""]
    return Response("\n".join(lines), media_type="text/vtt; charset=utf-8", headers={"Cache-Control": "no-cache"})


# --------------------------------------------------------------------------- #
# VoxCPM2 – optional local voice engine (more voices + voice cloning)
# --------------------------------------------------------------------------- #
def _vox_err(exc: VoxError, status: int = 400) -> HTTPException:
    return _err(status, getattr(exc, "code", "VOX_FAILED"), str(exc))


@app.get("/api/vox/status")
def vox_status():
    return vox_manager().status()


@app.post("/api/vox/setup")
def vox_setup_start(body: dict = Body(default={})):
    if os.environ.get("KDS_VOX_DISABLE_INSTALL") == "1":   # e.g. a shared demo server: install on your own computer instead
        raise _err(403, "VOX_INSTALL_DISABLED", "Installing VoxCPM2 is disabled on this server. Install it on your own computer.")
    r = vox_manager().setup_start(cpu=bool(body.get("cpu")))
    if not r.get("started"):
        raise _err(409, "BUSY", "The installation is already running.")
    return r


@app.post("/api/vox/setup/cancel")
def vox_setup_cancel():
    return {"cancelled": vox_manager().setup_cancel()}


@app.get("/api/vox/log")
def vox_log(which: str = Query("setup"), n: int = Query(120, ge=1, le=600)):
    return {"lines": vox_manager().log_tail("setup" if which == "setup" else "worker", n)}


@app.post("/api/vox/start")
def vox_start():
    """Start the engine AND load the model in the background (poll /api/vox/status to see the progress)."""
    m = vox_manager()
    try:
        m.start()
    except VoxError as exc:
        raise _vox_err(exc, 409)

    def _load() -> None:
        try:
            m.ensure_ready()
        except Exception:
            pass  # the error is visible in /api/vox/status (worker.state == "error") and in the engine log

    threading.Thread(target=_load, daemon=True).start()
    return {"ok": True}


@app.post("/api/vox/stop")
def vox_stop():
    vox_manager().stop()
    return {"ok": True}


@app.put("/api/vox/config")
def vox_config(body: dict = Body(...)):
    m = vox_manager()
    before = m.config()
    cfg = m.set_config(body)
    if cfg != before:
        m.stop()  # the device is chosen when the engine starts
    return cfg


@app.get("/api/vox/voices")
def vox_voices():
    return {"custom": voxvoices.list_custom(), "presets": voxpresets.list_presets(vox_manager().home)}


@app.post("/api/vox/presets/{key}/reroll")
def vox_preset_reroll(key: str):
    """Designed voice: make a new person in the same style (the next use creates the new voice; old jobs are untouched)."""
    if not voxpresets.get(key):
        raise _err(404, "NOT_FOUND", "Designed voice not found.")
    n = voxpresets.bump_variant(vox_manager().home, key)
    return {"id": f"vox:p:{key}", "variant": n}


@app.post("/api/vox/voices")
def vox_voice_add(body: dict = Body(...)):
    try:
        return voxvoices.save_custom_voice(body.get("name") or "", body.get("filename") or "", body.get("data") or "", body.get("gender") or "")
    except VoxError as exc:
        raise _vox_err(exc)


@app.patch("/api/vox/voices/{vid}")
def vox_voice_update(vid: str, body: dict = Body(...)):
    """Change a saved voice: {"name": "..."} and / or {"gender": "Female" | "Male" | ""} (the id is the 8 characters after `vox:c:`)."""
    name, gender = body.get("name"), body.get("gender")
    if name is None and gender is None:
        raise _err(400, "BAD_REQUEST", "Send a name and / or a gender.")
    if name is not None and not isinstance(name, str):
        raise _err(400, "BAD_REQUEST", "name must be text.")
    if gender is not None and gender not in ("Female", "Male", ""):
        raise _err(400, "BAD_REQUEST", "gender must be Female, Male or empty.")
    try:
        v = voxvoices.rename_custom(vid, name) if name is not None else None
        if gender is not None:
            v = voxvoices.set_custom_gender(vid, gender)
    except VoxError as exc:
        raise _vox_err(exc)
    if not v:
        raise _err(404, "NOT_FOUND", "Voice not found.")
    return v


@app.delete("/api/vox/voices/{vid}")
def vox_voice_delete(vid: str):
    if not voxvoices.delete_custom(vid):
        raise _err(404, "NOT_FOUND", "Voice not found.")
    return {"ok": True}


@app.get("/api/vox/voices/{vid}/audio")
def vox_voice_audio(vid: str):
    p = voxvoices.custom_ref_path(vid)
    if not p:
        raise _err(404, "NOT_FOUND", "Voice not found.")
    return MediaFile(p, media_type="audio/wav")


VOX_PREVIEWS: Dict[str, dict] = {}


def _vox_preview_run(pid: str, voice_id: str, quality: str, text: str = "") -> None:
    st = VOX_PREVIEWS[pid]
    try:
        vs = VoiceSettings(engine="voxcpm", vox_id=voice_id, vox_quality=quality, vox_consent=True)
        if voice_id == "vox:original":
            raise VoxError("VOX_NO_ORIGINAL", "The original speaker's voice can only be heard after a dubbing job.")
        m = vox_manager()

        def status(msg: str) -> None:
            st["detail"] = str(msg)[:120]

        resolved = voxvoices.resolve_voice(vs, mgr=m, status=status)
        say = (text or "").strip() or voxvoices.PREVIEW_TEXT
        key = hashlib.sha1(json.dumps([resolved.ref_hash, quality, say], ensure_ascii=False).encode()).hexdigest()
        path = PREVIEW_DIR / f"vox-{key}.mp3"
        if not path.exists():
            _, readings = parse_glossary_text(load_glossary_text())
            synth = voxvoices.VoxSynth(resolved, quality, m, status=status)
            t0 = time.time()
            arr = asyncio.run(synth.segment(say, vs, readings))
            if not len(arr):
                raise VoxError("VOX_FAILED", "VoxCPM2 returned no audio.")
            audio.encode_array(arr, path)
            st["seconds"] = round(len(arr) / 24000.0, 1)
            st["elapsed"] = round(time.time() - t0, 1)
        st.update(state="done", file=str(path), detail="")
    except VoxError as exc:
        st.update(state="error", code=getattr(exc, "code", "VOX_FAILED"), message=str(exc))
    except Exception as exc:  # pragma: no cover - unexpected
        st.update(state="error", code="VOX_FAILED", message=f"{type(exc).__name__}: {exc}")


@app.post("/api/vox/preview")
def vox_preview(body: dict = Body(...)):
    voice_id = str(body.get("voice") or "")
    if not voice_id:
        raise _err(400, "BAD_REQUEST", "voice is required")
    for k in [k for k, v in VOX_PREVIEWS.items() if time.time() - v.get("created", 0) > 3600]:
        VOX_PREVIEWS.pop(k, None)
    pid = uuid.uuid4().hex[:10]
    VOX_PREVIEWS[pid] = {"state": "running", "detail": "", "created": time.time()}
    threading.Thread(target=_vox_preview_run, args=(pid, voice_id, str(body.get("quality") or "balanced"),
                                                    str(body.get("text") or "")[:600]), daemon=True).start()
    return {"id": pid}


@app.get("/api/vox/preview/{pid}")
def vox_preview_status(pid: str):
    st = VOX_PREVIEWS.get(pid)
    if not st:
        raise _err(404, "NOT_FOUND", "Preview not found.")
    out = {k: v for k, v in st.items() if k != "file"}
    if st.get("state") == "done":
        out["url"] = f"/api/vox/preview/{pid}/audio"
    return out


@app.get("/api/vox/preview/{pid}/audio")
def vox_preview_audio(pid: str):
    st = VOX_PREVIEWS.get(pid)
    if not st or st.get("state") != "done":
        raise _err(404, "NOT_FOUND", "Preview not ready.")
    return MediaFile(st["file"], media_type="audio/mpeg", headers={"Cache-Control": "max-age=3600"})
