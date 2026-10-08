"""API tests against a real server: stub VoxCPM2 engine, real Google Translate + real Microsoft Edge TTS."""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

from lib import *  # noqa: E402,F401,F403

c = Checker(f"API v{VERSION}")
data = WORK / "data_api"
shutil.rmtree(data, ignore_errors=True)
data.mkdir(parents=True)
home = make_stub_home(WORK / "voxhome_api")
srv = Server(8011, data, home, name="api").start()


def dominant_freq(mp3_bytes: bytes) -> float:
    from app import audio
    p = WORK / "tmp_probe.mp3"
    p.write_bytes(mp3_bytes)
    x = audio.decode_to_array(p, sr=24000)
    x = x[: 24000 * 3]
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return float(np.argmax(spec) * 24000 / len(x))


def f0_of(x, sr=24000):
    """Median fundamental frequency (Hz) of the voiced frames, by autocorrelation (female ~190-260 Hz, male ~100-140 Hz)."""
    n, hop = int(0.04 * sr), int(0.02 * sr)
    lo, hi = int(sr / 400), int(sr / 70)
    f = []
    for i in range(0, len(x) - n, hop):
        w = x[i:i + n] * np.hanning(n)
        if np.sqrt(np.mean(w ** 2)) < 0.02:
            continue
        ac = np.correlate(w, w, "full")[n - 1:]
        ac = ac / (ac[0] + 1e-9)
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.4:
            f.append(sr / k)
    return float(np.median(f)) if len(f) > 10 else None


def row_f0(mp3_bytes, seg):
    from app import audio
    p = WORK / "tmp_f0.mp3"
    p.write_bytes(mp3_bytes)
    x = audio.decode_to_array(p, sr=24000)
    return f0_of(x[int(seg["out_start"] * 24000): int(seg["out_end"] * 24000)])


