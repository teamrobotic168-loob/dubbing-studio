"""Text-to-speech with Microsoft Edge neural voices (Srey Mom / Piseth).

Hybrid synthesis
----------------
Edge's Khmer voices mispronounce English words ("API" → "Happy"). So Khmer text with embedded
English terms is split into runs:

    ថ្ងៃនេះយើងប្រើ  [OpenAI API]  ដើម្បី …
    └─ Khmer voice ┘ └ English voice ┘

and every run is synthesised by the right voice, loudness-matched and joined seamlessly.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from . import audio, autovoice
from .config import KHMER_VOICE_IDS, SAMPLE_RATE as SR, TTS_CACHE_DIR, default_en_voice_for
from .glossary import apply_readings
from .textutil import (
    has_khmer,
    is_speakable,
    pause_after,
    split_runs,
    split_sentences,
    strip_zero_width,
)

try:  # edge-tts is imported lazily so the UI can still start without it
    import edge_tts
    from edge_tts.exceptions import NoAudioReceived
except Exception:  # pragma: no cover
    edge_tts = None  # type: ignore

    class NoAudioReceived(Exception):  # type: ignore
        pass


class TTSError(RuntimeError):
    pass


@dataclass
class VoiceSettings:
    voice: str = "km-KH-SreymomNeural"
    rate: int = 0            # percent, -50 … +100
    pitch: int = 0           # Hz, -30 … +30
    volume: int = 0          # percent offset applied as final gain
    term_mode: str = "english_voice"   # "english_voice" | "khmer_voice"
    en_voice: str = ""
    # ---- optional local engine (VoxCPM2) -------------------------------------------------
    engine: str = "edge"               # "edge" | "voxcpm"
    vox_id: str = ""                   # "vox:c:<custom id>" | "vox:original" | "vox:default"
    vox_quality: str = "balanced"      # "fast" | "balanced" | "high"
    vox_ref_start: Optional[float] = None   # seconds: where to cut the "original speaker" reference (None = automatic)
    vox_consent: bool = False          # the user confirmed they may copy this voice
    # ---- voices by character (app/autovoice.py): men and women of the video get a male / female voice by themselves -------------
    auto: bool = False                 # on: the lines that have a detected character use the voice of that character
    auto_male: str = ""                # '' = automatic | a voice id | "vox:s" (clone each character) | "vox:mine" (My voices of that gender)
    auto_female: str = ""

    def __post_init__(self):
        if self.voice not in KHMER_VOICE_IDS:
            self.voice = "km-KH-SreymomNeural"
        if not self.en_voice:
            self.en_voice = default_en_voice_for(self.voice)
        self.rate = int(max(-60, min(150, self.rate)))
        self.pitch = int(max(-50, min(50, self.pitch)))
        self.volume = int(max(-80, min(100, self.volume)))
        if self.term_mode not in ("english_voice", "khmer_voice"):
            self.term_mode = "english_voice"
        if self.engine not in ("edge", "voxcpm"):
            self.engine = "edge"
        if self.vox_quality not in ("fast", "balanced", "high"):
            self.vox_quality = "balanced"
        if self.engine == "voxcpm" and not self.vox_id:
            self.vox_id = "vox:original"
        self.auto = bool(self.auto)
        self.auto_male = autovoice.clean_choice(self.auto_male, mine=True)
        self.auto_female = autovoice.clean_choice(self.auto_female, mine=True)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "VoiceSettings":
        d = d or {}
        vox = d.get("vox") or {}
        ref_start = vox.get("ref_start")
        try:
            ref_start = float(ref_start) if ref_start not in (None, "") else None
            if ref_start is not None and ref_start < 0:
                ref_start = None
        except (TypeError, ValueError):
            ref_start = None
        auto = d.get("auto") if isinstance(d.get("auto"), dict) else {}
        return cls(
            auto=bool(auto.get("on")),
            auto_male=str(auto.get("male") or ""),
            auto_female=str(auto.get("female") or ""),
            voice=d.get("id") or d.get("voice") or "km-KH-SreymomNeural",
            rate=int(d.get("rate", 0) or 0),
            pitch=int(d.get("pitch", 0) or 0),
            volume=int(d.get("volume", 0) or 0),
            term_mode=d.get("term_mode") or "english_voice",
            en_voice=d.get("en_voice") or "",
            engine=d.get("engine") or "edge",
            vox_id=str(vox.get("id") or ""),
            vox_quality=str(vox.get("quality") or "balanced"),
            vox_ref_start=ref_start,
            vox_consent=bool(vox.get("consent")),
        )

    @property
    def gain(self) -> float:
        return float(max(0.2, min(2.5, 1.0 + self.volume / 100.0)))


def _fmt_rate(p: int) -> str:
    return f"{int(p):+d}%"


def _fmt_pitch(p: int) -> str:
    return f"{int(p):+d}Hz"


def _to_cache(arr: np.ndarray) -> np.ndarray:
    """float32 [-1, 1] → int16 (halves the disk footprint of the TTS cache; inaudible difference)."""
    return (np.clip(arr, -1.0, 1.0) * 32767.0).astype(np.int16)


def _from_cache(arr: np.ndarray) -> np.ndarray:
    if arr.dtype == np.int16:
        return arr.astype(np.float32) / 32767.0
    return arr.astype(np.float32, copy=False)


class Synth:
    """Async Edge-TTS wrapper with disk cache, retries, concurrency limit and in-flight de-duplication."""

    def __init__(self, concurrency: int = 4, proxy: Optional[str] = None, on_retry: Optional[Callable[[str], None]] = None):
        if edge_tts is None:
            raise TTSError("The 'edge-tts' package is not installed. Run: pip install edge-tts")
        self._sem = asyncio.Semaphore(concurrency)
        self._proxy = proxy or None
        self._on_retry = on_retry           # called with a short message when a request has to be repeated
        self._last_retry_note = 0.0
        self._inflight: Dict[str, "asyncio.Future"] = {}
        self.calls = 0
        self.cache_hits = 0

    def _communicate(self, text: str, voice: str, rate: int, pitch: int):
        kw = dict(rate=_fmt_rate(rate), pitch=_fmt_pitch(pitch), volume="+0%", proxy=self._proxy)
        try:  # fail within seconds when Microsoft's server does not answer (default would wait 60 s)
            return edge_tts.Communicate(text, voice, connect_timeout=10, receive_timeout=30, **kw)
        except TypeError:  # older edge-tts without these parameters
            return edge_tts.Communicate(text, voice, **kw)

    def _note_retry(self, attempt: int, exc: Exception) -> None:
        now = time.monotonic()
        if not self._on_retry or now - self._last_retry_note < 5.0:
            return
        self._last_retry_note = now
        try:
            self._on_retry(f"Edge TTS: {type(exc).__name__}: {str(exc)[:120]} – trying again ({attempt + 1}/5)")
        except Exception:
            pass

    # -- one request ------------------------------------------------------- #
    async def chunk(self, text: str, voice: str, rate: int = 0, pitch: int = 0) -> np.ndarray:
        """Synthesize a short piece of text → trimmed float32 mono audio (not loudness-normalised).

        Identical requests that are in flight at the same time (repeated phrases such as
        "Thank you" or song lyrics) share ONE network call; results are cached on disk.
        """
        text = text.strip()
        if not is_speakable(text):
            return np.zeros(0, dtype=np.float32)
        key = hashlib.sha1(json.dumps([voice, int(rate), int(pitch), text], ensure_ascii=False).encode("utf-8")).hexdigest()
        npy = TTS_CACHE_DIR / f"{key}.npy"
        if npy.exists():
            try:
                arr = _from_cache(np.load(npy))
                self.cache_hits += 1
                return arr
            except Exception:
                pass  # half-written / corrupt → regenerate
        fut = self._inflight.get(key)
        if fut is None:
            fut = asyncio.ensure_future(self._fetch(key, text, voice, rate, pitch))
            self._inflight[key] = fut
            fut.add_done_callback(lambda _f, k=key: self._inflight.pop(k, None))
        else:
            self.cache_hits += 1
        return await asyncio.shield(fut)

    async def _fetch(self, key: str, text: str, voice: str, rate: int, pitch: int) -> np.ndarray:
        npy = TTS_CACHE_DIR / f"{key}.npy"
        tmp_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        mp3 = TTS_CACHE_DIR / f"{key}.{tmp_id}.tmp.mp3"
        last: Optional[Exception] = None
        arr: Optional[np.ndarray] = None
        try:
            async with self._sem:
                for attempt in range(5):
                    try:
                        comm = self._communicate(text, voice, rate, pitch)
                        await comm.save(str(mp3))
                        self.calls += 1
                        last = None
                        break
                    except NoAudioReceived:
                        arr = np.zeros(0, dtype=np.float32)
                        last = None
                        break
                    except Exception as exc:  # network hiccup / throttling → retry
                        last = exc
                        self._note_retry(attempt, exc)
                        await asyncio.sleep(0.8 * (attempt + 1))
            if last is not None:
                raise TTSError(f"Edge TTS failed for voice {voice}: {type(last).__name__}: {last}")
            if arr is None:
                arr = await asyncio.to_thread(audio.decode_to_array, mp3)
                arr = audio.trim_silence(arr)
            # atomic write so concurrent readers never see a partial file
            tmp_npy = TTS_CACHE_DIR / f"{key}.{tmp_id}.tmp.npy"
            with open(tmp_npy, "wb") as fh:
                np.save(fh, _to_cache(arr))
            os.replace(tmp_npy, npy)
            return _from_cache(_to_cache(arr))  # identical to what a later cache hit returns
        finally:
            try:
                mp3.unlink()
            except OSError:
                pass

    # -- one Khmer segment (possibly with English terms) -------------------- #
    async def segment(
        self,
        km_text: str,
        vs: VoiceSettings,
        readings: Optional[Dict[str, str]] = None,
        rate: Optional[int] = None,
    ) -> np.ndarray:
        """Synthesize a Khmer sentence/segment using the hybrid Khmer+English voice logic."""
        rate = vs.rate if rate is None else int(rate)
        text = strip_zero_width(km_text or "").strip()
        text = apply_readings(text, readings or {})
        if not text:
            return np.zeros(0, dtype=np.float32)

        # decide the plan: list of ("voice", voice_id, text) | ("pause", seconds)
        plan: List[tuple] = []
        runs = split_runs(text) if vs.term_mode == "english_voice" else [("km", text)]
        for kind, chunk in runs:
            if kind == "en":
                plan.append(("voice", vs.en_voice, chunk))
            elif is_speakable(chunk):
                pieces_km = [chunk] if len(chunk) <= 300 else split_sentences(chunk, max_chars=300)
                for j, piece in enumerate(pieces_km):
                    if j:
                        plan.append(("pause", 0.28))
                    plan.append(("voice", vs.voice, piece))
            else:
                p = pause_after(chunk)
                if p:
                    plan.append(("pause", p))

        # synthesize all voiced pieces concurrently
        voiced = [(i, p) for i, p in enumerate(plan) if p[0] == "voice"]
        audios = await asyncio.gather(*[self.chunk(p[2], p[1], rate, vs.pitch) for _, p in voiced])
        by_index = {i: a for (i, _), a in zip(voiced, audios)}

        pieces: List[np.ndarray] = []
        for i, p in enumerate(plan):
            if p[0] == "pause":
                if pieces:  # no leading pause
                    pieces.append(audio.silence(p[1]))
                continue
            a = by_index.get(i)
            if a is None or len(a) == 0:
                continue
            pieces.append(audio.fade(audio.normalize_rms(a)))
        while pieces and np.max(np.abs(pieces[-1])) == 0:  # no trailing pause
            pieces.pop()
        if not pieces:
            return np.zeros(0, dtype=np.float32)
        out = np.concatenate(pieces)
        return (out * vs.gain).astype(np.float32)


# --------------------------------------------------------------------------- #
# convenience helpers
# --------------------------------------------------------------------------- #
async def synth_long_text(
    text: str,
    vs: VoiceSettings,
    readings: Optional[Dict[str, str]] = None,
    progress=None,
    cancelled=lambda: False,
    proxy: Optional[str] = None,
    on_retry: Optional[Callable[[str], None]] = None,
    status: Optional[Callable[[str], None]] = None,
) -> np.ndarray:
    """Speak an arbitrary amount of Khmer text (sentence by sentence)."""
    if vs.engine == "voxcpm":
        from .voxvoices import vox_long_text  # local import: the optional engine is only loaded when used

        return await vox_long_text(text, vs, readings, progress=progress, cancelled=cancelled, status=status, log=on_retry or (lambda m: None))
    sentences = split_sentences(text, max_chars=300)
    if not sentences:
        raise TTSError("There is no text to speak.")
    synth = Synth(proxy=proxy, on_retry=on_retry)
    done = 0
    results: List[Optional[np.ndarray]] = [None] * len(sentences)

    async def one(i: int, s: str):
        nonlocal done
        if cancelled():
            return
        results[i] = await synth.segment(s, vs, readings)
        done += 1
        if progress:
            progress(done, len(sentences))

    await asyncio.gather(*[one(i, s) for i, s in enumerate(sentences)])
    parts: List[np.ndarray] = []
    for a in results:
        if a is None or len(a) == 0:
            continue
        if parts:
            parts.append(audio.silence(0.30))
        parts.append(a)
    if not parts:
        raise TTSError("Edge TTS returned no audio for this text.")
    return np.concatenate(parts)


async def preview_audio(vs: VoiceSettings, text: str, readings: Optional[Dict[str, str]] = None) -> np.ndarray:
    synth = Synth(concurrency=3)
    a = await synth.segment(text, vs, readings)
    if len(a) == 0:
        raise TTSError("Edge TTS returned no audio.")
    return a
