"""v1.7.0 - translate with Claude by copy / paste:  the parser + prompt (units), draft jobs + the two endpoints (API, real Edge TTS),
the editor panel (UI: Playwright / Chromium)."""
import json
import os
import re
import shutil
import sys

from lib import *  # noqa: E402,F401,F403

WORK.mkdir(parents=True, exist_ok=True)
os.environ["KDS_DATA_DIR"] = str(WORK / "data_claude_units")
from app import manualtr as M  # noqa: E402

c = Checker("Translate with Claude (copy / paste)")
SHOTS = WORK / "shots"
SHOTS.mkdir(exist_ok=True)


def srt_of(n, secs=3):
    def ts(t):
        return f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(round((t - int(t)) * 1000)):03}"
    return "\n".join(f"{i + 1}\n{ts(i * secs)} --> {ts(i * secs + secs - 0.2)}\nThis is line number {i + 1} about the API and the Dashboard.\n" for i in range(n))


def reply_of(nums, fence=True, tail=""):
    body = "\n".join(f"{n}. ជួរទី {n} ជាមួយ API និង Dashboard" for n in nums)
    return ("Here is the translation:\n\n```text\n" + body + "\n```\n" + tail) if fence else body


# =================================================================================== A. units: the parser
segs12 = [{"idx": i, "en": f"Line number {i + 1} about the API and Python.", "km": ""} for i in range(12)]


def parse(text, total=12, first=None, last=None):
    return M.parse_reply(text, total, first, last)


def nums_of(r):
    return [it["idx"] + 1 for it in r["items"]]


r = parse(reply_of(range(1, 13)), 12, 1, 12)
c.check(r["count"] == 12 and nums_of(r) == list(range(1, 13)) and r["missing"] == [] and r["items"][0] == {"idx": 0, "km": "ជួរទី 1 ជាមួយ API និង Dashboard"},
        "parser: a normal answer in a code block (chatter before / after is ignored)", str(r["count"]))
r = parse("```text\n1. សួស្តី\n2. ជំរាបសួរ\n3. អរគុណ")
c.check(nums_of(r) == [1, 2, 3], "parser: a code block that was never closed (the chat was cut off) is still read")
r = parse("1) ក\n2: ខ\n3 - គ\n[4] ឃ\n(5) ង\n6។ ច\n7| ឆ\n8\tជ\nLine 9: ឈ\nជួរទី 10: ញ\n១១. ដ\n១២．ឋ")
c.check(nums_of(r) == list(range(1, 13)) and r["items"][11]["km"] == "ឋ", "parser: 1) 1: 1 - [1] (1) 1។ 1| tab · Line 1: · ជួរទី 1: · Khmer / full-width digits",
        str(nums_of(r)))
r = parse("**1.** ក\n**2**. **ខ** គ\n- 3. ឃ\n* **4.** ង\n`5.` ច")
c.check(nums_of(r) == [1, 2, 3, 4, 5] and r["items"][0]["km"] == "ក" and r["items"][1]["km"] == "ខ គ" and r["items"][4]["km"] == "ច",
        "parser: markdown (**1.**, bullets, backticks) is removed", json.dumps(r["items"], ensure_ascii=False))
r = parse("1. ប្រើ __init__ ក្នុង Python\n2. ពាក្យ `API` និង **Dashboard**")
c.check(r["items"][0]["km"] == "ប្រើ __init__ ក្នុង Python" and r["items"][1]["km"] == "ពាក្យ API និង Dashboard", "parser: bold / code ticks go, a real __init__ stays")
r = parse("1. ឃ្លាវែងមួយ\nបន្តនៅបន្ទាត់ក្រោម\n2. ឃ្លាបន្ទាប់\n\nNote: I kept the terms in English.\n3. ឃ្លាទីបី")
c.check(r["items"][0]["km"] == "ឃ្លាវែងមួយ បន្តនៅបន្ទាត់ក្រោម" and r["items"][1]["km"] == "ឃ្លាបន្ទាប់" and r["ignored"] == 1 and nums_of(r) == [1, 2, 3],
        "parser: a wrapped line is joined; a comment after a blank line is not glued on", json.dumps(r, ensure_ascii=False)[:200])
r = parse("1. ក\n2. ខ\n2. គ\n3. ឃ")
c.check(r["duplicates"] == [2] and r["items"][1]["km"] == "គ", "parser: a repeated number -> the last one wins and it is reported")
r = parse("0. ក\n1. ខ\n13. គ\n99. ឃ\n12. ង")
c.check(nums_of(r) == [1, 12] and r["unknown"] == [0, 13, 99], "parser: numbers outside the job are skipped and reported", str(r["unknown"]))
r = parse("1. ក\nតម្លៃ\n1.5 លាន ដុល្លារ\n2. ខ")
c.check(nums_of(r) == [1, 2] and "1.5 លាន" in r["items"][0]["km"], "parser: '1.5 million' inside a wrapped line is not a new item", json.dumps(r["items"], ensure_ascii=False))
r = parse("2. ខ\n3. គ\n5. ង\n7. ច", 12, 1, 8)
c.check(r["missing"] == [1, 4, 6, 8] and r["range"] == [2, 7] and r["expected"] == [1, 8], "parser: which lines of the asked range are missing", str(r["missing"]))
r = parse("1. ក\n2.\n3. គ", 12, 1, 3)
c.check(nums_of(r) == [1, 3] and r["missing"] == [2], "parser: an empty item counts as missing")
r = parse("ក\nខ\nគ", 12, 4, 6)
c.check(r["positional"] and nums_of(r) == [4, 5, 6] and r["items"][0]["km"] == "ក", "parser: no numbers but exactly the asked number of lines -> matched by order")
r = parse("Here you go:\n```\nក\nខ\nគ\n```", 12, 4, 6)
c.check(r["positional"] and nums_of(r) == [4, 5, 6], "parser: ... also when the lines are inside a code block with a preamble")
r = parse("ក\nខ", 12, 4, 6)
c.check(r["count"] == 0 and not r["positional"], "parser: no numbers and a different number of lines -> nothing is guessed")
r = parse("1. Hello world\n2. ជំរាបសួរ\n3. 2024\n4. API", 12)
c.check(r["no_khmer"] == [1, 4], "parser: lines without any Khmer letter are flagged (digits only is fine)", str(r["no_khmer"]))
r = parse("1. ក\r\n2. ខ\r\n3. គ\r\n")
c.check(nums_of(r) == [1, 2, 3], "parser: Windows line ends")
r = parse("```text\n1. ក\n2. ខ\n```\n\nPart two:\n\n```\n3. គ\n4. ឃ\n```")
c.check(nums_of(r) == [1, 2, 3, 4], "parser: two code blocks are read together")
r = parse("Some preamble\n3. គ\n1. ក\n2. ខ\nThanks!")
c.check(nums_of(r) == [1, 2, 3] and r["items"][2]["km"] == "គ" and r["items"][1]["km"] == "ខ Thanks!", "parser: any order is fine (without a code block a closing sentence directly under the last line is glued to it - the known limit)", json.dumps(r["items"], ensure_ascii=False))
r = parse("```text\n1. ក\n2. ខ\n```\nThanks!")
c.check(r["items"][1]["km"] == "ខ", "parser: ... but with a code block the closing sentence is never part of a line")
r = parse(reply_of(range(1, 41), tail="Let me know!"), 40, 1, 40)
c.check(r["count"] == 40 and r["missing"] == [], "parser: 40 lines")
for bad in (None, 5, ["x"]):
    try:
        M.parse_reply(bad, 5)
        ok = False
    except ValueError:
        ok = True
    c.check(ok, f"parser: {bad!r} is rejected")
