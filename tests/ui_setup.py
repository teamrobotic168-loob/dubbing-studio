"""Builds the data folder + server used by the UI tests: the finished jobs of the API test + the 3 demo jobs of the project
+ a copy of the dubbing job that pretends to come from a YouTube video (so the 'speaker in the video' voice is offered)."""
import json
import shutil
import subprocess
import sys

from lib import *  # noqa: F401,F403

def audio_ffmpeg():
    from app import audio
    return audio.ffmpeg_exe()


VIDEO_JOB = "feed00000a"
EXTEND_JOB = "feed00000b"
DRAFT_JOB = "feed00000c"
MP3_JOB = "feed00000d"


def _youtube(title):
    return {"id": "dQw4w9WgXcQ", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": title, "channel": "x",
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg", "duration": 80}


def build(port=8012, name="ui", extra=False):
    data = WORK / f"data_{name}"
    shutil.rmtree(data, ignore_errors=True)
    (data / "jobs").mkdir(parents=True)
    src = WORK / "data_api" / "jobs"             # the finished jobs of test_api (run it first; a suite also works without them)
    for d in (src.iterdir() if src.exists() else []):
        shutil.copytree(d, data / "jobs" / d.name)
    for d in FIXTURE_JOBS.iterdir():            # the three demo jobs
        shutil.copytree(d, data / "jobs" / d.name)
    # a "YouTube" job
    def _made_by_test_api(d):
        j = json.loads((d / "job.json").read_text())
        return j["kind"] == "dub" and not j["title"].startswith("Sample")
    new = next((d for d in (data / "jobs").iterdir() if _made_by_test_api(d)), None) or sorted((data / "jobs").iterdir())[0]   # no test_api data: a demo job
    clone = data / "jobs" / VIDEO_JOB
    shutil.copytree(new, clone)
    j = json.loads((clone / "job.json").read_text())
    j["id"] = VIDEO_JOB
    j["title"] = "Fixture video"
    j["video"] = _youtube("Fixture video")
    # a playable "dubbed.mp4" (Chromium of the test machine has no H.264 decoder, so the file is really WebM VP8 + Vorbis; browsers detect the
    # format from the content, not from the name) - 80 s, tiny
    subprocess.run([audio_ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x90:r=5:d=80", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                    "-t", "80", "-c:v", "libvpx", "-b:v", "40k", "-c:a", "libvorbis", "-f", "webm", str(clone / "dubbed.mp4")], check=True)
    j["outputs"]["dubbed.mp4"] = "dubbed.mp4"
    j["meta"]["video"] = {"width": 1920, "height": 1080, "codec": "h264", "limit": 1080}
    (clone / "job.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    # a hand-made job with exact numbers (to test the "extend" button: free time before / after a line)
    ext = data / "jobs" / EXTEND_JOB
    shutil.copytree(new, ext)
    j = json.loads((ext / "job.json").read_text())
    j["id"], j["title"], j["video"] = EXTEND_JOB, "Fixture extend", None
    rows = [  # (start, end, natural duration of the Khmer audio)
        (1.0, 3.0, 1.0), (5.0, 9.0, 5.0), (9.5, 12.0, 2.9), (12.2, 14.0, 4.0), (14.3, 16.0, 7.0), (20.0, 22.0, 1.0)]
    segs = []
    for i, (a, b, d) in enumerate(rows):
        nxt = rows[i + 1][0] - 0.10 if i + 1 < len(rows) else b + 3.9
        need = d / max(0.6, nxt - a)
        speed = min(need * 1.03, 1.4) if need > 1.05 else 1.0
        segs.append({"idx": i, "start": a, "end": b, "en": f"English line {i + 1}", "km": "ឃ្លាខ្មែរទី " + str(i + 1) + " " + "ក" * 20,
                     "slot": [a, round(nxt, 3)], "out_start": a, "out_end": round(a + d / speed, 3), "speed": round(speed, 2), "dur": d})
    j["segments"] = segs
    j["meta"].update({"source_end": 22.0, "audio_duration": 25.0, "row_voices": 0, "row_times": 0})
    (ext / "job.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    if extra:     # two more YouTube jobs (test_clickplay): "MP3 only" (the Khmer audio, no MP4) and a "Translate with Claude" draft
        mp = data / "jobs" / MP3_JOB
        shutil.copytree(new, mp)
        j = json.loads((mp / "job.json").read_text())
        j["id"], j["title"], j["video"] = MP3_JOB, "Fixture MP3 only", _youtube("Fixture MP3 only")
        j["outputs"] = {k: v for k, v in j["outputs"].items() if k != "dubbed.mp4"}
        (mp / "job.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        # the draft of a YouTube video: the subtitles are read, there is no audio yet, the Khmer boxes are empty
        dr = data / "jobs" / DRAFT_JOB
        dr.mkdir(parents=True)
        j = json.loads((new / "job.json").read_text())
        j["id"], j["title"], j["status"], j["video"] = DRAFT_JOB, "Fixture draft", "done", _youtube("Fixture draft")
        j["outputs"] = {"original.srt": "original.srt"}
        j["meta"] = {"transcript": {"source": "manual", "timed": True, "language": "en"}, "timed": True, "source_end": 75.05, "src_lang": "en", "draft": True}
        j["segments"] = [{"idx": s["idx"], "start": s["start"], "end": s["end"], "en": s["en"], "km": ""} for s in j["segments"]]
        j["params"] = dict(j.get("params") or {}, output={"sync": "fit", "video": False})
        def _ts(x):
            return "%02d:%02d:%02d,%03d" % (int(x // 3600), int(x // 60) % 60, int(x) % 60, round((x - int(x)) * 1000))
        (dr / "original.srt").write_text("".join(f"{k + 1}\n{_ts(s['start'])} --> {_ts(s['end'])}\n{s['en']}\n\n" for k, s in enumerate(j["segments"])), encoding="utf-8")
        (dr / "job.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    home = make_stub_home(WORK / f"voxhome_{name}")
    srv = Server(port, data, home, name=name).start()
    srv.new_job_id = new.name
    srv.video_job_id = VIDEO_JOB
    srv.extend_job_id = EXTEND_JOB
    srv.draft_job_id = DRAFT_JOB if extra else None
    srv.mp3_job_id = MP3_JOB if extra else None
    return srv
