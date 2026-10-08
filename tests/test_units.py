"""Unit tests: designed voices catalogue, per-line voice / time (validation, windows, track building, synthesis plan)."""
import asyncio
import json
import math
import random
import re
import sys
import threading
import types
from pathlib import Path

import numpy as np

import os

from lib import Checker, PROJECT, VERSION, WORK  # noqa: E402  (lib also puts the project folder on sys.path)

os.environ.setdefault("KDS_DATA_DIR", str(WORK / "data_units"))
from app import pipeline, voxpresets  # noqa: E402
from app.config import SAMPLE_RATE as SR  # noqa: E402
from app.tts import VoiceSettings  # noqa: E402

c = Checker(f"units v{VERSION}")

# ------------------------------------------------------------------ designed voices catalogue
P = voxpresets.PRESETS
c.check(len(P) == 8, "8 designed voices")
c.check(sum(p.gender == "Female" for p in P) == 4 and sum(p.gender == "Male" for p in P) == 4, "4 female + 4 male")
c.check(len({p.key for p in P}) == 8 and len({p.seed for p in P}) == 8 and len({p.style for p in P}) == 8, "unique keys / seeds / styles")
c.check(all(voxpresets.KEY_RE.match(p.key) for p in P), "keys match the id pattern")
c.check(all("(" not in p.style and ")" not in p.style for p in P), "styles contain no brackets (the engine wraps them in brackets)")
c.check(not voxpresets.SAMPLE_TEXT.startswith("("), "sample text does not start with a bracket")
c.check(len(voxpresets.SAMPLE_TEXT) > 60, "sample text is long enough for ~8 s of speech")
home = WORK / "presets_home"
import shutil
shutil.rmtree(home, ignore_errors=True)
lst = voxpresets.list_presets(home)
c.check(len(lst) == 8 and all(not x["ready"] and x["variant"] == 0 and x["id"].startswith("vox:p:") for x in lst), "list_presets: fresh home")
c.check(voxpresets.variant_of(home, "f_warm") == 0, "variant 0 at the start")
n1 = voxpresets.bump_variant(home, "f_warm")
n2 = voxpresets.bump_variant(home, "f_warm")
c.check((n1, n2) == (1, 2) and voxpresets.variant_of(home, "f_warm") == 2 and voxpresets.variant_of(home, "m_deep") == 0, "bump_variant counts per voice")
c.check(voxpresets.seed_for(P[0], 0) != voxpresets.seed_for(P[0], 1), "re-roll changes the seed")
c.check(voxpresets.ref_path(home, "f_warm").name == "preset-f_warm-v2.wav", "anchor file name carries the variant")
(home / "voices").mkdir(parents=True, exist_ok=True)
for v in range(4):
    (home / "voices" / f"preset-m_deep-v{v}.wav").write_bytes(b"x")
voxpresets.prune_old(home, "m_deep", 3)
left = sorted(f.name for f in (home / "voices").glob("preset-m_deep-*"))
c.check(left == ["preset-m_deep-v2.wav", "preset-m_deep-v3.wav"], "prune keeps the current + previous anchor", str(left))
(home / "presets.json").write_text("not json")
c.check(voxpresets.variant_of(home, "f_warm") == 0, "a damaged presets.json is ignored")
c.check(voxpresets.get("nope") is None and voxpresets.get("m_anchor").gender == "Male", "get()")

# ------------------------------------------------------------------ valid_row_voice
ok = ["km-KH-SreymomNeural", "km-KH-PisethNeural", "vox:original", "vox:c:0123abcd", "vox:p:f_warm", "vox:p:m_anchor"]
bad = ["", None, 5, "vox:p:nope", "vox:c:XYZ", "vox:c:0123abc", "vox:default", "en-US-AvaNeural", "vox:", "../etc/passwd", "vox:p:"]
c.check(all(pipeline.valid_row_voice(v) for v in ok), "valid row voices accepted")
c.check(not any(pipeline.valid_row_voice(v) for v in bad), "invalid row voices rejected", str([v for v in bad if pipeline.valid_row_voice(v)]))