try:
    M.parse_reply("x" * (M.MAX_REPLY_CHARS + 1), 5)
    ok = False
except ValueError:
    ok = True
c.check(ok, "parser: an answer of more than 400,000 characters is rejected")
c.check(M.parse_reply("", 5)["count"] == 0 and M.parse_reply("   \n\n", 5)["items"] == [], "parser: an empty answer gives nothing")

# =================================================================================== A. units: parts + prompt
c.check(M.plan(50, 20) == (20, 3) and M.plan(50, 0) == (0, 1) and M.plan(50, 80) == (80, 1) and M.plan(0, 20) == (20, 1) and M.plan(40, 40) == (40, 1) and M.plan(41, 40) == (40, 2),
        "parts: plan(total, size)")
c.check([M.part_range(50, 20, p) for p in (1, 2, 3, 4, 0)] == [(0, 20), (20, 40), (40, 50), (40, 50), (0, 20)] and M.part_range(50, 0, 1) == (0, 50),
        "parts: part_range (a part beyond the last is the last, 'all' = one part)")
c.check(M.clean_size("x") == 40 and M.clean_size(None) == 40 and M.clean_size(-5) == 0 and M.clean_size(2) == 5 and M.clean_size(9999) == 300 and M.clean_size("20") == 20, "parts: clean_size")

big = [{"idx": i, "en": f"Line {i + 1}\nabout the API", "km": ""} for i in range(50)]
p = M.build_prompt(big, "en", "My course", part=2, size=20)
txt = p["text"]
c.check(p["part"] == 2 and p["parts"] == 3 and p["first"] == 21 and p["last"] == 40 and p["total"] == 50 and p["chars"] == len(txt), "prompt: part 2 of 3 = lines 21-40", str({k: v for k, v in p.items() if k != "text"}))
body_lines = [ln for ln in txt.split("\n") if re.match(r"^\d+\. Line ", ln)]
c.check(len(body_lines) == 20 and body_lines[0].startswith("21. Line 21 about the API") and body_lines[-1].startswith("40. "), "prompt: the numbered lines use the numbers of the table (a source line is one line)")
c.check("part 2 of 3" in txt and "lines 21-40 of 50" in txt and "Video title: My course" in txt and "English subtitle lines" in txt, "prompt: part / title / language are told")
c.check("Output format" in txt and "ONE code block" in txt and "21. <Khmer translation of line 21>" in txt and "22. <Khmer translation of line 22>" in txt, "prompt: the answer format shows the right numbers")
c.check("Keep exactly the same line numbers" in txt and "(Latin letters)" in txt and "Keep people's, character's and place names in Latin letters" in txt, "prompt: rules (numbers, English terms, names in Latin)")
c.check("must stay exactly as written: API" in txt and p["terms"] == ["API"], "prompt: the terms found in the part are listed", str(p["terms"]))
c.check(p["instructions"].startswith("You are an expert") and "This is part 2 of 3" in p["instructions"] and "Line 21" not in p["instructions"] and p["lines_text"].startswith("21. Line 21 about the API\n22. ") and p["lines_text"].endswith("40. Line 40 about the API\n")
        and p["text"] == p["instructions"] + "\nSubtitle lines (part 2 of 3, lines 21-40 of 50):\n" + p["lines_text"] + "\n(End of the lines. Reply now with the code block only.)\n",
        "prompt: the two halves - the instructions alone, the numbered lines alone - add up to the whole text")
p2 = M.build_prompt(big, "en", "1", part=1, size=0, names="khmer")
c.check(p2["parts"] == 1 and p2["first"] == 1 and p2["last"] == 50 and "Video title" not in p2["text"] and "Write people's and character names in Khmer letters" in p2["text"] and "This is part" not in p2["text"],
        "prompt: all lines in one message, a junk title ('1') is left out, names in Khmer letters", str({k: v for k, v in p2.items() if k != "text"}))
p3 = M.build_prompt(big, "en", "", part=1, size=20, keep_terms=False)
c.check("Translate everything into Khmer" in p3["text"] and "must stay exactly as written" not in p3["text"] and p3["terms"] == [], "prompt: 'keep terms' off -> translate everything")
zh = [{"idx": 0, "en": "我们的服务器运行在 Docker 上", "km": ""}, {"idx": 1, "en": "你好", "km": ""}]
p4 = M.build_prompt(zh, "zh", "")
c.check("Chinese subtitle lines" in p4["text"] and "服务器 → server" in p4["terms"] and "Write these source words in English" in p4["text"] and "Docker" in p4["terms"], "prompt: Chinese - the word -> English form is listed", str(p4["terms"]))
ko = [{"idx": 0, "en": "서버를 배포합니다", "km": ""}]
p5 = M.build_prompt(ko, "ko", "")
c.check("Korean subtitle lines" in p5["text"] and any(t.endswith("→ server") for t in p5["terms"]), "prompt: Korean - the word -> English form is listed", str(p5["terms"]))
c.check(M.build_prompt(big, "xx", "")["lang"] == "en" and M.build_prompt(big, "en", "", names="zzz")["names"] == "latin" and M.build_prompt([], "en", "")["total"] == 0,
        "prompt: unknown language / names fall back; an empty job does not crash")
c.check(M.good_title("Intro to the API") == "Intro to the API" and M.good_title("1") == "" and M.good_title("00:01 --> 00:03") == "" and M.good_title("ab") == "", "prompt: good_title")

# the round trip: whatever the prompt asks for, the parser reads back
asked = M.build_prompt(big, "en", "", part=3, size=20)
echo = "```text\n" + "\n".join(f"{n}. ខ្មែរ {n}" for n in range(asked["first"], asked["last"] + 1)) + "\n```"
rt = M.parse_reply(echo, 50, asked["first"], asked["last"])
c.check(rt["count"] == 10 and rt["missing"] == [] and rt["range"] == [41, 50], "round trip: the answer to the last part is read completely")

