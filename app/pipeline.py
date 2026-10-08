"""Dubbing + Text-to-Speech pipelines. Each `run_*` function executes inside a worker thread."""
from __future__ import annotations

import asyncio
import copy
import dataclasses
import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from . import asr, audio, autovoice, frame, hardsub, speakers, uploads, voxpresets
from .config import SAMPLE_RATE as SR, default_en_voice_for
from .glossary import load_glossary_text, parse_glossary_text
from .jobs import Cancelled, Job
from .langs import AUTO, LANGS, lang_name, normalize_lang, resolve_lang
from .textutil import ensure_khmer_terminal
from .transcript import Seg, clean_segments, fix_overlaps, merge_segments, parse_any, parse_srt_vtt, to_srt
from .translate import TranslateConfig, Translator, TranslationError
from .tts import Synth, TTSError, VoiceSettings, synth_long_text
from .ytsource import (
    SourceError,
    canonical_url,
    clean_video_height,
    download_audio,
    download_video,
    extract_video_id,
    fetch_transcript,
)

MAX_TTS_CHARS = 30000


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sanitize_params(req: dict) -> dict:
    """Copy of the request that is safe to store/show (no API keys, no huge text)."""
    p = copy.deepcopy(req)
    llm = (p.get("translate") or {}).get("llm")
    if isinstance(llm, dict) and llm.get("api_key"):
        llm["api_key"] = "***"
    tr = p.get("translate") or {}
    tr.pop("glossary_text", None)
    src = p.get("source") or {}
    if src.get("type") in ("transcript", "upload") and src.get("text"):
        src["text"] = f"<{len(src.get('text') or '')} chars>"
    if "text" in p:
        p["text_chars"] = len(p.get("text") or "")
        p["text"] = (p["text"] or "")[:200]
    return p


def _fail(job: Job, code: str, message: str) -> None:
    job.status = "error"
    job.error = {"code": code, "message": message}
    for s in job.steps:
        if s["status"] == "running":
            s["status"] = "error"
            s["detail"] = message.split(" Details:")[0][:160]
    job.log(f"✖ [{code}] {message}")


def _guard(job: Job, fn) -> None:
    """Run a pipeline function and translate exceptions into job state."""
    try:
        fn()
        if job.status == "running":
            job.status = "done"
    except Cancelled:
        job.status = "cancelled"
        for s in job.steps:
            if s["status"] == "running":
                s["status"] = "pending"
        job.log("Cancelled by user.")
    except SourceError as e:
        _fail(job, e.code, e.message)
    except TranslationError as e:
        _fail(job, "TRANSLATE_FAILED", str(e))
    except TTSError as e:
        _fail(job, getattr(e, "code", None) or "TTS_FAILED", str(e))
    except audio.FFmpegError as e:
        _fail(job, "FFMPEG_FAILED", str(e))
    except PermissionError as e:          # Windows: a file of the job is open in a player / scanned by an antivirus (or the folder is read-only)
        job.log(traceback.format_exc())
        _fail(job, "FILE_IN_USE", f"{Path(str(e.filename)).name if e.filename else 'a file'}: {e.strerror or e}")
    except Exception as e:  # pragma: no cover - unexpected
        job.log(traceback.format_exc())
        _fail(job, "INTERNAL", f"{type(e).__name__}: {e}")
    finally:
        job.updated = time.time()
        job.save()


@dataclass
class AudioCtx:
    vs: VoiceSettings
    readings: dict
    sync: str = "fit"             # "fit" | "natural"
    max_speed: float = 1.4
    max_height: int = 1080        # tallest picture of the MP4 export (480 / 720 / 1080)
    want_video: bool = False
    orig_vol: float = 0.0         # 0..1
    duck: bool = True             # mute the original audio while somebody is speaking (needs orig_vol > 0)
    vid: Optional[str] = None
    cookies: str = ""
    proxy: str = ""
    local_video: Optional[Path] = None      # an uploaded file: the picture (and the original sound) of the MP4 come from it
    aspect: str = "original"      # "original" | "9:16" (TikTok / Reels / Shorts: the picture is put into a vertical frame)
    fit: str = "blur"             # how: "blur" (blurred background) | "crop" (fill the frame) | "bars" (black bars)
    crop_x: float = 50.0          # fit "crop": which part of a wide picture is kept (0 = left edge ... 100 = right edge)
    hide_subs: bool = False       # blur / cover the subtitles that are burned into the ORIGINAL picture (hardsub.py)
    hide_effect: str = "blur"     # "blur" | "mosaic" | "dark" | "frost"
    hide_bottom: float = 3.0      # the band: % of the picture height between its lower edge and the lower edge of the picture
    hide_height: float = 16.0     # ... and how high it is (% of the picture height)
    hide_strength: int = 50       # 10 .. 100


def _ctx_from(req: dict, vid: Optional[str], timed: bool, local_video: Optional[Path] = None) -> AudioCtx:
    out = req.get("output") or {}
    yt = req.get("youtube") or {}
    _, readings = parse_glossary_text(load_glossary_text())
    sync = out.get("sync", "fit")
    if not timed:
        sync = "natural"
    hide_bottom = hardsub.clean_bottom(out.get("hide_bottom"))
    return AudioCtx(
        vs=VoiceSettings.from_dict(req.get("voice")),
        readings=readings,
        sync=sync if sync in ("fit", "natural") else "fit",
        max_speed=float(max(1.0, min(2.0, float(out.get("max_speedup", 1.4) or 1.4)))),
        max_height=clean_video_height(out.get("max_height")),
        aspect=frame.clean_aspect(out.get("aspect")),
        fit=frame.clean_fit(out.get("fit")),
        crop_x=frame.clean_crop_x(out.get("crop_x")),
        hide_subs=hardsub.clean_on(out.get("hide_subs")),
        hide_effect=hardsub.clean_effect(out.get("hide_effect")),
        hide_bottom=hide_bottom,
        hide_height=hardsub.clean_height(out.get("hide_height"), hide_bottom),
        hide_strength=hardsub.clean_strength(out.get("hide_strength")),
        want_video=bool(out.get("video")),
        orig_vol=float(max(0.0, min(1.0, float(out.get("orig_volume", 0) or 0) / 100.0))),
        duck=bool(out.get("duck", True)),
        vid=vid,
        cookies=yt.get("cookies_browser") or "",
        proxy=yt.get("proxy") or "",
        local_video=local_video,
    )


# --------------------------------------------------------------------------- #
# DUBBING JOB
# --------------------------------------------------------------------------- #
def run_dub_job(job: Job, req: dict) -> None:
    _guard(job, lambda: _dub(job, req))