# ------------------------------------------------------------------ clean_segment_edits
segs = [{"idx": i, "start": 10.0 + i * 4, "end": 12.5 + i * 4, "en": f"line {i}", "km": f"ខ្មែរ {i}"} for i in range(6)]
segs[2]["t1"] = 20.0
ce = pipeline.clean_segment_edits
c.check(ce(segs, None) == [] and ce(segs, []) == [], "no edits")
r = ce(segs, [{"idx": 1, "km": "សួស្តី", "voice": "km-KH-PisethNeural", "t0": 14.5, "t1": 17.25}])
c.check(r == [{"idx": 1, "km": "សួស្តី", "voice": "km-KH-PisethNeural", "t0": 14.5, "t1": 17.25}], "full edit cleaned", str(r))
r = ce(segs, [{"idx": 0, "km": "x"}, {"idx": 3, "voice": ""}, {"idx": 4, "voice": None, "t0": None, "t1": ""}])
c.check(r[0] == {"idx": 0, "km": "x"} and r[1] == {"idx": 3, "voice": None} and r[2] == {"idx": 4, "voice": None, "t0": None, "t1": None},
        "only the sent fields are returned; ''/null = reset", str(r))
c.check(ce(segs, [{"idx": 0, "t0": "12.5", "t1": "15"}])[0] == {"idx": 0, "t0": 12.5, "t1": 15.0}, "numeric strings accepted")
c.check(ce(segs, [{"idx": 0, "km": None}])[0] == {"idx": 0, "km": ""}, "km null -> empty")
c.check(ce(segs, [{"idx": 0, "t0": 1.23456}])[0]["t0"] == 1.235, "times rounded to ms")


