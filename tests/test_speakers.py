"""v1.13.0 - voices by character: the app listens to the video, finds out who speaks every line (man / woman, which lines belong to
the same person) and gives men a male voice and women a female voice - without anybody choosing a voice per character.

  A  units    pitch measurement, man / woman, grouping into characters, the voice rules (autovoice), the request checks
  B  API      a real server (VoxCPM2 stub engine, no network): upload a dialogue -> characters -> voices -> edits -> detect again,
              the gender of an uploaded My-voices clip (+ one real Edge TTS round trip when the network is there)
  C  browser  Playwright / Chromium: the settings block, the Characters panel, the badges, the labels, the requests it sends

The sounds are made by tests/synthvoice.py (numpy only): no recordings, no downloads.   Set ONLY=A,B,C to run a part.
"""
import atexit
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave

import numpy as np

from lib import *  # noqa: E402,F401,F403
from synthvoice import SR, voice  # noqa: E402

WORK.mkdir(parents=True, exist_ok=True)
os.environ["KDS_DATA_DIR"] = str(WORK / "data_speakers_units")
shutil.rmtree(WORK / "data_speakers_units", ignore_errors=True)
from app import audio, autovoice, pipeline, speakers  # noqa: E402
from app.tts import VoiceSettings  # noqa: E402

ONLY = set((os.environ.get("ONLY") or "A,B,C").split(","))
c = Checker("Voices by character")
FX = WORK / "fx_speakers"
shutil.rmtree(FX, ignore_errors=True)
FX.mkdir(parents=True)
(WORK / "shots").mkdir(exist_ok=True)

# the speakers of the tests:  (pitch Hz, vocal-tract scale)
MAN, WOMAN, MAN2, GIRL = (110, 0.92), (215, 1.2), (150, 1.08), (300, 1.4)


def say(who, dur, seed):
    return voice(who[0], who[1], dur, seed=seed)


