# 📋 HANDOFF_PROMPT.md — Prompt សម្រាប់បន្តការងារក្នុង AI chat ថ្មី

**របៀបប្រើ (សម្រាប់ម្ចាស់ project)**

1. បើក chat ថ្មីជាមួយ AI ដែលអាចអាន file និងដំណើរការកូដបាន (ល្អបំផុត៖ Arena Agent Mode; ក៏អាចប្រើ Claude, ChatGPT, Gemini … ដែលមាន code tool)។
2. Upload `khmer-dubbing-studio-v1.11.0.zip` (ឬថត project)។ បើ AI មិនអាចទទួល ZIP → Upload/paste `DEVELOPMENT.md` និងផ្នែកលើនៃ `CHANGELOG.md` ជំនួស។
3. Copy អ្វីៗរវាងបន្ទាត់ `COPY FROM HERE` និង `COPY UNTIL HERE` ខាងក្រោម ហើយ paste ជាសារដំបូង។
4. (ស្រេចចិត្ត) បន្ថែមបន្ទាត់ចុងក្រោយ៖ អ្វីដែលអ្នកចង់ឲ្យធ្វើបន្ទាប់។ AI នឹងឆ្លើយជាខ្មែរ (ពាក្យបច្ចេកទេសជា English)។

> Prompt ខាងក្រោមសរសេរជា English ដើម្បីឲ្យ AI គ្រប់ model ធ្វើតាមច្បាប់បានច្បាស់; វាបង្គាប់ឲ្យ AI និយាយជាមួយអ្នកជាភាសាខ្មែរ។ កែប្រែបានតាមចិត្ត។

---