def _dub(job: Job, req: dict) -> None:
    src = req.get("source") or {}
    yt = req.get("youtube") or {}
    cookies, proxy = yt.get("cookies_browser") or "", yt.get("proxy") or ""
    use_whisper = bool(yt.get("whisper", True))
    whisper_model = yt.get("whisper_model") or "base"
    sel_lang = normalize_lang(src.get("lang"))        # what the user chose: auto | en | zh | ko

    # ------------------------------------------------------------ transcript
    job.step("transcript", "running", progress=0.05)
    vid: Optional[str] = None
    timed = True
    if src.get("type") == "youtube":
        vid = extract_video_id(src.get("url", ""))
        if not vid:
            raise SourceError("INVALID_URL", "That does not look like a YouTube link.")
        job.video = req.get("video") or {
            "id": vid, "url": canonical_url(vid), "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "title": None, "channel": None, "duration": None,
        }
        job.video.setdefault("id", vid)
        job.title = job.video.get("title") or vid
        job.log(f"YouTube video: {vid}")
        want = LANGS[sel_lang].name if sel_lang != AUTO else "English, Chinese or Korean"
        job.log(f"Video language: {LANGS[sel_lang].name if sel_lang != AUTO else 'auto-detect'}")
        try:
            raw, meta = fetch_transcript(vid, cookies, proxy, job.log, sel_lang, job.video.get("title") or "")
        except SourceError as e:
            if e.code == "NO_CAPTIONS" and use_whisper:
                if not asr.whisper_installed():
                    raise SourceError(
                        "NO_CAPTIONS_NO_WHISPER",
                        f"This video has no {want} captions, and Whisper (AI transcription) is not installed. "
                        "Install it with:  pip install faster-whisper   — or paste the transcript manually.",
                    )
                model = asr.model_for(sel_lang, whisper_model)
                if model != whisper_model:
                    job.log(f"Whisper '{whisper_model}' is too weak for {LANGS[sel_lang].name} → using '{model}' (first time downloads the model).")
                job.log(f"No {want} captions → downloading audio for Whisper transcription …")
                ap = download_audio(vid, job.dir / "audio", cookies, proxy, progress=lambda p: job.step("transcript", progress=0.1 + 0.3 * p))
                job.check_cancel()
                raw, spoken = asr.transcribe(
                    ap, model, sel_lang,
                    progress=lambda p: job.step("transcript", progress=0.4 + 0.55 * p),
                    cancelled=job.cancel_flag.is_set, log=job.log,
                )
                meta = {"source": "whisper", "generated": True, "language": spoken, "model": model}
            else:
                raise
    elif src.get("type") == "upload":
        up = job.meta.get("upload") or {}
        media = local_media_of(job)
        if not media:
            raise SourceError("UPLOAD_GONE", "The uploaded file is no longer on disk. Upload it again.")
        job.log(f"Uploaded file: {up.get('name')} ({(up.get('size') or 0) / 1048576:.1f} MB"
                + (f", {up['duration'] / 60:.1f} min" if up.get("duration") else "") + ")")
        job.log(f"Video language: {LANGS[sel_lang].name if sel_lang != AUTO else 'auto-detect'}")
        raw, meta, timed = _upload_transcript(job, src, up, media, sel_lang, whisper_model)
        if not timed:
            job.warn("UNTIMED_UPLOAD", "The text you supplied has no timestamps, so the Khmer voice is read at a natural pace and is NOT "
                                       "lined up with the picture. Use an SRT / VTT file (or leave the box empty so the app listens to the video).")
    else:
        text = src.get("text") or ""
        raw, timed = parse_any(text, resolve_lang(sel_lang, text)[0])
        job.title = (src.get("title") or "").strip() or (text.strip().splitlines() or ["Pasted transcript"])[0][:60]
        meta = {"source": "manual", "timed": timed}
        job.log(f"Pasted transcript: {len(raw)} lines ({'with timestamps' if timed else 'plain text, no timing → natural pace'})")

    job.check_cancel()
    segs = fix_overlaps(clean_segments(raw))
    if not segs:
        raise SourceError("EMPTY_TRANSCRIPT", "The transcript is empty after cleaning.")
    # the writing system of the text decides the language (a mislabelled caption track must not be translated as English)
    lang, note = resolve_lang(sel_lang, " ".join(s.text for s in segs), meta.get("language"))
    if note:
        job.log(note)
    if lang not in LANGS:
        raise SourceError("LANG_UNSUPPORTED", f"The transcript is written in {lang_name(lang)}. Only English, Chinese and Korean are supported.")
    meta["language"] = lang
    if timed:
        segs = fix_overlaps(merge_segments(segs, lang=lang))
    if not segs:
        raise SourceError("EMPTY_TRANSCRIPT", "The transcript is empty after cleaning.")
    job.segments = [
        {"idx": i, "start": round(s.start, 3), "end": round(s.end, 3), "en": s.text, "km": ""}
        for i, s in enumerate(segs)
    ]
    job.meta.update({"transcript": meta, "timed": timed, "source_end": round(segs[-1].end, 2), "src_lang": lang})
    job.step("transcript", "done", detail=f"{len(segs)} segments")
    job.log(f"Prepared {len(segs)} dubbing segments ({segs[-1].end / 60:.1f} min of speech) · source language: {LANGS[lang].name}.")
    job.save()

    # ------------------------------------------------- characters: who speaks which line (man / woman)
    _speakers_stage(job, req, vid, timed)

    # ------------------------------------------------------------- translate
    tcfg = TranslateConfig.from_dict(req.get("translate"))
    tcfg.src_lang = lang
    if tcfg.engine == "manual":                       # copy / paste with a chat AI (Claude ...): the subtitles are ready, the user translates them
        _make_draft(job)
        return
    job.step("translate", "running", progress=0.0)
    tr = Translator(tcfg, log=job.log)
    job.log(f"Translating {LANGS[lang].name} → Khmer with {'AI / LLM' if tcfg.engine == 'llm' else 'Google Translate'} "
            f"({'keeping technical terms in English' if tcfg.keep_terms else 'no term protection'}) …")
    try:
        kms = tr.translate_many(
            [s["en"] for s in job.segments],
            progress=lambda d, t: job.step("translate", progress=d / max(1, t), detail=f"{d}/{t}"),
            cancelled=job.cancel_flag.is_set,
            status=lambda m: job.step("translate", detail=m),
        )
    finally:
        tr.close()
    job.check_cancel()
    for s, k in zip(job.segments, kms):
        s["km"] = k or s["en"]
    job.step("translate", "done", detail=f"{len(kms)} segments")
    job.save()

    # ----------------------------------------------------- tts + mix + video
    ctx = _ctx_from(req, vid, timed, local_media_of(job))
    _audio_stages(job, ctx)


def local_media_of(job: Job) -> Optional[Path]:
    """The uploaded file of a job (None for a YouTube / pasted-text job, or when the file is gone)."""
    up = (job.meta or {}).get("upload") or {}
    name = str(up.get("file") or "")
    if not name or "/" in name or "\\" in name:
        return None
    p = job.dir / name
    return p if p.is_file() else None


