"""Which voice speaks a line when "voices by character" is on.

`speakers.py` finds out who speaks every line (a character, man or woman).  This module turns that into voices - no per-character
work for the user:

  * Microsoft Edge (Khmer has only two voices):  men -> Piseth, women -> Srey Mom.
  * VoxCPM2 - what the user chose for the job is respected:
      "Speaker in the video" (a clone of the video's speaker)  ->  every character is cloned from ITS OWN lines (vox:s:<n>);
      a designed voice / a saved voice (My voices)             ->  the characters it fits (same gender, or a saved voice of no
                                                                  known gender: everybody) speak with it, the other gender gets a
                                                                  designed voice (the lowest-pitched man the deepest one ...).
    "My voices" of the right gender or a clone of each character can also be chosen in the two pickers of the settings.

The order of priority for a line is   the voice chosen for that line  >  the voice chosen for its character  >  the automatic
voice of its gender  >  the voice of the whole job (a line nobody could be measured on).
"""
from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Optional

from . import voxpresets
from .config import KHMER_VOICE_IDS

EDGE_VOICE = {"male": "km-KH-PisethNeural", "female": "km-KH-SreymomNeural"}
# designed voices by how many characters of the gender there are; handed out from the lowest-pitched character upwards
DESIGNED = {
    "male": {1: ["m_deep"], 2: ["m_deep", "m_young"], 3: ["m_deep", "m_anchor", "m_young"], 4: ["m_deep", "m_elder", "m_anchor", "m_young"]},
    "female": {1: ["f_warm"], 2: ["f_warm", "f_bright"], 3: ["f_calm", "f_warm", "f_bright"], 4: ["f_calm", "f_warm", "f_pro", "f_bright"]},
}
CLONE = "vox:s"                    # "copy this character's own voice from the video" (a choice; a line carries vox:s:<character id>)
MINE = "vox:mine"                  # "My voices of this gender" (a choice for the male / female pickers only)
GENDERS = ("male", "female")
MAX_NAME = 40
PITCH_GAP = 0.25                # octaves (3 semitones): characters of one gender closer than this in pitch share a designed / My voice

_VOX_ROW_ID = re.compile(r"^vox:(?:original|c:[0-9a-f]{8}|p:[a-z][a-z0-9_]{1,23}|s:[1-9][0-9]?)$")


def valid_row_voice(voice) -> bool:
    """Edge voice id, or a VoxCPM2 voice id (speaker in the video / my voice / designed voice / a character cloned from the video)."""
    if not isinstance(voice, str):
        return False
    if voice in KHMER_VOICE_IDS:
        return True
    if _VOX_ROW_ID.match(voice):
        return not voice.startswith("vox:p:") or voxpresets.get(voice[6:]) is not None
    return False


def valid_choice(v, *, mine: bool = False) -> bool:
    """A voice picker of the "by character" settings: '' = automatic, a voice id, 'vox:s' (clone), 'vox:mine' (only the male / female pickers)."""
    if v in (None, ""):
        return True
    if not isinstance(v, str):
        return False
    return v == CLONE or (mine and v == MINE) or valid_row_voice(v)


def clean_choice(v, *, mine: bool = False) -> str:
    return v if isinstance(v, str) and v and valid_choice(v, mine=mine) else ""


def gender_label(g: str) -> str:
    return "Male" if g == "male" else "Female"


def designed_for(gender: str, n: int) -> List[str]:
    """The designed voices of `n` characters of one gender (lowest pitch first)."""
    sets = DESIGNED[gender]
    n = max(1, int(n))
    if n in sets:
        return [f"vox:p:{k}" for k in sets[n]]
    full = sets[max(sets)]
    return [f"vox:p:{full[i % len(full)]}" for i in range(n)]


def voice_groups(mine: List[dict]) -> List[int]:
    """For the characters of ONE gender (lowest pitch first): which "voice" each one is.  Two characters whose pitch is within
    PITCH_GAP of each other share a voice: telling two such people apart from the sound is a guess (one person can be split in
    two by it), and a voice that changes in the middle of a person is worse than two people who share one."""
    out: List[int] = []
    ref = None
    for c in mine:
        f = float(c.get("f0") or 0.0)
        if ref is None or (f > 0 and ref > 0 and math.log2(f / ref) > PITCH_GAP):
            out.append(out[-1] + 1 if out else 0)
            ref = f
        else:
            out.append(out[-1])
    return out


