"""Core text / audio logic - fast and OFFLINE.  The pure functions that every dub goes through: language detection, glossary term protection,
subtitle parsing, sentence splitting, audio helpers, voice settings, configuration.

Until 1.9.1 these were only exercised end-to-end (test_api: real Google Translate + real Edge TTS).  These are characterization tests: they
pin down today's behaviour so that a refactor cannot change it by accident.  When a change is intended, change the expectation too.
"""
import os
import sys

import numpy as np

from lib import Checker, PROJECT, VERSION, WORK

os.environ.setdefault("KDS_DATA_DIR", str(WORK / "data_core"))
from app import audio, cjkterms, config, glossary, langs, textutil, transcript, translate, tts  # noqa: E402
from app.transcript import Seg  # noqa: E402

c = Checker(f"core logic v{VERSION}")

# ------------------------------------------------------------------ textutil: Khmer / English runs (the hybrid voice depends on it)
km = "ថ្ងៃនេះយើងប្រើ OpenAI API ដើម្បីបង្កើត Dashboard ។"
runs = textutil.split_runs(km)
c.check("".join(t for _, t in runs) == km, "split_runs loses nothing (the pieces joined = the text)")
c.check([t for k, t in runs if k == "en"] == ["OpenAI API", "Dashboard"], "split_runs: 'OpenAI API' and 'Dashboard' are the English runs", str(runs))
c.check(all(k == "km" for k, _ in runs if textutil.has_khmer(_)), "split_runs: every piece that has Khmer letters is a 'km' run")
c.check(textutil.split_runs("សួស្តីអ្នកទាំងអស់គ្នា") == [("km", "សួស្តីអ្នកទាំងអស់គ្នា")] and textutil.split_runs("Hello world") == [("en", "Hello world")], "split_runs: pure Khmer = one km run, pure English = one en run")
c.check(textutil.has_khmer("សួស្តី") and not textutil.has_khmer("hello 123"), "has_khmer")
c.check(textutil.ensure_khmer_terminal("សួស្តី") == "សួស្តី។" and textutil.ensure_khmer_terminal("សួស្តី។") == "សួស្តី។" and textutil.ensure_khmer_terminal("") == "", "ensure_khmer_terminal: adds ។ once, leaves an empty line empty")
long_km = "ប្រយោគទីមួយ។ ប្រយោគទីពីរ។ " * 30
ch = textutil.split_sentences(long_km, max_chars=120)
c.check(len(ch) > 5 and all(len(x) <= 120 for x in ch), "split_sentences: Khmer text is cut into pieces of at most max_chars", str([len(x) for x in ch][:6]))
c.check(" ".join(ch).split() == long_km.split(), "split_sentences: …without losing a word")
c.check(textutil.split_sentences("This is one. This is two! Is this three? Yes.", max_chars=40, min_chunk=5) == ["This is one.", "This is two!", "Is this three?", "Yes."], "split_sentences: English sentences")

# ------------------------------------------------------------------ transcript: parsing, merging, writing
srt = "1\n00:00:01,000 --> 00:00:03,500\nHello <i>world</i>.\n\n2\n00:00:04,000 --> 00:00:06,000\nSecond line\ncontinues here.\n"
sg = transcript.parse_srt_vtt(srt)
c.check([(s.start, s.end) for s in sg] == [(1.0, 3.5), (4.0, 6.0)] and sg[1].text == "Second line continues here.", "parse SRT: times, and a two-line caption becomes one line", str([(s.start, s.end, s.text) for s in sg]))
vtt = "WEBVTT\n\n00:01.000 --> 00:03.500\nHello world\n\n00:00:04.000 --> 00:00:06.000 align:start\nSecond\n"
sv = transcript.parse_srt_vtt(vtt)
c.check([(s.start, s.end, s.text) for s in sv] == [(1.0, 3.5, "Hello world"), (4.0, 6.0, "Second")], "parse VTT: mm:ss.mmm times and cue settings (align:start)", str([(s.start, s.end, s.text) for s in sv]))
items = [{"start": 1.0, "end": 3.5, "km": "សួស្តី"}, {"start": 4.0, "end": 6.25, "km": "លាហើយ"}]
out = transcript.to_srt(items)
c.check(out.startswith("1\n00:00:01,000 --> 00:00:03,500\nសួស្តី\n\n2\n"), "to_srt: standard SRT layout", repr(out[:60]))
back = transcript.parse_srt_vtt(out)
c.check([(s.start, s.end, s.text) for s in back] == [(1.0, 3.5, "សួស្តី"), (4.0, 6.25, "លាហើយ")], "to_srt -> parse: a round trip gives the same lines")
c.check(transcript.parse_any(srt)[1] is True and transcript.parse_any("Hello there. How are you? Fine.")[1] is False, "parse_any: SRT is timed, plain text is not")
frag = [Seg(0.0, 1.0, "this is"), Seg(1.0, 2.0, "a long sentence"), Seg(2.0, 3.0, "that goes on."), Seg(5.0, 6.0, "Next one here.")]
mg = transcript.merge_segments(frag)
c.check(len(mg) == 2 and mg[0].text == "this is a long sentence that goes on." and (mg[0].start, mg[0].end) == (0.0, 3.0) and mg[1].text == "Next one here.", "merge_segments: fragments become one sentence; a separate sentence stays separate", str([(s.start, s.end, s.text) for s in mg]))
ov = transcript.fix_overlaps([Seg(0, 3, "a"), Seg(2, 4, "b")])
c.check(ov[0].end <= ov[1].start and ov[1].end == 4, "fix_overlaps: a line never ends after the next one starts")
c.check(transcript.clean_caption_text("[Music] >> Hello   <b>there</b> &amp; welcome") == "Hello there & welcome", "clean_caption_text: [Music], >>, tags, entities and double spaces are gone")

