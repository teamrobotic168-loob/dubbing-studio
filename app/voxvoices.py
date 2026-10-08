"""VoxCPM2 voices and the synthesizer.

* "Speaker in the video" (vox:original) cuts a clean 8-20 s clip out of the video's own audio and clones it.
* "My voices" (vox:c:<id>) are short clips the user uploads (their own voice, or someone who gave permission).
* "Designed voices" (vox:p:<key>) are 8 ready-made voices described in words (see voxpresets.py): the engine speaks
  a short sentence in the described voice ONCE, and every line afterwards clones that clip, so the voice never changes.
* "vox:default" speaks with no reference at all (a fixed-seed voice). Only the Settings "test" uses it.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from . import audio, speakers, voxpresets
from .config import DATA_DIR, SAMPLE_RATE as SR, TTS_CACHE_DIR
from .glossary import apply_readings
from .jobs import Cancelled
from .textutil import is_speakable, normalize_ws, split_sentences, strip_zero_width
from .vox import VoxError, VoxManager, manager

VOICES_DIR = DATA_DIR / "voices"
MODEL_TAG = "voxcpm2"
QUALITY_STEPS = {"fast": 6, "balanced": 10, "high": 20}
CFG = 2.0
SEED = 1234
MAX_UPLOAD_BYTES = 30 * 1024 * 1024

PREVIEW_TEXT = "សួស្តី! នេះគឺជាសំឡេងគំរូ។ យើងអាចប្រើ API និង Machine Learning ដើម្បីបកប្រែវីដេអូជាភាសាខ្មែរបានយ៉ាងឆាប់រហ័ស។"


# --------------------------------------------------------------------------- #
# small utilities
# --------------------------------------------------------------------------- #
def _sha(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        h.update(fh.read(4 * 1024 * 1024))
    h.update(str(path.stat().st_size).encode())
    return h.hexdigest()[:12]


def _convert_ref(src: Path, dst: Path, start: Optional[float] = None, dur: Optional[float] = None) -> None:
    """Any audio/video file -> clean mono 24 kHz WAV reference (light high-pass + loudness normalisation)."""
    cmd = [audio.ffmpeg_exe(), "-v", "error", "-nostdin", "-y"]
    if start:
        cmd += ["-ss", f"{max(0.0, start):.3f}"]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", str(src), "-vn", "-ac", "1", "-ar", "24000", "-af", "highpass=f=60,loudnorm=I=-20:TP=-2:LRA=11",
            "-codec:a", "pcm_s16le", str(dst)]
    audio._run(cmd, timeout=600)


# --------------------------------------------------------------------------- #
# custom voices (uploaded by the user)
# --------------------------------------------------------------------------- #
def list_custom() -> List[dict]:
    out = []
    if VOICES_DIR.exists():
        for d in sorted(VOICES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                if (d / "ref.wav").exists():
                    out.append({"id": f"vox:c:{meta['id']}", "name": meta.get("name") or meta["id"], "native": "",
                                "gender": meta.get("gender") or "", "duration": meta.get("duration"), "kind": "custom",
                                "created": meta.get("created")})
            except Exception:
                continue
    return out


def custom_ref_path(cid: str) -> Optional[Path]:
    if not re.fullmatch(r"[0-9a-f]{8}", cid or ""):
        return None
    p = VOICES_DIR / cid / "ref.wav"
    return p if p.exists() else None


def save_custom_voice(name: str, filename: str, data_b64: str, gender: str = "") -> dict:
    try:
        raw = base64.b64decode(data_b64.split(",", 1)[-1], validate=False)
    except Exception:
        raise VoxError("VOX_BAD_AUDIO", "The audio file could not be read.")
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise VoxError("VOX_BAD_AUDIO", "The audio file is empty or larger than 30 MB.")
    cid = uuid.uuid4().hex[:8]
    d = VOICES_DIR / cid
    d.mkdir(parents=True, exist_ok=True)
    ext = Path(filename or "voice.wav").suffix.lower()
    ext = ext if re.fullmatch(r"\.[a-z0-9]{1,5}", ext) else ".wav"
    src = d / f"upload{ext}"
    try:
        src.write_bytes(raw)
        _convert_ref(src, d / "ref.wav", dur=40.0)
        arr = audio.decode_to_array(d / "ref.wav", sr=SR)
        arr = audio.trim_silence(arr)
        dur = len(arr) / SR
        if dur < 3.0:
            raise VoxError("VOX_BAD_AUDIO", "The clip is too short. Please use 8-25 seconds of clear speech from one person.")
        if dur > 30.0:
            arr = arr[: int(30.0 * SR)]
        audio.encode_array(arr, d / "ref.wav", sr=SR)
        dur = len(arr) / SR
    except VoxError:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except audio.FFmpegError as exc:
        shutil.rmtree(d, ignore_errors=True)
        raise VoxError("VOX_BAD_AUDIO", f"This file could not be decoded: {str(exc)[-200:]}")
    finally:
        try:
            src.unlink()
        except OSError:
            pass
    auto = False
    if gender not in ("Female", "Male"):
        gender = ""
        try:                                    # nobody has to say whether it is a man or a woman: the pitch of the voice tells (only when it is clear)
            g = speakers.gender_of_clip(d / "ref.wav")
            if g and g["sure"]:
                gender, auto = g["gender"], True
        except Exception:
            pass
    meta = {"id": cid, "name": (name or "My voice").strip()[:60] or "My voice", "created": time.time(), "duration": round(dur, 1),
            "gender": gender, "gender_auto": auto}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return {"id": f"vox:c:{cid}", "name": meta["name"], "duration": meta["duration"], "kind": "custom", "gender": meta["gender"], "native": ""}


def _update_meta(cid: str, change: dict) -> Optional[dict]:
    """Write fields of meta.json of a saved voice (None when the voice does not exist).  The list is sorted by the age of the
    folders, so the age is put back: changing a voice must not move it to the top."""
    if not re.fullmatch(r"[0-9a-f]{8}", cid or ""):
        return None
    d = VOICES_DIR / cid
    mp = d / "meta.json"
    if not mp.exists() or not (d / "ref.wav").exists():
        return None
    meta = json.loads(mp.read_text(encoding="utf-8"))
    meta.update(change)
    age = d.stat()
    tmp = mp.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    tmp.replace(mp)
    try:
        os.utime(d, ns=(age.st_atime_ns, age.st_mtime_ns))
    except OSError:
        pass
    return {"id": f"vox:c:{cid}", "name": meta.get("name") or cid, "duration": meta.get("duration"), "kind": "custom", "gender": meta.get("gender") or "", "native": ""}


def rename_custom(cid: str, name: str) -> Optional[dict]:
    """Give a saved voice another name (the name of the character). None when the voice does not exist; VoxError when the name is empty."""
    new = normalize_ws(strip_zero_width(str(name or ""))).strip()[:60].strip()
    if not new:
        raise VoxError("BAD_REQUEST", "The name cannot be empty.")
    return _update_meta(cid, {"name": new})


def set_custom_gender(cid: str, gender: str) -> Optional[dict]:
    """Say that a saved voice is a woman (Female), a man (Male) or not decided (''): "voices by character" uses the voices of the right gender."""
    if gender not in ("Female", "Male", ""):
        raise VoxError("BAD_REQUEST", "The gender must be Female, Male or empty.")
    return _update_meta(cid, {"gender": gender, "gender_auto": False})


def delete_custom(cid: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{8}", cid or ""):
        return False
    d = VOICES_DIR / cid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


# --------------------------------------------------------------------------- #
# designed voices: the anchor clip that every line clones
# --------------------------------------------------------------------------- #
_PRESET_LOCKS: Dict[str, threading.Lock] = {}
_PRESET_LOCKS_GUARD = threading.Lock()


def _preset_lock(key: str) -> threading.Lock:
    with _PRESET_LOCKS_GUARD:
        return _PRESET_LOCKS.setdefault(key, threading.Lock())


def ensure_preset_ref(preset: "voxpresets.Preset", mgr: VoxManager, status: Optional[Callable[[str], None]] = None,
                      cancelled: Optional[Callable[[], bool]] = None, log: Callable[[str], None] = lambda m: None) -> Path:
    """The anchor clip of a designed voice. Made once (the engine speaks SAMPLE_TEXT in the described voice), then reused."""
    home = mgr.home
    variant = voxpresets.variant_of(home, preset.key)
    path = voxpresets.ref_path(home, preset.key, variant)
    if path.exists():
        return path
    with _preset_lock(preset.key):
        variant = voxpresets.variant_of(home, preset.key)
        path = voxpresets.ref_path(home, preset.key, variant)
        if path.exists():
            return path
        log(f"Designed voice '{preset.name}': creating it once (this first line takes a little longer) ...")
        if status:
            status("creating the designed voice ...")
        if not mgr.ensure_ready(on_status=status, cancelled=cancelled):
            raise Cancelled()
        path.parent.mkdir(parents=True, exist_ok=True)
        tag = uuid.uuid4().hex[:8]
        raw = mgr.tmp / f"preset-{preset.key}-{tag}.wav"
        clean = path.with_name(f"{path.stem}.{tag}.tmp.wav")
        try:
            mgr.synth(voxpresets.SAMPLE_TEXT, raw, ref=None, style=preset.style, steps=QUALITY_STEPS["balanced"], cfg=CFG,
                      seed=voxpresets.seed_for(preset, variant), cancelled=cancelled)
            _convert_ref(raw, clean, dur=14.0)
            arr = audio.trim_silence(audio.decode_to_array(clean, sr=SR))
            if len(arr) / SR < 2.0:
                raise VoxError("VOX_FAILED", f"The engine returned almost no speech for the designed voice '{preset.name}'. Try Re-roll.")
            audio.encode_array(arr, clean, sr=SR)
            clean.replace(path)
        finally:
            for f in (raw, clean):
                try:
                    f.unlink()
                except OSError:
                    pass
        voxpresets.prune_old(home, preset.key, variant)
        return path


# --------------------------------------------------------------------------- #
# "original speaker": pick a clean window of the video's own audio
# --------------------------------------------------------------------------- #
def pick_ref_window(segs: List[dict], want: float = 12.0, lo: float = 7.0, hi: float = 20.0) -> tuple:
    """Best run of consecutive caption segments: dense speech, ~12 s long, not the very first seconds (intro music)."""
    best = None
    n = len(segs)
    for i in range(n):
        speech = 0.0
        for j in range(i, n):
            span = segs[j]["end"] - segs[i]["start"]
            if span > hi:
                break
            speech += max(0.0, segs[j]["end"] - segs[j]["start"])
            if span >= lo:
                density = speech / max(span, 0.1)
                score = density - abs(span - want) / 40.0
                if segs[i]["start"] < 8.0:
                    score -= 0.06
                if best is None or score > best[0]:
                    best = (score, segs[i]["start"], segs[j]["end"])
    if best:
        return float(best[1]), float(best[2])
    if segs:
        s0 = segs[0]["start"]
        return float(s0), float(min(segs[-1]["end"], s0 + want))
    return 3.0, 3.0 + want


def prepare_original_ref(job_dir: Path, segs: List[dict], vid: Optional[str], ref_start: Optional[float], cookies: str, proxy: str,
                         log: Callable[[str], None], progress: Optional[Callable[[float], None]] = None,
                         media: Optional[Path] = None) -> Path:
    from .ytsource import download_audio  # local import: only needed here

    out = job_dir / "voice_ref.wav"
    meta_p = job_dir / "voice_ref.json"
    want = {"start": round(float(ref_start), 2) if ref_start not in (None, "") else None}
    if out.exists() and meta_p.exists():
        try:
            if json.loads(meta_p.read_text(encoding="utf-8")).get("want") == want:
                return out
        except Exception:
            pass
    log("Original voice: preparing the audio to pick a clean reference clip ...")
    ap = Path(media) if media else download_audio(vid, job_dir / "audio", cookies, proxy, progress=progress)     # an uploaded file is already here
    if media and not audio.probe_media(ap).get("has_audio"):
        raise VoxError("VOX_NO_REF", "This file has no sound, so there is no voice to copy. Choose another voice.")
    if want["start"] is not None:
        start, end = float(want["start"]), float(want["start"]) + 12.0
    else:
        start, end = pick_ref_window(segs)
    dur = min(max(end - start, 5.0), 20.0)
    _convert_ref(ap, out, start=start, dur=dur + 0.1)
    arr = audio.decode_to_array(out, sr=SR)
    if audio.rms_of_voiced(arr) <= 0.0 or len(arr) / SR < 3.0:
        raise VoxError("VOX_NO_REF", "Could not find clear speech in the video's audio to copy the voice from. "
                                      "Choose a start time in the voice options, or upload a short clip of the voice.")
    meta_p.write_text(json.dumps({"want": want, "start": round(start, 2), "dur": round(dur, 2)}), encoding="utf-8")
    log(f"Original voice: using {dur:.0f} s of speech starting at {start:.0f} s as the voice reference.")
    return out


def prepare_character_ref(job_dir: Path, chars: Optional[List[dict]], cid: int, vid: Optional[str], cookies: str, proxy: str,
                          log: Callable[[str], None], progress: Optional[Callable[[float], None]] = None, media: Optional[Path] = None) -> Path:
    """The voice of ONE character of the video as a reference clip: the clearest of its lines (picked by speakers.py), cut out of the
    video's audio and joined with short pauses.  Made once per set of lines, then kept in the job folder."""
    from .ytsource import download_audio  # local import: only needed here

    ch = next((c for c in (chars or []) if c.get("id") == cid), None)
    ranges = []
    for r in (ch or {}).get("ref") or []:
        try:
            a, b = float(r[0]), float(r[1])
            if b - a >= 0.8:
                ranges.append([round(a, 2), round(b, 2)])
        except (TypeError, ValueError, IndexError):
            continue
    if not ranges:
        raise VoxError("VOX_NO_REF", f"Character {cid} has no clear speech to copy the voice from. Choose another voice for it.")
    out = job_dir / f"voice_ref_c{cid}.wav"
    meta_p = job_dir / f"voice_ref_c{cid}.json"
    if out.exists() and meta_p.exists():
        try:
            if json.loads(meta_p.read_text(encoding="utf-8")).get("ranges") == ranges:
                return out
        except Exception:
            pass
    log(f"Character {cid}: cutting {sum(b - a for a, b in ranges):.0f} s of its clearest lines as the voice reference ...")
    ap = Path(media) if media else download_audio(vid, job_dir / "audio", cookies, proxy, progress=progress)
    parts: List[np.ndarray] = []
    gap = audio.silence(0.35, SR)
    tmp = job_dir / f"_cref_{cid}.wav"
    try:
        for a, b in ranges:
            _convert_ref(ap, tmp, start=max(0.0, a), dur=min(b - a, 12.0) + 0.05)
            x = audio.trim_silence(audio.decode_to_array(tmp, sr=SR))
            if len(x) / SR >= 0.6:
                parts += [x, gap]
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    arr = np.concatenate(parts[:-1]) if parts else np.zeros(0, dtype=np.float32)
    if len(arr) / SR < 3.0 or audio.rms_of_voiced(arr) <= 0.0:
        raise VoxError("VOX_NO_REF", f"Could not find clear speech of character {cid} to copy the voice from. Choose another voice for it.")
    arr = arr[: int(20.0 * SR)]
    audio.encode_array(arr, out, sr=SR)
    meta_p.write_text(json.dumps({"ranges": ranges, "dur": round(len(arr) / SR, 1)}), encoding="utf-8")
    log(f"Character {cid}: voice reference of {len(arr) / SR:.0f} s ready.")
    return out