def raises(fn, label, contains=""):
    try:
        fn()
    except ValueError as exc:
        c.check(contains.lower() in str(exc).lower(), label, f"message: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        c.check(False, label, f"wrong exception {type(exc).__name__}: {exc}")
        return
    c.check(False, label, "no error")


raises(lambda: ce(segs, "x"), "edits must be a list", "list")
raises(lambda: ce(segs, [{"km": "x"}]), "idx required", "idx")
raises(lambda: ce(segs, [{"idx": "a"}]), "idx must be a number", "bad line")
raises(lambda: ce(segs, [{"idx": 99}]), "unknown line", "does not exist")
raises(lambda: ce(segs, [{"idx": 1}, {"idx": 1}]), "duplicate line", "twice")
raises(lambda: ce(segs, [{"idx": 1, "voice": "vox:p:zzz"}]), "unknown designed voice", "unknown voice")
raises(lambda: ce(segs, [{"idx": 1, "voice": "en-US-AvaNeural"}]), "english voices are not row voices", "unknown voice")
raises(lambda: ce(segs, [{"idx": 1, "t0": "abc"}]), "Start not a number", "not a number")
raises(lambda: ce(segs, [{"idx": 1, "t1": float("nan")}]), "NaN rejected", "out of range")
raises(lambda: ce(segs, [{"idx": 1, "t0": -1}]), "negative rejected", "out of range")
raises(lambda: ce(segs, [{"idx": 1, "t0": 1e9}]), "huge rejected", "out of range")
raises(lambda: ce(segs, [{"idx": 1, "t0": 14.0, "t1": 14.1}]), "End too close to Start", "at least")
raises(lambda: ce(segs, [{"idx": 1, "t1": 13.0}]), "End before the caption start", "at least")
raises(lambda: ce(segs, [{"idx": 2, "t0": 19.9}]), "Start moved next to the stored End", "at least")
c.check(ce(segs, [{"idx": 2, "t0": 19.9, "t1": None}])[0]["t1"] is None, "…but fine when End is cleared in the same edit")
raises(lambda: ce(segs, [{"idx": 1, "km": 5}]), "km must be text", "text")

# ------------------------------------------------------------------ row_settings
base = VoiceSettings(voice="km-KH-SreymomNeural", rate=10, pitch=3, volume=5, term_mode="english_voice", en_voice="", engine="edge",
                     vox_id="vox:original", vox_quality="high", vox_consent=True)
rs = pipeline.row_settings
r = rs(base, "km-KH-PisethNeural")
c.check(r.engine == "edge" and r.voice == "km-KH-PisethNeural" and r.en_voice == "en-US-AndrewNeural", "edge row: voice + the matching English voice", str((r.voice, r.en_voice)))
c.check(r.rate == 10 and r.pitch == 3 and r.volume == 5 and r.vox_quality == "high" and r.vox_consent, "edge row keeps rate / pitch / volume / quality / consent")
c.check(base.voice == "km-KH-SreymomNeural" and base.en_voice == "en-US-AvaNeural", "base settings are not modified")
hand = VoiceSettings(voice="km-KH-SreymomNeural", en_voice="en-US-EmmaNeural")
c.check(rs(hand, "km-KH-PisethNeural").en_voice == "en-US-EmmaNeural", "an English voice picked by hand is kept")
r = rs(base, "vox:p:f_warm")
c.check(r.engine == "voxcpm" and r.vox_id == "vox:p:f_warm" and r.vox_quality == "high" and r.vox_consent, "vox row")
c.check(rs(base, "") is None and rs(base, None) is None and rs(base, "nonsense") is None and rs(base, "vox:p:nope") is None, "no / invalid voice -> follows the job")
vbase = VoiceSettings(engine="voxcpm", vox_id="vox:c:0123abcd", rate=0)
r = rs(vbase, "km-KH-PisethNeural")
c.check(r.engine == "edge" and r.voice == "km-KH-PisethNeural", "edge row inside a VoxCPM2 job")

# ------------------------------------------------------------------ windows: identical to v1.3 when nothing is set by hand
def old_slot(segs, i):
    end = segs[i + 1]["start"] if i + 1 < len(segs) else segs[i]["end"] + 4.0
    return max(0.6, end - segs[i]["start"] - 0.10)


random.seed(7)
plain = []
t = 3.0
for i in range(40):
    d = random.uniform(0.5, 6)
    plain.append({"idx": i, "start": round(t, 3), "end": round(t + d, 3), "en": "x", "km": "x"})
    t += d + random.uniform(0, 2.5)
w = pipeline._windows(plain)
c.check(all(abs(pipeline._slot_for(w, i) - old_slot(plain, i)) < 1e-9 for i in range(40)), "default slots == v1.3 slots (40 random lines)")

s2 = [dict(s) for s in plain]
s2[5]["t0"] = s2[5]["start"] + 0.8
w2 = pipeline._windows(s2)
c.check(abs(w2[5][0] - (plain[5]["start"] + 0.8)) < 1e-9, "t0 moves the start")
c.check(abs(w2[4][1] - (plain[5]["start"] + 0.8 - 0.10)) < 1e-9, "the line BEFORE gets the time (its default End follows the next Start)")
s3 = [dict(s) for s in plain]
s3[7]["t1"] = s3[7]["start"] + 9.0
w3 = pipeline._windows(s3)
c.check(abs(w3[7][1] - (plain[7]["start"] + 9.0)) < 1e-9 and abs(w3[7][1] - w3[7][0] - 9.0) < 1e-9, "t1 is the deadline (no 0.1 s margin)")
c.check(abs(w3[8][0] - plain[8]["start"]) < 1e-9, "a hand-set End does not move the next line")
s4 = [dict(s) for s in plain]
s4[-1]["t1"] = s4[-1]["start"] + 1.0
c.check(abs(pipeline._windows(s4)[-1][1] - (plain[-1]["start"] + 1.0)) < 1e-9, "t1 on the last line")
c.check(pipeline._slot_for([(5.0, 5.2)], 0) == 0.6, "slot floor 0.6 s")

# ------------------------------------------------------------------ _build_track with fake audio
def tone(sec, freq=220.0):
    n = int(sec * SR)
    return (0.3 * np.sin(2 * np.pi * freq * np.arange(n) / SR)).astype(np.float32)


class FakeJob:
    def __init__(self, segments=None):
        self.meta, self.outputs, self.segments, self.logs = {}, {}, segments or [], []
        self.cancel_flag = threading.Event()
        self.dir = WORK / "fakejob"
        self.dir.mkdir(exist_ok=True)
        self.steps = []

    def check_cancel(self):
        pass

    def log(self, m):
        self.logs.append(m)

    def step(self, *a, **k):
        self.steps.append((a, k))


def ctx_for(**kw):
    vs = kw.pop("vs", VoiceSettings())
    return pipeline.AudioCtx(vs=vs, readings={}, **kw)


def first_nonzero(track):
    idx = np.flatnonzero(np.abs(track) > 1e-4)
    return idx[0] / SR if len(idx) else None


segs = [{"idx": 0, "start": 2.0, "end": 4.0, "en": "a", "km": "ក"}, {"idx": 1, "start": 6.0, "end": 8.0, "en": "b", "km": "ខ"},
        {"idx": 2, "start": 10.0, "end": 12.0, "en": "c", "km": "គ"}]
job = FakeJob(segs)
track = pipeline._build_track(job, segs, [tone(1.0), tone(1.0), tone(1.0)], [0, 0, 0], ctx_for())
c.check([s["out_start"] for s in segs] == [2.0, 6.0, 10.0], "defaults: lines start at their captions", str([s["out_start"] for s in segs]))
c.check(all(s["slot"][0] == s["start"] for s in segs) and abs(segs[0]["slot"][1] - 5.9) < 1e-6, "slot stored for every line", str(segs[0]["slot"]))
c.check(all(abs(s["dur"] - 1.0) < 0.01 and s["speed"] == 1.0 for s in segs), "dur = natural length, speed 1.0", str([(s["dur"], s["speed"]) for s in segs]))
c.check("warn" not in segs[0], "no warning for a fitting line")

segs = [{"idx": 0, "start": 2.0, "end": 4.0, "en": "a", "km": "ក", "t0": 0.5}, {"idx": 1, "start": 6.0, "end": 8.0, "en": "b", "km": "ខ", "t0": 6.75}]
job = FakeJob(segs)
pipeline._build_track(job, segs, [tone(1.0), tone(1.0)], [0, 0], ctx_for())
c.check(segs[0]["out_start"] == 0.5 and segs[1]["out_start"] == 6.75, "hand-set Start places the line there (earlier or later than the caption)", str([s["out_start"] for s in segs]))
c.check(first_nonzero(pipeline._build_track(FakeJob(segs), segs, [tone(1.0), tone(1.0)], [0, 0], ctx_for())) < 0.6, "…and the audio really starts there")

# End deadline: a 3 s line in a 2 s window -> residual stretch up to 1.15, then flagged 'long'
segs = [{"idx": 0, "start": 2.0, "end": 4.0, "en": "a", "km": "ក", "t1": 4.0}, {"idx": 1, "start": 9.0, "end": 11.0, "en": "b", "km": "ខ"}]
job = FakeJob(segs)
pipeline._build_track(job, segs, [tone(3.0), tone(1.0)], [0, 0], ctx_for())
d0 = segs[0]["out_end"] - segs[0]["out_start"]
c.check(abs(d0 - 3.0 / 1.15) < 0.05, "deadline: stretched by the residual 1.15", f"{d0:.2f}")
c.check(segs[0].get("warn") == "long", "…and flagged 'long' because it still overruns", str(segs[0].get("warn")))
c.check(abs(segs[0]["dur"] - 3.0) < 0.05 and abs(segs[0]["speed"] - 1.15) < 0.01, "dur stays the natural length", str((segs[0]["dur"], segs[0]["speed"])))
# when the line was already sped up by the TTS stage (rates[i] > base) dur is still the natural length
segs = [{"idx": 0, "start": 2.0, "end": 4.0, "en": "a", "km": "ក"}, {"idx": 1, "start": 5.0, "end": 6.0, "en": "b", "km": "ខ"}]
job = FakeJob(segs)
pipeline._build_track(job, segs, [tone(1.0), tone(1.0)], [25, 0], ctx_for())     # 1.0 s of audio that was spoken 25 % faster
c.check(abs(segs[0]["dur"] - 1.25) < 0.01 and abs(segs[0]["speed"] - 1.25) < 0.01, "dur accounts for the speed-up already applied", str((segs[0]["dur"], segs[0]["speed"])))
# late: pushed by the previous line
segs = [{"idx": 0, "start": 1.0, "end": 2.0, "en": "a", "km": "ក"}, {"idx": 1, "start": 2.2, "end": 3.0, "en": "b", "km": "ខ"}, {"idx": 2, "start": 3.5, "end": 4.0, "en": "c", "km": "គ"}]
job = FakeJob(segs)
pipeline._build_track(job, segs, [tone(8.0), tone(1.0), tone(1.0)], [0, 0, 0], ctx_for())
c.check("late" in (segs[2].get("warn") or ""), "pushed lines are flagged 'late'", str([s.get("warn") for s in segs]))
c.check("long" in (segs[0].get("warn") or ""), "the line that causes it is flagged 'long'", str([s.get("warn") for s in segs]))
# natural pace ignores the hand-set times but keeps order
segs = [{"idx": 0, "start": 2.0, "end": 4.0, "en": "a", "km": "ក", "t0": 50.0}, {"idx": 1, "start": 6.0, "end": 8.0, "en": "b", "km": "ខ"}]
job = FakeJob(segs)
pipeline._build_track(job, segs, [tone(1.0), tone(1.0)], [0, 0], ctx_for(sync="natural"))
c.check(segs[0]["out_start"] == 0.0 and segs[1]["out_start"] > segs[0]["out_end"], "natural mode: times are ignored", str([s["out_start"] for s in segs]))
# empty text
segs = [{"idx": 0, "start": 2.0, "end": 4.0, "en": "[Music]", "km": "", "dur": 9, "speed": 1.2}, {"idx": 1, "start": 6.0, "end": 8.0, "en": "b", "km": "ខ"}]
job = FakeJob(segs)
pipeline._build_track(job, segs, [np.zeros(0, np.float32), tone(1.0)], [0, 0], ctx_for())
c.check(segs[0]["out_start"] is None and "dur" not in segs[0] and "slot" in segs[0], "a line without speech: no times, no dur, slot kept")

# ------------------------------------------------------------------ _synth_all: which engine / voice speaks which line
calls = {"edge": [], "vox_resolved": [], "vox_lines": []}


class FakeSynth:
    def __init__(self, concurrency=4, on_retry=None):
        self.calls = 0
        self.cache_hits = 0

    async def segment(self, km, vs, readings=None, rate=None):
        calls["edge"].append((km, vs.voice, vs.en_voice, rate))
        self.calls += 1
        return tone(0.5 + 0.05 * len(km), 200 if vs.voice.endswith("SreymomNeural") else 140)


class FakeVoxSynth:
    def __init__(self, resolved, quality="balanced", mgr=None, status=None, cancelled=None):
        self.v, self.calls, self.cache_hits, self.gen_s, self.audio_s = resolved, 0, 0, 0.0, 0.0

    async def segment(self, km, vs, readings=None, rate=None):
        calls["vox_lines"].append((km, self.v.id, vs.vox_id))
        self.calls += 1
        self.gen_s += 0.1
        self.audio_s += 0.5
        return tone(0.5 + 0.05 * len(km), 400)


def fake_resolve(vs, **kw):
    calls["vox_resolved"].append(vs.vox_id)
    from app.voxvoices import Resolved
    kind = "original" if vs.vox_id == "vox:original" else "designed" if vs.vox_id.startswith("vox:p:") else "custom"
    return Resolved(vs.vox_id, kind, Path("/nonexistent.wav"), "h" + vs.vox_id, vs.vox_id.split(":")[-1])


import app.voxvoices as vv  # noqa: E402
import app.vox as voxmod  # noqa: E402
pipeline.Synth = FakeSynth
vv.VoxSynth, vv.resolve_voice = FakeVoxSynth, fake_resolve
voxmod.manager = lambda: object()

segs = [{"idx": i, "start": 2.0 + 3 * i, "end": 4.0 + 3 * i, "en": "x", "km": "ឃ្លា" * (i + 1)} for i in range(6)]
segs[1]["voice"] = "km-KH-PisethNeural"
segs[2]["voice"] = "vox:p:f_warm"
segs[3]["voice"] = "vox:p:m_deep"
segs[4]["voice"] = "vox:p:f_warm"
segs[5]["voice"] = "vox:c:0123abcd"
job = FakeJob(segs)
ctx = ctx_for(vs=VoiceSettings(voice="km-KH-SreymomNeural"))
audios, rates = asyncio.run(pipeline._synth_all(job, segs, ctx))
c.check(all(a is not None and len(a) > 0 for a in audios), "every line got audio")
c.check([x[1] for x in calls["edge"] if x[3] is None] == ["km-KH-SreymomNeural", "km-KH-PisethNeural"], "edge lines: job voice + the line's own voice", str(calls["edge"]))
c.check(dict((x[0], x[2]) for x in calls["edge"])[segs[1]["km"]] == "en-US-AndrewNeural", "Piseth's line reads English terms with Andrew")
c.check(calls["vox_resolved"] == ["vox:p:f_warm", "vox:p:m_deep", "vox:c:0123abcd"], "each vox voice is prepared once, in order of first use", str(calls["vox_resolved"]))
c.check([x[2] for x in calls["vox_lines"]] == ["vox:p:f_warm", "vox:p:m_deep", "vox:p:f_warm", "vox:c:0123abcd"], "vox lines use their own voice, in order", str(calls["vox_lines"]))
c.check(job.meta["vox"]["lines"] == 4 and job.meta["vox"]["voices"] == ["vox:p:f_warm", "vox:p:m_deep", "vox:c:0123abcd"], "meta.vox lists the voices", str(job.meta.get("vox")))
c.check(len(rates) == 6 and all(r == 0 or r > 0 for r in rates), "rates list is complete")

# job voice = VoxCPM2, one line with an Edge voice
calls["edge"].clear(), calls["vox_resolved"].clear(), calls["vox_lines"].clear()
segs = [{"idx": i, "start": 2.0 + 3 * i, "end": 4.0 + 3 * i, "en": "x", "km": "ឃ្លា"} for i in range(3)]
segs[1]["voice"] = "km-KH-SreymomNeural"
job = FakeJob(segs)
ctx = ctx_for(vs=VoiceSettings(engine="voxcpm", vox_id="vox:p:m_elder"))
audios, rates = asyncio.run(pipeline._synth_all(job, segs, ctx))
c.check(len(calls["edge"]) == 1 and calls["edge"][0][1] == "km-KH-SreymomNeural", "vox job: the Edge line is spoken by Edge", str(calls["edge"]))
c.check(calls["vox_resolved"] == ["vox:p:m_elder"] and len(calls["vox_lines"]) == 2, "…the others by the job's vox voice", str(calls))
# plain edge job (no overrides) behaves like before
calls["edge"].clear(), calls["vox_resolved"].clear(), calls["vox_lines"].clear()
segs = [{"idx": i, "start": 2.0 + 3 * i, "end": 4.0 + 3 * i, "en": "x", "km": "ឃ្លា"} for i in range(3)]
job = FakeJob(segs)
audios, rates = asyncio.run(pipeline._synth_all(job, segs, ctx_for()))
c.check(len(calls["edge"]) == 3 and "vox" not in job.meta and not calls["vox_resolved"], "plain Edge job unchanged")
# the speed-up pass re-speaks only the lines that are too long, with their own voice
calls["edge"].clear()
segs = [{"idx": 0, "start": 1.0, "end": 2.0, "en": "x", "km": "ឃ្លា" * 30, "voice": "km-KH-PisethNeural"}, {"idx": 1, "start": 3.0, "end": 4.0, "en": "x", "km": "ក"}]
job = FakeJob(segs)
audios, rates = asyncio.run(pipeline._synth_all(job, segs, ctx_for()))
again = [x for x in calls["edge"] if x[3] is not None]
c.check(len(again) == 1 and again[0][1] == "km-KH-PisethNeural" and again[0][3] > 0, "pass 2 re-speaks the long line with ITS voice, faster", str(calls["edge"]))
c.check(rates[0] > 0 and rates[1] == 0, "only that line has a higher rate", str(rates))

# ------------------------------------------------------------------ MP4 export: up to 1080p
import inspect
import subprocess
import tempfile
from app import audio as aud, ytsource

ytsource_default = inspect.signature(ytsource.download_video).parameters["max_height"].default
c.check(ytsource_default == 1080 and ytsource.DEFAULT_VIDEO_HEIGHT == 1080, "the default limit is now 1080p")
chv = ytsource.clean_video_height
c.check([chv(x) for x in (None, "", "abc", 720, "720", 1080, "1080", 480, 360, 2160, 0, -5, 1080.0)] == [1080, 1080, 1080, 720, 720, 1080, 1080, 480, 1080, 1080, 1080, 1080, 1080], "clean_video_height: 480 / 720 / 1080, anything else -> 1080")
c.check(pipeline._ctx_from({"output": {"max_height": 720}}, None, True).max_height == 720 and pipeline._ctx_from({"output": {}}, None, True).max_height == 1080
        and pipeline._ctx_from({"output": {"max_height": "junk"}}, None, True).max_height == 1080 and pipeline._ctx_from({}, None, True).max_height == 1080, "_ctx_from reads output.max_height")

ff = aud.ffmpeg_exe()
tmp = WORK / "ytunit"
shutil.rmtree(tmp, ignore_errors=True)
tmp.mkdir(parents=True)


def make_video(path, w, h, with_audio):
    cmd = [ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=10:duration=1.2"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1.2"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"] + (["-c:a", "aac"] if with_audio else []) + [str(path)]
    subprocess.run(cmd, check=True)


v1080, v360 = tmp / "a1080.mp4", tmp / "v360.mp4"
make_video(v1080, 1920, 1080, True)
make_video(v360, 640, 360, False)
i1 = aud.probe_media(v1080)
i2 = aud.probe_media(v360)
c.check((i1["width"], i1["height"], i1["video_codec"], i1["has_audio"]) == (1920, 1080, "h264", True), "probe_media reads 1920x1080 h264 + audio", str(i1))
c.check((i2["width"], i2["height"], i2["has_audio"]) == (640, 360, False), "probe_media reads 640x360, no audio", str(i2))

# a fake yt-dlp: records the format it was asked for and writes a video of the matching height
dl_calls = []


class FakeYDL:
    fail = False

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def download(self, urls):
        fmt = self.opts["format"]
        dl_calls.append(fmt)
        if FakeYDL.fail:
            raise RuntimeError("boom")
        out = Path(self.opts["outtmpl"]).parent / "source.mp4"
        shutil.copy(v1080 if "+ba" in fmt else v360, out)


sys.modules["yt_dlp"] = types.SimpleNamespace(YoutubeDL=FakeYDL)
d = tmp / "job1"
p1 = ytsource.download_video("dQw4w9WgXcQ", d)
c.check(len(dl_calls) == 1 and "height<=1080" in dl_calls[0] and "+ba" not in dl_calls[0], "first download asks for height<=1080 (video only)", str(dl_calls))
mk = json.loads((d / "source.json").read_text())
c.check(mk == {"max_height": 1080, "with_audio": False} and p1.name == "source.mp4", "…and writes a marker file next to it", str(mk))
ytsource.download_video("dQw4w9WgXcQ", d)
c.check(len(dl_calls) == 1, "the same request reuses the video on disk", str(len(dl_calls)))
ytsource.download_video("dQw4w9WgXcQ", d, with_audio=True)
c.check(len(dl_calls) == 2 and "+ba[ext=m4a]" in dl_calls[1] and "height<=1080" in dl_calls[1], "the original sound is needed but the file has none -> downloaded again (with sound)", str(dl_calls[1:]))
c.check(sorted(f.name for f in d.glob("*")) == ["source.json", "source.mp4"] and json.loads((d / "source.json").read_text())["with_audio"] is True, "…replacing the old file (no leftovers)")
ytsource.download_video("dQw4w9WgXcQ", d, with_audio=False, max_height=1080)
c.check(len(dl_calls) == 2, "a file with sound also serves a request without sound")
ytsource.download_video("dQw4w9WgXcQ", d, with_audio=True, max_height=720)
c.check(len(dl_calls) == 3 and "height<=720" in dl_calls[2] and json.loads((d / "source.json").read_text())["max_height"] == 720, "a LOWER limit (720p chosen after 1080p) downloads again, so the MP4 has the quality that was chosen", str(dl_calls[2:]))
ytsource.download_video("dQw4w9WgXcQ", d, with_audio=True, max_height=1080)
c.check(len(dl_calls) == 4 and "height<=1080" in dl_calls[3], "…and 1080p after 720p downloads again")
c.check(ytsource._find_download(d, "source").name == "source.mp4", "the marker file is never taken for the video")

# a download made by v1.3 (no marker file, <= 720p)
d2 = tmp / "job_legacy_audio"
d2.mkdir()
shutil.copy(v1080, d2 / "source.mp4")                       # (has sound; its real height does not matter - the marker rule assumes 720p)
n0 = len(dl_calls)
ytsource.download_video("x", d2, with_audio=True, max_height=720)
c.check(len(dl_calls) == n0, "old download (no marker) with sound is reused for 720p (that is what it was)")
ytsource.download_video("x", d2, with_audio=True, max_height=1080)
c.check(len(dl_calls) == n0 + 1 and (d2 / "source.json").exists(), "old download is replaced when 1080p is wanted")
d3 = tmp / "job_legacy_silent"
d3.mkdir()
shutil.copy(v360, d3 / "source.mp4")
n0 = len(dl_calls)
ytsource.download_video("x", d3, with_audio=False, max_height=720)
c.check(len(dl_calls) == n0, "old silent download is reused when no sound is needed (720p)")
ytsource.download_video("x", d3, with_audio=True, max_height=720)
c.check(len(dl_calls) == n0 + 1, "old silent download is replaced when the original sound is needed")
# failures
d4 = tmp / "job_fail"
FakeYDL.fail = True
try:
    ytsource.download_video("x", d4)
    c.check(False, "a failing download raises SourceError")
except ytsource.SourceError as exc:
    c.check(exc.code == "DOWNLOAD_FAILED", "a failing download raises SourceError(DOWNLOAD_FAILED)", exc.code)
FakeYDL.fail = False
c.check(not list(d4.glob("source.*")), "…and leaves nothing behind")
# the 480 / 720 limits end up in the format string
dl_calls.clear()
ytsource.download_video("x", tmp / "job720", max_height=720)
ytsource.download_video("x", tmp / "job480", max_height=480)
c.check("height<=720" in dl_calls[0] and "height<=480" in dl_calls[1], "720 / 480 limits are passed to yt-dlp", str(dl_calls))

# ------------------------------------------------------------------ static guard: the interface dictionaries (km / en)
_i18n = (PROJECT / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
_head, _tail = _i18n.split("\n  en: {")
_rx = re.compile(r"^\s{4}'([^']+)':", re.M)
_km, _en = _rx.findall(_head), _rx.findall(_tail)
c.check(len(_km) > 500 and len(_km) == len(set(_km)) and len(_en) == len(set(_en)), "i18n: no key is defined twice in a language", f"{len(_km)} / {len(_en)}")
c.check(set(_km) == set(_en), "i18n: Khmer and English have exactly the same keys", str(sorted(set(_km) ^ set(_en))[:8]))
_code = (PROJECT / "static" / "index.html").read_text(encoding="utf-8") + (PROJECT / "static" / "js" / "app.js").read_text(encoding="utf-8")
_used = set(re.findall(r'data-i18n(?:-ph)?="([^"]+)"', _code)) | set(re.findall(r"""\bt\(\s*['"]([A-Za-z0-9_.\-]+)['"]""", _code))
_missing = sorted(k for k in _used if k not in set(_km) and not any(x.startswith(k) for x in _km))      # 't("status." + x)': a prefix of real keys is fine
c.check(len(_used) > 300 and not _missing, "i18n: every key that index.html / app.js uses exists (no raw key can show on screen)", str(_missing[:8]))

# ------------------------------------------------------------------ guards added in 1.12.0
# the owner does not want the PC's specs on the screen: no text may name the hardware (no GPU name / VRAM / CUDA / RAM) - warnings say "this computer"
_kv = re.compile(r"^\s{4}'([^']+)':\s*'(.*)',\s*$", re.M)
_strings = {("km", k): v for k, v in _kv.findall(_head)} | {("en", k): v for k, v in _kv.findall(_tail)}
_SPEC = re.compile(r"NVIDIA|GeForce|\bRTX\b|VRAM|CUDA|\bGPU\b|\bRAM\b", re.I)
_spec_bad = sorted(f"{lang}:{k}" for (lang, k), v in _strings.items() if _SPEC.search(v))
c.check(len(_strings) > 1000 and not _spec_bad, "i18n: no text names the computer's hardware (no NVIDIA / GPU / VRAM / CUDA / RAM in any language)", str(_spec_bad[:6]))
c.check("voice.engine.hint.vox" not in _km and "voice.engine.hint.vox" not in _en and "voice.engine.hint.vox" not in _code, "i18n: the 'Runs on your own computer ... needs an NVIDIA GPU' paragraph is gone (the key and its use)")
c.check(not [k for (l, k), v in _strings.items() if k in ("vox.banner.ready", "set.vox.status.ready", "set.vox.speed.measured") and re.search(r"\{(device|dev)\}", v)], "i18n: the 'running' / 'speed' texts do not take the device (GPU name) any more")
_ui_files = [PROJECT / "static" / n for n in ("index.html", "offline.html", "manifest.webmanifest", "sw.js", "css/app.css", "js/i18n.js", "js/app.js")]
_old_name = [f.name for f in _ui_files if "KhmerDub" in f.read_text(encoding="utf-8")]
c.check(not _old_name, "the old product name 'KhmerDub' is in no page / manifest / text (the product is 'V_Heang Studio')", str(_old_name))
_idx = (PROJECT / "static" / "index.html").read_text(encoding="utf-8")
c.check("<title>V_Heang Studio" in _idx and 'class="brand-name">V_Heang Studio<' in _idx, "index.html: the title and the name in the menu say 'V_Heang Studio'")

# ------------------------------------------------------------------ guards for two rules that had no test (added in 1.9.1)
from app import jobs as jobs_mod, langs  # noqa: E402
_jp = "これは日本語のテストです。ひらがなとカタカナがあります。今日はサーバーについて話します。"
c.check(langs.detect_lang(_jp) == "ja" and "ja" not in langs.LANGS, "Japanese is recognised (kana) and is NOT a supported language (the owner's decision)")
_jp_job = jobs_mod.Job("dub", {}, "japanese")
pipeline.run_dub_job(_jp_job, {"source": {"type": "transcript", "text": _jp, "lang": "auto"}, "translate": {"engine": "google"}})
c.check(_jp_job.status == "error" and (_jp_job.error or {}).get("code") == "LANG_UNSUPPORTED", "a Japanese transcript is refused with LANG_UNSUPPORTED (before any translation)", str(_jp_job.error))
for _st in ("running", "queued"):
    _j = jobs_mod.Job("dub", {}, "interrupted")
    _j.status = _st
    _j.save()
    _back = jobs_mod.Job.load(_j.dir / "job.json")
    c.check(_back is not None and _back.status == "error" and (_back.error or {}).get("code") == "INTERRUPTED" and not (_j.dir / "job.json.tmp").exists(),
            f"a job that was '{_st}' when the server stopped comes back as error INTERRUPTED (job.json is written atomically)")

sys.exit(c.done())