# ------------------------------------------------------------------ glossary: technical terms stay English
terms, readings = glossary.parse_glossary_text("# comment\nAPI\nmachine learning\nnginx = អេនជីនអិច\n")
c.check(terms == ["API", "machine learning", "nginx"] and readings == {"nginx": "អេនជីនអិច"}, "parse_glossary_text: terms, a '=' line is a Khmer reading, # is a comment", str((terms, readings)))
c.check(glossary.parse_glossary_maps("机器学习 => machine learning\nAPI\n") == {"机器学习": "machine learning"}, "parse_glossary_maps: '源词 => English' lines")
tm = glossary.TermMatcher(["API", "machine learning", "Dashboard"], auto_detect=True)
prot, mapping = tm.protect("We use the API and machine learning to build a Dashboard with Node.js and iPhone 15.")
c.check(prot == "We use the X1X and X2X to build a X3X with X4X and X5X 15." and mapping == {1: "API", 2: "machine learning", 3: "Dashboard", 4: "Node.js", 5: "iPhone"},
        "TermMatcher.protect: glossary terms AND product names (Node.js, iPhone) become placeholders", repr(prot) + str(mapping))
fake = " ".join(w if w.startswith("X") else "ខ្មែរ" + w for w in prot.split())              # a 'translation' that keeps the placeholders
restored, ok = glossary.TermMatcher.restore(fake, mapping)
c.check(ok and all(t in restored for t in mapping.values()) and "X1X" not in restored, "TermMatcher.restore: every term comes back, once", restored)
r2, ok2 = glossary.TermMatcher.restore("សូម X១X និង X២X", {1: "API", 2: "Dashboard"})
c.check(ok2 and r2 == "សូម API និង Dashboard", "restore understands Khmer digits in a placeholder (the translator may write X១X)", r2)
r3, ok3 = glossary.TermMatcher.restore("សូម X1X", {1: "API", 2: "Dashboard"})
c.check(ok3 is False, "restore says so (False) when a placeholder was lost by the translator (the engine then retries with another style)")
c.check(glossary.TermMatcher([], auto_detect=False).protect("hello world") == ("hello world", {}), "no terms: the text is not touched")
zh = glossary.TermMatcher([], auto_detect=False, src_map=cjkterms.builtin_terms("zh"))
c.check(zh.protect("我们把代码部署到服务器上") == ("我们把代码部署到 X1X 上", {1: "server"}), "Chinese: 服务器 is protected as the English word 'server'")
ko = glossary.TermMatcher([], auto_detect=False, src_map=cjkterms.builtin_terms("ko"))
c.check(ko.protect("서버에서 파이썬을 실행합니다") == ("X1X에서 X2X을 실행합니다", {1: "server", 2: "Python"}), "Korean: 서버 / 파이썬 become 'server' / 'Python' (particles stay)")
c.check(cjkterms.builtin_terms("zh").get("服务器") == "server" and cjkterms.builtin_terms("ko").get("서버") == "server" and not cjkterms.builtin_terms("en"), "built-in term tables: zh + ko have entries, en has none")
c.check(glossary.apply_readings("We run nginx here", {"nginx": "អេនជីនអិច"}) == "We run អេនជីនអិច here", "apply_readings: a term with a Khmer reading is spoken in Khmer")
c.check(len(glossary.DEFAULT_GLOSSARY_TEXT.splitlines()) > 100 and glossary.parse_glossary_text(glossary.DEFAULT_GLOSSARY_TEXT)[0], "the default glossary is not empty")