# --------------------------------------------------------------------------- #
# voice resolution
# --------------------------------------------------------------------------- #
@dataclass
class Resolved:
    id: str
    kind: str               # custom | original | designed | default
    ref: Optional[Path]
    ref_hash: str
    label: str


def resolve_voice(vs, *, mgr: Optional[VoxManager] = None, status: Optional[Callable[[str], None]] = None,
                  cancelled: Optional[Callable[[], bool]] = None, log: Callable[[str], None] = lambda m: None,
                  job_dir: Optional[Path] = None, segs: Optional[List[dict]] = None, vid: Optional[str] = None,
                  cookies: str = "", proxy: str = "", progress: Optional[Callable[[float], None]] = None,
                  media: Optional[Path] = None, chars: Optional[List[dict]] = None) -> Resolved:
    mgr = mgr or manager()
    vid_ = vs.vox_id or ""
    if vid_.startswith("vox:s:"):
        if not (job_dir and (vid or media)):
            raise VoxError("VOX_NO_ORIGINAL", "A character's own voice needs a YouTube link or an uploaded video as the source.")
        if not vs.vox_consent:
            raise VoxError("VOX_CONSENT_REQUIRED", "Please confirm that you have permission to copy this voice.")
        cid = int(vid_[6:])
        ref = prepare_character_ref(job_dir, chars, cid, vid, cookies, proxy, log, progress, media=media)
        return Resolved(vid_, "character", ref, _sha(ref), f"character {cid}")
    if vid_ == "vox:original":
        if not (job_dir and (vid or media)):
            raise VoxError("VOX_NO_ORIGINAL", "The original speaker's voice needs a YouTube link or an uploaded video as the source.")
        if not vs.vox_consent:
            raise VoxError("VOX_CONSENT_REQUIRED", "Please confirm that you have permission to copy this voice.")
        ref = prepare_original_ref(job_dir, segs or [], vid, vs.vox_ref_start, cookies, proxy, log, progress, media=media)
        return Resolved(vid_, "original", ref, _sha(ref), "original speaker")
    if vid_.startswith("vox:c:"):
        if not vs.vox_consent:
            raise VoxError("VOX_CONSENT_REQUIRED", "Please confirm that you have permission to use this voice.")
        ref = custom_ref_path(vid_[6:])
        if not ref:
            raise VoxError("VOX_NO_REF", "This saved voice no longer exists. Pick another voice or upload it again.")
        return Resolved(vid_, "custom", ref, _sha(ref), "custom voice")
    if vid_ == "vox:default":
        return Resolved(vid_, "default", None, "default", "default voice")
    if vid_.startswith("vox:p:"):
        preset = voxpresets.get(vid_[6:])
        if not preset:
            raise VoxError("VOX_VOICE_GONE", f"The designed voice '{vid_[6:]}' does not exist. Pick another voice.")
        ref = ensure_preset_ref(preset, mgr, status, cancelled, log)
        return Resolved(vid_, "designed", ref, _sha(ref), preset.name)
    raise VoxError("VOX_FAILED", f"Unknown VoxCPM2 voice: {vid_ or '(none)'}")