def vox_preview(voice, text="", quality="fast", timeout=60):
    body = {"voice": voice, "quality": quality}
    if text:
        body["text"] = text
    r = srv.api("POST", "/api/vox/preview", json=body)
    pid = r.json()["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = srv.api("GET", f"/api/vox/preview/{pid}").json()
        if s["state"] != "running":
            return s
        time.sleep(0.3)
    raise TimeoutError("preview")


try:
    # ---------------------------------------------------------------- voices list
    v = srv.api("GET", "/api/voices").json()
    pres = v["vox"]["presets"]
    c.check(len(pres) == 8 and [p["gender"] for p in pres].count("Female") == 4, "/api/voices lists 8 designed voices")
    c.check(all(p["kind"] == "designed" and p["id"].startswith("vox:p:") and p["ready"] is False for p in pres), "fresh: none ready yet")
    c.check("presets" in srv.api("GET", "/api/vox/voices").json(), "/api/vox/voices has presets too")

    # ---------------------------------------------------------------- designed voices: create once, then clone
    s1 = vox_preview("vox:p:f_warm", "សួស្តីបងប្អូន នេះជាការសាកល្បងសំឡេង")
    c.check(s1["state"] == "done", "designed voice preview works", str(s1))
    anchor = home / "voices" / "preset-f_warm-v0.wav"
    c.check(anchor.exists(), "anchor clip was created", str(list((home / 'voices').glob('*')) if (home / 'voices').exists() else 'no voices dir'))
    pres = srv.api("GET", "/api/voices").json()["vox"]["presets"]
    c.check([p for p in pres if p["key"] == "f_warm"][0]["ready"] is True, "…and the list says ready")
    f1 = dominant_freq(srv.api("GET", s1["url"]).content)
    s2 = vox_preview("vox:p:f_warm", "ជំរាបសួរម្តងទៀត យើងនឹងចាប់ផ្តើមមេរៀនថ្ងៃនេះ")
    f2 = dominant_freq(srv.api("GET", s2["url"]).content)
    c.check(abs(f1 - f2) < 8, "same designed voice -> same voice for different lines", f"{f1:.0f} vs {f2:.0f} Hz")
    s3 = vox_preview("vox:p:m_deep", "សួស្តីបងប្អូន នេះជាការសាកល្បងសំឡេង")
    f3 = dominant_freq(srv.api("GET", s3["url"]).content)
    c.check(s3["state"] == "done" and abs(f3 - f1) > 8, "another designed voice sounds different", f"{f3:.0f} vs {f1:.0f} Hz")
    log = (home / "worker.log").read_text(errors="ignore") if (home / "worker.log").exists() else ""
    t0 = time.time()
    s4 = vox_preview("vox:p:f_warm", "សួស្តីបងប្អូន នេះជាការសាកល្បងសំឡេង")
    c.check(s4["state"] == "done" and time.time() - t0 < 3, "second preview of the same text comes from the cache", f"{time.time() - t0:.1f}s")

    # ---------------------------------------------------------------- re-roll
    r = srv.api("POST", "/api/vox/presets/f_warm/reroll")
    c.check(r.status_code == 200 and r.json() == {"id": "vox:p:f_warm", "variant": 1}, "re-roll bumps the variant", r.text)
    c.check([p for p in srv.api("GET", "/api/voices").json()["vox"]["presets"] if p["key"] == "f_warm"][0]["ready"] is False, "after re-roll the new voice is not made yet")
    c.check(srv.api("POST", "/api/vox/presets/zzz/reroll").status_code == 404, "re-roll of an unknown voice -> 404")
    s5 = vox_preview("vox:p:f_warm", "សួស្តីបងប្អូន នេះជាការសាកល្បងសំឡេង")
    f5 = dominant_freq(srv.api("GET", s5["url"]).content)
    c.check(s5["state"] == "done" and (home / "voices" / "preset-f_warm-v1.wav").exists(), "new anchor is made on first use")
    c.check(abs(f5 - f1) > 8, "re-rolled voice is a different person", f"{f5:.0f} vs {f1:.0f} Hz")
    c.check((home / "voices" / "preset-f_warm-v0.wav").exists(), "the previous anchor is kept (a running job may still read it)")
    srv.api("POST", "/api/vox/presets/f_warm/reroll"); srv.api("POST", "/api/vox/presets/f_warm/reroll")
    vox_preview("vox:p:f_warm", "ឃ្លាថ្មី")
    c.check(not (home / "voices" / "preset-f_warm-v0.wav").exists(), "older anchors are cleaned up")
    # ---------------------------------------------------------------- several requests for a voice that does not exist yet: made ONCE
    import threading
    res = {}

    def go(k, text):
        res[k] = vox_preview("vox:p:m_anchor", text)

    ths = [threading.Thread(target=go, args=(i, f"ឃ្លាទី {i} សាកល្បងសំឡេងម្តងទៀត យើងនឹងចាប់ផ្តើម")) for i in range(3)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    c.check(all(r["state"] == "done" for r in res.values()), "3 simultaneous requests for a new designed voice all succeed", str(res))
    c.check(len(list((home / "voices").glob("preset-m_anchor-*.wav"))) == 1, "…and the voice was made once (one anchor)")
    fr = [dominant_freq(srv.api("GET", r["url"]).content) for r in res.values()]
    c.check(max(fr) - min(fr) < 8, "…so all three lines have the same voice", str(fr))
    bad = vox_preview("vox:p:nope")
    c.check(bad["state"] == "error" and bad.get("code") == "VOX_VOICE_GONE", "unknown designed voice -> VOX_VOICE_GONE", str(bad))
    bad = vox_preview("vox:original")
    c.check(bad["state"] == "error" and bad.get("code") == "VOX_NO_ORIGINAL", "original speaker cannot be previewed", str(bad))

    # ---------------------------------------------------------------- Edge preview with the user's own text
    r1 = srv.api("GET", "/api/voices/preview", params={"voice": "km-KH-PisethNeural", "text": "សួស្តី នេះជាការសាកល្បង"})
    r2 = srv.api("GET", "/api/voices/preview", params={"voice": "km-KH-PisethNeural"})
    c.check(r1.status_code == 200 and r2.status_code == 200 and r1.headers["content-type"] == "audio/mpeg" and r1.content != r2.content, "Edge preview speaks the given text")
    c.check(srv.api("GET", "/api/voices/preview", params={"voice": "km-KH-PisethNeural", "text": "ក" * 601}).status_code == 422, "text over 600 characters is refused")

    # ---------------------------------------------------------------- a dubbing job (real Google + Edge) to edit
    srt = (PROJECT / "samples" / "technical-tutorial.srt").read_text(encoding="utf-8")
    body = {"source": {"type": "transcript", "text": srt, "lang": "en"},
            "voice": {"id": "km-KH-SreymomNeural", "rate": 0, "pitch": 0, "volume": 0, "term_mode": "english_voice", "engine": "edge",
                      "vox": {"id": "vox:original", "quality": "fast", "consent": False}},
            "translate": {"engine": "google", "keep_terms": True}, "output": {"sync": "fit", "max_speedup": 1.4}}
    jid = srv.api("POST", "/api/jobs/dub", json=body).json()["id"]
    job = srv.wait_job(jid, 400)
    c.check(job["status"] == "done", "dub job done", str(job.get("error")))
    segs = job["segments"]
    n = len(segs)
    c.check(n >= 10 and all(s.get("slot") and s.get("dur") for s in segs if s["out_start"] is not None), "segments carry slot + dur", f"n={n}")
    c.check(all("voice" not in s and "t0" not in s and "t1" not in s for s in segs), "no overrides in a fresh job")
    c.check(job["meta"]["row_voices"] == 0 and job["meta"]["row_times"] == 0, "meta counts 0 overrides")
    dur0 = job["meta"]["audio_duration"]
    out_start_before = {s["idx"]: s["out_start"] for s in segs}
    base_audio = srv.api("GET", f"/api/jobs/{jid}/file/dub.mp3").content
    f_base = {i: row_f0(base_audio, segs[i]) for i in (1, 2, 3)}
    c.check(all(v and 150 < v < 320 for v in f_base.values()), "baseline: Srey Mom's lines have a female pitch", str(f_base))

    def regen(edits=None, voice=None, output=None, expect=200, timeout=400):
        body = {}
        if edits is not None:
            body["segments"] = edits
        if voice is not None:
            body["voice"] = voice
        if output is not None:
            body["output"] = output
        r = srv.api("POST", f"/api/jobs/{jid}/regenerate", json=body)
        if r.status_code != 200:
            return r, None
        return r, srv.wait_job(jid, timeout)

    # ---------------------------------------------------------------- validation (400, nothing is changed)
    for label, edits, needle in [
        ("unknown voice", [{"idx": 1, "voice": "vox:p:nope"}], "unknown voice"),
        ("unknown line", [{"idx": 999, "km": "x"}], "does not exist"),
        ("End too early", [{"idx": 1, "t1": segs[1]["start"] + 0.1}], "at least"),
        ("not a number", [{"idx": 1, "t0": "soon"}], "not a number"),
        ("duplicate", [{"idx": 1, "km": "a"}, {"idx": 1, "km": "b"}], "twice"),
        ("not a list", {"idx": 1}, "list"),
    ]:
        r, _ = regen(edits)
        det = (r.json().get("detail") or {}) if r.status_code == 400 else {}
        c.check(r.status_code == 400 and det.get("code") == "BAD_REQUEST" and needle in (det.get("message") or "").lower(),
                f"validation: {label}", f"{r.status_code} {r.text[:160]}")
    c.check(srv.api("GET", f"/api/jobs/{jid}").json()["status"] == "done", "a rejected request does not touch the job")

    # ---------------------------------------------------------------- old-style request still works
    r, j = regen([{"idx": 0, "km": segs[0]["km"] + " "}])
    c.check(j and j["status"] == "done", "old {idx, km} request still works", str(j and j.get("error")))

    # ---------------------------------------------------------------- per-line Edge voice
    r, j = regen([{"idx": 1, "voice": "km-KH-PisethNeural"}, {"idx": 3, "voice": "km-KH-PisethNeural"}])
    c.check(j["status"] == "done", "regenerate with two Piseth lines", str(j.get("error")))
    s = {x["idx"]: x for x in j["segments"]}
    c.check(s[1].get("voice") == "km-KH-PisethNeural" and s[3].get("voice") == "km-KH-PisethNeural" and "voice" not in s[2], "voice stored on those lines only")
    c.check(j["meta"]["row_voices"] == 2, "meta.row_voices == 2")
    c.check(any("Per-line voices: 2 of" in l for l in j["logs"]), "log mentions per-line voices")
    c.check(abs(j["meta"]["audio_duration"] - dur0) < dur0 * 0.35, "track length stays plausible", f"{dur0} -> {j['meta']['audio_duration']}")
    new_audio = srv.api("GET", f"/api/jobs/{jid}/file/dub.mp3").content
    f_new = {i: row_f0(new_audio, s[i]) for i in (1, 2, 3)}
    c.check(f_new[1] and f_new[3] and f_new[1] < 0.8 * f_base[1] and f_new[3] < 0.8 * f_base[3], "the audio of lines 2 and 4 REALLY changed to the male voice (pitch dropped)", f"{f_base} -> {f_new}")
    c.check(f_new[2] and abs(f_new[2] / f_base[2] - 1) < 0.12, "…while line 3 still has Srey Mom's voice", f"{f_base[2]:.0f} -> {f_new[2]:.0f}")

    # ---------------------------------------------------------------- per-line designed voice + Edge in one job (stub engine)
    vox_default = {"id": "km-KH-SreymomNeural", "engine": "edge", "vox": {"id": "vox:original", "quality": "fast", "consent": False}}
    r, j = regen([{"idx": 2, "voice": "vox:p:m_deep"}, {"idx": 4, "voice": "vox:p:f_pro"}, {"idx": 5, "voice": "vox:p:m_deep"}], voice=vox_default)
    c.check(j["status"] == "done", "designed voices on three lines (mixed with Edge)", str(j.get("error")))
    c.check(j["meta"].get("vox") and j["meta"]["vox"]["lines"] == 3 and len(j["meta"]["vox"]["voices"]) == 2, "meta.vox: 3 lines, 2 voices", str(j["meta"].get("vox")))
    c.check(j["meta"]["tts_engine"] == "edge" and j["meta"]["row_voices"] == 5, "job engine stays edge; 5 lines have own voice", str((j["meta"]["tts_engine"], j["meta"]["row_voices"])))
    c.check((home / "voices" / "preset-m_deep-v0.wav").exists() and (home / "voices" / "preset-f_pro-v0.wav").exists(), "anchors of the two voices exist")
    r, j2 = regen([{"idx": 2, "km": [x for x in j["segments"] if x["idx"] == 2][0]["km"]}], voice=vox_default)
    c.check(j2["meta"]["vox"]["cached"] == 3 and j2["meta"]["vox"]["lines"] == 0, "unchanged designed-voice lines come from the cache", str(j2["meta"].get("vox")))

    # ---------------------------------------------------------------- the job's own voice is a designed voice, some lines use Edge
    vj = {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:p:m_elder", "quality": "fast", "consent": False}}
    r, j = regen([{"idx": 1, "voice": "km-KH-SreymomNeural"}], voice=vj)
    c.check(j["status"] == "done" and j["meta"]["tts_engine"] == "voxcpm", "vox job with an Edge line", str(j.get("error")))
    c.check(j["meta"]["vox"]["voices"] and j["meta"]["vox"]["voices"][0] == "vox:p:m_elder" and "Wise elder" in j["meta"]["vox"]["label"] or "Wise" in j["meta"]["vox"]["label"], "label of the job voice", str(j["meta"]["vox"]))
    # back to a plain Edge job: clear every override
    clear = [{"idx": i, "voice": None} for i in range(n)]
    r, j = regen(clear, voice=vox_default)
    c.check(j["status"] == "done" and all("voice" not in x for x in j["segments"]) and j["meta"]["row_voices"] == 0 and "vox" not in j["meta"], "null clears every per-line voice", str(j.get("error")))

    # ---------------------------------------------------------------- clone voices need consent / a video (also per line)
    r, j = regen([{"idx": 1, "voice": "vox:original"}], voice=vox_default)
    c.check(j["status"] == "error" and j["error"]["code"] in ("VOX_NO_ORIGINAL", "VOX_CONSENT_REQUIRED"), "vox:original needs a YouTube source (and consent)", str(j.get("error")))
    r, j = regen([{"idx": 1, "voice": "vox:c:0123abcd"}], voice=vox_default)
    c.check(j["status"] == "error" and j["error"]["code"] == "VOX_CONSENT_REQUIRED", "a clone voice needs the consent flag", str(j.get("error")))
    vc = {"id": "km-KH-SreymomNeural", "engine": "edge", "vox": {"id": "vox:original", "quality": "fast", "consent": True}}
    r, j = regen([{"idx": 1, "voice": "vox:c:0123abcd"}], voice=vc)
    c.check(j["status"] == "error" and j["error"]["code"] == "VOX_NO_REF", "…and the voice must exist", str(j.get("error")))
    r, j = regen([{"idx": 1, "voice": None}], voice=vox_default)
    c.check(j["status"] == "done", "job recovers after those errors", str(j.get("error")))

    # ---------------------------------------------------------------- per-line time
    s = {x["idx"]: x for x in j["segments"]}
    # a line whose predecessor ends well before it starts (free time to borrow)
    k = next((i for i in range(1, n) if s[i - 1]["out_end"] is not None and s[i]["out_start"] is not None
              and s[i - 1]["out_end"] + 0.06 < s[i]["start"] - 0.65), 5)
    t_start = round(s[k]["start"] - 0.6, 2)
    t_end = round(s[k]["start"] + 4.0, 2)
    r, j = regen([{"idx": k, "t0": t_start, "t1": t_end}])
    c.check(j["status"] == "done", "regenerate with a hand-set Start / End", str(j.get("error")))
    s = {x["idx"]: x for x in j["segments"]}
    c.check(s[k]["t0"] == t_start and s[k]["t1"] == t_end, "t0 / t1 stored")
    c.check(abs(s[k]["slot"][0] - t_start) < 1e-6 and abs(s[k]["slot"][1] - t_end) < 1e-6, "slot reflects them", str(s[k]["slot"]))
    c.check(abs(s[k]["out_start"] - t_start) < 0.02, "the line starts at the hand-set Start (earlier than its caption)", f"{s[k]['out_start']} vs {t_start} (caption {s[k]['start']})")
    c.check(abs(s[k - 1]["slot"][1] - (t_start - 0.10)) < 1e-6, "the line before gets the time up to the new Start", str(s[k - 1]["slot"]))
    c.check(j["meta"]["row_times"] == 1 and any("Per-line timing: 1 lines" in l for l in j["logs"]), "meta + log mention the hand-set time")
    # make a line start later: its predecessor may use the time
    k2 = k + 2 if k + 2 < n else 1
    r, j = regen([{"idx": k2, "t0": round(s[k2]["start"] + 0.7, 2)}])
    s = {x["idx"]: x for x in j["segments"]}
    c.check(j["status"] == "done" and s[k2]["out_start"] >= s[k2]["start"] + 0.69, "a later Start delays the line", f"{s[k2]['out_start']} vs {s[k2]['start']}")
    c.check(abs(s[k2 - 1]["slot"][1] - (s[k2]["t0"] - 0.10)) < 1e-6, "…and the line before gets 0.7 s more", str(s[k2 - 1]["slot"]))
    # a window that is far too short: the line cannot fit even at the top speed -> flagged 'long'
    r, j = regen([{"idx": k2, "t0": None}, {"idx": k, "t0": None, "t1": round(s[k]["start"] + 0.6, 2)}])
    s = {x["idx"]: x for x in j["segments"]}
    c.check(j["status"] == "done" and "long" in (s[k].get("warn") or ""), "a 0.6 s window is flagged 'long'", str((s[k].get("warn"), s[k]["dur"], s[k]["speed"])))
    c.check(s[k]["speed"] >= 1.39, "…after speeding up as far as allowed (max 1.4 + residual)", str(s[k]["speed"]))
    # reset
    r, j = regen([{"idx": k, "t0": None, "t1": None}])
    s = {x["idx"]: x for x in j["segments"]}
    c.check(j["status"] == "done" and all("t0" not in x and "t1" not in x for x in j["segments"]) and j["meta"]["row_times"] == 0, "null clears the times")
    c.check({i: s[i]["out_start"] for i in (0, 1, 2)} == {i: out_start_before[i] for i in (0, 1, 2)}, "…back to the original placement")
    c.check("long" not in (s[k].get("warn") or ""), "…and the warning is gone")
    # natural pace: times are ignored (and say so)
    r, j = regen([{"idx": k, "t0": 3.0, "t1": 9.0}], output={"sync": "natural"})
    c.check(j["status"] == "done" and any("ignored here" in l for l in j["logs"]), "natural pace: the log says the times are ignored", str(j.get("error")))
    r, j = regen([{"idx": k, "t0": None, "t1": None}], output={"sync": "fit", "max_speedup": 1.4})

    # ---------------------------------------------------------------- TTS tab with a designed voice
    tb = {"text": "សួស្តី! នេះគឺជាការសាកល្បងសំឡេងដែលបានបង្កើត។ យើងអាចប្រើ API ជា English ក្នុងប្រយោគខ្មែរ។", "input_lang": "km",
          "voice": {"id": "km-KH-SreymomNeural", "engine": "voxcpm", "vox": {"id": "vox:p:f_bright", "quality": "fast", "consent": False}},
          "translate": {"engine": "google", "keep_terms": True}}
    tj = srv.api("POST", "/api/jobs/tts", json=tb).json()["id"]
    tjob = srv.wait_job(tj, 120)
    c.check(tjob["status"] == "done" and tjob["meta"]["audio_duration"] > 2, "Text to Speech with a designed voice", str(tjob.get("error")))
    c.check((home / "voices" / "preset-f_bright-v0.wav").exists(), "…which made that voice's anchor")
    sp = srv.api("GET", f"/api/jobs/{tj}/file/speech.mp3")
    c.check(sp.status_code == 200 and len(sp.content) > 5000, "speech.mp3 downloadable")

    # ---------------------------------------------------------------- the job list / history is unaffected
    jl = srv.api("GET", "/api/jobs").json()["jobs"]
    c.check(len(jl) == 2, "history has the dub + tts jobs", str(len(jl)))
    c.check(srv.api("GET", "/api/health").json()["version"] == VERSION, f"version {VERSION}")

    # ---------------------------------------------------------------- caching: the page is never cached, UI files are always revalidated
    page = srv.api("GET", "/")
    c.check(page.status_code == 200 and "no-store" in page.headers.get("cache-control", ""), "GET / is sent with Cache-Control: no-store")
    asset = srv.api("GET", "/static/js/app.js")
    c.check(asset.status_code == 200 and "no-cache" in asset.headers.get("cache-control", ""), "UI files (/static/js/app.js) are sent with Cache-Control: no-cache")
    c.check(re.search(r"/static/js/app\.js\?v=" + re.escape(VERSION) + r"-[0-9a-f]{10}", page.text) is not None, "asset URLs carry ?v=<version>-<hash of the files>")
finally:
    srv.stop()
sys.exit(c.done())