def plan(chars: Optional[Iterable[dict]], engine: str = "edge", male: str = "", female: str = "", custom: Optional[List[dict]] = None,
         job_voice: str = "", job_gender: str = "") -> Dict[int, str]:
    """character id -> the voice id its lines are spoken with ('' = the voice of the job).

    `chars`: the job's characters ({id, gender, f0, voice, ref}); `engine`: the job's engine (edge | voxcpm); `male` / `female`: the
    pickers of the settings ('' = automatic); `custom`: "My voices" ({id, gender}); `job_voice`: the VoxCPM2 voice chosen for the
    job (engine voxcpm only) and `job_gender`: "male" / "female" / "" (unknown) - what the automatic choice builds on."""
    chars = [c for c in (chars or []) if isinstance(c, dict) and isinstance(c.get("id"), int) and c.get("gender") in GENDERS]
    out: Dict[int, str] = {}
    for g in GENDERS:
        mine = sorted([c for c in chars if c["gender"] == g], key=lambda c: (c.get("f0") or 0.0, c["id"]))
        if not mine:
            continue
        pref = clean_choice(male if g == "male" else female, mine=True)
        pool = [v["id"] for v in (custom or []) if v.get("gender") == gender_label(g) and isinstance(v.get("id"), str)]
        grp = voice_groups(mine)
        nv = grp[-1] + 1
        if engine != "voxcpm":
            fallback = [EDGE_VOICE[g]] * nv
        elif job_voice == "vox:original":
            fallback = None                                        # every character is cloned from its own lines (below)
        elif job_voice and job_voice != "vox:default" and job_gender in ("", g):
            fallback = [job_voice] * nv                            # the voice chosen for the job fits this gender: keep it
        else:
            fallback = designed_for(g, nv)
        for k, c in enumerate(mine):
            own = clean_choice(c.get("voice"))
            can_clone = bool(c.get("ref"))                         # a character without a clear line of its own has nothing to copy
            if own == CLONE or (not own and pref == CLONE):
                v = f"vox:s:{c['id']}" if can_clone else (fallback[grp[k]] if fallback else "")
            elif own:
                v = own
            elif pref == MINE:
                v = pool[grp[k] % len(pool)] if pool else (fallback[grp[k]] if fallback else (f"vox:s:{c['id']}" if can_clone else ""))
            elif pref:
                v = pref
            elif fallback is None:
                v = f"vox:s:{c['id']}" if can_clone else ""
            else:
                v = fallback[grp[k]]
            out[c["id"]] = v
    return out


def line_voice(seg: dict, voices: Dict[int, str]) -> Optional[str]:
    """The voice of one line chosen by character (None = the line follows the job's voice).  A voice set for the line itself is not
    handled here: it always wins."""
    c = seg.get("char")
    return voices.get(c) if isinstance(c, int) and not isinstance(c, bool) else None


def clean_character_edits(chars: List[dict], edits) -> List[dict]:
    """Validate the character edits of a Regenerate request: [{id, gender?, voice?, name?}].  Raises ValueError (shown to the user)."""
    if edits is None:
        return []
    if not isinstance(edits, list):
        raise ValueError("characters must be a list")
    known = {c["id"] for c in chars or []}
    out: List[dict] = []
    seen = set()
    for e in edits:
        if not isinstance(e, dict) or "id" not in e:
            raise ValueError("every edited character needs an id")
        try:
            cid = int(e["id"])
        except (TypeError, ValueError):
            raise ValueError(f"bad character number: {e.get('id')!r}")
        if cid not in known:
            raise ValueError(f"character {cid} does not exist")
        if cid in seen:
            raise ValueError(f"character {cid} is listed twice")
        seen.add(cid)
        c: dict = {"id": cid}
        if "gender" in e:
            if e["gender"] not in GENDERS:
                raise ValueError(f"character {cid}: the gender must be male or female")
            c["gender"] = e["gender"]
        if "voice" in e:
            v = e["voice"]
            if v in (None, ""):
                c["voice"] = ""
            elif valid_choice(v):
                c["voice"] = v
            else:
                raise ValueError(f"character {cid}: unknown voice {v!r}")
        if "name" in e:
            if e["name"] is not None and not isinstance(e["name"], str):
                raise ValueError(f"character {cid}: the name must be text")
            c["name"] = " ".join(str(e["name"] or "").split())[:MAX_NAME]
        out.append(c)
    return out


def apply_character_edits(chars: List[dict], edits: List[dict]) -> None:
    by_id = {c["id"]: c for c in chars}
    for e in edits:
        c = by_id[e["id"]]
        if "gender" in e and e["gender"] != c.get("gender"):
            c["gender"] = e["gender"]
            c["gender_set"] = True                    # decided by the user, not by the sound
        for k in ("voice", "name"):
            if k in e:
                c[k] = e[k]