# ------------------------------------------------------------------ langs: the script of the text decides
c.check([langs.detect_lang(t) for t in ("Hello world, this is English", "你好，我们今天学习 Python", "안녕하세요 오늘은 파이썬을 배웁니다", "12345 ...", "")] == ["en", "zh", "ko", None, None], "detect_lang: en / zh (with English product names) / ko / no letters = None")
code, note = langs.resolve_lang("en", "你好，我们今天学习编程")
c.check(code == "zh" and note, "resolve_lang: Chinese text wins over a selected 'English' (and says so)", note)
c.check(langs.resolve_lang("auto", "Hello there") == ("en", "") and langs.resolve_lang("en", "Hello there") == ("en", ""), "resolve_lang: no note when the choice agrees with the text")
c.check(list(langs.LANGS) == ["en", "zh", "ko"], "supported source languages are exactly en, zh, ko")
for name, want in (("technical-tutorial.srt", "en"), ("technical-tutorial.zh.srt", "zh"), ("technical-tutorial.ko.srt", "ko")):
    txt = (PROJECT / "samples" / name).read_text(encoding="utf-8")
    segs, timed = transcript.parse_any(txt)
    c.check(timed and len(segs) >= 10 and langs.detect_lang(" ".join(s.text for s in segs)) == want, f"samples/{name}: {len(segs)} timed lines, detected as {want}")

# ------------------------------------------------------------------ audio helpers (24 kHz mono float32)
SR = config.SAMPLE_RATE
x = (np.sin(np.linspace(0, 440 * 2 * np.pi * 2, SR * 2)) * 0.3).astype(np.float32)
y = audio.time_stretch(x, 1.25)
c.check(SR == 24000 and abs(len(y) / SR - 1.6) < 0.05, "time_stretch 1.25: 2.0 s becomes about 1.6 s", str(len(y) / SR))
c.check(len(audio.time_stretch(x, 1.0)) == len(x), "time_stretch 1.0 does not change the length")
c.check(float(np.abs(audio.soft_limit(np.ones(100, dtype=np.float32) * 3.0)).max()) <= 0.97 + 1e-6, "soft_limit: nothing is louder than 0.97")
padded = np.concatenate([np.zeros(SR, dtype=np.float32), x[: SR // 2], np.zeros(SR, dtype=np.float32)])
c.check(len(audio.trim_silence(padded)) / SR < 0.8, "trim_silence: 2.5 s with silence around 0.5 s of sound -> well under a second")
mixed = audio.mix_into(np.zeros(SR * 3, dtype=np.float32), np.ones(2400, dtype=np.float32) * 0.5, 1.0)
c.check(int(np.argmax(mixed != 0)) == SR and len(mixed) == SR * 3 and abs(float(mixed[SR]) - 0.5) < 1e-6, "mix_into: a clip starts exactly at its second")

# ------------------------------------------------------------------ voices + configuration
vs = tts.VoiceSettings.from_dict({"id": "bad-voice", "rate": 999, "pitch": -999, "volume": 999, "term_mode": "x", "engine": "nope"})
c.check((vs.voice, vs.rate, vs.pitch, vs.volume, vs.term_mode, vs.engine) == ("km-KH-SreymomNeural", 150, -50, 100, "english_voice", "edge"), "VoiceSettings: junk is clamped / replaced by the defaults", str(vs))
v2 = tts.VoiceSettings.from_dict({"id": "km-KH-PisethNeural", "engine": "voxcpm"})
c.check((v2.en_voice, v2.vox_id) == ("en-US-AndrewNeural", "vox:original"), "VoiceSettings: Piseth reads English terms with Andrew; engine voxcpm defaults to 'vox:original'")
c.check({v["id"] for v in config.KHMER_VOICES} == {"km-KH-SreymomNeural", "km-KH-PisethNeural"} and all(v["en_voice"] in config.EN_VOICE_IDS for v in config.KHMER_VOICES), "config: the two Khmer voices and their English partners exist")
c.check("../x" not in config.DOWNLOADABLE_FILES and all("/" not in n and "\\" not in n for n in config.DOWNLOADABLE_FILES)
        and {"dub.mp3", "dubbed.mp4", "khmer.srt", "original.srt", "script_km.txt"} <= set(config.DOWNLOADABLE_FILES), "config: the download whitelist has the output files and no path separators")
c.check(translate._extract_json('Here you go: ```json\n["a", "b"]\n``` done') == ["a", "b"] and translate._clean_khmer("  សួស្តី  \n") == "សួស្តី", "translate helpers: JSON inside a code fence, Khmer text cleaning")

sys.exit(c.done())