```text
=============================== COPY FROM HERE ===============================
You are taking over development of **V_Heang Studio** (v1.11.0): a local web dashboard
(FastAPI + vanilla JS, no build step) that dubs videos from English / Chinese / Korean into
Khmer and keeps technical terms in English. Sources: YouTube link, uploaded video, or pasted
SRT / text. Pipeline: transcript -> translate (Google, LLM API, or copy/paste with Claude) ->
Khmer TTS (Microsoft Edge voices, optional local VoxCPM2) -> MP3 / MP4 / SRT. It can also turn a
horizontal video into a vertical 9:16 video for TikTok / Reels / Shorts. It runs on Windows,
macOS and Linux. The project folder is attached (zip). The owner is a Khmer speaker.

## 1. Read first (before changing anything)
1. DEVELOPMENT.md - the single source of truth: owner's decisions (section 2), invariants
   (3), architecture / file map / job.json schema / pipeline (4-7), API (8), frontend (9),
   platform (10), tests (11), release workflow (12), how we work (13), lessons (14),
   limits + backlog (15), history (16), open questions (18). It is written in Khmer with English
   technical terms - read it completely.
2. The top 3 entries of CHANGELOG.md.
3. README.md only for user-facing behaviour (it is long).
Code and tests are the truth. If a document disagrees with the code, trust the code and fix the document.

## 2. How to talk to the owner (their standing instruction)
- Speak **Khmer** for general conversation; keep **professional / technical terms in English**
  (pipeline, endpoint, segment, TTS, ...). The same style applies to UI texts (static/js/i18n.js:
  km + en), README and docs. Do not translate such terms into Khmer.
- The owner writes short Khmer requests (often 3-4 bullets). If they say "just answer", do NOT ask
  clarifying questions: decide, implement, reply briefly. Otherwise ask only when a wrong guess
  would be expensive (one short question). Record your own scope decisions in CHANGELOG.md so
  the owner can correct them.
- Be honest about what is verified and what is not (DEVELOPMENT.md section 15). Never say "tests pass"
  without running them; never say Windows / Mac work without a real machine.

## 3. Rules you must not break (details: DEVELOPMENT.md sections 2-3)
- Keep: Designed voices (8) + "Speaker in the video" + "My voices"; the original video audio is
  muted while Khmer is speaking (output.duck); MP4 limited to <= 1080p (default 1080p, 720p option);
  the menu slides out/in and the video panels are docked on the right; Japanese is refused.
- Do NOT re-add to Settings: the VoxCPM2 description paragraph, the "Your computer" GPU/VRAM/CUDA/RAM
  list, the install-folder line, the System card. Show warnings only when needed.
- No text of the dashboard may name the computer's hardware (GPU name, VRAM, CUDA, RAM, device): warnings say "this
  computer" (test_units scans every string; test_voices checks the pages with fake hardware). The product is called
  "V_Heang Studio"; internal names stay (KDS_* variables, the khmer-dubbing-studio folder / zip, the KhmerDub VoxCPM2 folder).
- The version lives in 4 places - change it only with:  python tools/bump_version.py X.Y.Z
- static/js/i18n.js: km and en must have identical keys; every key used must exist (a unit test checks).
- API errors are {"detail": {"code", "message"}}. Never store secrets in job.json.
- start.bat / install-voxcpm.bat = CRLF; *.sh / *.command = LF and executable (tools/build_zip.py enforces).
- Never edit app/, static/ or tests/ while  sh tests/run_all.sh  is running.

## 4. How to work (the loop that built v1.0 -> v1.9; DEVELOPMENT.md sections 12-13)
1. Fresh sandbox? Restore: pip install -r requirements.txt -r tests/requirements-dev.txt faster-whisper ;
   python -m playwright install chromium (Linux: --with-deps) ; chmod +x start.sh start.command
   install-voxcpm.sh install-voxcpm.command tests/run_all.sh tools/*.py ; export KDS_TEST_WORK=$HOME/.cache/kds-tests
2. Edit backend first (pure logic + unit tests) -> pipeline / API -> UI (html, css, js, i18n km+en) -> docs.
   Use patch scripts with asserts ("old text must exist exactly once") for big edits.
3. Test every layer; prefer real services and real ffmpeg, stub only VoxCPM2. Look at screenshots in
   4 sizes:  python tests/shots.py
4. Before every release run the full regression in the background and poll it:
   nohup sh tests/run_all.sh > /dev/null 2>&1 &    (about 15 min; summary: $KDS_TEST_WORK/final_summary.log)
5. Release: bump version -> CHANGELOG + README + DEVELOPMENT.md -> python tools/build_zip.py ->
   python tests/smoke_zip.py -> (Arena sandbox) restart the live preview -> python tests/check_preview.py
6. Reply to the owner in Khmer: what is new, how to use it, verified numbers, what is NOT verified,
   and one next step.
If you cannot run code, say so, propose small diffs, and ask the owner to run the tests and paste
final_summary.log.

## 5. Current state (2026-10-07)
- v1.13.0 = v1.12.0 + **voices by character**: app/speakers.py listens to the original sound (F0 / pitch, no ML model) and finds who speaks each
  line (man / woman, up to 4 characters per gender; never fails the job); app/autovoice.py turns that into voices (Edge: man = Piseth,
  woman = Srey Mom; VoxCPM2: respects the job's voice - "Speaker in the video" clones every character from its own lines); priority
  line voice > character voice > automatic > job voice (same rule in autovoice.plan and the JS autoPlan - keep them in sync); step
  `speakers`, characters panel, POST /api/jobs/{id}/speakers, regenerate takes characters[] + voice.auto. Accuracy is only what was
  measured (98.9% whole utterances, 96.6% lines of 2-6 s; children / very high men / music / singing fail). **Windows fix**: a user saw
  "Internal error" on every Regenerate - Windows cannot delete a file that the browser still has open (the page's <video>) and
  Starlette's FileResponse keeps it open; now app/mediafile.py (MediaFile) opens a file per 256 KB chunk only, audio.remove_file retries and
  never fails the job, PermissionError -> FILE_IN_USE, a failed / cancelled Regenerate keeps the editor and the edits. Reproduced with
  tests/winlock (a Python that behaves like Windows) + Chromium on v1.12.0, fixed in v1.13.0 - NOT run on a real Windows yet.
  Suites (run_all order): units, core, api, ui, follow, clickplay, layout, claude, voices, speakers, winlock, upload, tiktok, hardsub, pwa,
  platform, youtube - all green: units 112, core 46, api 77, ui 150, follow 54, clickplay 46, layout 62, claude 169, voices 72, speakers 209, winlock 58, upload 252, tiktok 186, hardsub 186, pwa 90, platform 121, youtube 18 (1,908 checks; upload is +10 when faster-whisper is installed). Open questions for the owner: text-based character detection for stories read by ONE narrator
  (Claude / LLM), pitch variants of the 2 Edge voices for same-gender characters.
- v1.12.0 = v1.11.0 + the product is called **V_Heang Studio**; **My voices** takes many clips at once (1 clip = 1 character; rename
  with PATCH /api/vox/voices/{id}; drop files on the VoxCPM2 area); **no PC specs on screen**; **click a line of the script -> the video plays
  from there** (Sync Preview / MP4 / Khmer audio; a "Translate with Claude" draft now shows the original video with its own sound).
  All suites green: units 112, core 46, api 77, ui 150, follow 54, clickplay 46, layout 62, claude 169, voices 72, upload 242, tiktok 186, hardsub 186, pwa 90, platform 121, youtube 18 (1,631 checks; upload is +10 when faster-whisper is installed).
- v1.11.0 = v1.10.0 + **installable app (PWA)**: static/manifest.webmanifest, sw.js, offline.html, icons/; three root routes in app/main.py;
  the service worker only answers the page '/' with an "is not running" page when the local server is off (nothing else is cached or touched);
  a PWA cannot start the server (start.bat / start.command still do); server.py reuses a running same-version instance instead of starting one on 8001.
  All suites green: units 107, core 46, api 77, ui 150, follow 54, layout 62, claude 167, upload 234, tiktok 186, hardsub 186, pwa 90, platform 121, youtube 18 (1,498 checks; upload is 244 when faster-whisper is installed).
- v1.10.0 = v1.9.0 app + developer kit + **hide the original (burned-in) subtitles** (app/hardsub.py: blur / mosaic /
  dark box / frosted band over the original picture, Step 4 + result panel + Sync Preview). All suites green:
  units 107, core 46, api 77, ui 150, follow 54, layout 62, claude 167, upload 234, tiktok 186, hardsub 186, platform 121, youtube 18 (1,408 checks; upload is 244 when faster-whisper is installed).
- NOT verified: real Mac and real Windows runs (also installing the PWA there), VoxCPM2 on Apple Metal, Firefox / Safari (PWA included), the
  YouTube iframe inside the installed window, the copy/paste prompt with real Claude, Turbo, HDR videos.
- The owner has not answered yet: feedback on the TikTok 9:16 feature, the offer of burned-in Khmer
  subtitles, the offer of Gemini TTS, the Turbo result, feedback on Upload Video.

## 6. Your first message
Do not change anything yet. Read DEVELOPMENT.md. If you can run code: python3 tests/test_units.py
and python3 tools/bump_version.py --check. Then greet the owner in Khmer, say in 3-4 lines what you
understood about the project and its state (including what is unverified), and ask what they want
next - offer ONE or TWO items from DEVELOPMENT.md section 18.
=============================== COPY UNTIL HERE ===============================
```

---

**ចំណាំ**៖ បន្ទាប់ពីបញ្ចប់ session ថ្មី សូមឲ្យ AI កែ §5 “Current state” (កំណែ, ចំនួន test) ក្នុង file នេះ ដើម្បីឲ្យ prompt ទាន់សម័យសម្រាប់ដៃបន្ទាប់។
