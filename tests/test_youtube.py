"""End-to-end with REAL YouTube (the one video the sandbox can reach), real Google Translate and real Edge TTS: MP4 export at 1080p / 720p."""
import shutil, sys, time
from lib import *
from app import audio

c = Checker("YouTube MP4 quality + Claude draft")
data = WORK / "data_yt"
shutil.rmtree(data, ignore_errors=True)
data.mkdir(parents=True)
srv = Server(8013, data, make_stub_home(WORK / "voxhome_yt"), name="yt").start()
try:
    body = {"source": {"type": "youtube", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "lang": "en"},
            "video": {"id": "dQw4w9WgXcQ", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "yt test", "duration": 213},
            "voice": {"id": "km-KH-SreymomNeural", "engine": "edge", "vox": {"id": "vox:original", "quality": "fast", "consent": False}},
            "translate": {"engine": "google", "keep_terms": True},
            "output": {"sync": "fit", "video": True, "orig_volume": 25, "duck": True, "max_speedup": 1.4, "max_height": 1080},
            "youtube": {"whisper": False}}
    t0 = time.time()
    jid = srv.api("POST", "/api/jobs/dub", json=body).json()["id"]
    job = srv.wait_job(jid, 600)
    print("job 1 finished in", round(time.time() - t0), "s")
    c.check(job["status"] == "done", "YouTube job with MP4 output done", str(job.get("error")) + str(job.get("warnings")))
    c.check(not job.get("warnings"), "no warnings", str(job.get("warnings")))
    v = job["meta"].get("video") or {}
    c.check((v.get("width"), v.get("height"), v.get("codec"), v.get("limit")) == (1920, 1080, "h264", 1080), "the downloaded video is 1920x1080 h264 (limit 1080p)", str(v))
    c.check(any("Video: 1920×1080 h264 (limit 1080p)" in l for l in job["logs"]), "log says so")
    mp4 = srv.api("GET", f"/api/jobs/{jid}/file/dubbed.mp4", timeout=120)
    c.check(mp4.status_code == 200 and len(mp4.content) > 5_000_000, "dubbed.mp4 downloadable", f"{len(mp4.content) / 1e6:.1f} MB")
    (WORK / "yt_out.mp4").write_bytes(mp4.content)
    info = audio.probe_media(WORK / "yt_out.mp4")
    c.check(info["height"] == 1080 and info["width"] == 1920 and info["has_audio"] and abs(info["duration"] - 213) < 3, "the exported MP4 is 1080p with sound", str(info))
    j2 = job["segments"]
    c.check(len(j2) > 20 and all(s.get("out_start") is not None for s in j2), "dubbing segments exist", str(len(j2)))

    # 720p chosen afterwards -> downloaded again so the MP4 really is 720p
    r = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [], "output": {"sync": "fit", "video": True, "orig_volume": 25, "duck": True, "max_height": 720}})
    j = srv.wait_job(jid, 600)
    v = j["meta"].get("video") or {}
    c.check(j["status"] == "done" and v.get("height") == 720 and v.get("limit") == 720, "Regenerate with 720p -> the video is downloaded again at 720p", str(v) + str(j.get("error")))
    srv.api("GET", f"/api/jobs/{jid}/file/dubbed.mp4")
    (WORK / "yt_out720.mp4").write_bytes(srv.api("GET", f"/api/jobs/{jid}/file/dubbed.mp4", timeout=120).content)
    i720 = audio.probe_media(WORK / "yt_out720.mp4")
    c.check(i720["height"] == 720, "…and the exported MP4 is 720p", str(i720))
    # same limit again -> reused (fast), 1080p again -> downloaded again
    t1 = time.time()
    srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [], "output": {"sync": "fit", "video": True, "orig_volume": 25, "duck": True, "max_height": 720}})
    j = srv.wait_job(jid, 300)
    c.check(j["status"] == "done" and (j["meta"].get("video") or {}).get("height") == 720, "same limit again: reused", str(j.get("error")))
    srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [], "output": {"sync": "fit", "video": True, "orig_volume": 25, "duck": True}})
    j = srv.wait_job(jid, 300)
    c.check(j["status"] == "done" and (j["meta"].get("video") or {}).get("height") == 720, "a request without max_height keeps the job's last choice (720p)", str((j["meta"].get("video"), j.get("error"))))
    srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [], "output": {"sync": "fit", "video": True, "orig_volume": 25, "duck": True, "max_height": 1080}})
    j = srv.wait_job(jid, 600)
    c.check(j["status"] == "done" and (j["meta"].get("video") or {}).get("height") == 1080, "1080p again -> downloaded again at 1080p", str((j["meta"].get("video"), j.get("error"))))
    # a NEW job without max_height gets the default
    body2 = dict(body, output={"sync": "fit", "video": True, "orig_volume": 0, "duck": True})
    jid2 = srv.api("POST", "/api/jobs/dub", json=body2).json()["id"]
    j = srv.wait_job(jid2, 600)
    c.check(j["status"] == "done" and (j["meta"].get("video") or {}).get("height") == 1080, "a new job without max_height uses the default (1080p)", str((j["meta"].get("video"), j.get("error"))))

    # ---- copy / paste translation (Claude): a draft from YouTube downloads nothing; the MP4 is built when the audio is generated
    bodyd = dict(body, translate={"engine": "manual", "keep_terms": True}, output={"sync": "fit", "video": True, "orig_volume": 0, "duck": True, "max_height": 480})
    t2 = time.time()
    jidd = srv.api("POST", "/api/jobs/dub", json=bodyd).json()["id"]
    jd = srv.wait_job(jidd, 300)
    c.check(jd["status"] == "done" and jd["meta"].get("draft") and set(jd["outputs"]) == {"original.srt"} and all(s["km"] == "" for s in jd["segments"]),
            "manual draft from YouTube: subtitles only (no translation, no audio)", f"{jd['status']} {jd.get('error')} {sorted(jd['outputs'])}")
    c.check(time.time() - t2 < 120 and not (data / "jobs" / jidd / "video").exists() and not any("downloading" in x.lower() or x.startswith("Video:") for x in jd["logs"]),
            "manual draft from YouTube: no video was downloaded yet", f"{time.time() - t2:.0f}s")
    c.check(jd["video"] and jd["video"]["id"] == "dQw4w9WgXcQ" and len(jd["segments"]) > 20, "manual draft from YouTube: the video is known (for the MP4 later) and the lines are there", str(len(jd["segments"])))
    pr = srv.api("POST", f"/api/jobs/{jidd}/translation/prompt", json={"size": 20}).json()
    c.check(pr["parts"] >= 2 and "Video title: yt test" in pr["text"] and pr["lines_text"].startswith("1. "), "manual draft from YouTube: the prompt names the video and splits into parts", str(pr["parts"]))
    edits = [{"idx": sg["idx"], "km": f"ជួរទី {sg['idx'] + 1} ជាមួយ API"} for sg in jd["segments"]]
    srv.api("POST", f"/api/jobs/{jidd}/regenerate", json={"segments": edits, "output": {"sync": "fit", "video": True, "orig_volume": 0, "duck": True, "max_height": 480}})
    jd = srv.wait_job(jidd, 900)
    v = jd["meta"].get("video") or {}
    c.check(jd["status"] == "done" and "draft" not in jd["meta"] and "dub.mp3" in jd["outputs"] and "dubbed.mp4" in jd["outputs"] and 0 < (v.get("height") or 0) <= 480,
            "manual draft from YouTube: 'Generate audio' builds the dub AND the MP4 (<= 480p)", f"{jd['status']} {jd.get('error')} {v} {jd.get('warnings')}")
finally:
    srv.stop()
sys.exit(c.done())
