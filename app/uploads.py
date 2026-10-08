"""A video (or audio) file that the user downloaded earlier and uploads instead of pasting a YouTube link.

Life of an upload
  1. ``POST /api/uploads`` streams the body to ``data/uploads/<id>/upload.<ext>`` (no size limit in memory), looks inside the file with
     ffmpeg (length, picture, audio, subtitle tracks), makes a thumbnail and writes ``info.json``.
  2. ``POST /api/jobs/dub`` with ``source.type = "upload"`` makes a job.  The file is *linked* into the job folder (a hard link: no copy,
     no extra disk space; a copy when the disk cannot link), so the job owns its video (Regenerate, MP4, Sync Preview ...) and the
     upload stays usable for a second try - for example after Whisper was installed.
  3. Uploads that never became a job (or were used long ago) are removed after KEEP_HOURS.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import List, Optional

from . import audio
from .config import UPLOADS_DIR
from .langs import AUTO, LANGS, SUPPORTED, normalize_lang

VIDEO_EXT = (".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".ts", ".mts", ".m2ts", ".mpg", ".mpeg", ".3gp", ".ogv")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma", ".aiff", ".aif")
ALLOWED_EXT = frozenset(VIDEO_EXT + AUDIO_EXT)


def max_upload_bytes() -> int:
    """KDS_MAX_UPLOAD_MB (default 4096 = 4 GB; 0 = no limit)."""
    try:
        mb = float(os.environ.get("KDS_MAX_UPLOAD_MB", "4096"))
    except ValueError:
        mb = 4096.0
    return int(mb * 1024 * 1024) if mb > 0 else 0


KEEP_HOURS = 24
_ID_RE = re.compile(r"^[0-9a-f]{12}$")

# Subtitle formats ffmpeg can turn into SRT (text).  Picture based tracks (Blu-ray / DVD) cannot be read without OCR.
TEXT_SUB_CODECS = frozenset({"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text", "subviewer", "subviewer1", "microdvd",
                             "sami", "realtext", "jacosub", "stl", "mpl2", "pjs", "vplayer"})
_UNKNOWN_LANG = ("", "und", "unk", "mis", "mul", "zxx")


class UploadError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# --------------------------------------------------------------------------- #
# names and folders
# --------------------------------------------------------------------------- #
def display_name(name: str) -> str:
    """The file name as shown to the user: no folders, no control characters, not endless."""
    n = re.split(r"[\\/]", str(name or ""))[-1]
    n = re.sub(r"[\x00-\x1f\x7f]", "", n).strip()
    return n[:180] or "video"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def folder(uid: str) -> Path:
    if not isinstance(uid, str) or not _ID_RE.match(uid):
        raise UploadError(404, "UPLOAD_GONE", "This upload was not found. Upload the file again.")
    return UPLOADS_DIR / uid


def kind_of(ext: str) -> str:
    return "audio" if ext.lower() in AUDIO_EXT else "video"


# --------------------------------------------------------------------------- #
# looking inside a file
# --------------------------------------------------------------------------- #
def inspect(path: Path) -> dict:
    """Length, picture, audio and subtitle tracks of a media file. Raises UploadError(NOT_MEDIA) when ffmpeg finds neither."""
    try:
        pi = audio.probe_streams(path)
    except Exception as exc:  # noqa: BLE001 - ffmpeg missing / crashed
        raise UploadError(500, "FFMPEG_FAILED", f"ffmpeg could not open the file: {exc}") from exc
    streams = pi["streams"]
    vids = [s for s in streams if s["type"] == "video" and not s.get("attached")]          # the cover picture of an MP3 is not a video
    auds = [s for s in streams if s["type"] == "audio"]
    dur = pi["duration"]
    if not vids and not auds:
        raise UploadError(400, "NOT_MEDIA", "This file is not a video or audio file that ffmpeg can read.")
    if vids and not auds and (dur is None or dur < 0.05):
        raise UploadError(400, "NOT_MEDIA", "This file is a picture, not a video.")
    v = vids[0] if vids else None
    w, h = (v["width"], v["height"]) if v else (None, None)
    rot = (abs(v.get("rotation") or 0.0) % 360.0) if v else 0.0
    if v and w and h and (abs(rot - 90.0) < 1.0 or abs(rot - 270.0) < 1.0):
        w, h = h, w                                       # a phone video stored sideways: show it the way it is played
    subs = []
    for s in streams:
        if s["type"] != "subtitle":
            continue
        code = normalize_lang(s["lang"], "")
        subs.append({
            "pos": s["pos"], "index": s["index"], "lang": s["lang"], "code": code, "title": s["title"], "codec": s["codec"],
            "forced": bool(s["forced"]), "text": s["codec"] in TEXT_SUB_CODECS,
        })
    return {
        "duration": round(dur, 2) if dur else None,
        "width": w, "height": h, "video_codec": v["codec"] if v else None,
        "has_video": bool(v), "has_audio": bool(auds),
        "subtitles": subs,
    }


def make_thumbnail(src: Path, dst: Path, duration: Optional[float]) -> bool:
    """One picture from the video (a little after the start, so it is not black). False for audio files / on failure."""
    for at in ((min(duration * 0.1, 8.0) if duration and duration >= 3 else 0.0), 0.0):
        try:
            dst.unlink(missing_ok=True)
            cmd = [audio.ffmpeg_exe(), "-v", "error", "-nostdin", "-y", "-ss", f"{at:.2f}", "-i", str(src), "-frames:v", "1",
                   "-vf", "scale=480:-2", "-q:v", "5", str(dst)]
            subprocess.run(cmd, capture_output=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if dst.exists() and dst.stat().st_size > 200:
                return True
        except Exception:  # noqa: BLE001 - the thumbnail is decoration
            pass
    dst.unlink(missing_ok=True)
    return False


# --------------------------------------------------------------------------- #
# subtitles inside the file
# --------------------------------------------------------------------------- #
def lang_label(track: dict) -> str:
    code = track.get("code") or ""
    if code in LANGS:
        return LANGS[code].name
    return track.get("title") or track.get("lang") or "?"


def pick_subtitle(subs: List[dict], lang: str = AUTO) -> Optional[dict]:
    """The embedded subtitle track to use, or None.

    A track in the chosen language wins; then a track whose language is not tagged (the text itself is checked later: the script of the
    text decides the language); with "auto" any English / Chinese / Korean track.  Forced tracks (signs, foreign words only) and
    picture based tracks are never used."""
    usable = [s for s in subs if s.get("text") and not s.get("forced")]
    want = normalize_lang(lang)
    unknown = [s for s in usable if (s.get("lang") or "").lower() in _UNKNOWN_LANG]
    if want != AUTO:
        for s in usable:
            if s.get("code") == want:
                return s
        return unknown[0] if unknown else None
    for s in usable:
        if s.get("code") in SUPPORTED:
            return s
    return unknown[0] if unknown else None


def extract_subtitle(media: Path, pos: int, dst: Path) -> str:
    """Subtitle track number `pos` (counted among the subtitle tracks) of the file, as SRT text."""
    cmd = [audio.ffmpeg_exe(), "-v", "error", "-nostdin", "-y", "-i", str(media), "-map", f"0:s:{int(pos)}", "-f", "srt", str(dst)]
    audio._run(cmd, timeout=600)
    return dst.read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# the folder of an upload
# --------------------------------------------------------------------------- #
def save_info(uid: str, info: dict) -> None:
    d = folder(uid)
    tmp = d / "info.json.tmp"
    tmp.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "info.json")


def load(uid: str) -> dict:
    """The saved info of an upload (raises UploadError 404 UPLOAD_GONE when it was removed or the file is missing)."""
    d = folder(uid)
    try:
        info = json.loads((d / "info.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise UploadError(404, "UPLOAD_GONE", "This upload was not found. Upload the file again.") from exc
    if not (d / str(info.get("file") or "?")).is_file():
        raise UploadError(404, "UPLOAD_GONE", "This upload was not found. Upload the file again.")
    return info


def thumb_path(uid: str) -> Optional[Path]:
    p = folder(uid) / "thumb.jpg"
    return p if p.is_file() else None


def remove(uid: str) -> bool:
    d = folder(uid)
    if not d.exists():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return True


def prune(max_age_hours: float = KEEP_HOURS) -> int:
    """Delete uploads that are older than max_age_hours (a hard link in a job folder keeps the job's own copy). Returns the count."""
    n = 0
    try:
        now = time.time()
        for d in UPLOADS_DIR.iterdir():
            if not (d.is_dir() and _ID_RE.match(d.name)):
                continue
            try:
                newest = max([d.stat().st_mtime] + [p.stat().st_mtime for p in d.iterdir()])
            except OSError:
                continue
            if now - newest > max_age_hours * 3600:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
    except OSError:
        pass
    return n


def adopt(uid: str, job_dir: Path) -> dict:
    """Give a job its own handle on the uploaded file (hard link, or a copy) and its thumbnail. Returns the job's `meta.upload`."""
    info = load(uid)
    src = folder(uid) / info["file"]
    ext = src.suffix.lower()
    dst = job_dir / f"upload{ext}"
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    th = thumb_path(uid)
    if th:
        shutil.copy2(th, job_dir / "thumb.jpg")
    now = time.time()
    try:
        os.utime(folder(uid), (now, now))                 # used just now: it stays a day longer for a second try
    except OSError:
        pass
    return {
        "file": dst.name, "name": info["name"], "size": info["size"], "kind": info["kind"], "duration": info.get("duration"),
        "width": info.get("width"), "height": info.get("height"), "video_codec": info.get("video_codec"),
        "has_video": bool(info.get("has_video")), "has_audio": bool(info.get("has_audio")),
        "subtitles": info.get("subtitles") or [], "thumb": bool(th),
    }


def public(uid: str, info: dict, lang: str = AUTO) -> dict:
    """What the browser gets to see."""
    from . import asr

    pick = pick_subtitle(info.get("subtitles") or [], lang)
    out = {k: info.get(k) for k in ("name", "size", "kind", "duration", "width", "height", "video_codec", "has_video", "has_audio", "subtitles")}
    out.update({
        "id": uid,
        "thumbnail": f"/api/uploads/{uid}/thumb" if (folder(uid) / "thumb.jpg").is_file() else None,
        "pick": pick["pos"] if pick else None,
        "pick_label": lang_label(pick) if pick else None,
        "whisper": asr.whisper_installed(),
    })
    return out