def _upload_transcript(job: Job, src: dict, up: dict, media: Path, sel_lang: str, whisper_model: str):
    """The subtitles of an uploaded file -> (raw segments, transcript meta, timed).

    Order: the text the user gave (a pasted / chosen SRT, VTT or text)  >  a subtitle track inside the file  >  Whisper (speech recognition)."""
    text = (src.get("text") or "").strip()
    if text:
        raw, timed = parse_any(text, resolve_lang(sel_lang, text)[0])
        job.log(f"Subtitles from you: {len(raw)} lines ({'with timestamps' if timed else 'plain text, no timing'})")
        return raw, {"source": "manual", "timed": timed}, timed
    if (src.get("subs") or "auto") != "whisper":
        track = uploads.pick_subtitle(up.get("subtitles") or [], sel_lang)
        if track:
            label = uploads.lang_label(track)
            job.log(f"Using the subtitle track inside the file: {label} ({track.get('codec')})")
            raw: List[Seg] = []
            try:
                raw = parse_srt_vtt(uploads.extract_subtitle(media, int(track["pos"]), job.dir / "embedded.srt"))
            except (audio.FFmpegError, OSError, ValueError) as e:
                job.warn("EMBEDDED_SUBS_FAILED", f"The subtitle track inside the file could not be read ({str(e)[-160:]}) - listening to the audio instead.")
            if clean_segments(raw):
                return raw, {"source": "embedded", "generated": False, "language": track.get("code") or None, "track": label}, True
            if not raw:
                job.log("That subtitle track is empty - listening to the audio instead.")
    if not up.get("has_audio"):
        raise SourceError("NO_AUDIO", "This file has no sound and no subtitles, so there is nothing to translate. Add an SRT / VTT file.")
    if not asr.whisper_installed():
        raise SourceError(
            "NO_SUBTITLES_NO_WHISPER",
            "This file has no subtitles for the chosen language, and Whisper (AI speech recognition) is not installed. Install Whisper "
            "(Settings, or:  pip install faster-whisper)  - or choose / paste an SRT or VTT file.",
        )
    model = asr.model_for(sel_lang, whisper_model)
    if model != whisper_model:
        job.log(f"Whisper '{whisper_model}' is too weak for {LANGS[sel_lang].name} -> using '{model}' (first time downloads the model).")
    job.log(f"No subtitles to use -> Whisper '{model}' listens to the audio (this takes a while on a CPU) ...")
    job.step("transcript", detail="Whisper (AI) is listening … (the first time it also downloads the model)")
    raw, spoken = asr.transcribe(
        media, model, sel_lang,
        progress=lambda p: job.step("transcript", progress=0.1 + 0.85 * p),
        cancelled=job.cancel_flag.is_set, log=job.log,
    )
    job.check_cancel()
    if not raw:
        raise SourceError("NO_SPEECH", "Whisper did not hear any speech in this file. If the video has speech, choose its language "
                                       "(instead of Auto-detect) or paste an SRT / VTT file.")
    return raw, {"source": "whisper", "generated": True, "language": spoken, "model": model}, True


def _make_draft(job: Job) -> None:
    """Copy / paste translation: stop with the subtitles ready for a chat AI (Claude, ChatGPT ...).

    The Khmer lines are pasted into the editor table; "Generate audio" (= regenerate) then builds the dub.  `meta.draft` marks the
    job until its audio exists (so a failed first attempt keeps the pasted translation reachable)."""
    for s in job.segments:
        s["km"] = ""
    job.step("translate", "skipped", detail="copy & paste")
    for key in ("tts", "mix", "video"):
        job.step(key, "skipped")
    (job.dir / "original.srt").write_text(to_srt(job.segments, "en", "start", "end"), encoding="utf-8")     # "en" = source text, whatever the language
    job.outputs["original.srt"] = "original.srt"
    job.meta["draft"] = True
    job.log("Draft: the subtitles are ready. Translate them with Claude (copy / paste), paste the Khmer text back, then press “Generate audio”.")
    job.save()


# --------------------------------------------------------------------------- #
# characters: who speaks which line (speakers.py listens, autovoice.py picks the voices)
# --------------------------------------------------------------------------- #
def _clear_characters(job: Job) -> None:
    for s in job.segments:
        s.pop("char", None)
        s.pop("gp", None)
    job.meta.pop("characters", None)


def _apply_detection(job: Job, det: "speakers.Detection") -> None:
    for s, d in zip(job.segments, det.lines):
        if d.get("char"):
            s["char"] = int(d["char"])
            s["gp"] = d.get("p")
        else:
            s.pop("char", None)
            s.pop("gp", None)
    job.meta["characters"] = [
        {"id": c["id"], "gender": c["gender"], "lines": c["lines"], "seconds": c["seconds"], "f0": c["f0"], "p": c["p"], "ref": c["ref"], "name": "", "voice": ""}
        for c in det.characters
    ]


def _speaker_audio(job: Job, vid: Optional[str], cookies: str, proxy: str) -> Optional[Path]:
    """The sound to listen to: the uploaded file, or the audio of the YouTube video (downloaded once, then kept in the job)."""
    media = local_media_of(job)
    if media:
        return media if (job.meta.get("upload") or {}).get("has_audio", True) else None
    if vid:
        return download_audio(vid, job.dir / "audio", cookies, proxy,
                              progress=lambda p: job.step("speakers", progress=0.02 + 0.2 * p, detail="downloading the audio"))
    return None


def run_speakers(job: Job, vid: Optional[str], cookies: str = "", proxy: str = "", keep_old: bool = False) -> str:
    """Listen to the video and write who speaks every line into the job (`char`, `gp` per line, `meta.characters`).

    Never fails the job: whatever goes wrong (no sound, a blocked download, music only ...) the dub simply uses the one voice that
    was chosen.  `keep_old`: a second try that does not work leaves the characters of the first one as they are.
    Returns ok | no_audio | unsure | failed  (also kept in meta.speakers); Cancelled is not caught."""
    job.step("speakers", "running", progress=0.02, detail="")
    state, note, det = "failed", "", None
    try:
        media = _speaker_audio(job, vid, cookies, proxy)
        if media is None:
            state = "no_audio"
        else:
            job.check_cancel()
            job.step("speakers", progress=0.25, detail="listening to the voices")
            det = speakers.analyze(
                media, [s["start"] for s in job.segments], [s["end"] for s in job.segments],
                progress=lambda p: job.step("speakers", progress=0.25 + 0.7 * p), check=job.check_cancel,
            )
            state = "ok" if det.characters else "unsure"
    except Cancelled:
        raise
    except SourceError as e:
        state, note = "no_audio", e.message
    except audio.FFmpegError as e:
        state, note = "failed", str(e)[-160:]
    except Exception as e:  # pragma: no cover - a bug here must never cost the user the dub
        job.log(traceback.format_exc())
        state, note = "failed", f"{type(e).__name__}: {e}"
    meta = dict(job.meta.get("speakers") or {"state": "ok"}) if (keep_old and state != "ok" and job.meta.get("characters")) else {"state": state}
    if state == "ok" and det is not None:
        _apply_detection(job, det)
        m = sum(1 for c in det.characters if c["gender"] == "male")
        f = len(det.characters) - m
        meta.update({"coverage": det.coverage, "n": len(det.characters)})
        detail = f"{len(det.characters)} character{'s' if len(det.characters) != 1 else ''} ({m} male, {f} female)"
        job.step("speakers", "done", detail=detail)
        job.log(f"Characters: {detail}, found from {det.coverage * 100:.0f}% of the speech. "
                + "; ".join(f"{c['id']} = {c['gender']} {c['f0']:.0f} Hz ({c['lines']} lines)" for c in det.characters if c["f0"]))
    else:
        kept = keep_old and bool(job.meta.get("characters"))
        if not kept:
            _clear_characters(job)
        tail = "the characters were left as they were" if kept else "every line uses the voice you chose"
        if state == "unsure":
            job.warn("SPEAKERS_UNSURE", f"The voices in this video could not be measured clearly (music, noise or whispering), so {tail}.")
            meta["coverage"] = det.coverage if det is not None else 0.0
        elif state == "no_audio":
            job.log(f"Characters: no sound to listen to{' - ' + note if note else ''}; {tail}.")
            if note:
                job.warn("SPEAKERS_NO_AUDIO", f"The sound of the video could not be loaded to tell the voices apart ({note[:120]}), so {tail}.")
        else:
            job.warn("SPEAKERS_FAILED", f"The voices could not be told apart ({note[:140]}), so {tail}.")
        job.step("speakers", "done" if kept else "skipped", detail={"unsure": "not clear enough", "no_audio": "no audio", "failed": "failed"}.get(state, ""))
    job.meta["speakers"] = meta
    job.save()
    return state