# --------------------------------------------------------------------------- #
# synthesizer
# --------------------------------------------------------------------------- #
def prep_text(km_text: str, readings: Optional[Dict[str, str]] = None) -> str:
    text = strip_zero_width(km_text or "").strip()
    text = apply_readings(text, readings or {})
    # a leading "(...)" would be read as a style instruction by VoxCPM2 -> turn brackets into pauses
    text = re.sub(r"[()（）\[\]{}<>]", ", ", text)
    text = re.sub(r"(?:,\s*){2,}", ", ", text)
    return normalize_ws(text).strip(" ,")


class VoxSynth:
    """Same job as tts.Synth, but with VoxCPM2. One line at a time (a GPU can only do one), cached on disk."""

    def __init__(self, resolved: Resolved, quality: str = "balanced", mgr: Optional[VoxManager] = None,
                 status: Optional[Callable[[str], None]] = None, cancelled: Optional[Callable[[], bool]] = None):
        self.v = resolved
        self.steps = QUALITY_STEPS.get(quality, 10)
        self.mgr = mgr or manager()
        self.status = status
        self.cancelled = cancelled or (lambda: False)
        self._ready = False
        self.calls = 0
        self.cache_hits = 0
        self.gen_s = 0.0
        self.audio_s = 0.0

    def _key(self, text: str) -> str:
        return hashlib.sha1(json.dumps([MODEL_TAG, self.v.ref_hash, self.steps, CFG, SEED, text], ensure_ascii=False).encode("utf-8")).hexdigest()

    def _piece_blocking(self, text: str) -> np.ndarray:
        key = self._key(text)
        npy = TTS_CACHE_DIR / f"vox-{key}.npy"
        if npy.exists():
            try:
                arr = np.load(npy)
                self.cache_hits += 1
                return arr.astype(np.float32) / 32767.0 if arr.dtype == np.int16 else arr.astype(np.float32)
            except Exception:
                pass
        if not self._ready:
            if not self.mgr.ensure_ready(on_status=self.status, cancelled=self.cancelled):
                raise Cancelled()
            self._ready = True
        tmp = self.mgr.tmp / f"seg-{uuid.uuid4().hex[:10]}.wav"
        t0 = time.time()
        try:
            self.mgr.synth(text, tmp, ref=self.v.ref, style=None, steps=self.steps, cfg=CFG, seed=SEED, cancelled=self.cancelled)
            arr = audio.trim_silence(audio.decode_to_array(tmp, sr=SR))
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        self.calls += 1
        self.gen_s += time.time() - t0
        self.audio_s += len(arr) / SR
        tmp_npy = TTS_CACHE_DIR / f"vox-{key}.{uuid.uuid4().hex[:6]}.tmp.npy"
        with open(tmp_npy, "wb") as fh:
            np.save(fh, (np.clip(arr, -1.0, 1.0) * 32767.0).astype(np.int16))
        tmp_npy.replace(npy)
        return arr

    async def segment(self, km_text: str, vs, readings: Optional[Dict[str, str]] = None, rate: Optional[int] = None) -> np.ndarray:
        text = prep_text(km_text, readings)
        if not is_speakable(text):
            return np.zeros(0, dtype=np.float32)
        pieces = [text] if len(text) <= 320 else split_sentences(text, max_chars=300)
        outs: List[np.ndarray] = []
        for j, piece in enumerate(pieces):
            if not is_speakable(piece):
                continue
            if self.cancelled():
                raise Cancelled()
            a = await asyncio.to_thread(self._piece_blocking, piece)
            if len(a) == 0:
                continue
            if outs:
                outs.append(audio.silence(0.25))
            outs.append(a)
        if not outs:
            return np.zeros(0, dtype=np.float32)
        out = audio.fade(audio.normalize_rms(np.concatenate(outs)))
        r = vs.rate if rate is None else int(rate)
        if r:
            out = audio.time_stretch(out, max(0.4, 1.0 + r / 100.0))
        return (out * vs.gain).astype(np.float32)


