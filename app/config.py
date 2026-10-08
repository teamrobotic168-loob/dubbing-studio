"""Central configuration: paths, voices and defaults."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("KDS_DATA_DIR", BASE_DIR / "data")).resolve()
JOBS_DIR = DATA_DIR / "jobs"
CACHE_DIR = DATA_DIR / "cache"
TTS_CACHE_DIR = CACHE_DIR / "tts"
VIDEO_CACHE_DIR = CACHE_DIR / "video"
UPLOADS_DIR = DATA_DIR / "uploads"          # videos / audio files the user uploads (waiting to become a job)
STATIC_DIR = BASE_DIR / "static"
GLOSSARY_FILE = DATA_DIR / "glossary.txt"

for _d in (JOBS_DIR, TTS_CACHE_DIR, VIDEO_CACHE_DIR, UPLOADS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# All internal audio is mono float32 at this sample rate (same as Edge TTS output).
SAMPLE_RATE = 24000

# --------------------------------------------------------------------------- #
# Voices (Microsoft Edge "Read aloud" neural voices)
# --------------------------------------------------------------------------- #
KHMER_VOICES = [
    {
        "id": "km-KH-SreymomNeural",
        "name": "Srey Mom",
        "native": "ស្រីមុំ",
        "gender": "Female",
        "locale": "km-KH",
        "en_voice": "en-US-AvaNeural",
    },
    {
        "id": "km-KH-PisethNeural",
        "name": "Piseth",
        "native": "ពិសិដ្ឋ",
        "gender": "Male",
        "locale": "km-KH",
        "en_voice": "en-US-AndrewNeural",
    },
]

# English voices used to pronounce English technical terms inside Khmer speech.
EN_VOICES = [
    {"id": "en-US-AvaNeural", "name": "Ava", "gender": "Female"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Female"},
    {"id": "en-US-AriaNeural", "name": "Aria", "gender": "Female"},
    {"id": "en-US-EmmaNeural", "name": "Emma", "gender": "Female"},
    {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "Male"},
    {"id": "en-US-BrianNeural", "name": "Brian", "gender": "Male"},
    {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Male"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher", "gender": "Male"},
]

KHMER_VOICE_IDS = {v["id"] for v in KHMER_VOICES}
EN_VOICE_IDS = {v["id"] for v in EN_VOICES}
DEFAULT_KHMER_VOICE = KHMER_VOICES[0]["id"]


def default_en_voice_for(khmer_voice_id: str) -> str:
    for v in KHMER_VOICES:
        if v["id"] == khmer_voice_id:
            return v["en_voice"]
    return EN_VOICES[0]["id"]


# Output files a job may expose for download (whitelist).
DOWNLOADABLE_FILES = {
    "dub.mp3": "audio/mpeg",
    "khmer.srt": "application/x-subrip",
    "original.srt": "application/x-subrip",     # the source-language captions (English / Chinese / Korean)
    "english.srt": "application/x-subrip",      # jobs made before v1.3
    "script_km.txt": "text/plain; charset=utf-8",
    "dubbed.mp4": "video/mp4",
    "speech.mp3": "audio/mpeg",
    "voice_ref.wav": "audio/wav",
}