def _speakers_stage(job: Job, req: dict, vid: Optional[str], timed: bool) -> None:
    vs = VoiceSettings.from_dict(req.get("voice"))
    yt = req.get("youtube") or {}
    if not vs.auto:
        job.meta["speakers"] = {"state": "off"}
        job.step("speakers", "skipped", detail="off")
        return
    if not timed:                                    # lines without real times cannot be found in the sound
        job.meta["speakers"] = {"state": "untimed"}
        job.step("speakers", "skipped", detail="no timing")
        job.log("Characters: the text has no timestamps, so the voices cannot be matched to the lines; every line uses the voice you chose.")
        return
    run_speakers(job, vid, yt.get("cookies_browser") or "", yt.get("proxy") or "")


def run_detect_speakers(job: Job, req: dict) -> None:
    """"Detect characters" on a job that already exists (made before this feature, or made with it switched off)."""
    def work():
        yt = req.get("youtube") or {}
        if not any(x["key"] == "speakers" for x in job.steps):                      # a job from an older version has no such step
            job.steps.insert(min(1, len(job.steps)), {"key": "speakers", "status": "pending", "progress": 0.0, "detail": ""})
        job.warnings = [w for w in job.warnings if not str(w.get("code", "")).startswith("SPEAKERS_")]
        job.log("Listening to the video again to find the characters ...")
        before = next((dict(x) for x in job.steps if x["key"] == "speakers"), None)
        try:
            run_speakers(job, (job.video or {}).get("id"), yt.get("cookies_browser") or "", yt.get("proxy") or "", keep_old=True)
        except Cancelled:                           # the dub is fine: only the new search is dropped, the job stays as it was (not "cancelled")
            if before:
                job.step("speakers", before["status"], progress=before.get("progress", 0.0), detail=before.get("detail", ""))
            job.log("Cancelled - the characters were not changed.")

    job.status = "running"
    job.error = None
    _guard(job, work)


# --------------------------------------------------------------------------- #
# audio stages (shared with "regenerate")
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# per-line voice and timing (set in the editor table; stored in the segment as "voice", "t0", "t1")
# --------------------------------------------------------------------------- #
MIN_WINDOW = 0.3            # a hand-set End must come at least this long after the Start
MAX_TIME = 24 * 3600.0
valid_row_voice = autovoice.valid_row_voice       # Edge voice id | vox:original | vox:c:<id> | vox:p:<key> | vox:s:<character>


def clean_segment_edits(segments: List[dict], edits) -> List[dict]:
    """Validate the per-line edits of a Regenerate request: [{idx, km?, voice?, t0?, t1?}].
    voice "" / null = follow the job's voice again; t0 / t1 null = back to the caption times. Raises ValueError (shown to the user)."""
    if edits is None:
        return []
    if not isinstance(edits, list):
        raise ValueError("segments must be a list")
    by_idx = {s["idx"]: s for s in segments}
    out: List[dict] = []
    seen = set()
    for e in edits:
        if not isinstance(e, dict) or "idx" not in e:
            raise ValueError("every edited line needs an idx")
        try:
            idx = int(e["idx"])
        except (TypeError, ValueError):
            raise ValueError(f"bad line number: {e.get('idx')!r}")
        if idx not in by_idx:
            raise ValueError(f"line {idx + 1} does not exist")
        if idx in seen:
            raise ValueError(f"line {idx + 1} is listed twice")
        seen.add(idx)
        c: dict = {"idx": idx}
        if "km" in e:
            if e["km"] is not None and not isinstance(e["km"], str):
                raise ValueError(f"line {idx + 1}: the Khmer text must be text")
            c["km"] = e["km"] or ""
        if "voice" in e:
            v = e["voice"]
            if v in (None, ""):
                c["voice"] = None
            elif valid_row_voice(v):
                c["voice"] = v
            else:
                raise ValueError(f"line {idx + 1}: unknown voice {v!r}")
        for k, label in (("t0", "Start"), ("t1", "End")):
            if k in e:
                x = e[k]
                if x is None or x == "":
                    c[k] = None
                    continue
                try:
                    f = float(x)
                except (TypeError, ValueError):
                    raise ValueError(f"line {idx + 1}: {label} is not a number")
                if not (0.0 <= f <= MAX_TIME):          # also rejects NaN
                    raise ValueError(f"line {idx + 1}: {label} is out of range")
                c[k] = round(f, 3)
        seg = by_idx[idx]
        t0 = c["t0"] if "t0" in c else seg.get("t0")
        t1 = c["t1"] if "t1" in c else seg.get("t1")
        a0 = t0 if t0 is not None else float(seg["start"])
        if t1 is not None and t1 - a0 < MIN_WINDOW:
            raise ValueError(f"line {idx + 1}: End must be at least {MIN_WINDOW:.1f} s after Start")
        out.append(c)
    return out


def row_settings(base: VoiceSettings, voice: Optional[str]) -> Optional[VoiceSettings]:
    """Voice settings of a line that has its own voice; None = the line follows the job's voice."""
    if not voice or not valid_row_voice(voice):
        return None
    if voice.startswith("vox:"):
        return dataclasses.replace(base, engine="voxcpm", vox_id=voice)
    # the English voice that reads English terms normally follows the Khmer voice (Ava for Srey Mom, Andrew for Piseth),
    # unless the user picked one by hand
    own_en = bool(base.en_voice) and base.en_voice != default_en_voice_for(base.voice)
    return dataclasses.replace(base, engine="edge", voice=voice, en_voice=base.en_voice if own_en else "")


def auto_plan(job: Job, vs: VoiceSettings) -> Dict[int, str]:
    """character id -> voice, when "voices by character" is on and the job has characters (else empty)."""
    chars = (job.meta or {}).get("characters") or []
    if not (vs.auto and chars):
        return {}
    custom: List[dict] = []
    job_voice = vs.vox_id if vs.engine == "voxcpm" else ""
    job_gender = ""
    if vs.auto_male == autovoice.MINE or vs.auto_female == autovoice.MINE or job_voice.startswith("vox:c:"):
        from . import voxvoices

        custom = voxvoices.list_custom()
    if job_voice.startswith("vox:p:"):
        pr = voxpresets.get(job_voice[6:])
        job_gender = "female" if pr and pr.gender == "Female" else "male" if pr else ""
    elif job_voice.startswith("vox:c:"):
        cv = next((v for v in custom if v["id"] == job_voice), None)
        job_gender = {"Female": "female", "Male": "male"}.get((cv or {}).get("gender") or "", "")
    return autovoice.plan(chars, vs.engine, vs.auto_male, vs.auto_female, custom, job_voice, job_gender)


def _row_voices(segs: List[dict], ctx: "AudioCtx", voices: Optional[Dict[int, str]] = None) -> List[VoiceSettings]:
    """The voice settings of every line:  the line's own voice  >  its character's voice  >  the job's voice."""
    out = []
    for s in segs:
        v = s.get("voice") or (autovoice.line_voice(s, voices) if voices else None)
        out.append(row_settings(ctx.vs, v) or ctx.vs)
    return out


def _eff_start(s: dict) -> float:
    return float(s["t0"]) if s.get("t0") is not None else float(s["start"])


def _windows(segs: List[dict]) -> List[tuple]:
    """(start, deadline) of the time each line may use. A hand-set Start / End wins; otherwise a line runs from its caption
    start until just before the next line starts (the last line gets a few seconds extra)."""
    n = len(segs)
    out = []
    for i, s in enumerate(segs):
        a = _eff_start(s)
        if s.get("t1") is not None:
            b = float(s["t1"])
        elif i + 1 < n:
            b = _eff_start(segs[i + 1]) - 0.10
        else:
            b = float(s["end"]) + 4.0 - 0.10
        out.append((a, b))
    return out