async def vox_long_text(text: str, vs, readings, progress=None, cancelled=lambda: False, status=None,
                        log: Callable[[str], None] = lambda m: None) -> np.ndarray:
    """Text-to-speech tab: speak any amount of Khmer text, sentence by sentence."""
    sentences = split_sentences(text, max_chars=300)
    if not sentences:
        raise VoxError("VOX_FAILED", "There is no text to speak.")
    resolved = await asyncio.to_thread(resolve_voice, vs, mgr=manager(), status=status, cancelled=cancelled, log=log)
    synth = VoxSynth(resolved, vs.vox_quality, status=status, cancelled=cancelled)
    parts: List[np.ndarray] = []
    for i, s in enumerate(sentences):
        if cancelled():
            break
        a = await synth.segment(s, vs, readings)
        if len(a):
            if parts:
                parts.append(audio.silence(0.30))
            parts.append(a)
        if progress:
            progress(i + 1, len(sentences))
    if synth.calls:
        log(f"VoxCPM2: {synth.calls} lines in {synth.gen_s:.0f} s ({synth.gen_s / max(synth.audio_s, 0.1):.2f}x real time), {synth.cache_hits} from cache.")
    if not parts:
        if cancelled():
            return np.zeros(0, dtype=np.float32)
        raise VoxError("VOX_FAILED", "VoxCPM2 returned no audio for this text.")
    return np.concatenate(parts)