def write_wav(x, path, sr=SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def feats_of(who_list, dur=3.4, gap=0.6, t0=0.5):
    """A dialogue: one line per entry of who_list (a speaker tuple, or None for 'nothing but noise') -> (features, starts, ends, wav)."""
    feats, st, en, parts, t = [], [], [], [np.zeros(int(t0 * SR), np.float32)], t0
    for i, who in enumerate(who_list):
        d = dur + (i % 3) * 0.4
        x = say(who, d, seed=100 + i) if who else (np.random.default_rng(i).standard_normal(int(d * SR)) * 0.08).astype(np.float32)
        feats.append(speakers.line_feature(*speakers.pitch_frames(x)))
        st.append(t)
        en.append(t + d)
        parts += [x, np.zeros(int(gap * SR), np.float32)]
        t += d + gap
    return feats, st, en, np.concatenate(parts)


def gender_of_who(who):
    return "female" if who and who[0] > 165 else "male"


# =============================================================================================================== A. units
if "A" in ONLY:
    # ---- the pitch is measured within 4 % (with the natural movement of a voice), and man / woman follows
    for hz, sc in ((100, 0.9), (125, 1.0), (150, 1.05), (185, 1.15), (215, 1.2), (250, 1.3), (320, 1.4)):
        ft = speakers.line_feature(*speakers.pitch_frames(voice(hz, sc, 5.0, seed=hz)))
        c.check(ft.f0 is not None and abs(ft.f0 / hz - 1) < 0.04, f"the pitch of a {hz} Hz voice is measured within 4 %", str(ft.f0))
        want_female = hz > 165
        c.check(ft.p_female is not None and (ft.p_female > 0.5) == want_female, f"a {hz} Hz voice is a {'woman' if want_female else 'man'}", str(ft.p_female))
    c.check(abs(speakers.p_female_of(speakers.F_SPLIT) - 0.5) < 1e-6 and speakers.p_female_of(100) < 0.05 and speakers.p_female_of(250) > 0.95
            and speakers.p_female_of(None) is None and speakers.p_female_of(0) is None, "p_female_of: 0.5 at the boundary, sure at 100 / 250 Hz, None without a pitch")
    p_old = [speakers.p_female_of(h) for h in range(80, 300, 10)]
    c.check(all(a < b for a, b in zip(p_old, p_old[1:])), "the higher the pitch, the more likely a woman (monotonic)")

    # ---- sounds that are not a voice give no pitch
    noise = (np.random.default_rng(1).standard_normal(5 * SR) * 0.1).astype(np.float32)
    ft = speakers.line_feature(*speakers.pitch_frames(noise))
    c.check(ft.f0 is None and ft.p_female is None, "white noise: no pitch", str(ft.f0))
    ft = speakers.line_feature(*speakers.pitch_frames(np.zeros(4 * SR, np.float32)))
    c.check(ft.f0 is None and ft.voiced == 0, "digital silence: no pitch, nothing voiced", f"{ft.f0} {ft.voiced}")
    f0, cf, rm, mf = speakers.pitch_frames(np.zeros(100, np.float32))
    c.check(len(f0) == 0 and len(mf) == 0 and speakers.line_feature(f0, cf, rm, mf).f0 is None, "a clip shorter than one analysis window: nothing, no crash")
    ft = speakers.line_feature(*speakers.pitch_frames(voice(90, 0.9, 0.12, seed=1, pauses=False)))
    c.check(ft.f0 is None, "0.12 s of sound is too little to judge a voice", str(ft.f0))
    ft = speakers.line_feature(*speakers.pitch_frames(voice(90, 0.9, 0.5, seed=1, pauses=False)))
    c.check(ft.f0 is not None and abs(ft.f0 / 90 - 1) < 0.12, "…but half a second is enough (within 12 %)", str(ft.f0))
    low = np.sin(2 * np.pi * 50 * np.arange(3 * SR) / SR).astype(np.float32) * 0.3        # a rumble below any voice
    c.check(speakers.line_feature(*speakers.pitch_frames(low)).f0 is None, "a 50 Hz rumble is not a voice")

    # ---- one speaker
    feats, st, en, wav = feats_of([WOMAN] * 8)
    det = speakers.group_lines(feats, st, en)
    c.check(len(det.characters) == 1 and det.characters[0]["gender"] == "female" and det.characters[0]["lines"] == 8
            and all(x["char"] == 1 and x["gender"] == "female" for x in det.lines), "one woman: one character, female, all 8 lines", str(det.characters))
    c.check(det.coverage > 0.9, "…measured on nearly all of the speech", str(det.coverage))
    ch = det.characters[0]
    c.check(ch["f0"] and abs(ch["f0"] / 215 - 1) < 0.05 and ch["p"] > 0.9 and ch["seconds"] > 25, "…with her pitch, her certainty and her seconds of speech", str(ch))
    c.check(ch["ref"] and all(len(r) == 2 and r[1] > r[0] for r in ch["ref"]) and sum(b - a for a, b in ch["ref"]) >= 6
            and all(any(abs(a - s) < 0.01 and abs(b - e) < 0.01 for s, e in zip(st, en)) for a, b in ch["ref"]), "…and the lines that make a clean voice reference", str(ch["ref"]))
    feats, st, en, wav = feats_of([MAN] * 8)
    det = speakers.group_lines(feats, st, en)
    c.check(len(det.characters) == 1 and det.characters[0]["gender"] == "male" and all(x["gender"] == "male" for x in det.lines), "one man: one character, male")

    # ---- a man and a woman talking
    who = [MAN, WOMAN, MAN, WOMAN, WOMAN, MAN, MAN, WOMAN, MAN, WOMAN, WOMAN, MAN]
    feats, st, en, wav = feats_of(who)
    det = speakers.group_lines(feats, st, en)
    c.check([x["gender"] for x in det.lines] == [gender_of_who(w) for w in who], "a man and a woman: every line has the right gender", str([x["gender"] for x in det.lines]))
    c.check(len(det.characters) == 2 and {x["gender"] for x in det.characters} == {"male", "female"}, "…two characters", str(det.characters))
    c.check(det.characters[0]["id"] == 1 and det.characters[0]["gender"] == "male" and det.lines[0]["char"] == 1, "characters are numbered in order of appearance (line 1 is the man: character 1)")
    c.check(all(x["char"] in (1, 2) for x in det.lines) and sum(x["lines"] for x in det.characters) == 12, "…and every line belongs to a character")
    # more people of the same gender: the gender is right whatever the characters are
    who = [MAN, MAN2, WOMAN, MAN, MAN2, WOMAN, MAN2, MAN, WOMAN, MAN, MAN2, WOMAN, MAN, WOMAN]
    feats, st, en, wav = feats_of(who)
    det = speakers.group_lines(feats, st, en)
    c.check([x["gender"] for x in det.lines] == [gender_of_who(w) for w in who], "two men and a woman: every line has the right gender")
    c.check(1 <= sum(1 for x in det.characters if x["gender"] == "male") <= 2 and sum(1 for x in det.characters if x["gender"] == "female") == 1, "…one woman, one or two men (cautious: two men may be one character)", str(det.characters))
    # a child is a high voice: female voice (the table lets the user correct it)
    feats, st, en, wav = feats_of([GIRL] * 5)
    c.check(speakers.group_lines(feats, st, en).characters[0]["gender"] == "female", "a child's voice is high: female (can be flipped in the table)")

    # ---- a stray line of the other gender is not a second person; three lines are
    feats, st, en, wav = feats_of([MAN] * 10 + [WOMAN])
    det = speakers.group_lines(feats, st, en)
    c.check(len(det.characters) == 1 and all(x["gender"] == "male" for x in det.lines), "10 lines of a man and ONE of a woman: the stray line follows the rest (one character, male)", str(det.characters))
    feats, st, en, wav = feats_of([MAN] * 10 + [WOMAN] * 3)
    det = speakers.group_lines(feats, st, en)
    c.check(sorted(x["gender"] for x in det.characters) == ["female", "male"] and [x["gender"] for x in det.lines][-3:] == ["female"] * 3, "…but a woman with 3 lines is a character of her own")

    # ---- not enough to go on: no answer
    feats, st, en, wav = feats_of([None] * 6)
    det = speakers.group_lines(feats, st, en)
    c.check(det.characters == [] and all(x["char"] is None and x["gender"] is None for x in det.lines) and det.coverage == 0, "noise only: no characters, no gender (the dub keeps the chosen voice)", str(det.characters))
    feats, st, en, wav = feats_of([None] * 7 + [WOMAN])
    c.check(speakers.group_lines(feats, st, en).characters == [], "a single voiced line among noise is below the minimum (coverage): no answer")
    c.check(speakers.group_lines([], [], []).lines == [] and speakers.group_lines([speakers.LineFeat()], [0.0], [1.0]).characters == [], "no lines / an empty line: no crash, no answer")

    # ---- lines nobody could measure take the character of the line before (else after, else the main one)
    feats, st, en, wav = feats_of([MAN, MAN, WOMAN, WOMAN, WOMAN, MAN, MAN])
    feats.insert(3, speakers.LineFeat())                   # a cough between two lines of the woman (time: right after line 2)
    st.insert(3, en[2] + 0.1)
    en.insert(3, en[2] + 0.5)
    det = speakers.group_lines(feats, st, en)
    c.check(det.lines[3]["char"] == det.lines[2]["char"] and det.lines[3]["gender"] == "female", "a line without sound takes the character of the line before it", str(det.lines[3]))
    feats2 = [speakers.LineFeat()] + feats[:3]
    det = speakers.group_lines(feats2, [0.0] + [x + 3 for x in st[:3]], [0.5] + [x + 3 for x in en[:3]])
    c.check(det.lines[0]["char"] is not None, "…or of the line after it, when it is the first line")

    # ---- the voice that is on the boundary between men and women is ONE person, decided by all of its lines
    mid = (165, 1.1)
    feats, st, en, wav = feats_of([mid] * 10)
    det = speakers.group_lines(feats, st, en)
    c.check(len(det.characters) == 1 and len({x["gender"] for x in det.lines}) == 1, "a voice right on the boundary (165 Hz): ONE character, one gender for all its lines", str(det.characters))

    # ---- analyze(): the real thing, from a file
    who = [MAN, WOMAN, MAN, WOMAN, WOMAN, MAN]
    feats, st, en, wav = feats_of(who)
    wp = FX / "dialog_units.wav"
    write_wav(wav, wp)
    seen, calls = [], []
    det = speakers.analyze(wp, st, en, progress=seen.append, check=lambda: calls.append(1))
    c.check([x["gender"] for x in det.lines] == [gender_of_who(w) for w in who] and len(det.characters) == 2, "analyze(): from a WAV file, every line has the right gender", str([x["gender"] for x in det.lines]))
    c.check(seen and abs(seen[-1] - 1.0) < 1e-9 and calls and abs(det.duration - len(wav) / SR) < 0.05, "…reports progress up to 1 and checks for cancel; knows the duration")
    class Stop(Exception):
        pass

    def stop():
        raise Stop()
    try:
        speakers.analyze(wp, st, en, check=stop)
        c.check(False, "analyze(): the cancel check can stop it")
    except Stop:
        c.check(True, "analyze(): the cancel check can stop it")
    det = speakers.analyze(wp, st + [len(wav) / SR + 5.0, 2.0], en + [len(wav) / SR + 9.0, 2.0])
    c.check(len(det.lines) == len(who) + 2 and det.lines[-1]["char"] is not None, "analyze(): lines after the end of the sound / of zero length do no harm")
    mp4 = FX / "dialog_units.mp4"
    subprocess.run([audio.ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=160x90:r=5:d={len(wav) / SR + 1:.1f}", "-i", str(wp), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(mp4)], check=True)
    det = speakers.analyze(mp4, st, en)
    c.check([x["gender"] for x in det.lines] == [gender_of_who(w) for w in who], "analyze(): the sound of an MP4 video works the same (AAC)")

    # ---- the gender of a short voice sample (My voices)
    write_wav(say(MAN, 9, 5), FX / "man.wav")
    write_wav(say(WOMAN, 9, 6), FX / "woman.wav")
    write_wav((np.random.default_rng(3).standard_normal(8 * SR) * 0.1).astype(np.float32), FX / "noise.wav")
    write_wav(say((165, 1.1), 9, 7), FX / "mid.wav")
    g1, g2 = speakers.gender_of_clip(FX / "man.wav"), speakers.gender_of_clip(FX / "woman.wav")
    c.check(g1 and g1["gender"] == "Male" and g1["sure"] and g2 and g2["gender"] == "Female" and g2["sure"], "gender_of_clip: a man / a woman, and it is sure", f"{g1} {g2}")
    c.check(speakers.gender_of_clip(FX / "noise.wav") is None, "gender_of_clip: noise -> None")
    gm = speakers.gender_of_clip(FX / "mid.wav")
    c.check(gm is not None and not gm["sure"], "gender_of_clip: a voice on the boundary is not 'sure'", str(gm))

    # ---- autovoice: which voice a character gets
    ch = lambda i, g, f0, ref=True, **k: {"id": i, "gender": g, "f0": f0, "voice": "", "ref": [[1.0, 4.0]] if ref else [], **k}  # noqa: E731
    two = [ch(1, "male", 120), ch(2, "female", 210)]
    c.check(autovoice.plan(two, "edge") == {1: "km-KH-PisethNeural", 2: "km-KH-SreymomNeural"}, "Edge: men -> Piseth, women -> Srey Mom")
    c.check(autovoice.plan([ch(1, "male", 120), ch(2, "male", 160), ch(3, "female", 190)], "edge") == {1: "km-KH-PisethNeural", 2: "km-KH-PisethNeural", 3: "km-KH-SreymomNeural"},
            "Edge: every man has the one male voice, every woman the one female voice")
    c.check(autovoice.plan(two, "voxcpm") == {1: "vox:p:m_deep", 2: "vox:p:f_warm"}, "VoxCPM2: one man -> the deep designed voice, one woman -> the warm one")
    p3 = autovoice.plan([ch(1, "male", 155), ch(2, "male", 100), ch(3, "male", 125)], "voxcpm")
    c.check(len(set(p3.values())) == 3 and p3[2] == "vox:p:m_deep" and p3[1] == "vox:p:m_young" and all(autovoice.valid_row_voice(v) for v in p3.values()),
            "VoxCPM2: three men get three different designed voices, the lowest pitch the deepest", str(p3))
    p2 = autovoice.plan([ch(1, "female", 190), ch(2, "female", 200), ch(3, "female", 260)], "voxcpm")
    c.check(p2[1] == p2[2] and p2[3] != p2[1], "…but two characters whose pitch is within 3 semitones share one voice (they may be one person)", str(p2))
    c.check(autovoice.plan([ch(1, "male", 120, voice="km-KH-SreymomNeural"), ch(2, "female", 210)], "edge")[1] == "km-KH-SreymomNeural", "a voice chosen for the character wins over the automatic one")
    c.check(autovoice.plan(two, "voxcpm", male="km-KH-PisethNeural", female="vox:p:f_calm") == {1: "km-KH-PisethNeural", 2: "vox:p:f_calm"}, "the male / female pickers of the settings are used for every character of that gender")
    c.check(autovoice.plan(two, "edge", male="vox:s", female="vox:s") == {1: "vox:s:1", 2: "vox:s:2"} and autovoice.plan([ch(4, "male", 1, voice="vox:s")], "edge") == {4: "vox:s:4"},
            "'clone' = every character gets a copy of its own voice (vox:s:<character>)")
    cust = [{"id": "vox:c:aaaaaaaa", "gender": "Male"}, {"id": "vox:c:bbbbbbbb", "gender": "Female"}, {"id": "vox:c:cccccccc", "gender": ""}]
    c.check(autovoice.plan(two, "voxcpm", male="vox:mine", female="vox:mine", custom=cust) == {1: "vox:c:aaaaaaaa", 2: "vox:c:bbbbbbbb"}, "'My voices of this gender': the saved voice of the right gender (a voice without gender is not used)")
    c.check(autovoice.plan(two, "voxcpm", male="vox:mine", custom=[]) == {1: "vox:p:m_deep", 2: "vox:p:f_warm"}, "…and the designed voice when there is none")
    # VoxCPM2: what the user chose for the job is respected
    c.check(autovoice.plan(two, "voxcpm", job_voice="vox:original") == {1: "vox:s:1", 2: "vox:s:2"}, "VoxCPM2 + 'Speaker in the video': every character is cloned from its OWN lines (vox:s:<n>)")
    c.check(autovoice.plan([ch(1, "male", 120), ch(2, "female", 210, ref=False)], "voxcpm", job_voice="vox:original") == {1: "vox:s:1", 2: ""},
            "…a character without a clear line of its own has nothing to copy: it keeps the voice of the job ('')")
    c.check(autovoice.plan(two, "voxcpm", job_voice="vox:p:f_calm", job_gender="female") == {1: "vox:p:m_deep", 2: "vox:p:f_calm"}, "a designed woman's voice chosen for the job: the women keep it, the men get a designed voice")
    c.check(autovoice.plan([ch(1, "male", 100), ch(2, "male", 150), ch(3, "female", 210)], "voxcpm", job_voice="vox:p:m_deep", job_gender="male")
            == {1: "vox:p:m_deep", 2: "vox:p:m_deep", 3: "vox:p:f_warm"}, "…a designed man's voice: every man keeps it (it was chosen), the woman gets f_warm")
    c.check(autovoice.plan(two, "voxcpm", job_voice="vox:c:aaaaaaaa", job_gender="") == {1: "vox:c:aaaaaaaa", 2: "vox:c:aaaaaaaa"}, "a saved voice of no known gender chosen for the job: everybody keeps it")
    c.check(autovoice.plan(two, "voxcpm", job_voice="vox:c:aaaaaaaa", job_gender="male") == {1: "vox:c:aaaaaaaa", 2: "vox:p:f_warm"}, "…of a known gender: only that gender keeps it")
    c.check(autovoice.plan(two, "voxcpm", female="vox:p:f_calm", job_voice="vox:original") == {1: "vox:s:1", 2: "vox:p:f_calm"}, "a picker of the settings wins over the job's voice")
    c.check(autovoice.plan([ch(1, "male", 120, ref=False)], "voxcpm", male="vox:s", job_voice="vox:p:f_warm", job_gender="female") == {1: "vox:p:m_deep"}
            and autovoice.plan([ch(1, "male", 120, ref=False)], "edge", male="vox:s") == {1: "km-KH-PisethNeural"}, "'clone' for a character that has nothing to copy: the automatic voice instead (a job must not fail for that)")
    c.check(autovoice.plan(two, "edge", job_voice="vox:original") == {1: "km-KH-PisethNeural", 2: "km-KH-SreymomNeural"}, "the job's VoxCPM2 voice means nothing when the engine is Edge")
    c.check(autovoice.plan(two, "edge", male="nonsense", female="vox:p:nope") == {1: "km-KH-PisethNeural", 2: "km-KH-SreymomNeural"}, "an unknown voice in a picker is ignored")
    c.check(autovoice.plan(None) == {} and autovoice.plan([]) == {} and autovoice.plan([{"id": 1, "gender": "x"}, {"gender": "male"}, "no"]) == {}, "no characters / damaged characters: no plan, no crash")
    c.check(autovoice.line_voice({"char": 2}, {1: "a", 2: "b"}) == "b" and autovoice.line_voice({"char": 9}, {1: "a"}) is None and autovoice.line_voice({}, {1: "a"}) is None
            and autovoice.line_voice({"char": True}, {1: "a"}) is None, "line_voice: the voice of the line's character, else None")
    ok = ["vox:s:1", "vox:s:12", "vox:s:99", "km-KH-PisethNeural", "vox:p:m_deep"]
    bad = ["vox:s:0", "vox:s:100", "vox:s:", "vox:s:a", "vox:s:01", "vox:s:1 ", "vox:mine", "vox:s"]
    c.check(all(autovoice.valid_row_voice(v) for v in ok) and not any(autovoice.valid_row_voice(v) for v in bad), "valid_row_voice accepts vox:s:<1-99>, nothing else new", str([v for v in bad if autovoice.valid_row_voice(v)]))
    c.check(autovoice.valid_choice("vox:s") and autovoice.valid_choice("") and autovoice.valid_choice(None) and not autovoice.valid_choice("vox:mine") and autovoice.valid_choice("vox:mine", mine=True)
            and not autovoice.valid_choice(5) and not autovoice.valid_choice("x"), "valid_choice: '' / a voice / clone; 'My voices' only for the two pickers")

    # ---- the edits of the characters panel
    chars = [{"id": 1, "gender": "male", "name": "", "voice": ""}, {"id": 2, "gender": "female", "name": "", "voice": ""}]
    ce = autovoice.clean_character_edits
    r = ce(chars, [{"id": 1, "gender": "female", "voice": "vox:s", "name": "  Sok   Dara  "}, {"id": "2", "voice": None}])
    c.check(r == [{"id": 1, "gender": "female", "voice": "vox:s", "name": "Sok Dara"}, {"id": 2, "voice": ""}], "clean_character_edits: only the sent fields, names tidied, null = automatic", str(r))
    c.check(ce(chars, None) == [] and ce(chars, []) == [] and ce(chars, [{"id": 1, "name": "ក" * 99}])[0]["name"] == "ក" * 40, "…no edits -> nothing; a name is cut at 40 characters")
    for bad_e, why in (([{"id": 9}], "an unknown character"), ([{"id": 1, "gender": "robot"}], "a gender that is not male / female"), ([{"id": 1, "voice": "vox:p:nope"}], "an unknown voice"),
                       ([{"id": 1}, {"id": 1}], "the same character twice"), ([{"gender": "male"}], "no id"), ([{"id": "x"}], "an id that is not a number"), ("no", "not a list"),
                       ([{"id": 1, "name": 5}], "a name that is not text")):
        try:
            ce(chars, bad_e)
            c.check(False, f"clean_character_edits rejects {why}")
        except ValueError:
            c.check(True, f"clean_character_edits rejects {why}")
    autovoice.apply_character_edits(chars, ce(chars, [{"id": 1, "gender": "female", "name": "Anna", "voice": "km-KH-PisethNeural"}, {"id": 2, "gender": "female"}]))
    c.check(chars[0]["gender"] == "female" and chars[0]["gender_set"] and chars[0]["name"] == "Anna" and chars[0]["voice"] == "km-KH-PisethNeural" and "gender_set" not in chars[1],
            "apply_character_edits: a flipped gender is marked as the user's decision; an unchanged one is not", str(chars))

    # ---- the settings and the per-line rule
    v = VoiceSettings.from_dict({"auto": {"on": True, "male": "vox:mine", "female": "bad"}})
    c.check(v.auto and v.auto_male == "vox:mine" and v.auto_female == "" and not VoiceSettings.from_dict({}).auto and not VoiceSettings.from_dict({"auto": "yes"}).auto and not VoiceSettings.from_dict({"auto": {"on": 0}}).auto,
            "VoiceSettings: the by-character settings are read and cleaned (off by default)")
    c.check(VoiceSettings.from_dict({"auto": {"on": True}}).auto and VoiceSettings().auto is False, "…the object itself is off, the dashboard turns it on")
    ctx = pipeline.AudioCtx(vs=VoiceSettings(), readings={})
    segs = [{"idx": 0, "char": 1}, {"idx": 1, "char": 2}, {"idx": 2, "char": 2, "voice": "km-KH-PisethNeural"}, {"idx": 3}, {"idx": 4, "char": 7}]
    vs_ = pipeline._row_voices(segs, ctx, {1: "km-KH-PisethNeural", 2: "vox:p:f_warm"})
    c.check([x.engine for x in vs_] == ["edge", "voxcpm", "edge", "edge", "edge"] and vs_[0].voice == "km-KH-PisethNeural" and vs_[1].vox_id == "vox:p:f_warm" and vs_[2].voice == "km-KH-PisethNeural"
            and vs_[3].voice == "km-KH-SreymomNeural" and vs_[4].voice == "km-KH-SreymomNeural", "a line's voice: its own choice > its character's voice > the voice of the job", str([(x.engine, x.voice, x.vox_id) for x in vs_]))
    c.check([x.voice for x in pipeline._row_voices(segs[:2] + segs[3:], ctx)] == ["km-KH-SreymomNeural"] * 4 and pipeline._row_voices(segs[2:3], ctx)[0].voice == "km-KH-PisethNeural",
            "…and without a plan every line has the voice of the job (a line's own choice still wins)")

# =============================================================================================================== B. API
srv = None
SRT_LINES = ["Welcome back to the show, and thank you for joining us today.", "Thanks for having me, it is a pleasure to be here.", "Let us start with the basics of the new dashboard.",
             "Sure, the first thing to know is how the data is collected.", "And then we clean it before anything else happens.", "That is a very important step that many people skip.",
             "Exactly, and it saves a lot of time later on.", "Can you show us an example of that in practice?", "Of course, here is a small example with a real file.",
             "That looks simple enough, I think everyone can follow it.", "We will put the files in the description below the video.", "Thank you all for watching, and see you next time."]
WHO12 = [MAN, WOMAN, MAN, WOMAN, WOMAN, MAN, MAN, WOMAN, MAN, WOMAN, WOMAN, MAN]
KM_LINES = [f"នេះគឺជាឃ្លាទី {i + 1} សម្រាប់ការសាកល្បង។" for i in range(12)]


def srt_of(st, en, lines):
    def ts(t):
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round((t % 1) * 1000)) % 1000:03d}"
    return "\n".join(f"{i + 1}\n{ts(a)} --> {ts(b)}\n{x}\n" for i, (a, b, x) in enumerate(zip(st, en, lines)))


def b64(p):
    return base64.b64encode(p.read_bytes()).decode()


if "B" in ONLY or "C" in ONLY:
    feats12, ST12, EN12, wav12 = feats_of(WHO12, dur=3.0)
    DIALOG = FX / "dialog.wav"
    write_wav(wav12, DIALOG)
    SRT12 = srt_of(ST12, EN12, SRT_LINES)
    (FX / "dialog.srt").write_text(SRT12, encoding="utf-8")                         # (smoke_zip.py dubs this dialogue from the built zip)
    NOISE = FX / "noise_only.wav"
    write_wav((np.random.default_rng(9).standard_normal(20 * SR) * 0.1).astype(np.float32), NOISE)
    SRT_NOISE = srt_of([1, 5, 9, 13, 17], [4, 8, 12, 16, 19.5], SRT_LINES[:5])
    SILENT_MP4 = FX / "silent.mp4"
    subprocess.run([audio.ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=5", "-t", "14", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(SILENT_MP4)], check=True)
    SRT_SILENT = srt_of([1, 5, 9], [4, 8, 12], SRT_LINES[:3])
    write_wav(say(MAN, 9, 31), FX / "clip_man.wav")
    write_wav(say(WOMAN, 9, 32), FX / "clip_woman.wav")

    data = WORK / "data_speakers"
    shutil.rmtree(data, ignore_errors=True)
    (data / "jobs").mkdir(parents=True)
    srv = Server(8073, data, make_stub_home(WORK / "voxhome_speakers"), name="speakers").start()
    atexit.register(srv.stop)                       # a crashed run must not leave a server behind (the next run would talk to it)

    def upload(path, name=None):
        r = srv.api("POST", "/api/uploads", params={"name": name or path.name}, content=path.read_bytes(), timeout=120)
        assert r.status_code == 200, r.text
        return r.json()

    def jobdir(jid):
        return data / "jobs" / jid

    def make_job(up=None, text="", auto=True, engine="manual", kind="upload", voice_extra=None, title="t"):
        src = ({"type": "upload", "upload_id": up["id"], "text": text, "lang": "en", "subs": "auto"} if kind == "upload" else {"type": "transcript", "text": text, "lang": "en", "title": title})
        vb = {"id": "km-KH-SreymomNeural", "engine": "edge", "auto": {"on": auto, "male": "", "female": ""}}
        vb.update(voice_extra or {})
        body = {"source": src, "translate": {"engine": engine}, "voice": vb, "output": {"sync": "fit", "video": False}}
        r = srv.api("POST", "/api/jobs/dub", json=body)
        assert r.status_code == 200, r.text
        return srv.wait_job(r.json()["id"], 240)

    def regen(jid, voice=None, segments=None, characters=None, timeout=240):
        body = {"voice": voice or {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:p:f_warm", "quality": "fast", "consent": False}, "auto": {"on": True, "male": "", "female": ""}}}
        if segments is not None:
            body["segments"] = segments
        if characters is not None:
            body["characters"] = characters
        r = srv.api("POST", f"/api/jobs/{jid}/regenerate", json=body)
        if r.status_code != 200:
            return r
        return srv.wait_job(jid, timeout)

    def vox_voice(**kw):
        d = {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:p:f_warm", "quality": "fast", "consent": False}, "auto": {"on": True, "male": "", "female": ""}}
        for k, v in kw.items():
            if k == "vox":
                d["vox"].update(v)
            elif k == "auto":
                d["auto"].update(v)
            else:
                d[k] = v
        return d

if "B" in ONLY:
    # ---- A dialogue is uploaded; the app listens; (copy / paste mode stops after the subtitles, so there is no translation and no network)
    up = upload(DIALOG)
    c.check(up["has_audio"] and not up["has_video"], "upload: a WAV with sound (no picture)")
    job = make_job(up, SRT12)
    JID = job["id"]
    c.check(job["status"] == "done" and job["meta"].get("draft"), "an upload job with the subtitles typed in: done (a copy / paste draft)", str(job.get("error")))
    keys = [s["key"] for s in job["steps"]]
    c.check(keys == ["transcript", "speakers", "translate", "tts", "mix", "video"], "the dubbing job has a 'speakers' step after the transcript", str(keys))
    sp = next(s for s in job["steps"] if s["key"] == "speakers")
    c.check(sp["status"] == "done" and "2 characters" in sp["detail"] and "1 male, 1 female" in sp["detail"], "…it found 2 characters: 1 male, 1 female", sp["detail"])
    chars = job["meta"].get("characters") or []
    c.check(len(chars) == 2 and {x["gender"] for x in chars} == {"male", "female"}, "meta.characters: a man and a woman", str(chars))
    c.check(all(x["lines"] == 6 and x["name"] == "" and x["voice"] == "" and isinstance(x["ref"], list) and x["ref"] and x["f0"] for x in chars), "…6 lines each, no name, automatic voice, a voice reference, the pitch", str(chars))
    byid = {x["id"]: x for x in chars}
    got = [(byid[s["char"]]["gender"] if s.get("char") else None) for s in job["segments"]]
    c.check(got == [gender_of_who(w) for w in WHO12], "every line has `char`: the right gender for all 12 lines", str(got))
    c.check(all(isinstance(s.get("gp"), float) for s in job["segments"]) and all((s["gp"] > 0.5) == (byid[s["char"]]["gender"] == "female") for s in job["segments"]), "…and `gp` (how sure): on the side of its gender")
    c.check(job["meta"]["speakers"]["state"] == "ok" and job["meta"]["speakers"]["coverage"] > 0.9 and job["meta"]["speakers"]["n"] == 2, "meta.speakers: ok, coverage, count", str(job["meta"]["speakers"]))
    c.check(any("Characters:" in x for x in job["logs"]), "the log says what was found")

    # ---- the voices (VoxCPM2 stub): men -> the deep designed voice, women -> the warm one
    seg_km = [{"idx": i, "km": KM_LINES[i]} for i in range(12)]
    j = regen(JID, vox_voice(), seg_km)
    cm = {x["gender"]: x["id"] for x in j["meta"]["characters"]}
    c.check(j["status"] == "done" and j["meta"].get("char_voices") == {str(cm["male"]): "vox:p:m_deep", str(cm["female"]): "vox:p:f_warm"}, "VoxCPM2 + voices by character: meta.char_voices = man -> m_deep, woman -> f_warm", str(j["meta"].get("char_voices")) + str(j.get("error")))
    c.check(sorted((j["meta"].get("vox") or {}).get("voices", [])) == ["vox:p:f_warm", "vox:p:m_deep"] and "dub.mp3" in j["outputs"] and not j["meta"].get("draft"), "…both designed voices were used, the dub exists", str((j["meta"].get("vox") or {}).get("voices")))
    c.check(any("Voices by character:" in x for x in j["logs"]), "…and the log names the voice of every character")
    # voices by character OFF: one voice for the whole job
    j = regen(JID, vox_voice(auto={"on": False}))
    c.check(j["status"] == "done" and "char_voices" not in j["meta"] and (j["meta"].get("vox") or {}).get("voices") == ["vox:p:f_warm"], "switched off: every line has the voice of the job (no char_voices)", str((j["meta"].get("vox") or {}).get("voices")))
    # the user flips the gender of the man (it is a woman after all) and names her
    mid_ = cm["male"]
    j = regen(JID, vox_voice(vox={"id": "vox:p:m_deep"}), characters=[{"id": mid_, "gender": "female", "name": "  Sok  "}])
    flipped = next(x for x in j["meta"]["characters"] if x["id"] == mid_)
    c.check(flipped["gender"] == "female" and flipped["gender_set"] is True and flipped["name"] == "Sok", "a flipped gender and a name are kept in the job (marked as the user's decision)", str(flipped))
    cv = j["meta"]["char_voices"]
    c.check(cv[str(mid_)] == "vox:p:f_warm" and cv[str(cm["female"])] == "vox:p:f_bright", "…both are women now and the job's voice is a man's: the lower-pitched woman gets f_warm, the higher one f_bright", str(cv))
    j = regen(JID, vox_voice())
    cv = j["meta"]["char_voices"]
    c.check(cv[str(mid_)] == "vox:p:f_warm" and cv[str(cm["female"])] == "vox:p:f_warm", "…with a woman's designed voice chosen for the job (f_warm) both women keep it - what the user chose is respected", str(cv))
    # a voice chosen for ONE LINE wins over the character; a voice for the CHARACTER wins over the automatic one
    j = regen(JID, vox_voice(), segments=[{"idx": 0, "voice": "vox:p:m_anchor"}], characters=[{"id": cm["female"], "voice": "vox:p:f_calm"}, {"id": mid_, "gender": "male", "name": ""}])
    used = sorted((j["meta"].get("vox") or {}).get("voices", []))
    c.check(j["status"] == "done" and used == ["vox:p:f_calm", "vox:p:m_anchor", "vox:p:m_deep"], "a line's own voice (m_anchor) and a character's chosen voice (f_calm) are used; the other character stays automatic (m_deep)", str(used))
    c.check(j["meta"]["char_voices"][str(cm["female"])] == "vox:p:f_calm" and next(x for x in j["meta"]["characters"] if x["id"] == mid_)["gender"] == "male", "…and flipping back works")
    j = regen(JID, vox_voice(), segments=[{"idx": 0, "voice": None}], characters=[{"id": cm["female"], "voice": ""}])
    c.check(sorted((j["meta"].get("vox") or {}).get("voices", [])) == ["vox:p:f_warm", "vox:p:m_deep"], "null / '' = automatic again")
    # clone every character from the video (needs the permission tick)
    j = regen(JID, vox_voice(auto={"male": "vox:s", "female": "vox:s"}))
    c.check(j["status"] == "error" and (j.get("error") or {}).get("code") == "VOX_CONSENT_REQUIRED", "cloning the characters' own voices needs the permission tick (VOX_CONSENT_REQUIRED)", str(j.get("error")))
    j = regen(JID, vox_voice(vox={"consent": True}, auto={"male": "vox:s", "female": "vox:s"}))
    clones = sorted((j["meta"].get("vox") or {}).get("voices", []))
    refs = sorted(jobdir(JID).glob("voice_ref_c*.wav"))
    c.check(j["status"] == "done" and clones == [f"vox:s:{i}" for i in sorted(cm.values())] and len(refs) == 2, "clone: every character is spoken with its own voice (vox:s:<n>), a reference clip per character", f"{clones} {refs} {j.get('error')}")
    c.check(sorted(k for k in j["outputs"] if k.startswith("voice_ref")) == [f"voice_ref_c{i}.wav" for i in sorted(cm.values())], "…the samples that were copied are job outputs (voice_ref_c<n>.wav) - the page lets the user listen to them", str(list(j["outputs"])))
    rf = srv.api("GET", f"/api/jobs/{JID}/file/voice_ref_c{min(cm.values())}.wav")
    c.check(rf.status_code == 200 and "audio/wav" in rf.headers["content-type"] and len(rf.content) > 20000, "…and can be downloaded", f"{rf.status_code} {len(rf.content)}")
    rf = srv.api("GET", f"/api/jobs/{JID}/file/voice_ref_c{min(cm.values())}.wav", params={"download": 1})
    c.check(rf.status_code == 200 and "_voice_ref_c" in rf.headers.get("content-disposition", ""), "…with a file name for the download", rf.headers.get("content-disposition", ""))
    for bad_name in ("voice_ref_c0.wav", "voice_ref_c9.wav", "voice_ref_c100.wav", "voice_ref_c1.mp3", "voice_ref_cx.wav", "voice_ref_c01.wav"):
        c.check(srv.api("GET", f"/api/jobs/{JID}/file/{bad_name}").status_code == 404, f"/file/{bad_name} -> 404 (not an output of this job / not a valid name)")
    dur = [audio.probe_media(r)["duration"] for r in refs]
    c.check(all(3.0 <= d <= 20.5 for d in dur), "…each reference is 3-20 s of that character's clearest lines", str(dur))
    st_ref = [r.stat().st_mtime_ns for r in refs]
    j = regen(JID, vox_voice(vox={"consent": True}, auto={"male": "vox:s", "female": "vox:s"}))
    c.check([r.stat().st_mtime_ns for r in sorted(jobdir(JID).glob("voice_ref_c*.wav"))] == st_ref, "…the reference clips are made once and reused")
    # 'Speaker in the video' as the job's voice: every character is cloned from its own lines
    j = regen(JID, vox_voice(vox={"id": "vox:original", "consent": False}))
    c.check(j["status"] == "error" and (j.get("error") or {}).get("code") == "VOX_CONSENT_REQUIRED", "'Speaker in the video' + voices by character: still needs the permission tick", str(j.get("error")))
    j = regen(JID, vox_voice(vox={"id": "vox:original", "consent": True}))
    c.check(j["status"] == "done" and sorted((j["meta"].get("vox") or {}).get("voices", [])) == [f"vox:s:{i}" for i in sorted(cm.values())] and "voice_ref.wav" not in j["outputs"]
            and j["meta"]["char_voices"] == {str(i): f"vox:s:{i}" for i in cm.values()}, "'Speaker in the video' as the job's voice: each character is spoken with its OWN voice (vox:s:<n>), not one voice for everybody", str(j["meta"].get("char_voices")) + str(j.get("error")))
    j = regen(JID, vox_voice(vox={"id": "vox:original", "consent": True}, auto={"on": False}))
    c.check(j["status"] == "done" and "voice_ref.wav" in j["outputs"] and not any(k.startswith("voice_ref_c") for k in j["outputs"]) and (j["meta"].get("vox") or {}).get("voices") == ["vox:original"],
            "…with voices by character OFF it is the old behaviour: one sample of the speaker (voice_ref.wav), one voice", str(list(j["outputs"])))
    j = regen(JID, vox_voice(vox={"consent": True}), segments=[{"idx": 1, "voice": "vox:s:9"}])
    c.check(j["status"] == "error" and (j.get("error") or {}).get("code") == "VOX_NO_REF", "a clone of a character that does not exist -> VOX_NO_REF", str(j.get("error")))
    j = regen(JID, vox_voice(), segments=[{"idx": 1, "voice": None}])

    # ---- the checks of the request
    for body, label in (({"characters": [{"id": 99, "gender": "male"}]}, "an unknown character"), ({"characters": [{"id": 1, "gender": "robot"}]}, "a gender that is not male / female"),
                        ({"characters": [{"id": 1, "voice": "vox:p:nope"}]}, "an unknown voice"), ({"characters": [{"id": 1}, {"id": 1}]}, "the same character twice"),
                        ({"characters": "no"}, "characters that are not a list"), ({"segments": [{"idx": 0, "voice": "vox:s:0"}]}, "a line voice vox:s:0")):
        r = srv.api("POST", f"/api/jobs/{JID}/regenerate", json=body)
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "BAD_REQUEST", f"regenerate with {label} -> 400 BAD_REQUEST", r.text[:120])
    c.check(srv.api("GET", f"/api/jobs/{JID}").json()["status"] == "done", "…and the job is untouched")

    # ---- detect again (a job that exists)
    before = srv.api("GET", f"/api/jobs/{JID}").json()
    r = srv.api("POST", f"/api/jobs/{JID}/speakers", json={})
    c.check(r.status_code == 200 and r.json()["id"] == JID, "POST /api/jobs/<id>/speakers starts a new search")
    j = srv.wait_job(JID, 120)
    c.check(j["status"] == "done" and len(j["meta"]["characters"]) == 2 and [s.get("char") for s in j["segments"]] == [s.get("char") for s in before["segments"]]
            and [s["km"] for s in j["segments"]] == [s["km"] for s in before["segments"]] and "dub.mp3" in j["outputs"], "…the job is done again with the same characters; the text and the audio are untouched")
    c.check(next(s for s in j["steps"] if s["key"] == "speakers")["status"] == "done", "…the 'speakers' step shows done")
    c.check(srv.api("POST", "/api/jobs/nope/speakers", json={}).status_code == 404, "unknown job -> 404")
    tts_job = srv.api("POST", "/api/jobs/tts", json={"text": "សួស្តី", "voice": {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:p:f_warm", "quality": "fast"}}, "input_lang": "km"}).json()["id"]
    srv.wait_job(tts_job, 120)
    r = srv.api("POST", f"/api/jobs/{tts_job}/speakers", json={})
    c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NOT_DUB", "a text-to-speech job has no characters -> 400 NOT_DUB")

    # ---- other kinds of sources
    tr = make_job(text="1\n00:00:01,000 --> 00:00:04,000\nHello there and welcome.\n\n2\n00:00:05,000 --> 00:00:08,000\nThis is the second line.\n", kind="transcript")
    c.check(tr["status"] == "done" and tr["meta"]["speakers"]["state"] == "no_audio" and "characters" not in tr["meta"] and next(s for s in tr["steps"] if s["key"] == "speakers")["status"] == "skipped" and not tr["warnings"],
            "a pasted transcript has no sound: the step is skipped, no characters, no warning, the job goes on", str(tr["meta"].get("speakers")) + str(tr["warnings"]))
    r = srv.api("POST", f"/api/jobs/{tr['id']}/speakers", json={})
    c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NO_AUDIO_SOURCE", "…and 'detect' on it -> 400 NO_AUDIO_SOURCE", r.text[:120])
    tr2 = make_job(text="Hello there and welcome.\n\nThis is a plain text without any time.\n", kind="transcript")
    c.check(tr2["status"] == "done" and tr2["meta"]["speakers"]["state"] == "untimed" and next(s for s in tr2["steps"] if s["key"] == "speakers")["detail"] == "no timing", "text without timestamps: skipped ('no timing')", str(tr2["meta"].get("speakers")))
    r = srv.api("POST", f"/api/jobs/{tr2['id']}/speakers", json={})
    c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NO_TIMING", "…and 'detect' on it -> 400 NO_TIMING")
    sup = upload(SILENT_MP4)
    sj = make_job(sup, SRT_SILENT)
    c.check(sj["status"] == "done" and sj["meta"]["speakers"]["state"] == "no_audio" and "characters" not in sj["meta"], "a video without sound: no characters, the job goes on", str(sj["meta"].get("speakers")))
    r = srv.api("POST", f"/api/jobs/{sj['id']}/speakers", json={})
    c.check(r.status_code == 400 and r.json()["detail"]["code"] == "NO_AUDIO", "…and 'detect' on it -> 400 NO_AUDIO", r.text[:120])
    nup = upload(NOISE)
    nj = make_job(nup, SRT_NOISE)
    c.check(nj["status"] == "done" and nj["meta"]["speakers"]["state"] == "unsure" and any(w["code"] == "SPEAKERS_UNSURE" for w in nj["warnings"]) and "characters" not in nj["meta"]
            and all("char" not in s for s in nj["segments"]), "noise only: 'unsure' + a warning, no characters, no guess (the job keeps the chosen voice)", str(nj["meta"].get("speakers")) + str(nj["warnings"]))
    r = srv.api("POST", f"/api/jobs/{nj['id']}/speakers", json={})
    nj2 = srv.wait_job(nj["id"], 60)
    c.check(r.status_code == 200 and nj2["status"] == "done" and nj2["meta"]["speakers"]["state"] == "unsure" and sum(1 for w in nj2["warnings"] if w["code"] == "SPEAKERS_UNSURE") == 1,
            "detect again on noise: still unsure, one warning (the old one is replaced)", str(nj2["warnings"]))
    off = make_job(srv.api("POST", "/api/uploads", params={"name": "dialog2.wav"}, content=DIALOG.read_bytes()).json(), SRT12, auto=False)
    c.check(off["status"] == "done" and off["meta"]["speakers"]["state"] == "off" and next(s for s in off["steps"] if s["key"] == "speakers")["detail"] == "off" and "characters" not in off["meta"]
            and all("char" not in s for s in off["segments"]), "switched off when the job was made: the step is skipped ('off'), no characters")
    r = srv.api("POST", f"/api/jobs/{off['id']}/speakers", json={})
    off2 = srv.wait_job(off["id"], 60)
    c.check(r.status_code == 200 and len(off2["meta"].get("characters") or []) == 2 and off2["meta"]["speakers"]["state"] == "ok" and next(s for s in off2["steps"] if s["key"] == "speakers")["status"] == "done",
            "…'Detect characters' later finds them (2) without making the job again")
    # a job made before this version: no 'speakers' step at all
    old = json.loads((jobdir(off["id"]) / "job.json").read_text())
    c.check(isinstance(old["meta"].get("characters"), list), "the characters are stored in job.json (they survive a restart)")

    # ---- My voices: the gender of a clip is found from the sound (nobody has to say it)
    r1 = srv.api("POST", "/api/vox/voices", json={"name": "Dara", "filename": "clip_man.wav", "data": b64(FX / "clip_man.wav")})
    r2 = srv.api("POST", "/api/vox/voices", json={"name": "Sophea", "filename": "clip_woman.wav", "data": b64(FX / "clip_woman.wav")})
    r3 = srv.api("POST", "/api/vox/voices", json={"name": "Said", "filename": "clip_man.wav", "data": b64(FX / "clip_man.wav"), "gender": "Female"})
    c.check(r1.json().get("gender") == "Male" and r2.json().get("gender") == "Female", "a saved voice: the gender is found from the sound (man -> Male, woman -> Female)", f"{r1.text[:120]} {r2.text[:120]}")
    c.check(r3.json().get("gender") == "Female", "…a gender that is sent is taken as it is")
    lst = {v["name"]: v for v in srv.api("GET", "/api/vox/voices").json()["custom"]}
    c.check(lst["Dara"]["gender"] == "Male" and lst["Sophea"]["gender"] == "Female" and lst["Said"]["gender"] == "Female", "GET /api/vox/voices lists the genders")
    meta_d = json.loads((data / "voices" / r1.json()["id"].split(":")[2] / "meta.json").read_text())
    c.check(meta_d["gender_auto"] is True and json.loads((data / "voices" / r3.json()["id"].split(":")[2] / "meta.json").read_text())["gender_auto"] is False, "…and the file says whether it was guessed (gender_auto)")
    cid_d = r1.json()["id"].split(":")[2]
    r = srv.api("PATCH", f"/api/vox/voices/{cid_d}", json={"gender": "Female"})
    c.check(r.status_code == 200 and r.json()["gender"] == "Female" and r.json()["name"] == "Dara", "PATCH {gender} changes the gender (the name stays)", r.text[:120])
    c.check(json.loads((data / "voices" / cid_d / "meta.json").read_text())["gender_auto"] is False, "…it is then the user's decision (gender_auto false)")
    r = srv.api("PATCH", f"/api/vox/voices/{cid_d}", json={"gender": ""})
    c.check(r.status_code == 200 and r.json()["gender"] == "", "PATCH {gender: ''} = not decided")
    r = srv.api("PATCH", f"/api/vox/voices/{cid_d}", json={"gender": "Male", "name": "Dara 2"})
    c.check(r.status_code == 200 and r.json()["gender"] == "Male" and r.json()["name"] == "Dara 2", "PATCH with a name AND a gender does both")
    for body, label in (({"gender": "robot"}, "a gender that is not Female / Male"), ({}, "nothing to change"), ({"gender": 5}, "a gender that is a number")):
        r = srv.api("PATCH", f"/api/vox/voices/{cid_d}", json=body)
        c.check(r.status_code == 400 and r.json()["detail"]["code"] == "BAD_REQUEST", f"PATCH with {label} -> 400", r.text[:120])
    c.check(srv.api("PATCH", "/api/vox/voices/ffffffff", json={"gender": "Male"}).status_code == 404, "PATCH {gender} of an unknown voice -> 404")
    # 'My voices of this gender' picks the saved voice of the right gender
    j = regen(JID, vox_voice(vox={"consent": True}, auto={"male": "vox:mine", "female": "vox:mine"}))
    ids = {v["name"]: v["id"] for v in srv.api("GET", "/api/vox/voices").json()["custom"]}
    cvv = j["meta"].get("char_voices") or {}
    c.check(j["status"] == "done" and cvv.get(str(cm["male"])) == ids["Dara 2"] and cvv.get(str(cm["female"])) in (ids["Sophea"], ids["Said"]),
            "'My voices of this gender': the man's lines use the saved man's voice, the woman's lines a saved woman's voice", str(cvv) + str(j.get("error")))

    # ---- one real round trip with Microsoft's Khmer voices (needs the Internet; skipped without it)
    j = regen(JID, {"id": "km-KH-SreymomNeural", "engine": "edge", "auto": {"on": True, "male": "", "female": ""}}, timeout=300)
    if j["status"] == "done":
        cv = j["meta"]["char_voices"]
        c.check(cv[str(cm["male"])] == "km-KH-PisethNeural" and cv[str(cm["female"])] == "km-KH-SreymomNeural", "Edge: the man's lines are Piseth, the woman's lines Srey Mom", str(cv))
        dub = jobdir(JID) / "dub.mp3"
        segs = [s for s in j["segments"] if s.get("out_start") is not None]
        det = speakers.analyze(dub, [s["out_start"] for s in segs], [s["out_end"] for s in segs])
        c.check(len(segs) == 12 and [x["gender"] for x in det.lines] == [gender_of_who(w) for w in WHO12], "…and the Khmer dub really sounds that way: a male voice on the man's 6 lines, a female voice on the woman's 6", str([x["gender"] for x in det.lines]))
        c.check(len(det.characters) == 2, "…two voices in the whole dub", str(det.characters))
    else:
        print(f"  (skipped the Edge round trip: {j.get('error')})", flush=True)

# =============================================================================================================== C. browser
if "C" in ONLY:
    from playwright.sync_api import sync_playwright  # noqa: E402

    SHOTS = WORK / "shots"
    if not any(v["name"] == "Sophea" for v in srv.api("GET", "/api/vox/voices").json()["custom"]):       # (part B makes it; a run of C alone needs it too)
        srv.api("POST", "/api/vox/voices", json={"name": "Sophea", "filename": "clip_woman.wav", "data": b64(FX / "clip_woman.wav")})
    # a fresh draft job with characters (made through the API, like a user would)
    upc = upload(DIALOG, "ui_dialog.wav")
    ujob = make_job(upc, SRT12)
    UID = ujob["id"]
    ujob = regen(UID, vox_voice(vox={"id": "vox:original", "consent": True}), [{"idx": i, "km": KM_LINES[i]} for i in range(12)])      # (a draft has no audio: a finished dub - the stub engine speaks it, every character with its own copied voice)
    assert ujob["status"] == "done" and "dub.mp3" in ujob["outputs"], str(ujob.get("error"))
    trjob = make_job(text="1\n00:00:01,000 --> 00:00:04,000\nHello there and welcome.\n\n2\n00:00:05,000 --> 00:00:08,000\nThis is the second line.\n", kind="transcript", title="UI transcript")
    TID = trjob["id"]
    errors = []
    bodies = []

    def mk_page(b, w=1280, h=1000, lang="en", extra=None):
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','dark');" + (extra or ""))
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        return pg

    def open_job(pg, jid):
        pg.goto(srv.url + "/#history")
        pg.wait_for_selector(f'[data-open="{jid}"]', timeout=10000)
        pg.click(f'[data-open="{jid}"]')
        pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
        pg.wait_for_timeout(300)

    def first_opt(pg, sel):
        return pg.evaluate("(s) => { const o = document.querySelector(s + ' option[value=\"\"]'); return o ? o.textContent.trim() : null; }", sel)

    with sync_playwright() as p:
        b = p.chromium.launch()
        # ---------------------------------------------------------------- the settings block
        pg = mk_page(b)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_selector(".autovoice-block [data-bind='voice.auto.on']", timeout=10000)
        pg.wait_for_timeout(500)
        c.check(pg.locator("#page-dub .autovoice-block").count() == 1 and pg.locator("#page-tts .autovoice-block").count() == 0, "the 'voices by character' block is on the Dubbing page only (the text-to-speech page has no characters)")
        c.check(pg.locator("#page-dub .autovoice-block input[data-bind='voice.auto.on']").is_checked(), "…it is ON by default")
        txt = pg.locator("#page-dub .autovoice-block").inner_text()
        c.check("Voices by character" in txt and "Voice for men" in txt and "Voice for women" in txt, "…with the explanation and the two pickers (men / women)", txt[:160])
        c.check(first_opt(pg, "#auto-male") == "Automatic (Piseth)" and first_opt(pg, "#auto-female") == "Automatic (Srey Mom)", "Microsoft voices: 'Automatic (Piseth)' for men, 'Automatic (Srey Mom)' for women", f"{first_opt(pg, '#auto-male')} / {first_opt(pg, '#auto-female')}")
        opts_m = pg.eval_on_selector("#auto-male", "s => [...s.options].map(o => o.textContent.trim())")
        opts_f = pg.eval_on_selector("#auto-female", "s => [...s.options].map(o => o.textContent.trim())")
        c.check(any("Piseth" in o for o in opts_m) and not any("Srey Mom" in o for o in opts_m) and any("Srey Mom" in o for o in opts_f) and not any("Piseth" in o for o in opts_f), "the men's picker lists male voices, the women's picker female voices")
        c.check(any("Clone every character" in o for o in opts_m) and any("My voices of this gender" in o for o in opts_f) and any("Wise elder" in o or "Deep narrator" in o for o in opts_m)
                and not any("Wise elder" in o or "Deep narrator" in o for o in opts_f), "…VoxCPM2 (installed here): designed voices of the right gender, 'My voices of this gender', 'Clone every character'")
        pg.click("#page-dub .engine-switch [data-value='voxcpm']")
        pg.wait_for_timeout(400)
        c.check("every character's own voice from the video" in (first_opt(pg, "#auto-male") or ""), "VoxCPM2 + 'Speaker in the video' (the default): 'Automatic (every character's own voice from the video)'", str(first_opt(pg, "#auto-male")))
        pg.click("#page-dub .voice-card.vox[data-voxvoice='vox:p:f_calm']")
        pg.wait_for_timeout(400)
        c.check("the voice you chose if it fits" in (first_opt(pg, "#auto-male") or ""), "…a designed voice chosen for the job: 'Automatic (the voice you chose if it fits · otherwise a designed voice)'", str(first_opt(pg, "#auto-male")))
        pg.click("#page-dub .voice-card.vox[data-voxvoice='vox:original']")
        pg.wait_for_timeout(300)
        pg.select_option("#auto-male", "vox:s")
        pg.wait_for_timeout(300)
        c.check(pg.locator("#page-dub [data-auto-consent]").is_visible() and pg.evaluate("JSON.parse(localStorage.getItem('kds_settings')).voice.auto.male") == "vox:s", "choosing 'clone' shows the permission tick, and the choice is saved")
        pg.select_option("#auto-male", "")
        pg.wait_for_timeout(300)
        c.check(not pg.locator("#page-dub [data-auto-consent]").is_visible(), "…it goes away with the choice")
        pg.click("#page-dub .engine-switch [data-value='edge']")
        pg.click("#page-dub .autovoice-block .switch")
        pg.wait_for_timeout(300)
        c.check(not pg.locator("#page-dub [data-auto-opts]").is_visible() and pg.evaluate("JSON.parse(localStorage.getItem('kds_settings')).voice.auto.on") is False, "the switch hides the pickers and is saved (off)")
        pg.reload()
        pg.wait_for_selector(".autovoice-block [data-bind='voice.auto.on']", timeout=10000)
        c.check(not pg.locator("#page-dub .autovoice-block input[data-bind='voice.auto.on']").is_checked(), "…it is still off after a reload")
        pg.click("#page-dub .autovoice-block .switch")
        pg.wait_for_timeout(300)
        c.check(pg.locator("#page-dub .autovoice-block input[data-bind='voice.auto.on']").is_checked(), "…and on again")
        pg.screenshot(path=str(SHOTS / "speakers_settings.png"))
        pg.close()

        # ---------------------------------------------------------------- the progress list
        pg = mk_page(b)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(500)
        pg.close()

        # ---------------------------------------------------------------- the finished job
        pg = mk_page(b)
        open_job(pg, UID)
        c.check(pg.locator("#chars-panel").is_visible() and pg.locator("#chars-panel .char-row").count() == 2, "an upload job: the Characters panel shows its 2 characters")
        c.check(pg.locator("#chars-sum").inner_text().startswith("2 character(s)") and "♂ 1" in pg.locator("#chars-sum").inner_text() and "♀ 1" in pg.locator("#chars-sum").inner_text(), "…'2 character(s) · ♂ 1 · ♀ 1'", pg.locator("#chars-sum").inner_text())
        badges = pg.eval_on_selector_all("#chars-panel .char-row .cb", "els => els.map(e => e.textContent)")
        c.check(sorted(x[0] for x in badges) == ["♀", "♂"], "…a ♂ and a ♀ badge", str(badges))
        c.check(pg.locator("#chars-panel #btn-detect").count() == 1 and "Detect again" in pg.locator("#chars-panel #btn-detect").inner_text(), "…with 'Detect again'")
        c.check(pg.locator("#dub-result .vox-ref audio").count() == 2 and pg.locator("#dub-result .vox-ref .vox-ref-char .cb").count() == 2, "a job whose characters were cloned lists the voice sample copied from each of them (a badge + a player)")
        c.check(pg.locator("#chars-panel .chars-head input[data-bind='voice.auto.on']").is_checked(), "…and the switch (on)")
        c.check(pg.locator(".seg-row .cb").count() == 12 and pg.locator(".seg-row[data-char]:not([data-char=''])").count() == 12, "every one of the 12 lines has a badge with its character")
        rows = pg.eval_on_selector_all(".seg-row", "els => els.map(e => ({ch: e.dataset.char, badge: e.querySelector('.cb').textContent, label: e.querySelector('.vsel option[value=\"\"]').textContent}))")
        cmap = {x["id"]: x["gender"] for x in srv.api("GET", f"/api/jobs/{UID}").json()["meta"]["characters"]}
        ok = all(r["badge"][0] == ("♀" if cmap[int(r["ch"])] == "female" else "♂") and r["label"] == ("Automatic — Srey Mom" if cmap[int(r["ch"])] == "female" else "Automatic — Piseth") for r in rows)
        c.check(ok, "…the badge shows its gender, and the first choice of its voice picker says what will really speak it: 'Automatic — Piseth' / 'Automatic — Srey Mom'", str(rows[:3]))
        c.check(pg.eval_on_selector_all("#chars-panel .char-voice", "els => els.map(e => e.querySelector('option[value=\"\"]').textContent)") in (["Automatic — Piseth", "Automatic — Srey Mom"], ["Automatic — Srey Mom", "Automatic — Piseth"]), "…the same in the picker of each character")
        c.check(pg.eval_on_selector("#bulk-voice option[value='']", "o => o.textContent.trim()") == "Follow the character / job", "the bulk picker's first choice is 'Follow the character / job'")
        pg.locator("#chars-panel").screenshot(path=str(SHOTS / "speakers_panel.png"))

        # flip the gender of the man: the badges, the labels and the 'changed' note follow at once; nothing is sent until Regenerate
        mid_ui = int(pg.locator("#chars-panel .char-row[data-gender='male']").get_attribute("data-char"))
        mrow = pg.locator(f"#chars-panel .char-row[data-char='{mid_ui}']")
        mrow.locator("[data-flip]").click()
        pg.wait_for_timeout(200)
        c.check(mrow.get_attribute("data-gender") == "female" and mrow.locator(".cb").inner_text().startswith("♀"), "⇄ flips the gender of a character (the badge changes)")
        lab = pg.eval_on_selector_all(f".seg-row[data-char='{mid_ui}']", "els => els.map(e => e.querySelector('.vsel option[value=\"\"]').textContent + '|' + e.querySelector('.cb').textContent)")
        c.check(lab and all(x.startswith("Automatic — Srey Mom|♀") for x in lab), "…and so do all of its lines (the voice that will speak them, the badge)", str(lab[:2]))
        c.check("1 character(s) changed" in pg.locator("#dirty-label").inner_text(), "…the table says '1 character(s) changed'", pg.locator("#dirty-label").inner_text())
        pg.fill(f"#chars-panel .char-row[data-char='{mid_ui}'] .char-name", "Grandpa")
        pg.wait_for_timeout(100)
        # the switch of the panel turns the labels back to the plain ones
        pg.click("#chars-panel .chars-switch .switch")
        pg.wait_for_timeout(300)
        c.check(pg.eval_on_selector(".seg-row .vsel option[value='']", "o => o.textContent.trim()").startswith("Same as above") and pg.locator("#chars-panel.off").count() == 1, "the panel's switch off: the labels say 'Same as above (...)' and the panel is dimmed")
        pg.click("#chars-panel .chars-switch .switch")
        pg.wait_for_timeout(300)
        c.check(pg.eval_on_selector(".seg-row .vsel option[value='']", "o => o.textContent.trim()").startswith("Automatic —"), "…and on again")
        # a voice for ONE character; a voice for ONE line
        pg.select_option(f"#chars-panel .char-row:not([data-char='{mid_ui}']) .char-voice", "vox:p:f_calm")
        pg.wait_for_timeout(200)
        c.check("2 character(s) changed" in pg.locator("#dirty-label").inner_text(), "a voice picked for a character counts as a change too", pg.locator("#dirty-label").inner_text())
        pg.select_option(".seg-row[data-idx='0'] .vsel", "vox:p:m_anchor")
        pg.wait_for_timeout(200)
        c.check("1 line(s) and 2 character(s) changed" in pg.locator("#dirty-label").inner_text(), "…with a line: '1 line(s) and 2 character(s) changed'", pg.locator("#dirty-label").inner_text())

        def grab(route, request):
            bodies.append(json.loads(request.post_data or "{}"))
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"id": UID}))
        pg.route("**/api/jobs/*/regenerate", grab)
        pg.click("#btn-regen")
        pg.wait_for_timeout(1200)
        body = bodies[-1] if bodies else {}
        ce_ = {x["id"]: x for x in body.get("characters", [])}
        fid = [i for i in cmap if i != mid_ui][0]
        c.check(ce_.get(mid_ui) == {"id": mid_ui, "gender": "female", "name": "Grandpa"} and ce_.get(fid) == {"id": fid, "voice": "vox:p:f_calm"} and len(ce_) == 2, "Regenerate sends only what changed: {id, gender, name} / {id, voice}", str(body.get("characters")))
        c.check(body.get("segments") == [{"idx": 0, "voice": "vox:p:m_anchor"}] and body["voice"]["auto"] == {"on": True, "male": "", "female": ""}, "…the line's voice, and the by-character settings (voice.auto) go with it", str({k: body.get(k) for k in ("segments",)}) + str(body.get("voice", {}).get("auto")))
        pg.unroute("**/api/jobs/*/regenerate")
        pg.close()

        # ---------------------------------------------------------------- detect again, a transcript job, the Khmer UI
        pg = mk_page(b)
        open_job(pg, UID)
        det_calls = []

        def grab2(route, request):
            det_calls.append(request.post_data)
            route.continue_()
        pg.route("**/api/jobs/*/speakers", grab2)
        pg.click("#btn-detect")
        pg.wait_for_timeout(500)
        toast_txt = pg.locator("#toasts").inner_text()
        c.check(len(det_calls) == 1 and "Listening to the video" in toast_txt, "'Detect again' asks the server to listen again (and says so)", toast_txt)
        pg.wait_for_selector("#chars-panel .char-row", timeout=20000)
        c.check(pg.locator("#chars-panel .char-row").count() == 2, "…and the table comes back with the characters")
        pg.close()

        pg = mk_page(b)
        open_job(pg, TID)
        c.check(pg.locator("#chars-panel").is_visible() and pg.locator("#chars-panel .char-row").count() == 0 and pg.locator("#chars-panel #btn-detect").count() == 0
                and "no original sound" in pg.locator("#chars-panel .chars-none").inner_text(), "a pasted transcript: the panel says there is no original sound, and has no button")
        c.check(first_opt(pg, ".seg-row .vsel").startswith("Same as above"), "…the lines say 'Same as above (...)'")
        pg.close()

        pg = mk_page(b, lang="km")
        open_job(pg, UID)
        c.check("តួអង្គ" in pg.locator("#chars-panel .chars-head b").inner_text() and "ស្គាល់តួអង្គ" in pg.locator("#btn-detect").inner_text(), "Khmer UI: the panel is in Khmer")
        c.check(first_opt(pg, ".seg-row .vsel").startswith("ស្វ័យប្រវត្តិ —"), "…and the labels too", str(first_opt(pg, ".seg-row .vsel")))
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(500)
        c.check("សំឡេងតាមតួអង្គ" in pg.locator("#page-dub .autovoice-block").inner_text(), "…and the settings block")
        pg.close()

        # ---------------------------------------------------------------- narrow screen
        pg = mk_page(b, w=390, h=900)
        open_job(pg, UID)
        ov = pg.evaluate("() => { const p = document.querySelector('#chars-panel'); return [p.scrollWidth, p.clientWidth, document.documentElement.scrollWidth, window.innerWidth]; }")
        c.check(ov[0] <= ov[1] + 1 and ov[2] <= ov[3] + 1, "a phone screen (390 px): the panel and the page do not scroll sideways", str(ov))
        pg.locator("#chars-panel").scroll_into_view_if_needed()
        pg.screenshot(path=str(SHOTS / "speakers_panel_phone.png"))
        pg.close()

        # ---------------------------------------------------------------- My voices: the gender chip and the button that corrects it
        pg = mk_page(b)
        pg.goto(srv.url + "/#dub")
        pg.click("#page-dub .engine-switch [data-value='voxcpm']")
        pg.wait_for_selector("#page-dub .voice-card.vox [data-voxgender]", timeout=10000)
        card = pg.locator("#page-dub .voice-card.vox", has=pg.locator("[data-voxgender]")).filter(has_text="Sophea")
        chips = lambda: card.locator("[data-voxgender-chip]").inner_text()  # noqa: E731
        c.check(chips() == "Female", "My voices: the card shows the gender that was found from the sound", chips())
        cid_s = [v["id"] for v in srv.api("GET", "/api/vox/voices").json()["custom"] if v["name"] == "Sophea"][0]
        seq = []
        for _ in range(3):
            card.locator("[data-voxgender]").click()
            pg.wait_for_timeout(700)
            seq.append(next(v["gender"] for v in srv.api("GET", "/api/vox/voices").json()["custom"] if v["id"] == cid_s))
        c.check(seq == ["Male", "", "Female"], "the ⇄ button cycles woman -> man -> not decided -> woman", str(seq))
        card.locator("[data-voxgender]").click()
        pg.wait_for_timeout(500)
        card.locator("[data-voxgender]").click()
        pg.wait_for_timeout(700)
        c.check("Gender unknown" in card.locator(".voice-sub").inner_text(), "…'not decided' shows 'Gender unknown'", card.locator(".voice-sub").inner_text())
        card.locator("[data-voxgender]").click()
        pg.wait_for_timeout(500)
        pg.close()
        b.close()
    c.check(not errors, "no JavaScript errors in the browser", str(errors[:3]))

if srv:
    srv.stop()
raise SystemExit(c.done())
