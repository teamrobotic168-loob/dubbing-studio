"""VoxCPM2 "designed" voices: 8 ready-made voices (4 female, 4 male) described in words.

VoxCPM2 can invent a voice from a description ("a warm, friendly adult woman ...").  Speaking every line from the
description alone would give a slightly DIFFERENT person each time, so each designed voice is made once:

    1. the model speaks a short Khmer sentence in the described voice  (the "anchor" clip, ~10 s);
    2. every line of every later job CLONES that clip, so the voice stays the same from the first line to the last.

"Re-roll" makes a new person in the same style (a new random seed -> a new anchor).  This module only holds the
catalogue and the small bookkeeping files; building the anchor needs the engine and lives in voxvoices.py.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# ~10 seconds of clear, neutral Khmer (hello - I can read Khmer text clearly and smoothly - listen and choose a voice you like)
SAMPLE_TEXT = "សួស្តី! ខ្ញុំអាចអានអត្ថបទជាភាសាខ្មែរបានយ៉ាងច្បាស់ និងរលូន។ សូមស្តាប់សំឡេងរបស់ខ្ញុំ ហើយជ្រើសរើសសំឡេងដែលអ្នកពេញចិត្ត។"

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,23}$")
_LOCK = threading.Lock()


@dataclass(frozen=True)
class Preset:
    key: str
    gender: str          # "Female" | "Male"
    name: str            # English name (the UI shows a translated one)
    style: str           # the description given to VoxCPM2 (no brackets: the engine wraps it in "(...)")
    seed: int            # base random seed; every re-roll adds a different offset


PRESETS: List[Preset] = [
    Preset("f_warm", "Female", "Warm narrator",
           "A warm, friendly adult woman with a clear, gentle voice and a steady, relaxed pace", 4101),
    Preset("f_bright", "Female", "Bright and young",
           "A young woman with a bright, cheerful and lively voice, speaking at a natural pace", 4202),
    Preset("f_calm", "Female", "Calm and mature",
           "A calm, mature woman with a soft, low and composed voice, slow and soothing pace", 4303),
    Preset("f_pro", "Female", "Confident presenter",
           "A confident professional woman with a clear, energetic and authoritative voice, like a television presenter", 4404),
    Preset("m_deep", "Male", "Deep narrator",
           "A deep, steady adult man with a warm baritone voice and the calm pace of a documentary narrator", 4505),
    Preset("m_young", "Male", "Young and energetic",
           "A young man with an energetic, friendly and bright voice, speaking at a natural pace", 4606),
    Preset("m_elder", "Male", "Wise elder",
           "An older man with a calm, wise and slightly husky voice, slow and thoughtful pace", 4707),
    Preset("m_anchor", "Male", "Strong announcer",
           "A strong, confident man with a powerful, clear voice, like a news anchor", 4808),
]
BY_KEY: Dict[str, Preset] = {p.key: p for p in PRESETS}


def get(key: str) -> Optional[Preset]:
    return BY_KEY.get(key or "")


def seed_for(p: Preset, variant: int) -> int:
    return (p.seed + 7919 * int(variant)) % (2 ** 31 - 1)


# ----------------------------------------------------------------------------------- bookkeeping (presets.json)
def _state_file(home: Path) -> Path:
    return home / "presets.json"


def _read(home: Path) -> Dict[str, int]:
    try:
        d = json.loads(_state_file(home).read_text(encoding="utf-8"))
        v = d.get("variants") or {}
        return {k: int(x) for k, x in v.items() if k in BY_KEY and isinstance(x, (int, float)) and x >= 0}
    except Exception:
        return {}


def variant_of(home: Path, key: str) -> int:
    return _read(home).get(key, 0)


def bump_variant(home: Path, key: str) -> int:
    """Re-roll: the next time this voice is used it is made again with a new seed.  Returns the new variant number."""
    with _LOCK:
        v = _read(home)
        v[key] = v.get(key, 0) + 1
        home.mkdir(parents=True, exist_ok=True)
        tmp = _state_file(home).with_suffix(".tmp")
        tmp.write_text(json.dumps({"variants": v}), encoding="utf-8")
        tmp.replace(_state_file(home))
        return v[key]


def ref_path(home: Path, key: str, variant: Optional[int] = None) -> Path:
    n = variant_of(home, key) if variant is None else variant
    return home / "voices" / f"preset-{key}-v{n}.wav"


def prune_old(home: Path, key: str, keep_variant: int) -> None:
    """Delete the anchors of older variants (the previous one stays: a job that is running right now may still read it)."""
    d = home / "voices"
    if not d.exists():
        return
    for f in d.glob(f"preset-{key}-v*.wav"):
        m = re.search(r"-v(\d+)\.wav$", f.name)
        if m and int(m.group(1)) < keep_variant - 1:
            try:
                f.unlink()
            except OSError:
                pass


def list_presets(home: Path) -> List[dict]:
    variants = _read(home)
    out = []
    for p in PRESETS:
        v = variants.get(p.key, 0)
        out.append({"id": f"vox:p:{p.key}", "key": p.key, "name": p.name, "gender": p.gender, "style": p.style,
                    "kind": "designed", "variant": v, "ready": ref_path(home, p.key, v).exists(), "native": ""})
    return out