def _slot_for(wins: List[tuple], i: int) -> float:
    return max(0.6, wins[i][1] - wins[i][0])


def _fmt_eta(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 90:
        return f"{seconds}s"
    return f"{seconds // 60} min" if seconds < 3600 else f"{seconds // 3600}h {(seconds % 3600) // 60}m"


async def _vox_rows(job: Job, segs: List[dict], ctx: AudioCtx, idxs: List[int], vss: List[VoiceSettings], wins: List[tuple],
                    audios: list, rates: list, lo: float = 0.0, hi: float = 1.0) -> None:
    """Local VoxCPM2 engine: one line at a time (a GPU can only do one), timing fitted afterwards by time-stretching.
    Lines may use different VoxCPM2 voices; every voice is prepared once, in order of first use."""
    from .vox import manager
    from .voxvoices import VoxSynth, resolve_voice

    m = len(idxs)
    mgr = manager()

    def status(msg: str) -> None:
        job.step("tts", detail=str(msg)[:90])

    job.step("tts", detail="preparing the voice …")
    synths: Dict[str, "VoxSynth"] = {}
    labels: List[str] = []
    for i in idxs:
        vid = vss[i].vox_id
        if vid in synths:
            continue
        resolved = await asyncio.to_thread(
            resolve_voice, vss[i], mgr=mgr, status=status, cancelled=job.cancel_flag.is_set, log=job.log,
            job_dir=job.dir, segs=job.segments, vid=ctx.vid, cookies=ctx.cookies, proxy=ctx.proxy, media=ctx.local_video,
            chars=job.meta.get("characters"),
            progress=lambda p: job.step("tts", detail=f"downloading audio {int(p * 100)}%"),
        )
        job.check_cancel()
        if resolved.kind == "original":
            job.outputs["voice_ref.wav"] = "voice_ref.wav"
        elif resolved.kind == "character":                       # the sample that was copied from this character (the page lets the user listen to it)
            ref_name = f"voice_ref_c{vid[6:]}.wav"
            job.outputs[ref_name] = ref_name
        synths[vid] = VoxSynth(resolved, ctx.vs.vox_quality, mgr, status=status, cancelled=job.cancel_flag.is_set)
        labels.append(resolved.label)
    fit = ctx.sync == "fit"
    for k, i in enumerate(idxs):
        job.check_cancel()
        audios[i] = await synths[vss[i].vox_id].segment(segs[i]["km"], vss[i], ctx.readings)
        calls = sum(x.calls for x in synths.values())
        gen_s = sum(x.gen_s for x in synths.values())
        eta = f" · ~{_fmt_eta((gen_s / calls) * (m - k - 1))} left" if calls and k + 1 < m else ""
        job.step("tts", progress=lo + (hi - lo) * (0.92 if fit else 1.0) * (k + 1) / m, detail=f"{k + 1}/{m}{eta}")

    if fit:
        stretched = 0
        for i in idxs:
            a = audios[i]
            if a is None or not len(a):
                continue
            need = (len(a) / SR) / _slot_for(wins, i)
            if need > 1.05:
                factor = min(need * 1.03, ctx.max_speed)
                audios[i] = audio.time_stretch(a, factor)
                rates[i] = int(round(((1 + ctx.vs.rate / 100.0) * factor - 1) * 100))
                stretched += 1
        if stretched:
            job.log(f"Fitting timing: sped up {stretched} of {m} lines (max ×{ctx.max_speed:.2f}).")
    calls = sum(x.calls for x in synths.values())
    hits = sum(x.cache_hits for x in synths.values())
    gen_s = sum(x.gen_s for x in synths.values())
    audio_s = sum(x.audio_s for x in synths.values())
    rtf = gen_s / max(audio_s, 0.1) if calls else None
    job.meta["vox"] = {"voice": next(iter(synths)), "label": ", ".join(labels[:3]) + ("…" if len(labels) > 3 else ""),
                       "quality": ctx.vs.vox_quality, "rtf": round(rtf, 2) if rtf is not None else None,
                       "lines": calls, "cached": hits, "voices": list(synths)}
    job.log(f"VoxCPM2: {calls} lines generated"
            + (f" in {gen_s:.0f} s ({rtf:.2f}x real time)" if rtf is not None else "")
            + f", {hits} served from cache.")


async def _edge_rows(job: Job, segs: List[dict], ctx: AudioCtx, idxs: List[int], vss: List[VoiceSettings], wins: List[tuple],
                     audios: list, rates: list, lo: float = 0.0, hi: float = 1.0) -> None:
    """Microsoft Edge voices: all lines at once (4 requests in parallel); lines that are too long are then spoken again, faster."""
    synth = Synth(concurrency=4, on_retry=job.log)
    m = len(idxs)
    fit = ctx.sync == "fit"
    done = 0

    async def pass1(i: int):
        nonlocal done
        job.check_cancel()
        audios[i] = await synth.segment(segs[i]["km"], vss[i], ctx.readings)
        done += 1
        job.step("tts", progress=lo + (hi - lo) * (0.75 if fit else 1.0) * done / m, detail=f"{done}/{m}")

    await asyncio.gather(*[pass1(i) for i in idxs])

    if fit:
        todo = []
        for i in idxs:
            d = len(audios[i]) / SR
            need = d / _slot_for(wins, i)
            if need > 1.05:
                factor = min(need * 1.03, ctx.max_speed)
                rate_i = int(round(((1 + ctx.vs.rate / 100.0) * factor - 1) * 100))
                rate_i = min(rate_i, 120)
                if rate_i > ctx.vs.rate + 2:
                    todo.append((i, rate_i))
        if todo:
            job.log(f"Fitting timing: speeding up {len(todo)} of {m} segments (max ×{ctx.max_speed:.2f}).")
        done2 = 0

        async def pass2(i: int, rate_i: int):
            nonlocal done2
            job.check_cancel()
            a = await synth.segment(segs[i]["km"], vss[i], ctx.readings, rate=rate_i)
            if len(a):
                audios[i] = a
                rates[i] = rate_i
            done2 += 1
            job.step("tts", progress=lo + (hi - lo) * (0.75 + 0.25 * done2 / max(1, len(todo))))

        await asyncio.gather(*[pass2(i, r) for i, r in todo])
    job.log(f"Edge TTS: {synth.calls} requests, {synth.cache_hits} served from cache.")


async def _synth_all(job: Job, segs: List[dict], ctx: AudioCtx):
    """Speak every line. Lines can have their own voice (Edge and VoxCPM2 can be mixed in one job)."""
    n = len(segs)
    vss = _row_voices(segs, ctx, auto_plan(job, ctx.vs))
    wins = _windows(segs)
    audios: List[Optional[np.ndarray]] = [None] * n
    rates = [ctx.vs.rate] * n
    edge_idx = [i for i, v in enumerate(vss) if v.engine != "voxcpm"]
    vox_idx = [i for i, v in enumerate(vss) if v.engine == "voxcpm"]
    if edge_idx:
        await _edge_rows(job, segs, ctx, edge_idx, vss, wins, audios, rates, 0.0, 0.12 if vox_idx else 1.0)
    if vox_idx:
        await _vox_rows(job, segs, ctx, vox_idx, vss, wins, audios, rates, 0.12 if edge_idx else 0.0, 1.0)
    return audios, rates


def _build_track(job: Job, segs: List[dict], audios: List[np.ndarray], rates: List[int], ctx: AudioCtx) -> np.ndarray:
    n = len(segs)
    wins = _windows(segs)
    # Pre-allocate once (growing a big array segment by segment is O(n²) for hour-long videos).
    voiced = sum(len(a) for a in audios if a is not None) / SR
    last = max([float(s["end"]) for s in segs] + [w[1] for w in wins])
    horizon = (last if ctx.sync == "fit" else 0.0) + voiced + n * 1.0 + 15.0
    track = np.zeros(int(horizon * SR), dtype=np.float32)
    end_max = 0
    cursor = 0.0
    max_drift = 0.0
    stretched = 0
    for i, (s, a) in enumerate(zip(segs, audios)):
        job.check_cancel()
        s.pop("warn", None)
        s["slot"] = [round(wins[i][0], 3), round(wins[i][1], 3)]     # the time this line was allowed to use (the editor shows it)
        if a is None or len(a) == 0:
            s["out_start"] = s["out_end"] = None
            s["speed"] = None
            s.pop("dur", None)
            continue
        d = len(a) / SR
        resid = 1.0
        if ctx.sync == "natural":
            start = cursor
        else:
            start = max(wins[i][0], cursor)
            # a hand-set End is a deadline; otherwise the next line's start is
            limit = float(s["t1"]) if s.get("t1") is not None else (_eff_start(segs[i + 1]) - 0.06 if i + 1 < n else None)
            if limit is not None:
                avail = limit - start
                if d > avail > 0.5:
                    resid = min(d / avail, 1.15)
                    if resid > 1.03:
                        a = audio.time_stretch(a, resid)
                        d = len(a) / SR
                        stretched += 1
                    else:
                        resid = 1.0
        track = audio.mix_into(track, a, start)
        end_max = max(end_max, int((start + d) * SR))
        s["out_start"] = round(start, 3)
        s["out_end"] = round(start + d, 3)
        base_speed = (1 + rates[i] / 100.0) / (1 + ctx.vs.rate / 100.0)
        s["speed"] = round(base_speed * resid, 2)
        s["dur"] = round(d * base_speed * resid, 3)                  # how long the line is at normal speed (the editor predicts the speed-up from it)
        drift = start - wins[i][0]
        max_drift = max(max_drift, drift)
        warns = []
        if ctx.sync == "fit" and drift > 2.5:
            warns.append("late")                                       # pushed back by the line before it
        if ctx.sync == "fit" and start + d > wins[i][1] + 0.35:
            warns.append("long")                                       # does not fit its time even at the top speed
        if warns:
            s["warn"] = " ".join(warns)
        if ctx.sync == "natural":
            gap = 0.3
            if i + 1 < n:
                gap = min(0.9, max(0.2, segs[i + 1]["start"] - s["end"]))
            cursor = start + d + gap
        else:
            cursor = start + d + 0.06
    track = audio.soft_limit(track[: end_max + int(0.3 * SR)])
    job.meta["max_drift"] = round(max_drift, 2)
    job.meta["stretched"] = stretched
    job.meta["audio_duration"] = round(len(track) / SR, 2)
    job.log(f"Dubbed track: {len(track) / SR / 60:.2f} min · max lag behind video {max_drift:.1f}s")
    return track


def _duck_mask(job: Job, segs: List[dict], video_path, ctx: AudioCtx) -> Optional[Path]:
    """Gain envelope (WAV) that silences the ORIGINAL audio while somebody is speaking: the original speaker (English caption
    times) or the Khmer voice (where its line was placed). None when the option is off or there is nothing to mute."""
    if not (ctx.duck and ctx.orig_vol > 0):
        return None
    windows = []
    for s in segs:
        if not (s.get("km") or "").strip():
            continue                      # nothing replaces this caption (e.g. [Music]) -> leave the original sound alone
        windows.append((s["start"], s["end"]))
        if s.get("out_start") is not None:
            windows.append((s["out_start"], s["out_end"]))
    ivs = audio.duck_intervals(windows)
    if not ivs:
        return None
    total = max(audio.probe_media(video_path).get("duration") or 0.0, float(job.meta.get("audio_duration") or 0.0), ivs[-1][1]) + 2.0
    path = job.dir / "duck_mask.wav"
    audio.write_gain_wav(audio.duck_envelope(ivs, total), path)
    muted = sum(b - a for a, b in ivs)
    job.meta["duck"] = {"stretches": len(ivs), "muted_s": round(muted, 1)}
    job.log(f"Original audio: muted while Khmer speaks ({len(ivs)} stretches, {muted:.0f} s of {total:.0f} s); "
            f"in the pauses it plays at {ctx.orig_vol * 100:.0f}%.")
    return path


def _audio_stages(job: Job, ctx: AudioCtx) -> None:
    segs = job.segments
    for s in segs:
        s["km"] = ensure_khmer_terminal((s.get("km") or "").strip()) if (s.get("km") or "").strip() else ""

    # ---- TTS
    job.step("tts", "running", progress=0.0, detail="")
    for key in [k for k in job.outputs if k == "voice_ref.wav" or re.fullmatch(r"voice_ref_c\d+\.wav", k)]:
        job.outputs.pop(key, None)
    job.meta.pop("vox", None)
    job.meta["tts_engine"] = ctx.vs.engine
    own_voice = sum(1 for s in segs if s.get("voice"))
    own_time = sum(1 for s in segs if s.get("t0") is not None or s.get("t1") is not None)
    job.meta["row_voices"], job.meta["row_times"] = own_voice, own_time
    if ctx.vs.engine == "voxcpm":
        job.log(f"Speech: VoxCPM2 (local) · voice {ctx.vs.vox_id} · quality {ctx.vs.vox_quality} · speed {ctx.vs.rate:+d}% · sync: {ctx.sync}")
    else:
        job.log(f"Speech: {ctx.vs.voice} · speed {ctx.vs.rate:+d}% · terms: "
                f"{'English voice ' + ctx.vs.en_voice if ctx.vs.term_mode == 'english_voice' else 'Khmer voice only'} · sync: {ctx.sync}")
    if own_voice:
        job.log(f"Per-line voices: {own_voice} of {len(segs)} lines use a voice of their own.")
    plan = auto_plan(job, ctx.vs)
    if plan:
        job.meta["char_voices"] = {str(k): v for k, v in plan.items()}
        job.log("Voices by character: " + "; ".join(f"{c['id']} ({c['gender']}, {c['lines']} lines) -> {plan[c['id']] or 'the voice of the job'}" for c in job.meta["characters"] if c["id"] in plan) + ".")
    else:
        job.meta.pop("char_voices", None)
        if ctx.vs.auto:
            job.log("Voices by character is on, but this job has no characters (see the Detect characters step) - every line uses the chosen voice.")
    if own_time:
        job.log(f"Per-line timing: {own_time} lines have a Start / End set by hand"
                + ("." if ctx.sync == "fit" else " (ignored here: 'natural pace' mode places the lines one after another)."))
    audios, rates = asyncio.run(_synth_all(job, segs, ctx))
    job.step("tts", "done", detail=f"{sum(1 for a in audios if a is not None and len(a))}/{len(segs)} lines")
    job.check_cancel()

    # ---- MIX
    job.step("mix", "running", progress=0.1)
    track = _build_track(job, segs, audios, rates, ctx)
    job.step("mix", progress=0.5)
    audio.encode_array(track, job.dir / "dub.mp3", bitrate="128k")

    timed_segs = [s for s in segs if s.get("out_start") is not None]
    (job.dir / "khmer.srt").write_text(to_srt(timed_segs, "km", "out_start", "out_end"), encoding="utf-8")
    (job.dir / "original.srt").write_text(to_srt(segs, "en", "start", "end"), encoding="utf-8")   # "en" = source text, whatever the language
    (job.dir / "english.srt").unlink(missing_ok=True)          # jobs made before v1.3 wrote english.srt
    job.outputs.pop("english.srt", None)
    (job.dir / "script_km.txt").write_text("\n\n".join(s["km"] for s in segs if s["km"]), encoding="utf-8")
    job.outputs.update({"dub.mp3": "dub.mp3", "khmer.srt": "khmer.srt", "original.srt": "original.srt", "script_km.txt": "script_km.txt"})
    job.meta.pop("draft", None)                  # a copy / paste draft is a real dub from here on
    job.step("mix", "done")
    job.save()

    # ---- VIDEO (optional – failure keeps the audio result)
    _video_stage(job, ctx, segs)


# Warning codes that belong to the MP4 step (cleared when only the video is made again)
VIDEO_WARNINGS = ("NO_PICTURE", "NO_VIDEO_SOURCE", "FFMPEG_FAILED", "DUCK_FAILED", "TIKTOK_LONG", "TIKTOK_BIG")


def _video_stage(job: Job, ctx: AudioCtx, segs: List[dict]) -> None:
    """The optional MP4: the original picture - or its vertical 9:16 version for TikTok - with the Khmer audio.
    A failure keeps the audio result (the step shows an error and there is a warning); an older MP4 is only replaced when the new one is complete."""
    if not (ctx.want_video and (ctx.vid or ctx.local_video)):
        if ctx.want_video and not ctx.vid:
            job.warn("NO_VIDEO_SOURCE", "MP4 export needs a YouTube link or an uploaded video as the source.")
        job.step("video", "skipped")
        job.save()
        return
    local = ctx.local_video
    vertical = ctx.aspect == "9:16"
    job.step("video", "running", progress=0.02, detail="preparing your video …" if local else f"downloading video (up to {ctx.max_height}p) …")
    out_path = job.dir / "dubbed.mp4"
    try:
        if local:                                   # an uploaded file: nothing to download
            vp = local
            if not audio.probe_media(vp).get("has_video"):
                raise SourceError("NO_PICTURE", "This file has no picture (it is audio only), so only the MP3 was made.")
        else:
            vp = download_video(
                ctx.vid, job.dir / "video", ctx.cookies, ctx.proxy, with_audio=ctx.orig_vol > 0, max_height=ctx.max_height,
                progress=lambda p: job.step("video", progress=0.05 + 0.75 * p),
            )
        job.check_cancel()
        vi: dict = {}
        info: dict = {}
        try:
            vi = audio.probe_media(vp)
            scaled = audio.needs_scale(vi.get("width"), vi.get("height"), ctx.max_height)
            out_h = min(vi.get("width") or 0, vi.get("height") or 0) if vi.get("width") and vi.get("height") else None
            info = {"width": vi.get("width"), "height": (min(out_h, ctx.max_height) if (scaled and out_h) else vi.get("height")),
                    "codec": vi.get("video_codec"), "limit": ctx.max_height}
            job.log(f"Video: {vi.get('width')}×{vi.get('height')} {vi.get('video_codec')} (limit {ctx.max_height}p)"
                    + (f" – bigger than {ctx.max_height}p: will be scaled down (re-encoded, slower)" if scaled and not vertical
                       else ("" if vi.get("video_codec") in ("h264", "hevc", "mpeg4") or vertical else " – will be re-encoded to H.264 (slower)")))
        except Exception:  # noqa: BLE001 - only information
            pass
        plan = frame.plan(vi, ctx.aspect, ctx.fit, ctx.crop_x, ctx.max_height)      # None = the shape stays as it is
        hs = hardsub.plan(vi, ctx.hide_subs, ctx.hide_effect, ctx.hide_bottom, ctx.hide_height, ctx.hide_strength)     # None = the old subtitles stay
        what = "adding Khmer audio …"
        if hs is not None:
            what = "hiding the original subtitles …"
            job.log(f"Original subtitles hidden: {hs.label} - the picture is re-encoded (this takes longer).")
        if plan is not None:
            what = "making the vertical video …"
            job.log(f"TikTok / Reels / Shorts: {plan.label} - the picture is re-encoded (this takes longer than the original shape).")
        elif vertical:
            job.log("The picture already is 9:16 - nothing to fit.")
        job.step("video", progress=0.85, detail=what)

        def on_progress(p: float) -> None:
            job.step("video", progress=0.86 + 0.13 * p, detail=f"{what} {int(p * 100)}%")

        mask = None
        try:
            mask = _duck_mask(job, segs, vp, ctx)
        except Exception as e:  # noqa: BLE001 - the MP4 matters more than this extra
            job.warn("DUCK_FAILED", f"Could not prepare 'mute the original voice while Khmer speaks': {e}")
        try:
            audio.mux_video(vp, job.dir / "dub.mp3", out_path, ctx.orig_vol, progress=on_progress, duck_mask=mask,
                            max_height=ctx.max_height, frame=plan, hardsub=hs, cancel=job.cancel_flag.is_set)
        except audio.FFmpegError as e:
            job.check_cancel()                      # the user stopped it: not a failure
            if mask is None:
                raise
            job.warn("DUCK_FAILED", f"Could not mute the original voice while Khmer speaks ({str(e)[-200:]}). "
                                    "The original audio is mixed in at a constant level instead.")
            audio.mux_video(vp, job.dir / "dub.mp3", out_path, ctx.orig_vol, progress=on_progress,
                            max_height=ctx.max_height, frame=plan, hardsub=hs, cancel=job.cancel_flag.is_set)
        finally:
            if mask is not None:
                mask.unlink(missing_ok=True)
        # what was really made
        mo = audio.probe_media(out_path)
        size = out_path.stat().st_size
        info.update({"aspect": "9:16" if vertical else "original", "fit": plan.fit if plan else None, "crop_x": plan.crop_x if plan else None,
                     "hide": hs.as_info() if hs else None,
                     "out_width": mo.get("width"), "out_height": mo.get("height"), "size": size, "duration": mo.get("duration")})
        job.meta["video"] = info
        job.outputs["dubbed.mp4"] = "dubbed.mp4"
        if vertical:
            if (mo.get("duration") or 0) > frame.TIKTOK_MAX_MINUTES * 60 + 1:
                job.warn("TIKTOK_LONG", f"This video is {(mo.get('duration') or 0) / 60:.0f} minutes long. TikTok accepts up to "
                                        f"{frame.TIKTOK_MAX_MINUTES} minutes on most accounts.")
            if size > frame.TIKTOK_APP_MAX_MB * 1_000_000:
                job.warn("TIKTOK_BIG", f"The MP4 is {size / 1e6:.0f} MB. The TikTok phone app accepts about {frame.TIKTOK_APP_MAX_MB} MB (iPhone) "
                                       "or 72 MB (Android) - upload it from a computer (tiktok.com) or choose 720p.")
        job.step("video", "done")
    except SourceError as e:
        job.step("video", "error", detail=e.message[:160])
        job.warn(e.code, f"MP4 video was not created: {e.message}")
    except audio.FFmpegError as e:
        job.check_cancel()
        job.step("video", "error", detail=str(e)[:160])
        job.warn("FFMPEG_FAILED", f"MP4 video was not created: {e}")
    job.save()


# --------------------------------------------------------------------------- #
# REGENERATE (after the user edits Khmer text or changes the voice)
# --------------------------------------------------------------------------- #
def run_regenerate(job: Job, req: dict) -> None:
    def work():
        if job.kind == "tts":
            for key in ("tts", "mix"):
                job.step(key, "pending", progress=0.0, detail="")
            job.outputs.pop("speech.mp3", None)
            _tts_core(job, req.get("km_text") or job.meta.get("km_text") or "", VoiceSettings.from_dict(req.get("voice") or job.params.get("voice")))
            return
        by_idx = {e["idx"]: e for e in clean_segment_edits(job.segments, req.get("segments"))}
        for s in job.segments:
            e = by_idx.get(s["idx"])
            if not e:
                continue
            if "km" in e:
                s["km"] = e["km"]
            for k in ("voice", "t0", "t1"):            # null = back to the default (job voice / caption times)
                if k in e:
                    if e[k] is None:
                        s.pop(k, None)
                    else:
                        s[k] = e[k]
        if req.get("characters"):                       # edits of the characters panel: gender flip, a voice for the character, a name
            autovoice.apply_character_edits(job.meta.get("characters") or [], req["characters"])
        merged = copy.deepcopy(job.params)
        for k in ("voice", "output", "youtube"):
            if req.get(k):
                merged[k] = {**(merged.get(k) or {}), **req[k]}
        job.params = sanitize_params(merged)
        vid = (job.video or {}).get("id")
        ctx = _ctx_from(merged, vid, bool(job.meta.get("timed", True)), local_media_of(job))
        for key in ("tts", "mix", "video"):
            job.step(key, "pending", progress=0.0, detail="")
        job.error = None
        job.warnings = []
        job.outputs.pop("dubbed.mp4", None)
        if not audio.remove_file(job.dir / "dubbed.mp4"):         # Windows: a player may still hold the old MP4 - it is replaced when the new one is ready
            job.log("The old dubbed.mp4 is still open in another program (the browser?). It will be replaced when the new video is ready.")
        if job.meta.get("draft"):
            job.step("translate", "done", detail="copy & paste")
        job.log("Generating the audio from the pasted text …" if job.meta.get("draft") else "Regenerating audio with the edited text …")
        _audio_stages(job, ctx)

    job.status = "running"
    job.error = None
    _guard(job, work)


def run_remake_video(job: Job, req: dict) -> None:
    """Only the MP4 is made again (another shape for TikTok, another size): the Khmer audio and the edits stay as they are.
    When that fails or is cancelled, the previous MP4 (if there is one) and its settings stay."""
    def work():
        old_params = copy.deepcopy(job.params)
        had_mp4 = "dubbed.mp4" in job.outputs and (job.dir / "dubbed.mp4").exists()
        merged = copy.deepcopy(job.params)
        out = dict(merged.get("output") or {})
        for k in ("aspect", "fit", "crop_x", "max_height", "hide_subs", "hide_effect", "hide_bottom", "hide_height", "hide_strength"):
            if req.get(k) is not None:
                out[k] = req[k]
        out["video"] = True
        merged["output"] = out
        job.params = sanitize_params(merged)
        ctx = _ctx_from(merged, (job.video or {}).get("id"), bool(job.meta.get("timed", True)), local_media_of(job))
        job.warnings = [w for w in job.warnings if w.get("code") not in VIDEO_WARNINGS]
        job.error = None
        job.step("video", "pending", progress=0.0, detail="")
        job.log("Making the video again" + (" (vertical 9:16 for TikTok) …" if ctx.aspect == "9:16" else " …"))
        try:
            _video_stage(job, ctx, job.segments)
        except Cancelled:
            job.step("video", "done" if had_mp4 else "skipped", progress=1.0 if had_mp4 else 0.0, detail="")
            job.log("Cancelled - the previous video was kept." if had_mp4 else "Cancelled.")
            job.params = old_params
            return                                  # the dub itself is fine: the job is not 'cancelled'
        if had_mp4 and next((x for x in job.steps if x["key"] == "video"), {}).get("status") != "done":
            job.params = old_params                 # the new MP4 was not made: the settings of the old one stay

    job.status = "running"
    job.error = None
    _guard(job, work)


# --------------------------------------------------------------------------- #
# TEXT-TO-SPEECH JOB
# --------------------------------------------------------------------------- #
def run_tts_job(job: Job, req: dict) -> None:
    _guard(job, lambda: _tts(job, req))


def _tts(job: Job, req: dict) -> None:
    text = (req.get("text") or "").strip()
    if not text:
        raise TTSError("There is no text to speak.")
    if len(text) > MAX_TTS_CHARS:
        raise TTSError(f"Text is too long ({len(text)} characters). Maximum is {MAX_TTS_CHARS}.")
    vs = VoiceSettings.from_dict(req.get("voice"))
    input_lang = str(req.get("input_lang") or "km").lower()
    job.meta["source_text"] = text
    if input_lang != "km":
        # English / Chinese / Korean text is translated first; the writing system of the text has the last word
        lang, note = resolve_lang(input_lang, text)
        if note:
            job.log(note)
        if lang not in LANGS:
            raise SourceError("LANG_UNSUPPORTED", f"The text is written in {lang_name(lang)}. Only English, Chinese and Korean are supported.")
        job.meta["src_lang"] = lang
        job.step("translate", "running", progress=0.1)
        tcfg = TranslateConfig.from_dict(req.get("translate"))
        tcfg.src_lang = lang
        job.log(f"Translating {LANGS[lang].name} → Khmer …")
        tr = Translator(tcfg, log=job.log)
        try:
            km = tr.translate_text(
                text,
                progress=lambda d, t: job.step("translate", progress=d / max(1, t), detail=f"{d}/{t}"),
                cancelled=job.cancel_flag.is_set,
                status=lambda m: job.step("translate", detail=m),
            )
        finally:
            tr.close()
        job.step("translate", "done")
    else:
        job.step("translate", "skipped")
        km = text
    job.check_cancel()
    _tts_core(job, km, vs)


def _tts_core(job: Job, km_text: str, vs: VoiceSettings) -> None:
    km_text = (km_text or "").strip()
    if not km_text:
        raise TTSError("There is no text to speak.")
    job.meta["km_text"] = km_text
    _, readings = parse_glossary_text(load_glossary_text())
    job.step("tts", "running", progress=0.0)
    job.meta["tts_engine"] = vs.engine
    if vs.engine == "voxcpm":
        job.log(f"Speech: VoxCPM2 (local) · voice {vs.vox_id} · quality {vs.vox_quality} · speed {vs.rate:+d}% · {len(km_text)} characters")
    else:
        job.log(f"Speech: {vs.voice} · speed {vs.rate:+d}% · {len(km_text)} characters")
    track = asyncio.run(
        synth_long_text(
            km_text, vs, readings,
            progress=lambda d, t: job.step("tts", progress=d / max(1, t), detail=f"{d}/{t}"),
            cancelled=job.cancel_flag.is_set,
            on_retry=job.log,
            status=lambda m: job.step("tts", detail=str(m)[:90]),
        )
    )
    job.check_cancel()
    job.step("tts", "done")
    job.step("mix", "running", progress=0.3)
    track = audio.soft_limit(np.concatenate([track, audio.silence(0.15)]))
    audio.encode_array(track, job.dir / "speech.mp3", bitrate="128k")
    job.outputs["speech.mp3"] = "speech.mp3"
    job.meta["audio_duration"] = round(len(track) / SR, 2)
    job.step("mix", "done")
    job.log(f"Done: {len(track) / SR:.1f} s of audio.")