# =================================================================================== B. API: draft jobs
WORKDATA = WORK / "data_claude"
shutil.rmtree(WORKDATA, ignore_errors=True)
srv = Server(8032, WORKDATA, make_stub_home(WORK / "voxhome_claude"), name="claude").start()
errors = []
try:
    sample = (PROJECT / "samples" / "technical-tutorial.srt").read_text(encoding="utf-8")
    body = {"source": {"type": "transcript", "text": sample, "title": "Draft sample", "lang": "auto"}, "voice": {"id": "km-KH-SreymomNeural", "engine": "edge"},
            "translate": {"engine": "manual", "keep_terms": True}, "output": {"sync": "fit", "video": False}}
    t0 = time.time()
    jid = srv.api("POST", "/api/jobs/dub", json=body).json()["id"]
    j = srv.wait_job(jid, 60)
    c.check(j["status"] == "done" and time.time() - t0 < 30, "draft: the job finishes by itself right after the subtitles are read (no translation, no audio)", f"{j['status']} {time.time() - t0:.1f}s")
    n = len(j["segments"])
    c.check(j["meta"].get("draft") is True and n == 12 and all(s["km"] == "" for s in j["segments"]), "draft: meta.draft, every Khmer line is empty", str(j["meta"]))
    c.check(set(j["outputs"]) == {"original.srt"}, "draft: the only file is the original subtitle", str(j["outputs"]))
    st = {s["key"]: s["status"] for s in j["steps"]}
    c.check(st == {"transcript": "done", "speakers": "skipped", "translate": "skipped", "tts": "skipped", "mix": "skipped", "video": "skipped"}, "draft: steps - transcript done, the rest skipped (speakers too: a pasted transcript has no sound)", str(st))
    c.check(any("Draft:" in ln for ln in j["logs"]) and j["params"]["translate"]["engine"] == "manual", "draft: the log explains it; the request is stored with engine 'manual'")
    srt = srv.api("GET", f"/api/jobs/{jid}/file/original.srt").text
    c.check("Welcome back to the channel" in srt, "draft: original.srt can be downloaded")
    lst = srv.api("GET", "/api/jobs").json()["jobs"]
    c.check(any(x["id"] == jid and x["meta"].get("draft") for x in lst), "draft: the History list carries meta.draft")

    # ---- the prompt
    pr = srv.api("POST", f"/api/jobs/{jid}/translation/prompt", json={}).json()
    c.check(pr["part"] == 1 and pr["parts"] == 1 and pr["first"] == 1 and pr["last"] == 12 and pr["total"] == 12 and "1. Welcome back to the channel" in pr["text"], "prompt API: defaults = all 12 lines in one part")
    c.check(pr["lines_text"].startswith("1. Welcome back to the channel") and pr["lines_text"].count("\n") == 12 and pr["instructions"].startswith("You are an expert") and "Welcome back" not in pr["instructions"],
            "prompt API: 'instructions' and 'lines_text' are returned separately")
    pr = srv.api("POST", f"/api/jobs/{jid}/translation/prompt", json={"size": 5, "part": 2, "names": "khmer"}).json()
    c.check(pr["parts"] == 3 and pr["first"] == 6 and pr["last"] == 10 and "Khmer letters" in pr["text"] and "\n6. " in pr["text"] and "\n5. " not in pr["text"].split("Subtitle lines")[1], "prompt API: size 5, part 2 = lines 6-10")
    pr = srv.api("POST", f"/api/jobs/{jid}/translation/prompt", json={"size": 5, "part": 99}).json()
    c.check(pr["part"] == 3 and pr["first"] == 11 and pr["last"] == 12, "prompt API: a part beyond the last is the last")
    pr = srv.api("POST", f"/api/jobs/{jid}/translation/prompt", json={"size": 0}).json()
    c.check(pr["parts"] == 1 and pr["last"] == 12, "prompt API: size 0 = everything")
    pr = srv.api("POST", f"/api/jobs/{jid}/translation/prompt", json={"size": "abc", "part": "x", "names": 5}).json()
    c.check(pr["size"] == 40 and pr["part"] == 1, "prompt API: nonsense values fall back to the defaults")
    c.check(srv.api("POST", "/api/jobs/nope/translation/prompt", json={}).status_code == 404, "prompt API: unknown job -> 404")

    # ---- reading the answer
    rp = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": reply_of(range(1, 13)), "first": 1, "last": 12}).json()
    c.check(rp["count"] == 12 and rp["missing"] == [] and rp["items"][11]["idx"] == 11, "parse API: all 12 lines")
    rp = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": reply_of([1, 2, 3, 5, 6]), "first": 1, "last": 6}).json()
    c.check(rp["missing"] == [4] and rp["count"] == 5, "parse API: missing line 4")
    rp = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": "ក\nខ\nគ", "first": 4, "last": 6}).json()
    c.check(rp["positional"] and [i["idx"] for i in rp["items"]] == [3, 4, 5], "parse API: by order")
    rp = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": reply_of([1, 2, 99])}).json()
    c.check(rp["unknown"] == [99] and rp["count"] == 2, "parse API: number 99 is not a line of this job")
    r_ = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": "   "})
    c.check(r_.status_code == 400 and r_.json()["detail"]["code"] == "EMPTY_REPLY", "parse API: an empty answer -> 400 EMPTY_REPLY")
    r_ = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": 5})
    c.check(r_.status_code == 400, "parse API: not text -> 400")
    r_ = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": "x" * 400_001})
    c.check(r_.status_code == 400 and r_.json()["detail"]["code"] == "BAD_REQUEST", "parse API: too long -> 400")
    c.check(srv.api("POST", "/api/jobs/nope/translation/parse", json={"text": "1. x"}).status_code == 404, "parse API: unknown job -> 404")
    rp = srv.api("POST", f"/api/jobs/{jid}/translation/parse", json={"text": reply_of([1, 2]), "first": "1", "last": None}).json()
    c.check(rp["expected"] is None and rp["count"] == 2, "parse API: first / last that are not integers are ignored")

    # ---- a draft with no Khmer text cannot be generated
    r_ = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": []})
    c.check(r_.status_code == 400 and r_.json()["detail"]["code"] == "NO_KHMER_TEXT", "regenerate: a draft without any Khmer text -> 400 NO_KHMER_TEXT", r_.text[:120])
    r_ = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [{"idx": 0, "km": "   "}]})
    c.check(r_.status_code == 400, "regenerate: ... blank text does not count")

    # ---- saving pasted lines into a draft (so a reload / crash does not lose them)
    sv = srv.api("POST", f"/api/jobs/{jid}/translation/save", json={"items": [{"idx": 0, "km": "  ជួរទី 1 សាកល្បង  "}, {"idx": 11, "km": "ជួរទី 12 សាកល្បង"}]})
    c.check(sv.status_code == 200 and sv.json() == {"saved": 2, "filled": 2}, "save API: two lines saved into the draft", sv.text[:100])
    jj = srv.api("GET", f"/api/jobs/{jid}").json()
    c.check(jj["segments"][0]["km"] == "ជួរទី 1 សាកល្បង" and jj["segments"][11]["km"] == "ជួរទី 12 សាកល្បង" and jj["segments"][5]["km"] == "" and jj["meta"].get("draft"), "save API: stored (trimmed) in the job; other lines untouched; still a draft")
    on_disk = json.loads((WORKDATA / "jobs" / jid / "job.json").read_text(encoding="utf-8"))
    c.check(on_disk["segments"][0]["km"] == "ជួរទី 1 សាកល្បង", "save API: written to job.json (survives a server restart)")
    for label, payload in [("not a list", {"items": "x"}), ("no items", {}), ("idx out of range", {"items": [{"idx": 99, "km": "x"}]}), ("idx is a bool", {"items": [{"idx": True, "km": "x"}]}),
                           ("km is not text", {"items": [{"idx": 0, "km": 5}]}), ("an item that is not an object", {"items": ["x"]}), ("more items than lines", {"items": [{"idx": 0, "km": "x"}] * 13})]:
        r_ = srv.api("POST", f"/api/jobs/{jid}/translation/save", json=payload)
        c.check(r_.status_code == 400 and r_.json()["detail"]["code"] == "BAD_REQUEST", f"save API: {label} -> 400", r_.text[:80])
    c.check(srv.api("POST", "/api/jobs/nope/translation/save", json={"items": []}).status_code == 404, "save API: unknown job -> 404")
    # a draft that is only partly filled can still be generated: the other lines stay silent
    r_ = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": [], "voice": {"engine": "edge", "id": "km-KH-SreymomNeural"}})
    c.check(r_.status_code == 200, "regenerate: the saved lines are enough (no edits sent)", r_.text[:100])
    jp = srv.wait_job(jid, 240)
    c.check(jp["status"] == "done" and "draft" not in jp["meta"] and sum(1 for s_ in jp["segments"] if s_["out_start"] is not None) == 2, "partly filled draft: audio for the 2 saved lines, the other 10 stay silent", f"{jp['status']} {jp.get('error')}")
    r_ = srv.api("POST", f"/api/jobs/{jid}/translation/save", json={"items": [{"idx": 0, "km": "x"}]})
    c.check(r_.status_code == 409 and r_.json()["detail"]["code"] == "NOT_DRAFT", "save API: a finished dub is not a draft -> 409 NOT_DRAFT", r_.text[:100])
    # (the job above is a normal dub now; the next draft is used for the other API checks)
    jid = srv.wait_job(srv.api("POST", "/api/jobs/dub", json=body).json()["id"], 60)["id"]

    # ---- error recovery: a failed first attempt keeps the draft (and the pasted text) reachable
    def failed_draft(title):
        jid_ = srv.api("POST", "/api/jobs/dub", json={**body, "source": {**body["source"], "title": title}}).json()["id"]
        srv.wait_job(jid_, 60)
        edits = [{"idx": i, "km": f"ជួរទី {i + 1}"} for i in range(n)]
        srv.api("POST", f"/api/jobs/{jid_}/regenerate", json={"segments": edits, "voice": {"engine": "voxcpm", "vox": {"id": "vox:original", "quality": "fast", "consent": True}}})
        return jid_, srv.wait_job(jid_, 90)

    jid_err, je = failed_draft("Draft that failed A")
    c.check(je["status"] == "error" and je["meta"].get("draft") is True and "dub.mp3" not in je["outputs"],
            "recovery: the first attempt failed (no video for 'speaker in the video') -> still a draft", f"{je['status']} {je.get('error')} {je['meta'].get('draft')}")
    c.check(all(s_["km"].startswith(f"ជួរទី {i + 1}") for i, s_ in enumerate(je["segments"])), "recovery: ... and the pasted Khmer text was kept", je["segments"][0]["km"])
    r_ = srv.api("POST", f"/api/jobs/{jid_err}/regenerate", json={"segments": [], "voice": {"engine": "edge", "id": "km-KH-PisethNeural"}})
    c.check(r_.status_code == 200, "recovery: the kept text is enough to try again (no new edits needed)")
    je = srv.wait_job(jid_err, 240)
    c.check(je["status"] == "done" and "draft" not in je["meta"] and "dub.mp3" in je["outputs"], "recovery: the second attempt builds the dub (draft flag gone)", f"{je['status']} {je.get('error')}")
    DRAFT_ERR, _ = failed_draft("Draft that failed B")          # stays failed: the UI test opens it

    # ---- generate the audio (real Edge TTS) from pasted text, as the editor does it
    edits = [{"idx": i, "km": f"ជួរទី {i + 1} ជាមួយ API"} for i in range(n)]
    r_ = srv.api("POST", f"/api/jobs/{jid}/regenerate", json={"segments": edits, "voice": {"engine": "edge", "id": "km-KH-PisethNeural"}})
    c.check(r_.status_code == 200, "regenerate: a draft accepts the pasted lines as edits")
    j = srv.wait_job(jid, 240)
    c.check(j["status"] == "done" and "draft" not in j["meta"] and "dub.mp3" in j["outputs"], "generate: audio built from the pasted text -> a real dub (draft flag gone)", f"{j['status']} {j.get('error')}")
    st = {s_["key"]: s_["status"] for s_ in j["steps"]}
    c.check(st["translate"] == "done" and st["tts"] == "done" and st["mix"] == "done", "generate: steps are done", str(st))
    ks = srv.api("GET", f"/api/jobs/{jid}/file/khmer.srt").text
    c.check("ជួរទី 1 " in ks and "ជួរទី 12 " in ks, "generate: khmer.srt has the pasted text")
    mp3 = srv.api("GET", f"/api/jobs/{jid}/file/dub.mp3")
    c.check(mp3.status_code == 200 and len(mp3.content) > 8000, "generate: dub.mp3 downloads", str(len(mp3.content)))
    pr = srv.api("POST", f"/api/jobs/{jid}/translation/prompt", json={}).json()
    c.check(pr["total"] == 12, "the panel still works on a finished dub (translate again with Claude)")

    # a second draft from the full engine path: engine 'manual' for a transcript job without timestamps
    plain = "First paragraph about the API.\n\nSecond paragraph about Python and the Dashboard."
    j2 = srv.wait_job(srv.api("POST", "/api/jobs/dub", json={**body, "source": {"type": "transcript", "text": plain, "lang": "en"}}).json()["id"], 60)
    c.check(j2["status"] == "done" and j2["meta"].get("draft") and j2["meta"]["timed"] is False and len(j2["segments"]) >= 1, "draft: plain text without timestamps works too", str(j2["meta"]))

    # engine 'manual' must not break the Text to Speech jobs (the UI never sends it there; the server treats it like Google)
    tj = srv.api("POST", "/api/jobs/tts", json={"text": "សួស្តី", "input_lang": "km", "voice": {"id": "km-KH-SreymomNeural", "engine": "edge"}, "translate": {"engine": "manual"}}).json()["id"]
    tjob = srv.wait_job(tj, 120)
    c.check(tjob["status"] == "done", "TTS job with translate.engine = manual still works (nothing to translate)", str(tjob.get("error")))
    c.check(srv.api("POST", f"/api/jobs/{tj}/translation/prompt", json={}).status_code == 400, "prompt API: a Text to Speech job has no subtitle lines -> 400")
    r_ = srv.api("POST", f"/api/jobs/{tj}/translation/parse", json={"text": "1. x"})
    c.check(r_.status_code == 400, "parse API: ... same")

    # =============================================================================== C. UI
    from playwright.sync_api import sync_playwright  # noqa: E402

    DIALOGS, DIALOG_ACCEPT = [], [True]

    def new_page(b, lang="en", theme="dark", w=1440, h=900):
        ctx = b.new_context(viewport={"width": w, "height": h}, permissions=["clipboard-read", "clipboard-write"])
        ctx.add_init_script(f"if(!localStorage.getItem('kds_lang')){{localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}');}}")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
        pg.on("dialog", lambda d: (DIALOGS.append(d.message), d.accept() if DIALOG_ACCEPT[0] else d.dismiss()))
        return ctx, pg

    def settings(pg):
        pg.wait_for_timeout(450)
        return json.loads(pg.evaluate("localStorage.getItem('kds_settings') || '{}'"))

    def rows_text(pg):
        return pg.evaluate("[...document.querySelectorAll('#dub-result .seg-row textarea')].map((t) => t.value)")

    def wait_copy_ready(pg):
        pg.wait_for_function("document.querySelector('#cl-copy') && !document.querySelector('#cl-copy').disabled", timeout=15000)

    def part_label(pg):
        return pg.locator("#cl-partlabel").inner_text()

    def start_draft(pg, srt, title=""):
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(900)
        pg.locator("#src-tabs [data-tab=transcript]").click()
        pg.fill("#tr-text", srt)
        if title:
            pg.fill("#tr-title", title)
        if not settings(pg).get("translate", {}).get("manual"):
            pg.locator("#manual-row .switch").click()
        pg.locator("#btn-generate").click()
        pg.wait_for_selector("#claude-box[open]", timeout=40000)
        wait_copy_ready(pg)
        pg.wait_for_timeout(300)

    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # ---------------------------------------------------------------- the switch in step 3
        ctx, pg = new_page(b)
        pg.goto(srv.url + "/#dub")
        pg.wait_for_timeout(1000)
        c.check(pg.locator("#manual-row").is_visible() and "Translate with Claude" in pg.locator("#manual-row").inner_text(), "step 3: a 'Translate with Claude (copy / paste)' row")
        c.check(not pg.locator("#manual-hint").is_visible() and pg.locator("#btn-generate span").inner_text() == "Generate Khmer dubbing" and "dim" not in (pg.locator("#card-translate .seg[data-bind='translate.engine']").get_attribute("class") or ""),
                "step 3: switched off -> normal button, engine buttons normal, no hint")
        pg.locator("#manual-row .switch").click()
        pg.wait_for_timeout(400)
        c.check(pg.locator("#manual-hint").is_visible() and "How it works" in pg.locator("#manual-hint").inner_text(), "step 3: switched on -> 'How it works' is shown")
        c.check(pg.locator("#btn-generate span").inner_text() == "Prepare lines for Claude", "step 3: ... the button says 'Prepare lines for Claude'")
        c.check("dim" in (pg.locator("#card-translate .seg[data-bind='translate.engine']").get_attribute("class") or ""), "step 3: ... the engine buttons are dimmed (not used)")
        c.check(settings(pg)["translate"]["manual"] is True and settings(pg)["translate"]["engine"] == "google", "step 3: remembered; the engine itself is untouched")
        pg.locator("#card-translate").scroll_into_view_if_needed()
        pg.screenshot(path=str(SHOTS / "claude_step3.png"))
        # the Text to Speech page is not affected
        pg.locator("#nav button[data-page=tts]").click()
        pg.wait_for_timeout(300)
        pg.locator(".seg[data-bind='tts.input_lang'] button[data-value=en]").click()
        pg.wait_for_timeout(300)
        c.check(pg.locator("#tts-engine-box").is_visible() and "dim" not in (pg.locator("#tts-engine-box .seg").get_attribute("class") or "")
                and pg.locator("#tts-engine-box [data-llm-warn]").is_hidden(), "Text to Speech page: its engine buttons are normal (the switch belongs to the Dubbing page)")
        tts_req = []
        pg.on("request", lambda r: tts_req.append(r) if r.method == "POST" and r.url.endswith("/api/jobs/tts") else None)
        pg.fill("#tts-text", "Hello everyone")
        pg.locator("#tts-generate").click()
        pg.wait_for_function("document.querySelector('#tts-result') && !document.querySelector('#tts-result').classList.contains('hidden')", timeout=120000)
        sent = json.loads(tts_req[0].post_data)
        c.check(sent["translate"]["engine"] == "google", "Text to Speech request never carries engine 'manual'", sent["translate"]["engine"])
        ctx.close()

        # ---------------------------------------------------------------- a 50-line draft: the panel, parts, copy, paste
        ctx, pg = new_page(b)
        dub_req = []
        pg.on("request", lambda r: dub_req.append(r) if r.method == "POST" and r.url.endswith("/api/jobs/dub") else None)
        start_draft(pg, srt_of(50), "Fifty lines")
        sent = json.loads(dub_req[0].post_data)
        c.check(sent["translate"]["engine"] == "manual", "draft (UI): the request carries engine 'manual'")
        c.check(pg.locator(".draft-box").is_visible() and "translate them with Claude" in pg.locator(".draft-box").inner_text(), "draft (UI): the banner 'subtitles are ready - translate them with Claude'")
        c.check(pg.locator("#dub-audio").count() == 0 and pg.locator("#dub-result .player-box").count() == 0 and pg.locator("#mp4-panel").count() == 0 and pg.locator("#btn-sync").count() == 0,
                "draft (UI): no audio player, no MP4 / Sync Preview yet")
        dl = pg.locator("#dub-result .draft-box a[download]")
        c.check(dl.count() == 1 and "original.srt" in (dl.first.get_attribute("href") or ""), "draft (UI): only the original subtitle can be downloaded")
        rows = pg.locator("#dub-result .seg-row")
        c.check(rows.count() == 50 and all(v == "" for v in rows_text(pg)), "draft (UI): 50 lines, all Khmer cells empty")
        c.check(pg.locator("#dirty-label").inner_text() == "50 of 50 lines have no Khmer text yet" and pg.locator("#btn-regen span").inner_text() == "Generate audio", "draft (UI): the bar says '50 of 50 lines have no Khmer text yet' and the button 'Generate audio'")
        c.check(pg.locator(".seg-table.no-audio").count() == 1 and pg.locator("#dub-result .seg-row .go").first.evaluate("(e) => getComputedStyle(e).visibility") == "hidden", "draft (UI): the per-line play buttons are hidden (nothing to play)")
        c.check(pg.locator("[data-sub=follow]").count() == 0, "draft (UI): no 'Follow playback' switch")
        c.check(pg.locator("[data-sub=clickplay]").count() == 0, "draft (UI): no 'Click line -> play' switch either (no video, no audio)")
        pg.locator("#dub-result .seg-row .en").first.click()
        pg.wait_for_timeout(300)
        c.check(pg.locator("#sync-panel").count() == 0 and pg.locator("#dub-result .seg-row.active").count() == 0, "draft (UI): a click on a line does nothing (there is nothing to play) - and breaks nothing")
        c.check(pg.locator("#claude-box").evaluate("(e) => e.open") and "Translate with Claude" in pg.locator("#claude-box > summary").inner_text(), "panel: open by default for a draft")
        c.check(part_label(pg) == "Part 1 / 2 · lines 1-40 of 50", "panel: default 40 lines per part -> Part 1 / 2 · lines 1-40 of 50", part_label(pg))
        c.check(pg.locator("#cl-prev").is_disabled() and not pg.locator("#cl-next").is_disabled(), "panel: previous is off on the first part")
        c.check(pg.locator("[data-cl-size='40']").evaluate("(e) => e.classList.contains('active')") and pg.locator("[data-cl-names='latin']").evaluate("(e) => e.classList.contains('active')"), "panel: 40 and Latin are the active options")
        c.check(pg.locator("#cl-open").get_attribute("href") == "https://claude.ai/new" and pg.locator("#cl-open").get_attribute("target") == "_blank" and "noopener" in (pg.locator("#cl-open").get_attribute("rel") or ""), "panel: 'Open claude.ai' opens a new tab safely")
        pg.locator("[data-cl-size='20']").click()
        pg.wait_for_function("document.querySelector('#cl-partlabel').textContent.includes('/ 3')", timeout=8000)
        c.check(part_label(pg) == "Part 1 / 3 · lines 1-20 of 50" and settings(pg)["claude"]["size"] == 20, "panel: 20 lines per part -> Part 1 / 3 · lines 1-20 of 50 (remembered)", part_label(pg))
        wait_copy_ready(pg)
        # copy
        pg.locator("#cl-copy").click()
        pg.wait_for_timeout(500)
        clip = pg.evaluate("navigator.clipboard.readText()")
        shown = pg.locator("#cl-prompt").input_value()
        c.check(clip == shown and clip.startswith("You are an expert subtitle translator") and "\n1. This is line number 1 about the API" in clip and "\n20. This is line number 20" in clip and "\n21. " not in clip,
                "copy: the clipboard holds the instructions + lines 1-20 (and not line 21)", clip[:60])
        c.check("must stay exactly as written: API, Dashboard" in clip and "Video title: Fifty lines" in clip, "copy: the terms of this part and the title are in it")
        c.check(pg.locator("#cl-copy span").inner_text() == "Copied ✔", "copy: the button says 'Copied ✔'")
        c.check(pg.locator("#cl-prompt").evaluate("(e) => e.readOnly"), "copy: the preview is read-only")
        pg.locator("#cl-copy-lines").click()
        pg.wait_for_timeout(400)
        clip2 = pg.evaluate("navigator.clipboard.readText()")
        c.check(clip2.startswith("1. This is line number 1 about the API") and clip2.rstrip().endswith("20. This is line number 20 about the API and the Dashboard.") and "You are an expert" not in clip2 and "\n21. " not in clip2 and "numbered lines (without instructions)" in pg.locator("#toasts").inner_text(),
                "copy only: 'Numbered lines' puts just lines 1-20 on the clipboard (for a Claude Project that already has the instructions)", clip2[:50])
        pg.locator("#cl-copy-rules").click()
        pg.wait_for_timeout(400)
        clip3 = pg.evaluate("navigator.clipboard.readText()")
        c.check(clip3.startswith("You are an expert") and "This is line number" not in clip3 and "ONE code block" in clip3 and "instructions (without the lines)" in pg.locator("#toasts").inner_text(), "copy only: 'Instructions' puts just the instructions on the clipboard", clip3[:40])
        pg.locator("[data-cl-names='khmer']").click()
        pg.wait_for_function("document.querySelector('#cl-prompt').value.includes('Khmer letters (transliterated)')", timeout=8000)
        c.check(settings(pg)["claude"]["names"] == "khmer", "names: 'Khmer letters' -> the prompt tells it (remembered)")
        pg.locator("[data-cl-names='latin']").click()
        pg.wait_for_function("document.querySelector('#cl-prompt').value.includes('place names in Latin letters')", timeout=8000)
        # nothing pasted yet: 'Generate audio' with every cell empty -> a message, no request
        regen_reqs = []
        pg.on("request", lambda r: regen_reqs.append(r.url) if r.method == "POST" and "/regenerate" in r.url else None)
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(600)
        c.check(not regen_reqs and "no Khmer text yet" in pg.locator("#toasts").inner_text(), "Generate audio with every cell empty -> a message and no request", pg.locator("#toasts").inner_text()[:80])
        # empty / nonsense
        pg.locator("#cl-apply").click()
        pg.wait_for_timeout(300)
        c.check("Paste Claude's answer first" in pg.locator("#cl-result").inner_text(), "apply: nothing pasted -> a hint")
        pg.fill("#cl-reply", "I cannot help with that.")
        pg.locator("#cl-apply").click()
        pg.wait_for_timeout(600)
        c.check("No numbered lines found" in pg.locator("#cl-result").inner_text() and all(v == "" for v in rows_text(pg)), "apply: an answer without numbers -> an explanation, the table is untouched")
        # only a few lines pasted: 'Generate audio' asks first (Cancel sends nothing)
        pg.fill("#cl-reply", reply_of([1, 2, 3]))
        pg.locator("#cl-apply").click()
        pg.wait_for_function("document.querySelector('#cl-result').textContent.includes('Saved in the draft')", timeout=8000)
        DIALOG_ACCEPT[0] = False
        DIALOGS.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_timeout(700)
        c.check(len(DIALOGS) == 1 and "47 line(s) have no Khmer text and will be silent" in DIALOGS[0] and not regen_reqs, "Generate audio with 3 of 50 lines filled -> the browser asks ('47 line(s) ... silent'); 'Cancel' sends nothing", str(DIALOGS))
        DIALOG_ACCEPT[0] = True
        pg.fill("#cl-reply", "")
        # part 1
        pg.fill("#cl-reply", reply_of(range(1, 21)))
        pg.locator("#cl-apply").click()
        pg.wait_for_function("document.querySelector('#cl-partlabel').textContent.startsWith('Part 2')", timeout=8000)
        tx = rows_text(pg)
        c.check(tx[0] == "ជួរទី 1 ជាមួយ API និង Dashboard" and tx[19].startswith("ជួរទី 20 ") and tx[20] == "" and sum(1 for v in tx if v) == 20, "apply: lines 1-20 are in the table, 21+ are still empty")
        res = pg.locator("#cl-result").inner_text()
        c.check("20 line(s) filled (lines 1-20)" in res and "Part 1 applied - next: part 2" in res, "apply: status '20 lines filled' and 'next: part 2'", res)
        c.check(part_label(pg) == "Part 2 / 3 · lines 21-40 of 50" and pg.locator("#cl-reply").input_value() == "", "apply: a complete part -> the next part is ready and the box is cleared", part_label(pg))
        jobs_ = srv.api("GET", "/api/jobs").json()["jobs"]
        fifty = next(x["id"] for x in jobs_ if x["title"] == "Fifty lines")
        saved_n = sum(1 for sg in srv.api("GET", f"/api/jobs/{fifty}").json()["segments"] if sg["km"])
        c.check("Saved in the draft" in res and saved_n == 20 and pg.locator("#dub-result .seg-row.dirty").count() == 0 and pg.locator("#dirty-label").inner_text() == "30 of 50 lines have no Khmer text yet" and pg.locator("#cl-progress").inner_text() == "In the table: 20 of 50 lines have Khmer text",
                "apply: the 20 lines are saved in the draft (on the server, not just in the page); the bar and the panel count what is left", f"{saved_n} saved")
        # part 2: the answer is cut and has a gap
        nums = [n for n in range(21, 39) if n not in (30, 31)]
        pg.fill("#cl-reply", reply_of(nums))
        pg.locator("#cl-apply").click()
        pg.wait_for_timeout(900)
        res = pg.locator("#cl-result").inner_text()
        c.check("16 line(s) filled" in res and "2 line(s) missing: 30, 31" in res and "stop at line 38" in res and "continue from line 39" in res, "apply: a gap (30, 31) and a cut answer (stops at 38) are explained", res)
        c.check(part_label(pg).startswith("Part 2 /") and sum(1 for v in rows_text(pg) if v) == 36, "apply: ... no jump to the next part; the 16 lines that did come are in the table", part_label(pg))
        pg.fill("#cl-reply", reply_of([30, 31, 39, 40]))
        pg.locator("#cl-apply").click()
        pg.wait_for_function("document.querySelector('#cl-partlabel').textContent.startsWith('Part 3')", timeout=8000)
        res = pg.locator("#cl-result").inner_text()
        c.check("Part 2 applied - next: part 3" in res and sum(1 for v in rows_text(pg) if v) == 40, "apply: the missing pieces arrive later -> the part is complete and part 3 is next", res)
        # part 3 with the clipboard button
        pg.evaluate("(t) => navigator.clipboard.writeText(t)", reply_of(range(41, 51), fence=False))
        pg.locator("#cl-paste").click()
        pg.wait_for_timeout(1000)
        res = pg.locator("#cl-result").inner_text()
        c.check(all(rows_text(pg)) and "Every line has Khmer text" in res and pg.locator("#dirty-label").inner_text() == "Ready - Khmer text for all 50 lines" and pg.locator("#cl-reply").input_value().startswith("41. "),
                "paste button: the clipboard is read and applied (answer without a code block); all 50 lines are ready", res)
        c.check(part_label(pg) == "Part 3 / 3 · lines 41-50 of 50" and pg.locator("#cl-next").is_disabled(), "paste button: the last part stays (no part 4)")
        c.check(sum(1 for sg in srv.api("GET", f"/api/jobs/{fifty}").json()["segments"] if sg["km"]) == 50 and pg.locator("#dub-result .seg-row.dirty").count() == 0, "all 50 lines are saved in the draft")
        # warnings: English left in, duplicate, unknown
        pg.fill("#cl-reply", "```text\n41. Hello this is still English\n42. ជួរទី 42\n42. ជួរទី 42 ម្តងទៀត\n77. ហួស\n```")
        pg.locator("#cl-apply").click()
        pg.wait_for_timeout(800)
        res = pg.locator("#cl-result").inner_text()
        c.check("Lines without Khmer letters: 41" in res and "Repeated line numbers (the last one was used): 42" in res and "Unknown line numbers (skipped): 77" in res, "apply: English left in / repeated / unknown numbers are reported", res)
        tx = rows_text(pg)
        c.check(tx[41] == "ជួរទី 42 ម្តងទៀត" and srv.api("GET", f"/api/jobs/{fifty}").json()["segments"][41]["km"] == "ជួរទី 42 ម្តងទៀត", "apply: the last of a repeated number is used (and saved)")
        # clear
        pg.locator("#cl-clear").click()
        c.check(pg.locator("#cl-reply").input_value() == "" and pg.locator("#cl-result").inner_text() == "", "clear: the box and the report are emptied")
        pg.locator("#claude-box").scroll_into_view_if_needed()
        pg.screenshot(path=str(SHOTS / "claude_panel_en.png"))
        # the table is a draft: it survives a language switch
        pg.locator("#lang-switch button[data-lang=km]").click()
        pg.wait_for_timeout(900)
        tx2 = rows_text(pg)
        c.check(tx2 == tx, "language switch: the pasted text is still in the table")
        panel_txt = pg.locator("#claude-box").inner_text()
        c.check("បកប្រែជាមួយ Claude" in panel_txt and "Copy ទៅ Claude" in panel_txt and "បញ្ចូលក្នុងតារាង" in panel_txt and not re.search(r"\bcl\.[a-z]+", panel_txt) and not re.search(r"\btr\.manual", pg.locator("#card-translate").inner_text()),
                "Khmer UI: the panel is in Khmer (no raw keys)", panel_txt[:80])
        c.check(pg.locator("#btn-regen span").inner_text() == "បង្កើតសំឡេង" and pg.locator("#dirty-label").inner_text().startswith("ត្រៀមរួច"),
                "Khmer UI: 'Generate audio' button and the ready label", pg.locator("#dirty-label").inner_text())
        c.check(part_label(pg) == "ផ្នែក 3 / 3 · ជួរ 41–50 (សរុប 50)", "Khmer UI: part label - and the panel kept its part after the redraw", part_label(pg))
        pg.locator("#claude-box").scroll_into_view_if_needed()
        pg.screenshot(path=str(SHOTS / "claude_panel_km.png"))
        pg.locator("#manual-row").scroll_into_view_if_needed()
        c.check("បកប្រែដោយ Claude" in pg.locator("#manual-row").inner_text() and pg.locator("#btn-generate span").inner_text() == "ត្រៀមអត្ថបទសម្រាប់ Claude", "Khmer UI: step 3 row + 'prepare' button")
        pg.locator("#lang-switch button[data-lang=en]").click()
        pg.wait_for_timeout(500)
        # the draft in History
        pg.locator("#nav button[data-page=history]").click()
        pg.wait_for_timeout(900)
        card = pg.locator(".hist-card", has_text="Fifty lines")
        c.check(card.count() == 1 and card.locator(".chip.warn").inner_text() == "Draft", "History: the draft job carries a 'Draft' chip instead of 'Done'")
        card.locator("[data-open]").click()
        pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
        pg.wait_for_timeout(600)
        c.check(pg.locator("#claude-box").evaluate("(e) => e.open") and pg.locator(".draft-box").is_visible(), "History: opening the draft shows the banner and the open panel again")
        # a reload does not lose the pasted text: the draft kept it
        pg.reload()
        pg.wait_for_timeout(900)
        pg.locator("#nav button[data-page=history]").click()
        pg.wait_for_timeout(700)
        pg.locator(".hist-card", has_text="Fifty lines").locator("[data-open]").click()
        pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
        pg.wait_for_timeout(600)
        c.check(rows_text(pg) == tx and pg.locator("#dirty-label").inner_text() == "Ready - Khmer text for all 50 lines", "reload: the 50 pasted lines are still there (saved in the draft)")
        ctx.close()

        # ---------------------------------------------------------------- a draft -> audio (real Edge TTS) with the 12-line sample
        ctx, pg = new_page(b)
        start_draft(pg, sample, "Draft to audio")
        c.check(part_label(pg) == "Part 1 / 1 · lines 1-12 of 12" and pg.locator("#cl-next").is_disabled(), "12 lines -> one part")
        pg.fill("#cl-reply", reply_of(range(1, 13)))
        pg.locator("#cl-apply").click()
        pg.wait_for_function("document.querySelector('#cl-result').textContent.includes('Every line has Khmer text')", timeout=8000)
        c.check("Saved in the draft" in pg.locator("#cl-result").inner_text() and pg.locator("#dub-result .seg-row.dirty").count() == 0, "paste: saved in the draft right away (the rows are not 'edits')")
        reqs = []
        pg.on("request", lambda r: reqs.append(r) if r.method == "POST" and "/regenerate" in r.url else None)
        pg.locator("#btn-regen").click()
        pg.wait_for_selector("#dub-audio", timeout=240000)
        pg.wait_for_timeout(1200)
        sent = json.loads(reqs[0].post_data)
        c.check(sent["segments"] == [], "Generate audio: the pasted lines were saved before, so no edits have to be sent", str(len(sent["segments"])))
        c.check(pg.locator("#dub-audio").count() == 1 and pg.locator(".draft-box").count() == 0 and "mp3" in (pg.locator("#dub-result .dl-row a").first.get_attribute("href") or ""), "Generate audio: the result is a normal dub (player + downloads), the banner is gone")
        c.check(not pg.locator("#claude-box").evaluate("(e) => e.open") and pg.locator("[data-sub=follow]").count() == 1 and pg.locator(".seg-table.no-audio").count() == 0, "Generate audio: the panel is closed now; follow switch and play buttons are back")
        c.check(rows_text(pg)[0].startswith("ជួរទី 1 ជាមួយ API និង Dashboard") and pg.locator("#dub-result .seg-row.dirty").count() == 0 and pg.locator("#btn-regen span").inner_text() == "Regenerate audio", "Generate audio: the table shows the pasted text (nothing is an edit any more)", rows_text(pg)[0])
        # --- the same panel on a finished dub: translate again
        pg.locator("#claude-box > summary").click()
        wait_copy_ready(pg)
        c.check(part_label(pg) == "Part 1 / 1 · lines 1-12 of 12" and pg.locator("#cl-prompt").input_value().startswith("You are an expert"), "finished dub: the panel opens and loads the prompt on demand")
        pg.fill("#cl-reply", reply_of([1, 2, 3], fence=False).replace("ជួរទី", "ជួរថ្មី"))
        pg.locator("#cl-apply").click()
        pg.wait_for_timeout(900)
        c.check(pg.locator("#dub-result .seg-row.dirty").count() == 3 and pg.locator("#dirty-label").inner_text() == "3 line(s) changed" and rows_text(pg)[0].startswith("ជួរថ្មី 1"),
                "finished dub: 3 lines pasted -> 3 edits ('3 line(s) changed')", pg.locator("#dirty-label").inner_text())
        res = pg.locator("#cl-result").inner_text()
        c.check(res.startswith("✔ 3 line(s) filled (lines 1-3)"), "finished dub: the report names the 3 lines", res)
        reqs.clear()
        pg.locator("#btn-regen").click()
        pg.wait_for_function("document.querySelector('#dub-result').classList.contains('hidden')", timeout=15000)
        pg.wait_for_selector("#dub-audio", timeout=240000)
        pg.wait_for_timeout(1000)
        sent = json.loads(reqs[0].post_data)
        c.check([e["idx"] for e in sent["segments"]] == [0, 1, 2] and all("km" in e for e in sent["segments"]), "finished dub: Regenerate sends only the 3 edited lines", json.dumps(sent["segments"], ensure_ascii=False)[:100])
        c.check(rows_text(pg)[2].startswith("ជួរថ្មី 3") and rows_text(pg)[3].startswith("ជួរទី 4"), "finished dub: the new text is the dub's text now")
        ctx.close()

        # ---------------------------------------------------------------- a draft whose first attempt failed is still reachable
        ctx, pg = new_page(b)
        pg.goto(srv.url + "/#history")
        pg.wait_for_selector("[data-open]", timeout=10000)
        pg.wait_for_timeout(500)
        pg.evaluate("(id) => { [...document.querySelectorAll('[data-open]')].find((x) => x.dataset.open === id).click(); }", DRAFT_ERR)
        pg.wait_for_selector("#dub-result .seg-row", timeout=10000)
        pg.wait_for_timeout(700)
        c.check(not pg.locator("#dub-progress").evaluate("(e) => e.classList.contains('hidden')"), "failed draft (UI): the error is shown in the progress card")
        c.check("could not be built" in pg.locator(".draft-box").inner_text() and "your Khmer text is still here" in pg.locator(".draft-box").inner_text(), "failed draft (UI): the banner says the audio failed but the Khmer text is still here")
        c.check(rows_text(pg)[0].startswith("ជួរទី 1") and rows_text(pg)[11].startswith("ជួរទី 12") and pg.locator("#btn-regen span").inner_text() == "Generate audio", "failed draft (UI): the text is in the table and 'Generate audio' is offered again")
        c.check(pg.locator("#dub-result .card-head .chip").last.inner_text() != "Draft", "failed draft (UI): the header shows the failure, not 'Draft'", pg.locator("#dub-result .card-head").first.inner_text()[:80])
        pg.locator("#btn-regen").click()
        pg.wait_for_selector("#dub-audio", timeout=240000)
        pg.wait_for_timeout(800)
        c.check(pg.locator(".draft-box").count() == 0 and pg.locator("#dub-audio").count() == 1, "failed draft (UI): a second try (Edge voice) builds the dub", pg.locator("#dub-progress").inner_text()[:100])
        ctx.close()

        # ---------------------------------------------------------------- phone
        ctx, pg = new_page(b, w=390, h=844)
        start_draft(pg, srt_of(8), "Phone")
        pg.locator("#claude-box").scroll_into_view_if_needed()
        ow = pg.evaluate("() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth })")
        c.check(ow["sw"] <= ow["cw"] + 2, "phone: the panel causes no sideways scrolling", str(ow))
        pg.screenshot(path=str(SHOTS / "claude_phone.png"))
        ctx.close()

        # ---------------------------------------------------------------- light theme, wide window with the menu hidden
        ctx, pg = new_page(b, theme="light", w=1700, h=950)
        start_draft(pg, srt_of(30), "Light")
        pg.locator("#claude-box").scroll_into_view_if_needed()
        pg.screenshot(path=str(SHOTS / "claude_light.png"))
        ctx.close()
        b.close()
finally:
    srv.stop()

real = [e for e in errors if "favicon" not in e]
c.check(not real, "no JavaScript errors in any page", "; ".join(real[:4]))
sys.exit(c.done())
