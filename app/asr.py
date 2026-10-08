"""Optional Whisper transcription (faster-whisper) for videos without captions in the video's language."""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import audio
from .langs import AUTO, LANGS, SUPPORTED, lang_name, normalize_lang
from .transcript import Seg
from .ytsource import SourceError

# Whisper "base" is fine for English but makes many mistakes in Chinese and Korean.
CJK_MIN_MODEL = "small"
_ORDER = ("tiny", "base", "small", "medium")
_ZH_PROMPT = "以下是普通话的句子。"      # keeps Whisper writing Simplified Chinese with punctuation

_MODELS = {}


def whisper_installed() -> bool:
    """Is faster-whisper there?  (Looks for the package without importing it - importing loads a lot of libraries - and also
    sees a package that was installed a moment ago by the dashboard's own installer.)"""
    if "faster_whisper" in sys.modules:
        return True
    try:
        importlib.invalidate_caches()
        return importlib.util.find_spec("faster_whisper") is not None
    except Exception:
        return False


def model_for(lang: str, model_size: str) -> str:
    """Chinese and Korean need at least the 'small' model."""
    if model_size not in _ORDER:
        model_size = "base"
    if normalize_lang(lang) in ("zh", "ko") and _ORDER.index(model_size) < _ORDER.index(CJK_MIN_MODEL):
        return CJK_MIN_MODEL
    return model_size


def _load(model_size: str, log: Callable[[str], None]):
    from faster_whisper import WhisperModel

    model = _MODELS.get(model_size)
    if model is None:
        log(f"Loading Whisper '{model_size}' model (first time downloads it) …")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _MODELS[model_size] = model
    return model


def transcribe(
    media_path: str | Path,
    model_size: str = "base",
    language: Optional[str] = "en",
    progress: Optional[Callable[[float], None]] = None,
    cancelled: Callable[[], bool] = lambda: False,
    log: Callable[[str], None] = lambda m: None,
) -> Tuple[List[Seg], Optional[str]]:
    """Transcribe speech. `language` = 'en' | 'zh' | 'ko' | 'auto' (Whisper listens and decides).

    Returns (segments, language Whisper used or detected)."""
    try:
        import faster_whisper  # noqa: F401
    except Exception as exc:
        raise SourceError(
            "WHISPER_MISSING",
            "Whisper is not installed. Run:  pip install faster-whisper",
        ) from exc

    if model_size not in _ORDER:
        model_size = "base"
    lang = normalize_lang(language)
    wl = None if lang == AUTO else LANGS[lang].whisper
    model = _load(model_size, log)

    pcm = audio.decode_to_array(media_path, sr=16000)  # decode with ffmpeg → no PyAV needed
    total = max(1.0, len(pcm) / 16000.0)

    def run(m, code):
        kw = {"initial_prompt": _ZH_PROMPT} if code == "zh" else {}
        return m.transcribe(pcm, language=code, beam_size=3, vad_filter=True, condition_on_previous_text=False, **kw)

    segments, ainfo = run(model, wl)
    detected = wl or getattr(ainfo, "language", None)
    if wl is None and detected:
        log(f"Whisper detected the spoken language: {detected} (probability {float(getattr(ainfo, 'language_probability', 0) or 0):.0%})")
        got = normalize_lang(detected, "")
        if got not in SUPPORTED:      # found out in the first seconds → do not transcribe for nothing
            raise SourceError(
                "LANG_UNSUPPORTED",
                f"The speech was detected as {lang_name(str(detected).lower())} ('{detected}'). Only English, Chinese and Korean are supported.",
            )
        better = model_for(got, model_size)
        if better != model_size:     # Auto found Chinese / Korean but the chosen model is too small for it
            log(f"Whisper '{model_size}' is too weak for {lang_name(got)} → switching to '{better}' (first time downloads the model).")
            segments, ainfo = run(_load(better, log), LANGS[got].whisper)
            detected = LANGS[got].whisper
    out: List[Seg] = []
    for s in segments:
        if cancelled():
            break
        text = (s.text or "").strip()
        if text:
            out.append(Seg(float(s.start), float(s.end), text))
        if progress:
            progress(min(0.99, float(s.end) / total))
    return out, detected
