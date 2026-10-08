# 🛠️ DEVELOPMENT.md — សម្រាប់អ្នកបន្តអភិវឌ្ឍ V_Heang Studio

> **កំណែ** 1.13.0 · **ធ្វើបច្ចុប្បន្នភាព** 2026-10-07 · **ភាសា**៖ ខ្មែរ + English សម្រាប់ពាក្យបច្ចេកទេស (តាមការណែនាំរបស់ម្ចាស់ project)

**ឯកសារនេះសម្រាប់នរណា?** អ្នកដែលទទួលបន្ត project នេះ — មនុស្ស ឬ AI ក្នុង chat ថ្មី។ វាផ្តល់ (១) អ្វីដែលកម្មវិធីធ្វើ និងអ្វីដែលមិនត្រូវប៉ះ, (២) របៀបរៀបចំកូដ, (៣) **លំហូរការងារ (workflow)** ដែលបានប្រើសាងសង់ពី v1.0 ដល់ v1.9 — ដើម្បីឲ្យអ្នកបន្តធ្វើតាមវិធីតែមួយ ដោយមិនសួរម្ចាស់ម្តងទៀតពីរឿងដែលបានសម្រេចរួច។

**ការពិតមានតែមួយ៖ កូដ + tests។** បើឯកសារនេះខុសពីកូដ → កូដត្រូវ ហើយត្រូវកែឯកសារនេះភ្លាមៗ (ក្នុងការកែតែមួយជាមួយកូដ)។

### មាតិកា

0. ចាប់ផ្តើមលឿន · 1. ផលិតផល · 2. ការណែនាំរបស់ម្ចាស់ (មិនត្រូវបំពាន) · 3. Invariants · 4. Architecture · 5. File map · 6. `job.json` schema · 7. Pipeline · 8. API · 9. Frontend · 10. Platform + Environment variables · 11. Tests · 12. Release workflow · 13. របៀបធ្វើការជាមួយ AI agent · 14. មេរៀន និងអន្ទាក់ · 15. ដែនកំណត់ · មិនទាន់ផ្ទៀងផ្ទាត់ · Backlog · 16. ប្រវត្តិកំណែ · 17. បន្តក្នុង AI chat ថ្មី · 18. សំណួរដែលនៅបើកចំហ

---

## 0. ចាប់ផ្តើមលឿន (Quick start)

**ត្រូវការ**៖ Python 3.10+ (សាកល្បងលើ 3.13) · Internet (Google Translate, Microsoft Edge TTS, YouTube) · សម្រាប់ tests បន្ថែម៖ Chromium (Playwright) · Linux / macOS (tests ប្រើ `sh`; លើ Windows ប្រើ WSL)។

```sh
# 1) ដំឡើង
python3 -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r tests/requirements-dev.txt
python -m playwright install chromium                     # Linux: បន្ថែម --with-deps

# 2) ដំណើរការ → http://127.0.0.1:8000
python server.py            # ឬ start.bat (Windows) · start.command (Mac, ចុចពីរដង) · sh start.sh

# 3) សាកល្បង
python3 tests/test_units.py                               # suite តែមួយ (វិនាទី)
nohup sh tests/run_all.sh > /dev/null 2>&1 &              # ទាំងអស់ ≈ 15 នាទី → ចាំមើល៖
cat "${KDS_TEST_WORK:-${TMPDIR:-/tmp}/kds-tests}/final_summary.log"

# 4) ចេញផ្សាយកំណែថ្មី (លម្អិតក្នុង §12)
python3 tools/bump_version.py 1.9.2        # … កែ CHANGELOG / README … run_all …
python3 tools/build_zip.py && python3 tests/smoke_zip.py
```

> ⚠ ក្នុង sandbox ដែល `/tmp` ជា RAM (tmpfs តូច ដូច Arena៖ 1 GB) ត្រូវកំណត់ `KDS_TEST_WORK=$HOME/.cache/kds-tests` មុនរត់ tests។

**លំដាប់អាន** (ម៉ោងដំបូង)៖ §2 → §3 → §4 / §5 → §13 → `CHANGELOG.md` (៣ entry លើបំផុត) → `README.md` (ផ្នែក “របៀបប្រើ” — វាវែង ~១២៨ KB; អានតែពេលត្រូវការ)។ ពេលកែផ្នែកណា អាន §5 រក file ត្រឹមត្រូវ ហើយរក test របស់វាក្នុង §11។

**បើអ្នកជា AI ក្នុង chat ថ្មី** → ឲ្យម្ចាស់ paste `HANDOFF_PROMPT.md` ជាសារដំបូង (§17)។

---

## 1. ផលិតផល (មួយទំព័រ)

**V_Heang Studio** = dashboard ដំណើរការលើកុំព្យូទ័រផ្ទាល់ខ្លួន (FastAPI + vanilla JS, **គ្មាន build step**) ដែលបកប្រែសំឡេងវីដេអូ **English · 中文 · 한국어 → ខ្មែរ** ដោយ **រក្សាពាក្យបច្ចេកទេសជា English** (API, Dashboard, Machine Learning …) ហើយអានពាក្យទាំងនោះដោយ English voice ក្នុងប្រយោគខ្មែរ។

| | |
|---|---|
| **ប្រភព (Source)** | ① YouTube link (captions → Whisper បើគ្មាន) · ② **Upload Video** (v1.8៖ subtitle ក្នុងឯកសារ → SRT/VTT ដែលអ្នកដាក់ → Whisper) · ③ Paste Transcript / SRT / VTT / អត្ថបទធម្មតា |
| **បកប្រែ** | Google Translate (ឥតគិតថ្លៃ, លំនាំដើម) · AI/LLM (OpenAI-compatible API key) · **Claude Copy/Paste** (v1.7៖ គ្មាន API) |
| **សំឡេង** | Microsoft Edge៖ Srey Mom (ស្រី) · Piseth (ប្រុស) · **VoxCPM2** (ជម្រើស, local, venv ដាច់ដោយឡែក)៖ Designed voices ×8 · Speaker in the video (clone) · My voices (clone) |
| **លទ្ធផល** | `dub.mp3` · `dubbed.mp4` (រូបដើម ឬ **TikTok 9:16**, ≤1080p) · `khmer.srt` · `original.srt` · `script_km.txt` |
| **កែក្រោយបង្កើត** | តារាង Segments៖ កែអត្ថបទខ្មែរ · **Voice ក្នុងមួយជួរ** · **Start/End ក្នុងមួយជួរ** · 🔊 ស្តាប់ឃ្លា · Regenerate; Sync Preview (YouTube player ឬ វីដេអូ upload); MP4 preview; បង្កើត **តែ MP4** ឡើងវិញ (ប្តូរទម្រង់ TikTok) |
| **ទំព័រ UI** | Dubbing Studio (៤ ជំហាន៖ Source → Voice → Translate & Terms → Output) · Text to Speech · Technical Terms (glossary) · History · Settings |
| **Platform** | Windows (`start.bat`) · macOS (`start.command`; Apple Silicon ល្អបំផុត) · Linux (`start.sh`) |

**គំនិតស្នូល (រក្សាពាក្យបច្ចេកទេសជា English)**៖ `glossary.TermMatcher.protect()` ជំនួសពាក្យក្នុង glossary ដោយ placeholder (`X1X`) → បកប្រែ → `restore()` ដាក់ពាក្យ English វិញ → `tts.py` បំបែកអត្ថបទជា run (Khmer voice / English voice) រួចភ្ជាប់ឲ្យរលូន។ Chinese/Korean៖ `cjkterms.py` ស្គាល់ពាក្យ «服务器» / «서버» ហើយរក្សាជា “server”។

---

## 2. ការណែនាំរបស់ម្ចាស់ project (មិនត្រូវបំពាន)

ទាំងនេះជាអ្វីដែលម្ចាស់ **បានប្រាប់ច្បាស់** (មិនមែនការសន្និដ្ឋានរបស់ AI)។ បើចង់ប្តូរ ត្រូវសួរម្ចាស់ជាមុន។

| # | ការណែនាំ | កំណែ | ផលក្នុងកូដ |
|---|---|---|---|
| 1 | «Communicate with me in **Khmer** for general conversations, but use **English** for professional or technical terms.» | ជានិច្ច | ចម្លើយ chat · label UI (`i18n.js`) · README · ឯកសារនេះ = ខ្មែរ + ពាក្យបច្ចេកទេសជា English។ កុំបកពាក្យដូចជា pipeline / endpoint / segment ទៅជាខ្មែរ។ |
| 2 | **Designed voices ត្រូវមាន** — ម្ចាស់ធ្លាប់សុំលុប ហើយក្រោយមកសុំ «បន្ថែម Designed voices ដែលលុបពីមុនមកវិញ» | v1.4.0 | `voxpresets.py` (៨៖ ស្រី ៤ ប្រុស ៤ + Re-roll)។ **Speaker in the video (clone)** និង **My voices** នៅដដែល។ |
| 3 | ក្នុង **Settings** កុំបង្ហាញ ៤ ប្លុក (ម្ចាស់ highlight ហើយប្រាប់ថាមិនចាំបាច់)៖ (ក) កថាខណ្ឌពន្យល់ VoxCPM2 · (ខ) បញ្ជី “Your computer” (GPU / VRAM / CUDA / RAM) · (គ) បន្ទាត់ install-folder · (ឃ) កាត **System** ទាំងមូល | v1.2.0 | បង្ហាញតែ **warning** ពេលចាំបាច់ (Intel Mac, Rosetta, RAM < 15 GB, គ្មាន GPU …)។ `/api/system` នៅមាន ប៉ុន្តែ UI មិនបង្ហាញជាកាត។ **v1.12.0**៖ ម្ចាស់សុំម្តងទៀត («មិនត្រូវបង្ហាញ Spec របស់ PC») → គ្មានអត្ថបទ UI ណាដាក់ឈ្មោះ hardware (GPU / VRAM / CUDA / RAM) — §3 #27។ |
| 4 | **Original video audio (0 = muted)** ត្រូវបិទ **ពេលសំឡេងខ្មែរកំពុងនិយាយ** | v1.2.0 | `output.duck` (លំនាំដើម true) · `audio.duck_envelope` · ប៊ូតុងក្នុង Sync Preview។ |
| 5 | MP4 **≤ 1080p** (អត្ថបទ hint ម្ចាស់បានកែ) — លំនាំដើម 1080p, ជម្រើស 720p | v1.5.0 | `output.max_height` (480 / 720 / 1080)។ កុំទាញ 4K។ |
| 6 | ម៉ឺនុយខាងឆ្វេង **slide ចេញ/ចូល** · វីដេអូ (Sync Preview / MP4) **Fixed នៅខាងស្តាំ** ពេល scroll | v1.6.0 | `#side-toggle` · `.dockable` (dock បិទក្រោម 1180 px; dock បានតែមួយ)។ |
| 7 | ភាសាប្រភព **English · 中文 · 한국어** → ខ្មែរ។ **ភាសាជប៉ុនត្រូវបដិសេធ** (មិនបកខុសស្ងាត់ៗ) | v1.3.0 | `langs.detect_lang` → `LANG_UNSUPPORTED` (មាន test)។ |
| 8 | ពេលម្ចាស់សរសេរ «**just answer**» (សំណើ Upload Video) = **កុំសួរសំណួរបំភ្លឺ**; អនុវត្តភ្លាមដោយ default សមហេតុផល; ចម្លើយខ្លី ជាខ្មែរ | v1.8.0 | ជាទូទៅ៖ សួរតែពេលការទាយខុសថ្លៃ (សំណួរខ្លីមួយ ឬ `ask_user`)។ |
| 9 | **TikTok 9:16** («បម្លែងវីដេអូផ្តេក ឲ្យ Fit TikTok បញ្ឈរ») + **ដំណើរការលើ MacBook និង Windows** | v1.9.0 | ម្ចាស់ឲ្យតែ ៣ ចំណុច គ្មានលម្អិត → **វិសាលភាព (scope) ជាការសម្រេចរបស់ AI មិនទាន់បញ្ជាក់**៖ Step 4 “Video shape”, Blur ជា default, phone mock, panel remake, ការព្រមាន 10 នាទី / 287 MB, Mac (Metal)។ **សួរម្ចាស់ពី feedback** (§18)។ |
| 10 | ការបកប្រែ៖ ម្ចាស់មិនទាន់ឆ្លើយជម្រើស A / B / C (Claude copy-paste · API key · Gemini) | v1.4 → 1.7 | បានសាងសង់ **A (copy/paste)** ព្រោះ Claude Pro គ្មាន API; Google ជា default; engine API key (OpenAI-compatible) នៅដដែល។ |
| 11 | «ខ្ញុំចង់បានលំហូរការងារ… ឲ្យអ្នកផ្សេងអភិវឌ្ឍន៍បន្ត ឬបន្តលើ AI new chat» | v1.9.1 | ឯកសារនេះ + `HANDOFF_PROMPT.md` + `tests/` + `tools/`។ |
| 12 | «មិនបាច់ធ្វើតាមវិធីទាំងអស់នេះទេ។ គ្រាន់តែបង្កើតមុខងារមួយដែលធ្វើឲ្យ Subtitle មើលមិនច្បាស់ ឬមាន Effect លើ subtitle» (បន្ទាប់ពីសួរ «ធ្វើយ៉ាងណាកុំឲ្យជាប់ copyright»; កម្មវិធីសម្រាប់សាកល្បង AI មិនមែនអាជីវកម្ម) | v1.10.0 | ការបកស្រាយ៖ លាក់ **hard-sub របស់វីដេអូដើម** (មិនមែន Subtitle ខ្មែរ)។ Effect ៤ (blur / mosaic / dark / frost) + band ពេញទទឹង កំណត់ដោយដៃ + មើលជាមុន (រូបតូច + Sync Preview)។ **មិនមាន** burn-in Subtitle ខ្មែរ (ជាសំណើដាច់ដោយឡែក)។ AI បានប្រាប់ម្ចាស់ត្រង់ៗថា មុខងារនេះមិនការពារ copyright claim ហើយមិនណែនាំល្បិចគេច Content ID។ |
| 13 | «PWA<Note: មិនទាន់ Hosting នៅលើ online server ទេ>» (ជម្រើសដែលម្ចាស់ជ្រើស បន្ទាប់ពីសួរ «តើមានវិធីណាដើម្បីឲ្យការបើក Website នេះងាយស្រួលជាងមុន? Just answer») | v1.11.0 | កម្មវិធីនៅតែរត់ **local** (`start.bat` / `start.command`) — PWA ផ្តល់តែបង្អួច + រូបតំណាង ហើយ**មិនអាចចាប់ផ្តើម server ឲ្យបានទេ** → service worker ធ្វើតែមួយ៖ ទំព័រ «មិនទាន់ដំណើរការ» ពេល server ស្លាប់ (បើកដោយខ្លួនឯងពេលត្រឡប់)។ ត្រូវ **host-agnostic** (URL relative; ដំណើរការលើ https ថ្ងៃក្រោយ)។ App ជាប់ origin `127.0.0.1:8000` → `server.py` ប្រើច្បាប់ចម្លងដែលរត់ស្រាប់ ជំនួសឲ្យចាប់ផ្តើមលើ 8001។ AI បានប្រាប់ម្ចាស់ត្រង់ៗថា PWA មិនបើក server ឲ្យ។ |
| 14 | v1.12.0 — ៤ សំណើ៖ «កែឈ្មោះពី khmerdub studio ទៅជា **V_Heang Studio**» · «my voice អាច upload បានច្រើន sample voices ដើម្បីបញ្ចូលសំឡេងបានច្រើនតួរអង្គ» · «លុបចោល ហើយមិនត្រូវបង្ហាញ **Spec របស់ PC**» (រូប៖ កថាខណ្ឌ “Runs on your own computer … needs an NVIDIA GPU to be fast”) · «press លើឃ្លានិយាយនៅលើពេលណាមួយនៃ Script ហើយ Video play ចាប់ពីពេលនោះ» | v1.12.0 | ឈ្មោះ៖ អ្វីដែលអ្នកប្រើឃើញប្តូរ; **មិនប្តូរ** `KDS_*` · ឈ្មោះ folder / ZIP · ថត VoxCPM2 `KhmerDub` (§3 #28)។ My voices៖ ឯកសារច្រើនក្នុងពេលតែមួយ (**១ ឯកសារ = ១ តួអង្គ** — ការបកស្រាយរបស់ AI) + ✎ ប្តូរឈ្មោះ + drop។ គ្មាន hardware ក្នុង UI (§3 #27)។ ចុចជួរ → `playFromRow` (§3 #29)។ |
| 15 | v1.13.0 — ៣ ចំណុច៖ «កម្មវិធីស្គាល់ថាអ្នកណានិយាយ — **តួអង្គប្រុសប្រើសំឡេងប្រុស តួអង្គស្រីប្រើសំឡេងស្រី** ដោយមិនបាច់បញ្ចូលដោយដៃម្តងមួយៗ» (Voice ក្នុងមួយជួរនៅតែឈ្នះ) · រាយការណ៍ពី Windows៖ «Regenerate វាបង្ហាញ **internet error** ប៉ុន្តែ Internet ខ្ញុំធម្មតា … ខ្ញុំសាកច្រើនវីដេអូ app នៅតែបង្ហាញ» (រូប៖ «**Internal** error.») · សំណួរ៖ «បើក្នុងរឿងមានច្រើនតួអង្គ តើអ្នកអាចបញ្ចូលសំឡេងផ្សេងៗពីគ្នាបានទេ?» (**just answer**) | v1.13.0 | ការបកស្រាយរបស់ AI (មិនទាន់បញ្ជាក់)៖ switch លំនាំដើម**បើក** តែក្នុង Dub flow; Edge ♂ ពិសិដ្ឋ / ♀ ស្រីមុំ; VoxCPM2 **គោរពសំឡេងដែលជ្រើសសម្រាប់ការងារ** (§3 #30)។ Error៖ សារគឺ «Internal» (មិនមែន Internet) = **bug ក្នុង App លើ Windows** (§3 #31) — បង្កើតឡើងវិញបានដោយ simulation + កែ (មិនទាន់សាកលើ Windows ពិត)។ សំណួរ៖ ឆ្លើយត្រង់ៗ — កម្មវិធីស្តាប់សំឡេង ដូច្នេះអ្នកនិទានម្នាក់អានគ្រប់តួអង្គ = ១ តួអង្គ (§15)។ |

---

## 3. Invariants (ច្បាប់ដែលត្រូវតែពិតជានិច្ច)

ការ **ការពារដោយ** = test ឬកូដដែលនឹងបរាជ័យ/ព្រមាន បើច្បាប់ត្រូវបំពាន។ “design” = គ្មាន test ស្វ័យប្រវត្តិ (ប្រយ័ត្នពេលកែ)។

| # | ច្បាប់ | ហេតុផល | ការពារដោយ |
|---|---|---|---|
| 1 | កំណែ **៤ កន្លែង** ត្រូវដូចគ្នា៖ `app/__init__.py` · `index.html` (`kds-ui`) · `app.js` (`KDS_UI_VERSION`) · `i18n.js` (`I18N_VERSION`) | server ប្រៀបធៀបពេលចាប់ផ្តើម៖ ខុស → banner ក្រហម + `/api/health` `ui_ok:false` (ករណី extract ZIP មិនពេញ) | `tools/bump_version.py` · test_ui · test_platform E |
| 2 | `i18n.js`៖ `km` និង `en` មាន key ដូចគ្នា, គ្មានស្ទួន; រាល់ key ដែល `index.html` / `app.js` ប្រើត្រូវមាន | កុំឲ្យ “raw key” (`set.vox.install`) បង្ហាញក្នុង UI (បញ្ហា v1.1.2) | test_units (static guard) · `check_preview.py` |
| 3 | field `en` ក្នុង segment = **អត្ថបទប្រភព** (en/zh/ko); `km` = ខ្មែរ | ឈ្មោះប្រវត្តិសាស្ត្រ — កុំប្តូរ (job.json ចាស់ + frontend ទាំងមូល) | design (`langs.py` docstring) |
| 4 | error API = `{"detail": {"code", "message"}}` (មិនមែន string) | UI បកប្រែតាម `err.<CODE>` ក្នុង `i18n.js` | `_err()` ក្នុង `main.py` · test_api / upload |
| 5 | `job.params` មិនដែលមាន API key / `glossary_text` / អត្ថបទវែង | job.json ត្រូវរក្សាទុក ហើយបង្ហាញក្នុង History | `pipeline.sanitize_params` · test_upload |
| 6 | job រត់ក្នុង thread (pool ២); ផ្លាស់ប្តូរតាម `job.step / log / warn` តែប៉ុណ្ណោះ; `job.json` សរសេរ atomic (tmp → replace); status ∈ queued · running · done · error · cancelled; server restart → `running/queued` ក្លាយ `error INTERRUPTED` | មិនឲ្យ job.json ខូច | test_units (guard) |
| 7 | ជំហាន MP4 បរាជ័យ ≠ job បរាជ័យ (MP3 នៅ, `warnings`)។ MP4 ចាស់ត្រូវជំនួសតែពេលថ្មីចប់ (`dubbed.part.mp4` → `replace_file`)។ Cancel/បរាជ័យពេល remake → MP4 + params ចាស់នៅដដែល | លទ្ធផលមិនបាត់ដោយសារ encode ខុស | test_tiktok |
| 8 | ffmpeg បោះបង់ដោយ **`kill()`** (មិនមែន SIGTERM)។ ចប់ធម្មតាមិនត្រូវប៉ះ (+faststart pass) | ffmpeg 7.0 ចេញយឺតស្មើពេល encode បន្ទាប់ SIGTERM | `audio.run_with_progress` · test_tiktok |
| 9 | `frame.py` = logic សុទ្ធ (មិនបើក ffmpeg) | សាកល្បងបានដោយគ្មានវីដេអូ | test_tiktok A |
| 10 | VoxCPM2 រស់ក្នុង venv ដាច់ដោយឡែក + worker `127.0.0.1` (token, idle 30 នាទី)។ dashboard មិន import torch | torch 2–4 GB, Python 3.10–3.12 | design (`vox.py`) · stub ក្នុង tests |
| 11 | ឯកសារទាញយក = whitelist `DOWNLOADABLE_FILES`; `local_media_of` បដិសេធ `/` `\` ក្នុងឈ្មោះ; ឈ្មោះ upload កាត់ folder (`display_name`) | path traversal | test_upload · test_units |
| 12 | Upload = stream ចូល disk (មិនទុកក្នុង RAM), ពិនិត្យ `Content-Length` (413 `UPLOAD_TOO_LARGE`), `KDS_MAX_UPLOAD_MB` | វីដេអូធំ ៤ GB | test_upload |
| 13 | UI គ្មាន build step; asset URL `?v=<ver>-<sha1[:10]>`; static → `Cache-Control: no-cache`; `/` → `no-store` | browser ប្រើ script ចាស់ (បញ្ហា v1.1.2) | test_api (guard) |
| 14 | setting ថ្មីត្រូវដាក់ក្នុង `DEFAULTS()` (`app.js`) ជានិច្ច; `deepMerge` ការពារ `localStorage` ចាស់ | អ្នកប្រើចាស់មិនខូច | design |
| 15 | ancestor នៃ `.dockable` **មិនត្រូវមាន** `transform / filter / contain / will-change` | ធ្វើឲ្យ `position: fixed` ខូច (dock) | test_layout |
| 16 | `.bat` = **CRLF**; `.sh` / `.command` = **LF** + mode 0755 | `.bat` ជាមួយ LF ខូច; CR ក្នុង `.sh` ធ្វើឲ្យ `sh` បរាជ័យលើ Mac | `tools/build_zip.py` (បដិសេធ) · test_platform A, E |
| 17 | Windows៖ `os.replace` នៃ MP4 អាច PermissionError → `replace_file` ព្យាយាម ៨ × 0.4 វិ | antivirus / player ចាក់ឯកសារ | test_tiktok |
| 18 | macOS៖ កុំបើក `/usr/bin/python3` stub បើ `xcode-select -p` ខុស (ចេញ pop-up ដំឡើង); ដក quarantine flag; VoxCPM2 នៅ `~/Library/KhmerDub/voxcpm` (មិនក្នុង iCloud) | បទពិសោធន៍ Mac ដំបូង | test_platform A, C (Mac ក្លែង) |
| 19 | `manualtr.py` មិនប៉ះ network; `parse_reply` មិនបោះចោលអ្វីស្ងាត់ៗ (រាយ missing / unknown / duplicates / no_khmer) | អ្នកប្រើ paste ចម្លើយ AI ដែលរូបរាងផ្សេងៗ | test_claude |
| 20 | ភាសា `ja` ត្រូវបដិសេធ (`LANG_UNSUPPORTED`) មុន translate | ការសម្រេចរបស់ម្ចាស់ (#7) | test_units (guard) |
| 21 | Google Translate៖ batch ១៦ ជួរ/request; ឈប់ក្នុង ~30–60 វិ បើ Google មិនឆ្លើយ។ **កុំ** ប្រើ pattern “១ request ក្នុង ១ ជួរ” | ធ្លាប់ជាប់ ២០ នាទី (v1.0.1) | design · test_api ប្រើ Google ពិត |
| 22 | Edge TTS៖ អត្ថបទខ្មែរលាយ English បំបែកជា run (Khmer voice / English voice) ហើយ loudness ស្មើ | Edge អាន “API” ជា “Happy” | test_core (`split_runs`) · test_api (សំឡេងពិត) |
| 23 | សំឡេងដើមបិទ (0) ពេលអ្នកនិយាយដើម **ឬ** សំឡេងខ្មែរនិយាយ (`DUCK_PRE/POST` ជុំវិញ) | ការណែនាំម្ចាស់ #4 | test_tiktok · test_upload · test_youtube |
| 24 | ពាក្យបច្ចេកទេស៖ `TermMatcher.protect()` → placeholder `X1X` → បកប្រែ → `restore()` ត្រូវ round-trip; placeholder បាត់ → `ok=False` → engine សាកម្ដងទៀតដោយ style ផ្សេង (`X…X` → `QQ…QQ`); ចំណុចបញ្ចប់ដែលអ្នកប្រើឃើញ៖ ពាក្យ English នៅដដែល | ជាគុណតម្លៃស្នូលរបស់ផលិតផល | test_core |
| 25 | `hardsub.py` = logic សុទ្ធ (មិនបើក ffmpeg); band វាស់ជា % នៃកម្ពស់រូបភាព **ដើម** ហើយធ្វើ **មុន** ស៊ុម 9:16; ពេលបិទ MP4 ត្រូវតែ **ចម្លង** រូបភាព (មិន re-encode); label ក្រាហ្វ `kc*` មិនជាន់ `kbg / kfg …` ឬ audio | អ្នកដែលមិនប្រើមុខងារនេះមិនត្រូវរងផលប៉ះពាល់; label ជាន់គ្នា = ffmpeg បរាជ័យ | test_hardsub A + B |
| 26 | **PWA**៖ service worker (`static/sw.js`, ផ្តល់ដោយ route `/sw.js` ដែលដាក់ version ក្នុងឈ្មោះ cache) ឆ្លើយ **តែ** GET navigation ទៅ `/` ហើយ cache **តែ** `/offline.html`; មិនប៉ះ API / media (Range) / upload / download; `manifest` · icons · `offline.html` ប្រើ URL ដែលចាប់ផ្តើមដោយ `/` (មិនដាក់ `localhost` ឬ port ក្នុង file); ប៊ូតុងដំឡើងលាក់ពេល standalone / មិនមែន secure context / ក្នុង iframe / អេក្រង់តូច; `server.py` មិនចាប់ផ្តើមច្បាប់ចម្លងទី ២ ពេល V_Heang Studio **កំណែដដែល** រត់ស្រាប់លើ 8000 | cache ច្រើនជាងនេះ = កំណែចាស់ជាប់ (server local ជាប្រភពតែមួយ); worker ឆ្លើយ API = download / progress ខូច; ច្បាប់ចម្លងទី ២ លើ 8001 = App ដំឡើង (ជាប់ origin 8000) ជួបកំណែចាស់ | test_pwa A + B + C |
| 27 | **គ្មានអត្ថបទ UI ណាដាក់ឈ្មោះ hardware របស់ PC** (GPU · VRAM · CUDA · RAM · ឈ្មោះ device)។ ការព្រមាន = «កុំព្យូទ័រនេះ» (`set.vox.hw.*`, `vox.banner.nogpu`)។ `/api/vox/status` នៅតែផ្តល់ `hardware` (logic របស់ UI) ប៉ុន្តែមិនបង្ហាញ; log ដំឡើង (Settings → Log) នៅតែមានព័ត៌មានបច្ចេកទេស | ម្ចាស់ #3 / #14 | test_units (i18n scan) · test_voices (ទំព័រ Dub / TTS / Settings × 4 hardware ក្លែង × ២ ភាសា) |
| 28 | **ឈ្មោះផលិតផល = V_Heang Studio** ក្នុងអ្វីដែលអ្នកប្រើឃើញ។ identifier ខាងក្នុងមិនប្តូរ៖ `KDS_*` · `khmer-dubbing-studio` (folder / ZIP) · `KhmerDub` (ថត VoxCPM2 — ប្តូរ = ដំឡើង ១០ GB ម្តងទៀត) | ម្ចាស់ #14 | test_units · test_pwa · test_platform |
| 29 | **ចុចជួរ → លេងវីដេអូ** (`playFromRow` ក្នុង `wireDubResult`)៖ លំដាប់ Sync Preview បើក → MP4 → បើក Sync Preview → សំឡេងខ្មែរ; មិនចាក់ពី button / input / select / label / textarea / text selection; ចុច**ចូល**ប្រអប់ខ្មែរ (`pointerdown` + `focusin`; មិនមែន Tab); `openSync(kind, startAt)` មាន `syncOpening` (មិនបើក player ពីរ) និង `syncStartAt` (ចាំជួរចុងក្រោយ); ព្រាងបង្ហាញវីដេអូ + សំឡេងដើម (`NO_AUDIO`) | ម្ចាស់ #14 | test_clickplay · test_upload |
| 30 | **សំឡេងតាមតួអង្គ** (`speakers.py` + `autovoice.py`)៖ ជំហាន `speakers` (ក្រោយ transcript; តែ Dub ដែលមានម៉ោង + សំឡេង) **មិនដែលធ្វើឲ្យការងារបរាជ័យ** (`SPEAKERS_UNSURE / NO_AUDIO / FAILED` = warning; ស្តាប់ឮ < 20% ឬ < 3 វិ → **មិនស្មាន**)។ ភេទ = F0 (YIN 72–380 Hz) ព្រំដែន 165 Hz + ចែករំលែកភស្តុតាង (kNN); តួអង្គ = ក្រុមក្នុងភេទតែមួយ (≤ ៤ ក្នុងមួយភេទ; **ចូលចិត្តបញ្ចូលមនុស្សពីរនាក់ ជាងបំបែកមនុស្សម្នាក់**)។ **អាទិភាព Voice**៖ ជួរ (`segment.voice`) › តួអង្គ (`characters[].voice`) › ស្វ័យប្រវត្តិតាមភេទ › Voice របស់ការងារ — **ក្បួនដូចគ្នា**ក្នុង `autovoice.plan` (Python) និង `autoPlan` (JS) → កែទាំងពីរជានិច្ច។ Edge ♂ Piseth / ♀ Srey Mom; VoxCPM2៖ `vox:original` → `vox:s:N` (Clone តួអង្គ) តែពេលមាន `ref`, Designed / My voice → រក្សាសម្រាប់ភេទត្រូវ | ម្ចាស់ (សំណើ v1.13) | test_speakers · test_units |
| 31 | **Server មិនទុកឯកសារ media បើកទេ** (`app/mediafile.py` `MediaFile` ជំនួស `FileResponse` សម្រាប់ audio / video)៖ បើកម្តងមួយបំណែក (256 KB) រួចបិទភ្លាម; Range ✔ (RFC 7233, `If-Range`, 416); ឯកសារដែលត្រូវជំនួសពេលកំពុងផ្ញើ → ចប់មុនកំណត់ (មិនលាយចាស់ + ថ្មី)។ **ហេតុផល**៖ Windows លុប / ជំនួសឯកសារដែលនៅបើកស្រាប់មិនបាន (`PermissionError: [WinError 32]`) ហើយ `<video>` ទុក request ពាក់កណ្តាលអានអស់ពេលជាច្រើននាទី → `Regenerate` (លុប `dubbed.mp4`) បរាជ័យជា «Internal error»។ ក៏ត្រូវ៖ `audio.remove_file` (ព្យាយាមម្តងទៀត ១០ × 0.3 វិ; **មិនបរាជ័យការងារ**) · `audio.replace_file` (#17) · `Job.save` / `JobManager.delete` ព្យាយាមម្តងទៀត · `_guard`៖ `PermissionError` → `FILE_IN_USE` (មិនមែន INTERNAL) · UI `releaseMedia()` មុនសំណើ regenerate / remake។ **កុំប្រើ `FileResponse` សម្រាប់ឯកសារ audio / video ដែលអាចត្រូវជំនួស** | ការរាយការណ៍ពីម្ចាស់ (v1.13) | test_winlock (server ដែលធ្វើត្រាប់តាម Windows — `tests/winlock`) |
| 32 | **Regenerate ដែលបរាជ័យ / ត្រូវបោះបង់ មិនបំផ្លាញការងារ**៖ ការកែ (`km`, voice, ម៉ោង, តួអង្គ) ត្រូវបានរក្សាទុកក្នុង job មុនពេលអាចបរាជ័យ → UI បង្ហាញតារាងកែជាថ្មី (`retry` ក្នុង `renderJob`៖ `error` / `cancelled` + `dub.mp3` នៅមាន + មាន `km`) ជាមួយសារ `res.regen_failed` («សំឡេងខាងក្រោម = មុនពេលកែ»)។ ពីមុន តារាងបាត់ → ម្ចាស់ត្រូវធ្វើវីដេអូទាំងមូលឡើងវិញ | ការរាយការណ៍ពីម្ចាស់ (v1.13) | test_winlock C |

---

## 4. Architecture

```text
Browser  (static/: index.html + js/app.js + js/i18n.js + css/app.css — vanilla JS, គ្មាន framework)
   │  fetch /api/*  (JSON; error = {"detail": {code, message}})        media: /api/jobs/{id}/file/{name} (Range ✔ · mediafile.py)
   ▼
FastAPI  app/main.py ───────────────┬── JobManager (app/jobs.py): ThreadPoolExecutor(2) · job.json លើ disk
   │                                │        │
   │                                │        └── app/pipeline.py : run_dub_job · run_tts_job · run_regenerate · run_remake_video
   │                                │              ├─ source:    ytsource.py (yt-dlp, youtube-transcript-api) · uploads.py (ffmpeg probe) · transcript.py
   │                                │              ├─ voices:    speakers.py (ស្គាល់តួអង្គ ប្រុស / ស្រី ពី F0) → autovoice.py (Voice ណាសម្រាប់ជួរណា)
   │                                │              ├─ language:  langs.py → glossary.py + cjkterms.py (term protection)
   │                                │              ├─ translate: translate.py (Google batches | LLM)  ·  manualtr.py (Claude copy/paste)
   │                                │              ├─ speech:    tts.py (Edge TTS, hybrid km+en)  |  vox.py ──HTTP 127.0.0.1──▶ vox_worker.py (VoxCPM2, venv ដាច់ដោយឡែក)
   │                                │              └─ audio:     audio.py (ffmpeg via imageio-ffmpeg + numpy) · frame.py (9:16)
   └── /api/vox/*  → vox.py manager → vox_setup.py (installer, hardware detection)
Disk: data/ (ឬ $KDS_DATA_DIR)      VoxCPM2 home: Windows %LOCALAPPDATA%\KhmerDub\voxcpm · macOS ~/Library/KhmerDub/voxcpm · ផ្សេងទៀត data/voxcpm
```

- **Threads**៖ ១ request = ១ job ក្នុង pool (២ ស្របគ្នា)។ ក្នុង job, TTS ប្រើ `asyncio.run(...)` (Edge ជា async)។ UI **poll** `GET /api/jobs/{id}` (ទ្រនិច `state.tracking`) — គ្មាន WebSocket។
- **Audio ខាងក្នុង**៖ mono float32 **24 kHz** (`config.SAMPLE_RATE`) ទាំងអស់ → MP3 128k ពេលចប់។
- **ffmpeg**៖ មិនត្រូវការដំឡើងដោយអ្នកប្រើ — `imageio-ffmpeg` ដឹកជាមួយ (`audio.ffmpeg_exe()`); មិនប្រើ ffprobe (parse ចេញពី `ffmpeg -i`)។ Mac ដែលគ្មាន libx264 → `ffmpeg_failure()` ផ្តល់ hint (`brew install ffmpeg`)។

### Data layout (`data/`, មិនមានក្នុង ZIP)

```text
data/
├── jobs/<id>/    job.json · dub.mp3 · khmer.srt · original.srt · script_km.txt · dubbed.mp4 (+ dubbed.part.mp4 ពេល encode)
│                 thumb.jpg · upload.<ext> (hard link) · embedded.srt · video/ (YouTube + source.json marker) · audio/ (Whisper)
│                 voice_ref.wav (clip យោង VoxCPM2) · voice_ref_c<N>.wav (clip យោងរបស់តួអង្គនីមួយៗ) · duck_mask.wav (បណ្តោះអាសន្ន)
├── uploads/<uid>/    upload.<ext> · info.json · thumb.jpg      (លុបស្វ័យប្រវត្តិក្រោយ KEEP_HOURS ពេលមិនប្រើ)
├── cache/tts/*.npy (21 ថ្ងៃ / 1.5 GB) · cache/translate/*.txt (90 ថ្ងៃ) · cache/preview/*.mp3 · cache/video/
└── glossary.txt
```

---

## 5. File map

**Root**

| ឯកសារ | តួនាទី |
|---|---|
| `server.py` | ចាប់ផ្តើម uvicorn · រក port ទំនេរ 8000–8019 · `running_instance()` (V_Heang Studio កំណែដដែលរត់ស្រាប់លើ 8000 → បើកវា មិនចាប់ផ្តើមច្បាប់ចម្លងទី ២) · `use_system_certificates()` (Mac) · `HOST` `PORT` `NO_BROWSER` |
| `start.bat` (CRLF) · `start.sh` · `start.command` (LF, 0755) | launcher៖ រក Python 3.10+, បង្កើត `.venv`, `pip install`, run។ `start.command` = ចុចពីរដងលើ Mac (ផ្អាកពេលមានកំហុស) |
| `install-voxcpm.bat/.sh/.command` | ដំណើរការ `python -m app.vox_setup` ពី command line |
| `requirements.txt` | fastapi · uvicorn · edge-tts · yt-dlp · youtube-transcript-api · httpx · numpy · imageio-ffmpeg (faster-whisper = ជម្រើស) |
| `README.md` (~១៥៣ KB, ខ្មែរ) | សម្រាប់អ្នកប្រើ។ `CHANGELOG.md` = entry ក្នុងមួយកំណែ (ខ្មែរ + English terms) |
| `samples/` | `technical-tutorial.srt` / `.zh.srt` / `.ko.srt` |
| `tests/` · `tools/` | §11 · §12 |

**`app/`** (Python; `from __future__ import annotations`)

| ឯកសារ | ~បន្ទាត់ | តួនាទី |
|---|---|---|
| `main.py` | 991 | routes ទាំងអស់ · index (inject `?v=`) · `_UiStatic` (no-cache) · PWA root routes (`/manifest.webmanifest` `/sw.js` `/offline.html`) · upload streaming · ទាញយក (whitelist) · ពិនិត្យ marker កំណែ UI |
| `pipeline.py` | 1180 | `run_dub_job` `run_tts_job` `run_regenerate` `run_remake_video`; `_audio_stages` (tts → mix → video); Voice/Time ក្នុងមួយជួរ (`clean_segment_edits` `_windows` `_build_track`); `AudioCtx`; `sanitize_params`; `_make_draft` |
| `jobs.py` | 221 | `Job` (status, steps, logs, warnings, JSON atomic) · `JobManager` (pool ២, prune cache) |
| `config.py` | 80 | path (`KDS_DATA_DIR`) · Edge voices · `DOWNLOADABLE_FILES` · `SAMPLE_RATE` |
| `langs.py` | 220 | en/zh/ko · ស្គាល់ភាសាតាមអក្សរ · ជ្រើស caption track · ប្រវែងឃ្លា / ល្បឿននិយាយ |
| `cjkterms.py` | 370 | តារាង 中文 / 한국어 → English (នាមសព្ទ និងឈ្មោះប៉ុណ្ណោះ — កិរិយាសព្ទដាក់ចេញដោយចេតនា) |
| `glossary.py` | 730 | glossary លំនាំដើម + format ឯកសារ · `TermMatcher` (protect / restore, auto-detect ឈ្មោះ) · readings (ការអានខ្មែរ) |
| `transcript.py` | 300 | parse SRT / VTT / json3 / អត្ថបទ · សម្អាត · `fix_overlaps` · `merge_segments` · `to_srt` |
| `textutil.py` | 160 | `split_runs` (km / en) · `split_sentences` · ចន្លោះ · `ensure_khmer_terminal` |
| `translate.py` | 770 | `Translator`: Google (batch ១៦, ៤ route, fail-fast, cache) · LLM (OpenAI-compatible) |
| `tts.py` | 351 | `VoiceSettings` · `Synth` (Edge, hybrid, cache, retry) · `synth_long_text` · `preview_audio` |
| `vox.py` | 480 | `VoxManager`: install / start / stop worker, HTTP + token, `synth()` |
| `vox_setup.py` | 730 | installer (venv, torch GPU/CPU/MPS, self-test, marker `##PHASE/##PROGRESS/##ERROR`) · `hardware()` · `mac_arch()` · `vox_home()` |
| `vox_worker.py` | 620 | រត់ **ក្នុង venv VoxCPM2**; `/health /load /synth /shutdown` |
| `voxvoices.py` · `voxpresets.py` | 442 · 120 | ប្រភេទសំឡេង (original / custom / preset anchor) · បញ្ជី Designed voices ៨ |
| `audio.py` | 523 | ffmpeg helper · `time_stretch` · `mix_into` · `soft_limit` · duck envelope · `mux_video` · `run_with_progress` · `replace_file` · `ffmpeg_failure` |
| `frame.py` | 150 | 9:16៖ `canvas` · `plan()` · `build_graph` (blur / crop / bars) · `FramePlan.graph_from(src)` |
| `hardsub.py` | 160 | បិទបាំង Subtitle ដើម៖ `clean_*` · `sigma` / `block` / `opacity` · `plan()` · `build_graph` (blur / mosaic / dark / frost) |
| `ytsource.py` | 550 | YouTube៖ id, info, transcript (API → yt-dlp), download, marker reuse |
| `uploads.py` | 270 | upload: `inspect` · thumbnail · subtitle tracks · `adopt` (hard link) · `prune` |
| `asr.py` · `whisper_setup.py` | 110 · 90 | Whisper (faster-whisper) · ប៊ូតុង Install Whisper |
| `manualtr.py` | 310 | Claude copy/paste៖ `build_prompt` · `parse_reply` |
| `speakers.py` | 582 | **ស្គាល់តួអង្គ** (v1.13)៖ `analyze()` — F0 (YIN) ក្នុងជួរនីមួយៗ · ភេទ (logistic 165 Hz + kNN pooling + minority / coverage rule) · ក្រុមតួអង្គ (gender-pure clustering) · `ref` (ជួរច្បាស់បំផុតសម្រាប់ Clone) · ផ្ទុកសំឡេងពី ffmpeg (int16 mono) |
| `autovoice.py` | 197 | **Voice ណាសម្រាប់ជួរណា** (v1.13)៖ `plan()` (Edge ♂ / ♀ · VoxCPM2 clone / Designed / My voices) · `clean_character_edits` / `apply_character_edits` · `valid_row_voice` (ក្បួនដូចគ្នាក្នុង `autoPlan` របស់ JS) |
| `mediafile.py` | 151 | `MediaFile`៖ ផ្ញើ audio / video ដោយ **មិនទុកឯកសារបើក** (§3 #31) · `parse_range` |

**`static/`**៖ `index.html` (495) · `css/app.css` (787; dark/light, block v1.9 · v1.10 · v1.11 · v1.12 ចុងឯកសារ) · `js/app.js` (3,055) · `js/i18n.js` (1,341; 645 key × 2) · `fonts/` (Kantumruy Pro: Khmer + Latin) · **PWA (v1.11)**៖ `manifest.webmanifest` · `sw.js` (មាន `{{ver}}` — ជំនួសដោយ route) · `offline.html` (មាន `/*{{khmer-font}}*/` — route ដាក់ font ខ្មែរជា data URI) · `icons/` (`icon-192` `icon-512` `icon-maskable-512` `apple-touch-icon` — បង្កើតដោយ `python tools/make_icons.py`)។

---

## 6. `job.json` schema

សរសេរដោយ `Job.save()` ទៅ `data/jobs/<id>/job.json` (UTF-8, ensure_ascii=False)។ `GET /api/jobs/{id}` ឲ្យរចនាសម្ព័ន្ធដូចគ្នា (+ `logs` ១២០ ចុងក្រោយ)។ ពេល load៖ `running/queued` → `error` `INTERRUPTED`។

```jsonc
{
  "id": "6b011b123f", "kind": "dub", "status": "done",            // kind: dub | tts   status: queued|running|done|error|cancelled
  "title": "Sample: Technical tutorial (SRT)", "created": 1759650000.1, "updated": 1759650090.7,
  "params": {                                                    // សំណើដែល sanitize (គ្មាន key, អត្ថបទវែង → "<1568 chars>")
    "source":    {"type": "transcript", "text": "<1568 chars>", "title": "…", "lang": "auto"},    // type: youtube | upload | transcript
    "voice":     {"id": "km-KH-SreymomNeural", "rate": 0, "pitch": 0, "volume": 0, "term_mode": "english_voice",
                  "en_voice": "", "engine": "edge", "vox": {"id": "vox:original", "quality": "balanced", "ref_start": "", "consent": false},
                  "auto": {"on": true, "male": "", "female": ""}},       // v1.13: voices by character (male / female: "" = automatic · voice id · "vox:s" · "vox:mine")
    "translate": {"engine": "google", "keep_terms": true, "auto_detect": true},                  // engine: google | llm | manual
    "output":    {"sync": "fit", "video": true, "orig_volume": 20, "duck": true, "max_speedup": 1.4,
                  "max_height": 1080, "aspect": "original", "fit": "blur", "crop_x": 50,
                  "hide_subs": false, "hide_effect": "blur", "hide_bottom": 3, "hide_height": 16, "hide_strength": 50},
    "youtube":   {"whisper": true, "whisper_model": "base", "cookies_browser": "", "proxy": ""}
  },
  "steps": [ {"key": "transcript", "status": "done", "progress": 1.0, "detail": "12 segments"} ],   // dub: transcript·speakers·translate·tts·mix·video   tts: translate·tts·mix
  "video": null,                                                 // YouTube: {id,url,title,channel,thumbnail,duration}   upload: {id:null,upload:true,filename,width,height,has_video,thumbnail,…}
  "outputs": {"dub.mp3": "dub.mp3", "khmer.srt": "khmer.srt", "original.srt": "original.srt", "script_km.txt": "script_km.txt"},   // + dubbed.mp4 · speech.mp3 · voice_ref.wav
  "error": null,                                                 // {"code": "…", "message": "…"}
  "warnings": [],                                                // [{"code": "TIKTOK_BIG", "message": "…"}]
  "meta": {"transcript": {"source": "manual", "timed": true, "language": "en"}, "timed": true, "source_end": 75.05, "src_lang": "en",
           "tts_engine": "edge", "row_voices": 0, "row_times": 0, "max_drift": 0.21, "stretched": 0, "audio_duration": 76.22},
  "segments": [ {"idx": 0, "start": 1.0, "end": 6.097, "en": "Welcome back …", "km": "សូមស្វាគមន៍ …",
                 "slot": [1.0, 6.5], "out_start": 1.0, "out_end": 6.651, "speed": 1.0, "dur": 5.65,
                 "char": 1, "gp": 0.08} ],                              // v1.13: character id · P(female) of this line (UI: a faint badge = unsure)
  "logs": ["[14:02:11] Pasted transcript: 12 lines …"]            // រក្សា ៤០០ ចុងក្រោយ
}
```

| field | អត្ថន័យ |
|---|---|
| segment `en` / `km` | អត្ថបទប្រភព (en/zh/ko) / ខ្មែរ (§3 #3) |
| segment `start` `end` | ម៉ោង caption (វិនាទី) |
| segment `voice` `t0` `t1` | (ស្រេចចិត្ត) Voice ក្នុងមួយជួរ (`km-KH-…` ឬ `vox:p:<key>` · `vox:c:<id>` · `vox:original`) · Start / End កំណត់ដោយដៃ |
| segment `char` `gp` | (v1.13) តួអង្គរបស់ជួរ (`meta.characters[].id`) · `gp` = P(ស្រី) 0..1។ ជួរដែលមិនអាចវាស់ → គ្មាន `char` (ប្រើ Voice របស់ការងារ) |
| segment `slot` `out_start` `out_end` `speed` `dur` `warn` | ពេលដែលជួរមានសិទ្ធិប្រើ · កន្លែងដែលសំឡេងខ្មែរចាក់ពិត · ល្បឿនចុងក្រោយ · រយៈពេលនៅល្បឿនធម្មតា (UI ប្រើទាយ speed-up) · `late` / `long` |
| `meta.transcript.source` | `youtube-transcript-api` · `yt-dlp` · `whisper` · `embedded` (subtitle ក្នុងឯកសារ) · `manual` |
| `meta.draft` | true = ការងារ Claude copy/paste មិនទាន់មានសំឡេង (លុបពេលបង្កើតសំឡេងរួច) |
| `meta.upload` | `{file, name, size, kind, duration, width, height, video_codec, has_video, has_audio, subtitles[], thumb}` |
| `meta.video` | `{width, height, codec, limit, aspect, fit, crop_x, hide, out_width, out_height, size, duration}` — `hide` = `{effect, bottom, height, strength}` ឬ `null` |
| `meta.vox` | សំឡេង VoxCPM2 ដែលបានប្រើ (`voice`, `label`, `voices[]` …) |
| `meta.characters[]` | (v1.13) `{id, gender: male\|female, lines, seconds, f0 (Hz), p, ref: [[start, end] …], name, voice, gender_set?}` — `voice` = Voice ដែលអ្នកជ្រើសឲ្យតួអង្គ (`''` = ស្វ័យប្រវត្តិ); `gender_set` = អ្នកប្រើបានប្តូរភេទ (⇄) |
| `meta.speakers` | (v1.13) `{state: ok\|off\|untimed\|no_audio\|unsure\|failed, coverage, n}` |
| `meta.char_voices` | (v1.13) `{"<character id>": "<voice id>"}` ដែលបានប្រើពិតពេល generate ចុងក្រោយ |
| `warnings[].code` | `NO_VIDEO_SOURCE` `NO_PICTURE` `FFMPEG_FAILED` `DUCK_FAILED` `TIKTOK_LONG` `TIKTOK_BIG` `UNTIMED_UPLOAD` `EMBEDDED_SUBS_FAILED` `SPEAKERS_UNSURE` `SPEAKERS_NO_AUDIO` `SPEAKERS_FAILED` |
| `error.code` | `INVALID_URL` `NO_CAPTIONS` `NO_CAPTIONS_NO_WHISPER` `NO_SUBTITLES_NO_WHISPER` `NO_AUDIO` `NO_SPEECH` `UPLOAD_GONE` `FILE_IN_USE` `EMPTY_TRANSCRIPT` `LANG_UNSUPPORTED` `TRANSLATE_FAILED` `TTS_FAILED` `VOX_FAILED` `FFMPEG_FAILED` `YT_BLOCKED` `AGE_RESTRICTED` `VIDEO_UNAVAILABLE` `DOWNLOAD_FAILED` `TRANSCRIPT_FAILED` `INTERRUPTED` `INTERNAL` |

Job ចាស់ (មុន v1.3) មាន `english.srt` ជំនួស `original.srt` — `DOWNLOADABLE_FILES` នៅទទួលស្គាល់ទាំងពីរ។

---

## 7. Pipeline

**Dub job** — `run_dub_job(job, req)` → `_guard()` បកប្រែ exception ទៅជា status/error របស់ job

1. **transcript** (`_dub`)
   - *YouTube*៖ `fetch_transcript` = `youtube-transcript-api` → `yt-dlp` json3 → (ប្រសិនបើគ្មាន caption + Whisper ដំឡើង) ទាញ audio + `asr.transcribe`។ Caption ដែល YouTube បកដោយម៉ាស៊ីនមិនដែលត្រូវប្រើ។
   - *Upload*៖ អត្ថបទដែលអ្នកដាក់ (SRT/VTT/text) **ឈ្នះ** → subtitle track ក្នុងឯកសារ (`embedded.srt`) → Whisper។ គ្មានសំឡេង + គ្មាន subtitle → `NO_AUDIO`។
   - *Transcript*៖ `parse_any` (SRT · VTT · អត្ថបទមាន timestamp · អត្ថបទធម្មតា = គ្មាន timing → `sync=natural` + `UNTIMED_UPLOAD` សម្រាប់ upload)។
   - បន្ទាប់៖ `clean_segments` → `fix_overlaps` → `resolve_lang` (**អក្សរឈ្នះជម្រើសអ្នកប្រើ**; `ja` → `LANG_UNSUPPORTED`) → `merge_segments` (តែពេលមាន timing) → `job.segments`។
   - **speakers** (v1.13; `_speakers_stage` → `run_speakers`)៖ បើ `voice.auto.on` និងមានម៉ោង → ស្តាប់សំឡេងដើម (ឯកសារ upload ឬសំឡេង YouTube ដែលទាញមួយដង) → `speakers.analyze` → `char` / `gp` ក្នុងជួរ + `meta.characters`។ គ្មានសំឡេង / ឮមិនច្បាស់ / កំហុស → ជំហាន `skipped` + warning; **មិនដែលបរាជ័យការងារ**។ `POST /api/jobs/{id}/speakers` ដំណើរការជំហាននេះឡើងវិញលើការងារដែលមានរួច (`keep_old`)។
2. **translate**៖ `Translator.translate_many` (google | llm) ជាមួយ term protection (`glossary.build_matcher`)។ `engine == "manual"` → `_make_draft` (ឈប់; `meta.draft`; ជួរ `km` ទទេ; អ្នកប្រើ paste ពី Claude រួចចុច Generate = `regenerate`)។
3. **`_audio_stages`** (ចែករំលែកជាមួយ regenerate)
   - **tts**៖ `auto_plan` (character → voice) រួច `_synth_all` ដាក់ជួរតាម engine/voice (`row_settings`; ជួរ `voice` › តួអង្គ › Voice របស់ការងារ)។ Edge៖ hybrid runs។ VoxCPM2៖ ឆ្លងកាត់ `vox.py` (worker); Designed voice = anchor ម្តង រួច clone។ បើជួរវែងជាងបង្អួច → synthesize ម្តងទៀតដោយ rate លឿនជាងមុន (`min(need × 1.03, max_speedup)`; log “Fitting timing”)។
   - **mix**៖ `_build_track` — បង្អួចពេលរបស់ជួរ `(start, deadline)`៖ `start = t0 ?? caption start`, `deadline = t1 ?? (next start − 0.10 s)` (ជួរចុងក្រោយ៖ `end + 4 − 0.10`)។ បើសំឡេងនៅតែវែងជាងបង្អួច → `time_stretch` residual (> 1.03 ហើយ ≤ 1.15) បើនៅតែវែង → ជួរនោះបាន `warn: long`; ជួរដែលត្រូវរុញក្រោយ > 2.5 វិ → `late`។ `sync=natural` = ដាក់ត្រឹមត្រូវបន្តបន្ទាប់ (មិនស្តាប់ timing)។ `soft_limit` → `dub.mp3` (128k) + `khmer.srt` (ម៉ោង `out_*`) + `original.srt` + `script_km.txt`។
   - **video** (`_video_stage`, ស្រេចចិត្ត; បរាជ័យ = warning)៖ ទាញវីដេអូ (≤ `max_height`) ឬប្រើឯកសារ upload → `probe_media` → `frame.plan()` (None = រូបរាងដើម → copy ឬ scale) → `_duck_mask` (បើ `orig_volume>0` និង `duck`) → `audio.mux_video` → `meta.video` + ការព្រមាន TikTok។
4. **Regenerate** (`run_regenerate`)៖ បញ្ចូលការកែ (`km`, `voice`, `t0`, `t1`; `null` = ត្រឡប់ default) → ចាប់ពី `_audio_stages` (មិនបកប្រែឡើងវិញ)។ បញ្ចូលការកែតួអង្គ (`characters[]` — `apply_character_edits`)។ លុប `dubbed.mp4` ចាស់ដោយ `audio.remove_file` (ជាប់លើ Windows → បន្តទៅមុខ; `replace_file` ជំនួសពេលចប់ — §3 #31)។ បរាជ័យ / បោះបង់ → ការកែនៅក្នុង job (§3 #32)។
5. **Remake video** (`run_remake_video`)៖ តែ `_video_stage`; `dub.mp3` និងការកែមិនប៉ះ; បរាជ័យ/Cancel → MP4 + params ចាស់នៅដដែល; job នៅ `done`។

**TTS job** — `_tts`៖ (បើ `input_lang != km`) translate → `_tts_core` (`synth_long_text` ចែកជាឃ្លាខ្លីៗ; អត្ថបទ ≤ 30000 តួ) → `speech.mp3`។

**តារាងជំនួយ — ចង់ប្តូរអ្វី កែត្រង់ណា**

| ចង់ | កែ |
|---|---|
| ភាសាប្រភពថ្មី | `langs.py` (LangInfo, ប្រវែងឃ្លា, Google/Whisper code) · `cjkterms.py` · i18n km + en · test_units |
| Edge voice ថ្មី | `config.KHMER_VOICES` / `EN_VOICES` (+ `en_voice` ដែលអានពាក្យ English) |
| ឯកសារ output ថ្មី | `config.DOWNLOADABLE_FILES` · សរសេរក្នុង pipeline + `job.outputs` · ប៊ូតុង UI · suffix ឈ្មោះក្នុង `job_file` |
| option សំណើថ្មី | `DEFAULTS()` ក្នុង `app.js` + `data-bind` + request builder · `_ctx_from` / `AudioCtx` · `sanitize_params` · test |
| error code ថ្មី | `SourceError("CODE")` ឬ `_err()` · key `err.CODE` ក្នុង i18n km + en · (§6 តារាង) |
| ទម្រង់វីដេអូថ្មី | `frame.py` (`clean_*`, `build_graph`) · `audio.mux_video` · `#frame-row` · test_tiktok |
| Effect ថ្មីលើ Subtitle ដើម | `hardsub.EFFECTS` + `build_graph` · i18n `hs.fx.*` + `hs.fx.hint.*` (km + en; `data-i18n` ត្រូវជា **literal** — guard ក្នុង test_units មិនទទួល `${…}`) · CSS `.hs-fx[data-fx=…]` · `HS_FX` ក្នុង app.js · test_hardsub |
| ល្បឿន speed-up | `output.max_speedup` (1.0–2.0, `_ctx_from`) |

---

## 8. API (REST, JSON)

Base: `http://127.0.0.1:8000`។ **Error ទាំងអស់**៖ `{"detail": {"code": "…", "message": "…"}}` (§3 #4)។ គ្មាន multipart នៅកន្លែងណា (upload = body ឆៅ; custom voice = JSON base64) → មិនត្រូវការ `python-multipart`។

| Method · Path | Body / Query → លទ្ធផល · កំហុស |
|---|---|
| `GET /` · `GET /static/*` | page (inject `?v=`) · UI files (`no-cache`) |
| `GET /manifest.webmanifest` · `/sw.js` · `/offline.html` | PWA (§3 #26)៖ manifest (`application/manifest+json`) · service worker (ជំនួស `{{ver}}`; `Service-Worker-Allowed: /`) · ទំព័រ «មិនទាន់ដំណើរការ» (ដាក់ font ខ្មែរជា data URI) — `no-cache` ទាំងអស់ |
| `GET /api/health` | `{ok, version, assets, ui_ok}` |
| `GET /api/system` | `{version, python, platform, ffmpeg{ok,path,version}, edge_tts, yt_dlp, youtube_transcript_api, whisper, data_dir, vox{installed,state,device,gpu}}` |
| `GET /api/voices` | `{khmer[], english[], vox{custom[], presets[]}}` |
| `GET /api/voices/preview` | `voice rate pitch volume term_mode en_voice text(≤600)` → mp3 (cache); 502 `TTS_FAILED` |
| `POST /api/video/info` | `{url, youtube{cookies_browser, proxy}}` → ព័ត៌មានវីដេអូ + captions; 400 `INVALID_URL` · 404 `VIDEO_UNAVAILABLE` · 502 |
| `POST /api/uploads?name=` | **body = ឯកសារឆៅ** → `{id, name, size, duration, width, height, has_video, has_audio, subtitles[], pick, thumbnail …}`; 400 `BAD_FILE_TYPE` `EMPTY_UPLOAD` `NOT_MEDIA` · 413 `UPLOAD_TOO_LARGE` · 507 `DISK_FULL` · 500 |
| `GET·DELETE /api/uploads/{id}` · `GET …/thumb` | (`?lang=` → track ណាត្រូវប្រើ) · 404 `UPLOAD_GONE` |
| `GET /api/whisper/status` · `POST /api/whisper/install` | 403 `WHISPER_INSTALL_DISABLED` ពេល `KDS_*DISABLE_INSTALL` |
| `POST /api/jobs/dub` | `{source{type,url/upload_id/text,lang,title?,subs?}, video?, voice, translate, output, youtube}` → `{id}`; 400 `INVALID_URL` `EMPTY_TRANSCRIPT` `BAD_REQUEST` + កំហុស upload |
| `POST /api/jobs/tts` | `{text, input_lang(km·en·zh·ko), voice, translate}` → `{id}`; 400 `EMPTY_TEXT` |
| `GET /api/jobs` · `GET /api/jobs/{id}` | បញ្ជី (គ្មាន segments/logs, មាន `segment_count`) · job ពេញ |
| `POST /api/jobs/{id}/regenerate` | `{segments:[{idx, km?, voice?, t0?, t1?}], characters?:[{id, gender?, voice?, name?}], voice? (+ auto{on,male,female}), output?, youtube?}` → `{id}`; 409 `BUSY` · 400 `BAD_REQUEST` `NO_KHMER_TEXT` |
| `POST /api/jobs/{id}/video` | `{aspect, fit, crop_x, max_height, hide_subs, hide_effect, hide_bottom, hide_height, hide_strength}` (ទាំងអស់ស្រេចចិត្ត; តម្លៃខុស = កែដោយស្ងាត់) → `{id}`; 400 `NOT_DUB` `NO_AUDIO_YET` `NO_VIDEO_SOURCE` `NO_PICTURE` · 409 `BUSY` |
| `POST /api/jobs/{id}/speakers` | (v1.13) ស្គាល់តួអង្គឡើងវិញ៖ `{youtube?{cookies_browser, proxy}}` → `{id}`; ការងារនៅ `done` (បោះបង់ = ទុកតួអង្គចាស់); 400 `NOT_DUB` `NO_TIMING` `NO_AUDIO_SOURCE` `NO_AUDIO` · 409 `BUSY` |
| `POST /api/jobs/{id}/translation/prompt` · `/parse` · `/save` | Claude copy/paste៖ `{part,size,names}` → prompt · `{text,first?,last?}` → `items[] missing unknown …` (មិនរក្សា) · `{items:[{idx,km}]}` (draft ប៉ុណ្ណោះ; 409 `NOT_DRAFT`) · 400 `EMPTY_REPLY` |
| `POST /api/jobs/{id}/cancel` · `DELETE /api/jobs/{id}` | |
| `GET /api/jobs/{id}/file/{name}` | `name` ∈ whitelist (+ `voice_ref_c<1-99>.wav`; **`MediaFile`** — Range ✔, §3 #31); `?download=1` → `Content-Disposition` (`…_khmer_dub.mp3`, `…_khmer_tiktok_9x16.mp4` …) |
| `GET /api/jobs/{id}/source` · `/thumb` · `/subtitle/{en.vtt·km.vtt}` | វីដេអូ upload (Range ✔) · thumbnail · WebVTT បង្កើតពី segments |
| `GET·PUT /api/glossary` · `POST /api/glossary/reset` | អត្ថបទ glossary (`count`, `readings`, `maps`, `is_default`) |
| `POST /api/translate` · `GET /api/translate/diagnose` · `POST /api/llm/test` | បកអត្ថបទមួយ · សាកល្បង Google · សាកល្បង API key (ឆ្លើយ 200 `{ok:false,error}` ជានិច្ច) |
| `GET /api/vox/status` · `POST /api/vox/setup` · `/setup/cancel` · `GET /api/vox/log` | ដំឡើង VoxCPM2 (403 `VOX_INSTALL_DISABLED`; 409 `BUSY`) |
| `POST /api/vox/start` · `/stop` · `PUT /api/vox/config` | worker (quality, Turbo ⚡ …) |
| `GET·POST /api/vox/voices` · `PATCH·DELETE …/{id}` · `GET …/{id}/audio` | My voices (`{name, filename, data(base64), gender}`) · `PATCH {name?, gender?: Female\|Male\|""}` (ភេទស្គាល់ពីសំឡេងដោយខ្លួនឯងពេលប្រាកដ — `gender_auto`) |
| `POST /api/vox/presets/{key}/reroll` | Designed voice៖ មនុស្សថ្មីក្នុងស្ទីលដូចគ្នា (anchor ថ្មី) |
| `POST /api/vox/preview` → `{id}` · `GET …/{id}` · `GET …/{id}/audio` | សាកស្តាប់សំឡេង VoxCPM2 (thread; poll) |

---

## 9. Frontend (`static/`)

**គ្មាន build step, គ្មាន framework, គ្មាន CDN / font ខាងក្រៅ** (ដំណើរការ offline + ក្នុង preview ដែលគ្មាន network — font Kantumruy Pro ដាក់ក្នុង `static/fonts/`)។

- `index.html`៖ sidebar `#sidebar` (`#nav button[data-page]`), header (`#side-toggle`, ភាសា KM/EN, theme), ទំព័រ `#page-dub` `#page-tts` `#page-terms` `#page-history` `#page-settings`។ Step 4 = `#frame-row` (v1.9)។
- `app.js` = IIFE តែមួយ។ **រកផ្នែក**៖ `grep -n "^/\* =====" static/js/app.js` — helpers · icons · state · i18n · api/toast · theme/language · bindings · voices · navigation · source/video · upload · request builders · vertical video (TikTok) · jobs · **editor table** · Claude copy/paste · YouTube sync preview · history · terms · settings/system · docked players · menu slide · voices labels · VoxCPM2 · counters · init។
- **State**៖ `state.s` = settings (រក្សាក្នុង `localStorage.kds_settings`, debounce 200 ms; រចនាសម្ព័ន្ធ = `DEFAULTS()`: `voice` `translate` `output` `remake` `source` `youtube` `tts` `subs` `ui` `claude`)។ ផ្សេងទៀត៖ `kds_lang` · `kds_theme` · `kds_side` (ម៉ឺនុយ)។
- **Bindings**៖ `data-bind="output.fit"` លើ `.seg` (ក្រុមប៊ូតុង `data-value`) / checkbox / range / input / select → `syncBindings()` (state → DOM) និង handler (DOM → state); `data-out` + `data-fmt` បង្ហាញតម្លៃ។
- **i18n**៖ `data-i18n="key"` · `data-i18n-ph="key"` (placeholder) · `t(key, {var})` (`{var}` ក្នុងអត្ថបទ); key ត្រូវមានទាំង `km` និង `en` (§3 #2)។ `Ctrl+X` ក្លាយ `⌘X` លើ Mac (`IS_MAC`)។ កំហុស API → `errText(e)` រក `err.<CODE>`។
- **Job**៖ `trackJob(kind, id)` poll `/api/jobs/{id}` រៀងរាល់ ០.៩ វិ → `renderJob`; លទ្ធផល = `#dub-result` / `#tts-result` (តារាង Segments, player, ប៊ូតុងទាញយក, `#claude-box`, `#reframe-box` (bind `state.s.remake`))។
- **PWA** (v1.11)៖ ផ្នែក “install as an app” នៅចុង `app.js` — `beforeinstallprompt` (ទុក event, `preventDefault`) → ប៊ូតុង `#btn-install` ហៅ `prompt()`; គ្មាន event (Safari / Firefox) → បង្ហាញ `#install-help`; `appinstalled` → សារ + លាក់; `runsAsApp()` + `isSecureContext` + `window.self === window.top` + អេក្រង់ ≤ 900 px (CSS) → លាក់; `registerServiceWorker()` (secure context ប៉ុណ្ណោះ); `applyTheme()` ប្តូរ `meta[name=theme-color]`។ ប្តូរ `sw.js` / `offline.html` / `manifest` = សាកល្បងជាមួយ `test_pwa` (C ស្លាប់/ត្រឡប់ server ពិត)។
- **My voices** (v1.12)៖ `uploadVoiceFiles(files)` (ម្តងមួយឯកសារតាមលំដាប់ **បញ្ច្រាស់** — បញ្ជីបង្ហាញថ្មីជាងមុនមុន ដូច្នេះលំដាប់ចុងក្រោយ = លំដាប់ក្នុងប្រអប់ជ្រើសឯកសារ; `voxUploading` ការពារ batch ពីរ; `refreshVoices()` បន្ទាប់ពីឯកសារនីមួយៗ) · `[data-vox-upload-status]` (ក្នុង `#tpl-voice` — ប្រើក្នុងទំព័រ Dub និង TTS) · drag & drop លើ `.engine-vox` (`dragenter/over/leave/drop` ក្នុង `document`; `stopPropagation()` + `#up-drop, .engine-vox` ក្នុង handler `window` ដើម្បីកុំឲ្យឯកសារក្លាយជាវីដេអូ Upload) · `[data-voxrename]` → `PATCH`។ **គ្មាន device / GPU ក្នុងអត្ថបទ** (`voxDeviceLabel` ត្រូវបានលុប)។
- **សំឡេងតាមតួអង្គ** (v1.13)៖ `state.s.voice.auto {on, male, female}` (switch + ជម្រើស ♂ / ♀ ក្នុងកាត Voice; `voiceBody()` ផ្ញើ `auto`) · `autoPlan(chars)` (**ក្បួនដូចគ្នានឹង `autovoice.plan`**) · `#chars-panel` (ស្លាក ♂ / ♀ + ឈ្មោះ + Voice + ⇄ + «ស្គាល់ម្តងទៀត») · `.cb` លើជួរ · ជម្រើសទីមួយ «ស្វ័យប្រវត្តិ — ពិសិដ្ឋ» · `charChanged / charDirty` រាប់ក្នុងស្លាក «បានកែ» · `.vox-ref-char` (សំឡេងគំរូដែលបាន Clone ឲ្យស្តាប់)។
- **Regenerate រួសរាយ** (v1.13)៖ `releaseMedia()` (ដោះ `<audio>` / `<video>` មុនសំណើ; ត្រឡប់ `restore()` ពេលសំណើត្រូវបដិសេធ) · `renderJob` `retry` (§3 #32) + `staleBox` (`res.regen_failed`) ក្នុង `renderDubResult`។
- **ចុចជួរ** (v1.12)៖ `playFromRow` · `pointerdown`/`pointerup`/`keydown`/`focusin` ក្នុង `wireDubResult` · `subs.clickplay` (`DEFAULTS()`) · `.seg-table.clickplay` · `openSync(kind, startAt)` + `syncOpening` + `syncStartAt` · `NO_AUDIO` (ព្រាង)។
- **Dock** (v1.6)៖ `.dockable` ត្រូវបានកំណត់ទីតាំង fixed ខាងស្តាំ (≥ 1180 px; មួយបានតែមួយ) — §3 #15។

**ថែមការគ្រប់គ្រងថ្មី (checklist)**៖ ① HTML element + `data-bind` ② ដាក់តម្លៃក្នុង `DEFAULTS()` ③ i18n key (km + en) ④ request builder (ផ្នែក “request builders”) ⑤ server៖ `_ctx_from` / `sanitize_params` ⑥ test (UI + API) ⑦ screenshot ១៤៤០×៩០០ · ១៣៦៦×៧៦៨ · ១៩២០×១០៨០ · ៣៩០ (`python tests/shots.py`) ⑧ README + CHANGELOG។

---

## 10. Platform + Environment variables

| Variable | ប្រើនៅ | អត្ថន័យ |
|---|---|---|
| `HOST` · `PORT` · `NO_BROWSER` | `server.py` | លំនាំដើម `127.0.0.1`; `PORT` មិនកំណត់ + 8000 ជាប់ → ជាប់ដោយ V_Heang Studio **កំណែដដែល** (`running_instance`: `/api/health` ok + assets + version) = បើកវា ហើយចេញ (exit 0), ផ្សេងពីនេះ → 8001–8019; `PORT` កំណត់ដោយអ្នក + ជាប់ → ចេញ (exit 1); `NO_BROWSER=1` = មិនបើក browser |
| `KDS_DATA_DIR` | `config.py` | ថត data (លំនាំដើម `<project>/data`) |
| `KDS_VOX_HOME` · `KDS_VOX_IDLE_MIN` · `KDS_VOX_MODEL` | `vox_setup` `vox` `vox_worker` | ទីតាំង VoxCPM2 · idle ចេញ (30 នាទី) · model (`openbmb/VoxCPM2`) |
| `KDS_VOX_DISABLE_INSTALL=1` · `KDS_DISABLE_INSTALL=1` | `main` · `whisper_setup` | បិទប៊ូតុង Install (403) — សម្រាប់ server ចែករំលែក / preview ដូចក្នុង Arena |
| `KDS_VOX_STUB=1` | `vox_worker` | **tests ប៉ុណ្ណោះ**៖ មិនពិនិត្យ/ទាញ weights ពិត (ជាមួយ `PYTHONPATH=tests/stubvox` = `voxcpm` ក្លែង) |
| `KDS_MAX_UPLOAD_MB` | `uploads` | លំនាំដើម 4096; `0` = គ្មានដែនកំណត់ |
| `KDS_WHISPER_PIP_CMD` | `whisper_setup` | tests៖ ជំនួសពាក្យបញ្ជា pip |
| `KDS_DRY_RUN=1` · `KDS_PY_FALLBACKS` | `start.sh` | tests៖ បោះ `PYTHON=<path>` ហើយចេញ · បដិសេធ path Python បម្រុង |
| `KDS_TEST_WORK` · `KDS_PROJECT` · `PYTHON` | `tests/` | ថតការងាររបស់ tests · project · interpreter (`run_all.sh`) |

**Windows** (`start.bat`, CRLF)៖ `py -3` → `python` → `python3`; hint Microsoft Store; `PYTHONUTF8=1`; VoxCPM2 នៅ path ខ្លី `%LOCALAPPDATA%\KhmerDub\voxcpm` (ដែនកំណត់ 260 តួ); `CREATE_NO_WINDOW`។ GPU NVIDIA៖ installer ជ្រើស torch `cu128` (RTX 50 / Blackwell) ឬ build ផ្សេង; GPU ≤ 10 GB ប្រើ allocator ចំណេញ + សម្អាត cache។

**macOS** (`start.command` / `start.sh`, POSIX sh)៖ រក `python3`, `python3.13 … 3.10`, `python`, ក្រោយមក path Homebrew / python.org; រំលង stub `/usr/bin/python3` បើ `xcode-select -p` ខុស; ដក quarantine flag; ស្ថាបនា `.venv` ឡើងវិញបើខូច។ **Apple Silicon** → VoxCPM2 ប្រើ Metal (MPS, float32, `PYTORCH_ENABLE_MPS_FALLBACK=1`) — ការព្រមាន RAM < 15 GB; **Intel Mac** និង **Python Rosetta** → បដិសេធ (`INTEL_MAC` / `ROSETTA_PYTHON`; torch ថ្មីគ្មាន wheel Intel); `server.py` ប្រើ `certifi` បើ Python ពី python.org គ្មាន certificate។

**Linux**៖ `start.sh`; VoxCPM2 → `data/voxcpm`។

> ⚠ Windows និង Mac **មិនទាន់ដែលរត់លើម៉ាស៊ីនពិត** (§15) — Mac ត្រូវបានក្លែងលើ Linux (`test_platform` C), `start.bat` ត្រូវបានអានតែប៉ុណ្ណោះ។

---

## 11. Tests

**រត់**៖ `python3 tests/<suite>.py` (មួយ) · `sh tests/run_all.sh [suite …]` (ទាំងអស់ ≈ ១៥ នាទី; lint ជាមុន; `final_summary.log` មានពេលវេលា)។ ចំនួន check និងពេលវេលាខាងក្រោម = វាស់ក្នុង sandbox Linux (Python 3.13) នៅ v1.13.0 (`final_summary.log`)។ Chromium (Playwright) សម្រាប់ UI; **internet** សម្រាប់ suite ដែលសម្គាល់ 🌐 (Google Translate ពិត + Edge TTS ពិត + YouTube ពិត)។ ផ្នែកនៃ suite៖ `ONLY=A,B python3 tests/test_tiktok.py`។

| Suite | គ្របដណ្តប់ | 🌐 | Port | check · ពេល |
|---|---|---|---|---|
| `test_units` | logic សុទ្ធ៖ Designed voices, Voice/Time ក្នុងមួយជួរ (validation, windows, `_build_track`, `_synth_all`), ទំហំ MP4 · **static guards**៖ i18n, ជប៉ុនត្រូវបដិសេធ, `INTERRUPTED` | | — | 112 · 1 វិ |
| `test_core` | **logic សុទ្ធ offline** (characterization — ចាក់សោអាកប្បកិរិយាបច្ចុប្បន្ន)៖ `split_runs` / `split_sentences` · SRT/VTT parse / merge / `to_srt` · `TermMatcher` protect/restore (រួមទាំងលេខខ្មែរ) · terms 中文 / 한국어 · `detect_lang` · `time_stretch` / `soft_limit` / `mix_into` · `VoiceSettings` · config · `samples/` | | — | 46 · 0 វិ |
| `test_api` | server ពិត + VoxCPM2 stub៖ job lifecycle, Voice/Time, Designed voice anchors, TTS tab, History, cache headers | 🌐 | 8011 | 77 · 54 វិ |
| `test_ui` | Playwright៖ តារាង Segments, Voice/Time, Designed voices, footer កំណែ | | 8012 | 150 · 108 វិ |
| `test_follow` | តារាងតាមការចាក់ (audio / MP4 / YouTube player ក្លែង), គុណភាព MP4 | | 8014 | 54 · 86 វិ |
| `test_layout` | ម៉ឺនុយ slide, dock វីដេអូ (ទំហំអេក្រង់ច្រើន) | | 8017 | 62 · 65 វិ |
| `test_claude` | Claude copy/paste៖ parser + prompt (units), draft + endpoints (API), panel (UI) | 🌐 | 8032 | 169 · 72 វិ |
| `test_upload` | A units (probe, subtitle, parsers, installer) · B API · C browser · D **Whisper ពិត** (បើដំឡើង) | 🌐 | 8050–8054 | 252 · 122 វិ |
| `test_tiktok` (+`test_tiktok_ui`) | A units · B **ffmpeg ពិត — ពិនិត្យ pixel** · C API/jobs · D browser | 🌐 | 8060 · 8062 | 186 · 123 វិ |
| `test_hardsub` | A units (`clean_*`, ទំហំ effect, ក្រាហ្វ, label) · B **ffmpeg ពិត — pixel** (វីដេអូសាកល្បង៖ ២ pixel ជា «អក្សរ» → ជួរណា Blur ជួរណាមិនប៉ះ; 4 effect · strength · ទីតាំង · TikTok · 720p · ទំហំសេស · SAR · rotation · សំឡេងដើម · progress · ចម្លងពេលបិទ) · C API/jobs · D browser (Step 4, ប្រអប់លទ្ធផល, Sync Preview) | 🌐 | 8064 | 186 · 60 វិ |
| `test_pwa` | A ឯកសារ (manifest · icons PNG ទំហំ · sw · offline · `<head>` · i18n) · B routes + header + `server.running_instance` + `server.main()` (ប្រើឡើងវិញ / កំណែផ្សេង / PORT ដោយអ្នក) · C **Chromium**៖ installable (CDP `getInstallabilityErrors` ទទេ) · service worker + cache · **server ស្លាប់ → ទំព័រ offline → server ត្រឡប់ → dashboard បើកដោយខ្លួនឯង** · ប៊ូតុង install (event ក្លែង) · standalone / មិនមែន secure / iframe / អេក្រង់តូច · theme-color | | 8066 | 90 · 18 វិ |
| `test_platform` | A launchers (sh/dash/bash/shellcheck, Mac ក្លែង) · B `server.py` · C installer Mac · D browser · E **release tools** | | 8065 | 121 · 30 វិ |
| `test_clickplay` | ចុចជួរ → លេង៖ MP4 · YouTube player ក្លែង (បិទ / បើក / កំពុងផ្ទុក — `strict`) · សំឡេងខ្មែរ · ព្រាង (មានវីដេអូ + សំឡេងដើម) · switch · ប្រអប់ខ្មែរ (ចុច ≠ Tab) · text selection · dock · ខ្មែរ | | 8071 | 46 · 43 វិ |
| `test_voices` | **My voices**៖ API (POST / PATCH / DELETE, ឈ្មោះ, លំដាប់) · UI (ឯកសារច្រើន, ឈ្មោះដូចគ្នា, ឯកសារខុស, > 30 MB, ១ ឯកសារ + ប្រអប់សួរ, ✎, drop, batch ពីរ) · **គ្មាន spec របស់ PC** (៤ hardware ក្លែង × ២ ភាសា × ៣ ទំព័រ) | | 8072 | 72 · 66 វិ |
| `test_speakers` | **ស្គាល់តួអង្គ** (v1.13)៖ A units (F0 · ភេទ · ក្រុម · `autovoice.plan` · `clean_character_edits`) · B **សំឡេងដើមពិត** (សន្ទនា ១២ ជួរ ប្រុស / ស្រី ដោយ Edge Neural; Edge + VoxCPM2 stub; ⇄ · ឈ្មោះ · Voice ក្នុងមួយតួអង្គ / ជួរ · ស្គាល់ម្តងទៀត · សំឡេងរំខាន / ស្ងាត់) · C browser (ផ្ទាំងតួអង្គ · ស្លាក · ជម្រើស Voice · My voices ⇄) | 🌐 | 8073 | 209 · 62 វិ |
| `test_winlock` | **Windows**៖ A units (Range · `MediaFile` — ឯកសារមិនបើកចន្លោះបំណែក · ជំនួសពេលផ្ញើ · `remove_file` · `_guard` → `FILE_IN_USE`) · B API ជាមួយ **server ដែលធ្វើត្រាប់តាម Windows** (`tests/winlock`)៖ Regenerate ពេល ៣ download ពាក់កណ្តាលអាន · កម្មវិធីខាងក្រៅចាក់សោ MP4 មួយភ្លែត / ជារៀងរហូត · Regenerate បរាជ័យរក្សាសំឡេង + ការកែ · C Chromium (MP4 កំពុងចាក់ → Regenerate ជោគជ័យ; បោះបង់ / បរាជ័យ → តារាងកែនៅ) | 🌐 | 8074 | 58 · 37 វិ |
| `test_youtube` | **YouTube ពិត** `dQw4w9WgXcQ` (វីដេអូតែមួយដែលចូលបានពី sandbox) → MP4 1080p / 720p | 🌐 | 8013 | 18 · 47 វិ |
| _(មិនក្នុង run_all)_ `smoke_zip.py` · `check_preview.py` · `shots.py` | ZIP ដែលបានបង្កើត (unzip → start → dub → modes/line endings → unit suite ក្នុងថតថ្មី) · dashboard ដែលកំពុងរត់ · screenshot | 🌐 | 8020 · — · 8070 | — |

**Fixtures / stubs** (`tests/`)៖ `fixtures/jobs/` (job គំរូ ៣: EN / 中文 / 한국어) · `stubvox/voxcpm/` (កញ្ចប់ `voxcpm` ក្លែង៖ pitch ចេញពី style + seed ឬ bytes នៃ clip យោង — ដឹងសំឡេងណាត្រូវបានប្រើ) · `stubnowhisper/` (`sitecustomize.py` ធ្វើឲ្យ faster-whisper មើលទៅមិនទាន់ដំឡើង) · `winlock/` (`sitecustomize.py` ធ្វើឲ្យ Python លើ Linux / macOS ប្រព្រឹត្តដូច Windows៖ ឯកសារដែលនៅបើកស្រាប់ លុប / ជំនួសមិនបាន — `PYTHONPATH` + `KDS_WINLOCK_SIM=1`; `KDS_WINLOCK_LOG` · `KDS_WINLOCK_FILE` = កម្មវិធីខាងក្រៅចាក់សោ) · `synthvoice.py` (សំឡេងប្រុស / ស្រីពី Edge Neural សម្រាប់ test_speakers) · `fake_faster_whisper/` · វីដេអូតូចៗដែល suite បង្កើតដោយ ffmpeg ក្នុង `WORK/fx_*`។

**លំដាប់ និង dependency**៖ `test_ui` / `test_follow` / `test_layout` ចម្លង job ពី `WORK/data_api` (ផលិតដោយ `test_api`) — រត់ `test_api` មុន (មិនបាច់ក៏បាន៖ ប្រើ job គំរូ); `smoke_zip.py` ត្រូវការ fixture វីដេអូពី `test_upload` + `test_tiktok`; **កុំកែ `app/` `static/` `tests/` ពេល `run_all.sh` កំពុងរត់** (suite នីមួយៗអាន file ពេលចាប់ផ្តើម)។

**ទំរង់ test ថ្មី**៖

```python
from lib import *                       # Checker, Server, WORK, PROJECT, VERSION, make_stub_home, … (import មុន `app`)
import os
os.environ["KDS_DATA_DIR"] = str(WORK / "data_mytest")      # មុន `from app import …`
c = Checker("my feature")
srv = Server(8090, WORK / "data_mytest_srv", make_stub_home(WORK / "vox_mytest"), name="mytest").start()
try:
    r = srv.api("POST", "/api/jobs/dub", json={...}); job = srv.wait_job(r.json()["id"], 120)
    c.check(job["status"] == "done", "the job finishes", str(job.get("error")))
finally:
    srv.stop()
sys.exit(c.done())                       # 0 = ជោគជ័យ; បោះពុម្ព “== title: N passed, M failed ==”
```

UI test៖ `from ui_setup import build; srv = build(8091, "name")` (server + job គំរូ) រួច Playwright (`sync_playwright`)។ ផ្ទៀងផ្ទាត់ pixel (រូបភាព)៖ មើល `test_tiktok.py` ផ្នែក B (`Img`)។

**អន្ទាក់ពេលសរសេរ test** (ធ្លាប់ខាតពេល)៖ **v1.12** — `app.js` ជា module៖ `page.evaluate('state…')` មិនឃើញ `state` (ពិនិត្យ DOM) · `set_input_files` លាយ path និង buffer មិនបាន (ប្រើ buffer ទាំងអស់) · Chromium **Local Network Access** រារាំង iframe ពី `about:blank` · `Server.start()` លើ port ដដែលម្តងទៀតក្នុង ~៦០ វិនាទី → “Port … is already in use” (ប្រើ port ផ្សេង) · job ដែលសរសេរលើថាសក្រោយ server ចាប់ផ្តើម **មិនឃើញ** (`JobManager` load តែពេលចាប់ផ្តើម — ដាក់ fixture មុន `Server.start()`) · `pgrep -f` ត្រូវខ្លួនឯង (ប្រើ `-af`) · ffmpeg ក្លែងត្រូវជា **executable** (runner បញ្ចូល `-progress` បន្ទាប់ `cmd[0]`) · Playwright `route` handler ទទួល `(route, request)` · `saveSettings` debounce 200 ms → ចាំ ≥ 350 ms មុនអាន `localStorage` · ក្រោយចុច “make the video again” ចាំឲ្យកាត result ចាស់បាត់មុន · `add_init_script` រត់រាល់ navigation · `ffmpeg -shortest` កាត់ track SRT · `merge_segments` បិទភ្ជាប់ឃ្លាខ្លី (ប្រើអត្ថបទវែងគ្រប់គ្រាន់) · test launcher ប្រើ PATH គ្មាន Python + `KDS_PY_FALLBACKS=""` · កុំ chain suite ច្រើនក្នុង command តែមួយ (timeout) — `nohup` + poll។ **v1.13** — សំឡេងសាកល្បងតម្រូវឲ្យមាន internet (Edge) · test server ដែលគាំងទុក port → ការរត់បន្ទាប់លុប data ពេល server ចាស់នៅឆ្លើយ (`FileNotFoundError`) → `atexit.register(srv.stop)` · ការងារ draft៖ ស្លាក «N of N lines have no Khmer text» → តេស្តកែតួអង្គត្រូវការការងារ `done` · `locator[data-gender=…]` ឈប់ត្រូវបន្ទាប់ពី flip (ប្រើ `data-char`) · `locator.screenshot` (មិនមែន `clip=bounding_box()` ក្រោមបត់) · Chromium លើ sandbox ថ្មីត្រូវ `sudo python -m playwright install-deps chromium` · **ចុចប៊ូតុង ហើយរង់ចាំ job** — `status` ចាស់ `done` ត្រូវបានអាន មុនសំណើដល់ → ប្រើ `updated > since`

---

## 12. Release workflow (លំហូរចេញផ្សាយ)

```text
 ០  បម្រុងទុក      មុនកែធំ៖ git commit (ឬចម្លង app/ static/ README CHANGELOG ទៅថតបម្រុង)
 ១  កែកូដ          backend ជាមុន (logic សុទ្ធ + unit test) → pipeline / API → UI (html · css · js · i18n km+en) → docs
 ២  test តាម layer  units → API → UI ក្នុងពេលកែ (វិនាទី–នាទី)
 ៣  មើលដោយភ្នែក   python tests/shots.py  →  បើក PNG (១៤៤០×៩០០ · ១៣៦៦×៧៦៨ · ១៩២០×១០៨០ · ៣៩០)
 ៤  regression ពេញ  nohup sh tests/run_all.sh > /dev/null 2>&1 &     (≈ 15 នាទី; poll ≤ 120 វិ; មិនកែអ្វីពេលរត់)
 ៥  កំណែ           python tools/bump_version.py X.Y.Z               (៤ កន្លែង; --check ដើម្បីផ្ទៀងផ្ទាត់)
 ៦  docs           CHANGELOG (entry លើបំផុត) · README (“ថ្មីនៅ vX” + ផ្នែកពាក់ព័ន្ធ) · DEVELOPMENT.md (§11 ចំនួន check · §15 · §16 · §18)
 ៧  chmod +x       (បន្ទាប់ sandbox reset) start.sh start.command install-voxcpm.sh install-voxcpm.command tests/run_all.sh
 ៨  ZIP            python tools/build_zip.py            → ../khmer-dubbing-studio-vX.Y.Z.zip   (លុប ZIP ចាស់)
 ៩  smoke test ZIP python tests/smoke_zip.py            (unzip → start → dub ពិត → TikTok → modes · CRLF/LF → unit suite ក្នុងថតថ្មី)
១០  preview        (Arena) stop_process ចាស់ → start_process “V_Heang Studio” → python tests/check_preview.py
១១  ចម្លើយ         ជាខ្មែរ៖ ថ្មីអ្វី · របៀបប្រើ · ផ្ទៀងផ្ទាត់អ្វី (លេខពិត) · **មិនទាន់ផ្ទៀងផ្ទាត់អ្វី** · ជម្រើសបន្ទាប់ (ម្តងមួយ)
```

Preview ក្នុង Arena (`start_process`, name “V_Heang Studio”, cwd = project)៖

```sh
KDS_VOX_DISABLE_INSTALL=1 KDS_VOX_HOME=$HOME/.cache/kds-vox-preview HOST=0.0.0.0 PORT=8000 NO_BROWSER=1 python3 server.py
```

(`HOST=0.0.0.0` ដើម្បីឲ្យ preview ចូលបាន; `KDS_VOX_DISABLE_INSTALL=1` ព្រោះ sandbox គ្មាន RAM/GPU សម្រាប់ VoxCPM2។)

**បទដ្ឋានចេញផ្សាយ (Definition of Done)**៖ ☐ run_all បៃតងទាំងអស់ ☐ ZIP ត្រូវបាន **បើកដំណើរការពី ZIP** (មិនមែនតែថតកូដ) ☐ `bump_version --check` OK ☐ CHANGELOG + README + DEVELOPMENT.md ត្រូវ ☐ សារឆ្លើយប្រាប់ត្រង់ៗអំពីអ្វីមិនទាន់ផ្ទៀងផ្ទាត់។

---

## 13. របៀបធ្វើការជាមួយ AI agent (workflow ដែលបានប្រើពី v1.0 ដល់ v1.9)

នេះគឺជា **លំហូរការងារ** ដែលបាននាំ project ពី v1.0 ដល់ v1.9 ក្នុង session ជាបន្តបន្ទាប់ជាមួយម្ចាស់។ បន្តតាមវា ដើម្បីឲ្យលទ្ធផលមានគុណភាពដូចគ្នា។

1. **អានសំណើតាមព្យញ្ជនៈ** — ម្ចាស់សរសេរខ្លីៗជាខ្មែរ (ជាញឹកញាប់ជា bullet ៣-៤)។ កំណត់វិសាលភាពដោយខ្លួនឯង ហើយ **កត់ក្នុង CHANGELOG ថាអ្វីជាការសម្រេចរបស់ AI** (ដើម្បីឲ្យម្ចាស់កែបាន — ដូច TikTok v1.9)។ សួរតែពេលការទាយខុសថ្លៃ; បើម្ចាស់ថា “just answer” → កុំសួរ (§2 #8)។
2. **ស្រាវជ្រាវ (ពេលមានអត្ថន័យ spec)** — web search/fetch (ឧ. spec TikTok: 9:16, 1080×1920, H.264 + AAC, 10 នាទី, ~287 MB iOS; wheel PyTorch/ctranslate2/imageio-ffmpeg លើ Mac)។ ប្រភពដែលមិនត្រូវគ្នា → ជ្រើសតម្លៃប្រុងប្រយ័ត្ន ហើយកត់ក្នុង docs។
3. **រចនាជា layer** — logic សុទ្ធ (testable ដោយមិនត្រូវការ ffmpeg/browser) → pipeline/API → UI → docs។ ឧទាហរណ៍ `frame.py`៖ `plan()` សម្រេចចិត្ត, `audio.mux_video` ប្រតិបត្តិ។
4. **វិធីកែ** — កែធំច្រើនបន្ទាត់ = **patch script ដែលមាន assert** (ស្វែងរកអត្ថបទចាស់ត្រូវតែមាន **ម្តងប៉ុណ្ណោះ** បើមិនដូច្នេះឈប់; មិនរត់ម្តងទៀត)។ កែតូច = `edit_file`។ បម្រុងទុកមុនកែធំ។ ទម្លាប់នេះការពារការជំនួសខុសស្ងាត់ៗក្នុង file ១០០០+ បន្ទាត់។
5. **Test ពិតជាងក្លែង** — ប្រើសេវាពិត (Google Translate, Edge TTS, YouTube, ffmpeg) ឲ្យបានច្រើនបំផុត; ក្លែង (stub) តែអ្វីធ្ងន់ (VoxCPM2 ត្រូវការ ~8 GB RAM/GPU)។ Layer ៤៖ units → **ffmpeg ពិត + ពិនិត្យ pixel** → API → browser (Playwright)។ បើ test បរាជ័យ → រក **មូលហេតុ** (កុំបន្ធូរ test)។
6. **មើលដោយភ្នែក** — `python tests/shots.py` រួចមើល PNG៖ ក្នុងគ្រប់ទំហំ (១៤៤០ · ១៣៦៦ · ១៩២០ · ៣៩០ px) × ខ្មែរ/English × dark/light។ វារកឃើញបញ្ហា layout ច្រើនដែល test មិនឃើញ (កាត hint ត្រួតគ្នា, ទទឹង dock, phone mock)។
7. **Regression ពេញមុនចេញផ្សាយជានិច្ច** — ក្នុង background, poll ≤ 120 វិ (កុំរង់ចាំក្នុង command តែមួយ — timeout 30 វិ); **មិនកែ app/ static/ tests/ ពេលរត់**។ បើកែ test ពាក់កណ្តាលរត់ → suite ក្រោយអាន file ថ្មី → លទ្ធផលមិនអាចទុកចិត្ត (ធ្លាប់ត្រូវ revert)។
8. **ផ្ទៀងផ្ទាត់ ZIP ដែលបានបង្កើត** (មិនមែនតែថតកូដ)៖ `smoke_zip.py` — ចាប់បានបញ្ហា mode / line ending / ឯកសារបាត់។
9. **ទុក app ឲ្យរត់ក្នុង preview** (port 8000) ឲ្យម្ចាស់សាកភ្លាមៗ; restart + `check_preview.py` បន្ទាប់ពីគ្រប់ release។
10. **ចម្លើយទៅម្ចាស់** (ខ្មែរ + English terms)៖ ថ្មីអ្វី (អ្វីដែលអ្នកប្រើឃើញ) → របៀបប្រើ → **លេខពិត** ដែលបានផ្ទៀងផ្ទាត់ → **អ្វីដែលមិនទាន់ផ្ទៀងផ្ទាត់** (ត្រង់ៗ៖ Mac/Windows ពិត, Safari …) → ជម្រើសបន្ទាប់ម្តងមួយ។ ខ្លីពេលម្ចាស់ចង់ឲ្យខ្លី។
11. **រក្សា docs ឲ្យទាន់សម័យ** — CHANGELOG ក្នុងមួយកំណែ; ឯកសារនេះ (§11 §15 §16 §18)។ Session មួយអាចបាត់ memory → ឯកសារនេះជាអនុស្សរណៈតែមួយ។

### Sandbox របស់ Arena (បើបន្តនៅទីនោះ)

- Tools៖ `bash` (30 វិ លំនាំដើម, timeout អតិបរមា ១៨០០) · `start_process` (server ដែលត្រូវរស់ — **preview នៅទីនេះ**) · `present_file` (បង្ហាញ deliverable) · `ask_user` (សំណួរជ្រើសរើស) · web search/fetch · generate_image/speech (មិនប្រើក្នុង project នេះ)។
- **Sandbox អាច reset** (បាត់៖ pip packages · `~/.cache` · bit +x · process)។ File ក្នុង `/home/user` នៅដដែល។ ស្តារ៖

```sh
cd khmer-dubbing-studio
pip install --break-system-packages -r requirements.txt -r tests/requirements-dev.txt faster-whisper
python3 -m playwright install chromium && python3 -m playwright install-deps chromium     # install-deps ត្រូវ root/sudo
chmod +x start.sh start.command install-voxcpm.sh install-voxcpm.command tests/run_all.sh tools/*.py
export KDS_TEST_WORK=$HOME/.cache/kds-tests          # /tmp = tmpfs 1 GB
```

- RAM ~1.9 GB, `/tmp` = tmpfs 1 GB → ប្រើ VoxCPM2 stub; វីដេអូតូចៗក្នុង test។ YouTube ចូលបានតែវីដេអូ `dQw4w9WgXcQ`; Google Translate + Edge TTS ចូលបាន។
- ពេលបោះពុម្ពលទ្ធផល JSON ពី tool → backslash ត្រូវបាន escape (មើលកុំច្រឡំ)។ `pkill -f "python3 test_"` សម្លាប់ shell របស់ tool ខ្លួនឯង → ប្រើ pid ឬ `pgrep -af`។

---

## 14. មេរៀន និងអន្ទាក់ (Lessons learned)

**ffmpeg / វីដេអូ**
- ffmpeg 7.0 (static) ចេញយឺតស្មើពេល encode ទាំងមូលបន្ទាប់ SIGTERM → cancel ត្រូវ `kill()`; ចប់ធម្មតាកុំប៉ះ (+faststart ត្រូវការ pass ចុងក្រោយ)។
- Blur background ធ្វើលើច្បាប់ចម្លង **១/៨** (gblur sigma 3) → លឿនជាងមុនច្រើន; encode 1080×1920 ≈ 0.5× real time (CPU sandbox)។
- `frame.plan()` ត្រូវគិត rotation (ទូរស័ព្ទ) និង SAR (pixel មិនការ៉េ) → “already 9:16 ±1.5%” មិនធ្វើអ្វី។
- `-shortest` កាត់ track SRT; មិនត្រូវប្រើពេលមាន subtitle track។
- HDR៖ មិនទាន់ tone-map (ពណ៌អាចស្លេក — មិនទាន់សាក)។

**UI**
- Browser ប្រើ script ចាស់ → fingerprint `?v=<ver>-<sha1>` + `no-cache` (v1.1.2)។ ពេល extract ZIP មិនពេញ → banner ក្រហម។
- ancestor នៃ `.dockable` មិនត្រូវមាន `transform / filter / contain` (§3 #15)។
- thumbnail ពី YouTube (`hqdefault` → `mqdefault`) អាច 404 → `onerror` ត្រលប់ទៅរូបគំរូ SVG។
- panel លទ្ធផល (remake) ត្រូវមាន state ផ្ទាល់ខ្លួន (`state.s.remake`) — កុំចែករំលែកជាមួយ Step 4 (ពេលធ្វើនេះ ត្រូវប្តូរ Step 4 ដោយអចេតនា)។

**Platform**
- Windows៖ `os.replace` MP4 អាច PermissionError (antivirus) → `replace_file` ព្យាយាមម្តងទៀត។ `.bat` ត្រូវ CRLF (មួយ LF = ខូច)។
- macOS៖ `/usr/bin/python3` ជា stub ដែលបើក pop-up ដំឡើង Xcode → បដិសេធពេល `xcode-select -p` ខុស។ `.venv` ដែលមាន symlink `bin/python` ខូច → `[ -d .venv ]` (មិនមែន `[ -x ]` — false សម្រាប់ symlink ខូច) រួចបង្កើតឡើងវិញ។ Python ពី python.org គ្មាន certificate → `certifi`។
- VoxCPM2 លើ MPS បង្ខំ float32; ត្រូវ `PYTORCH_ENABLE_MPS_FALLBACK=1`។ torch ថ្មីគ្មាន wheel Intel Mac។

**Windows / ឯកសារ (v1.13)**
- Windows លុប / ប្តូរឈ្មោះ / ជំនួសឯកសារដែលនៅបើកស្រាប់មិនបាន (`PermissionError: [WinError 32]`; `open()` របស់ Python មិនប្រើ `FILE_SHARE_DELETE`)។ `FileResponse` ទុកឯកសារបើកអស់ពេល browser អាន → `<video>` ដែលអានយឺត / ឈប់ ទុក request ពាក់កណ្តាលអានអស់ពេលជាច្រើននាទី។ **កុំទុកឯកសារបើកចន្លោះ chunk** (`MediaFile`)។ លុប / ជំនួសឯកសារ output តាម `audio.remove_file` / `replace_file` (ព្យាយាមម្តងទៀត) ហើយ**កុំឲ្យការលុបឯកសារចាស់បរាជ័យការងារ**។ macOS / Linux មិនបង្ហាញ → bug លាក់ទុកយូរ; អ្នកប្រើអាន «Internal error» ជា «Internet error»។
- **ធ្វើត្រាប់តាមប្រព័ន្ធដែលគ្មាន** (`tests/winlock/sitecustomize.py`; បើក `PYTHONPATH` + `KDS_WINLOCK_SIM=1`)៖ រាប់ `open(..,'rb')` ហើយ `os.unlink / replace / rename` បោះ `PermissionError` ពេលមាន handle (+ `KDS_WINLOCK_FILE` = កម្មវិធីខាងក្រៅចាក់សោ)។ **បង្កើត bug ឡើងវិញជាមុនជាមួយកំណែចាស់ពី ZIP** (`KDS_PROJECT=…`) រួចទើបកែ — បានភស្តុតាងថារកមូលហេតុត្រូវ។ សញ្ញាពីរូបអេក្រង់របស់អ្នកប្រើ៖ ជំហាន TTS «Waiting» + error = ការបរាជ័យនៅក្នុង `run_regenerate` រវាង `job.step(…, 'pending')` និង `job.step('tts', 'running')` (`_fail` ដាក់ `error` តែលើជំហានដែល `running`)។
- Job ដែលបរាជ័យមិនត្រូវលាក់ការងាររបស់អ្នកប្រើ (§3 #32) — ការកែត្រូវតែនៅក្នុង job មុនពេលអាចបរាជ័យ ហើយ UI បង្ហាញតារាងកែឡើងវិញ។

**Test / ដំណើរការ**
- កែ test ពេល `run_all.sh` កំពុងរត់ = ខូច (suite អាន file ពេលចាប់ផ្តើម)។ កែ `run_all.sh` ខ្លួនឯងពេលវារត់ = ក៏ខូចដែរ (shell អាន script បន្តិចម្តងៗ)។
- `FAKE_YT` (YouTube player ក្លែង) ចែករំលែករវាង test_follow និង test_layout (អានពី source test_follow)។
- Chromium 153 ចាក់ H.264 + AAC បាន (កំណត់ត្រាចាស់ថាមិនបាន = លែងពិត)។
- `Server(extra_env=…)` ជំនួស default ណាក៏បាន (ឧ. `PYTHONPATH`, `KDS_VOX_DISABLE_INSTALL`)។

**កូដ**
- បកប្រែ Google មិនត្រូវប្រើ pattern “១ ជួរ = ១ request” (§3 #21)។
- `merge_segments` បិទភ្ជាប់ឃ្លាខ្លី → fixture test ត្រូវមានឃ្លាវែងគ្រប់គ្រាន់។
- `HTTPException` → JSON `{"detail": {...}}` (មិនមែន `{"code": …}` ត្រង់ៗ)។
- **ថត voices** (v1.12)៖ បញ្ជី My voices តម្រៀបតាម **mtime របស់ folder** (ថ្មីមុន)។ សរសេរ `meta.tmp` ក្នុង folder រួច `replace` ធ្វើឲ្យ mtime ប្តូរ → សំឡេងលោតទៅលើ; `rename_custom` ស្តារ mtime ដោយ `os.utime` (ទាំងនេះមាន test)។
- “Patch script” ក្នុង Python៖ ក្នុង file មាន `\` មួយ; ក្នុង string មិន raw ត្រូវសរសេរ `\\` (មិនមែន `\\\\`)។
- **/tmp ជា RAM** (tmpfs ~1 GB)៖ download ធំ (FLEURS / LibriSpeech ~៣៦០ MB) ទុកចោល → Chromium «Target crashed» ក្នុង test_voices។ ទុក scratch តូច ហើយលុប download ។ `pkill -f server.py` សម្លាប់ shell របស់ tool + preview។
- **ការស្គាល់ភេទ (v1.13)**៖ MFCC / timbre មិនប្រសើរជាង F0; whitening ប្រសើរ AUC ០.៨៤៤ → ០.៨៨៩ ប៉ុណ្ណោះ (មិនប្រើ); threshold ក្រុមតិច (2.4–2.8) បំបែកមនុស្សម្នាក់ (5–13%) → `SPLIT_C` 3.4; ជួរចម្លែក (octave error, តន្ត្រី) បង្កើតតួអង្គក្លែងក្លាយ → F0_OK + minority rule; sine 440 Hz អានជា 220 Hz = ស្រី។

---

## 15. ដែនកំណត់ · មិនទាន់ផ្ទៀងផ្ទាត់ · Backlog

### មិនទាន់ផ្ទៀងផ្ទាត់ (កុំអះអាងថា “ដំណើរការ” ដោយគ្មានភស្តុតាង)

| # | អ្វី | ហេតុអ្វី / របៀបផ្ទៀងផ្ទាត់ |
|---|---|---|
| 1 | **Mac ពិត** និង **Windows ពិត** | Mac ត្រូវបានក្លែងលើ Linux; `start.bat` ត្រូវបានអាន មិនដែលរត់។ ឲ្យម្ចាស់ paste កំហុសពី Terminal / cmd |
| 2 | VoxCPM2 លើ **Metal (MPS)** · `pip` ចូល `.venv` លើ Mac/Windows | គ្មានម៉ាស៊ីន |
| 3 | `imageio-ffmpeg` របស់ Mac មាន **libx264 / libmp3lame**? | បើគ្មាន → `ffmpeg_failure()` ផ្តល់ hint `brew install ffmpeg` |
| 4 | **Firefox / Safari** | សាកតែ Chromium |
| 5 | **Prompt Claude ពិត** (`manualtr.build_prompt`) | មិនដែលរត់ជាមួយ Claude ពិត។ បើចម្លើយមានរូបរាងផ្សេង → កែ `manualtr.py` + បន្ថែម case ក្នុង `test_claude.py` |
| 6 | Whisper លើ **zh / ko** | model ធំជាង (ទាញពេលប្រើលើកដំបូង) |
| 7 | Upload តាម **proxy e2b** (preview Arena) | មិនដែលសាក upload ធំតាម proxy |
| 8 | **Turbo ⚡** (CUDA graph) | លទ្ធផលពិតរបស់ម្ចាស់មិនទាន់មក |
| 9 | វីដេអូ **HDR** | ពណ៌អាចខុស (គ្មាន tone-map) |
| 10 | **PWA** ក្នុង Safari (Add to Dock) / Firefox · ការដំឡើងពិតលើ Windows / macOS · YouTube iframe ក្នុងបង្អួច App | សាកតែ Chromium លើ Linux (CDP + event ក្លែង + server ស្លាប់ពិត) |
| 11 | **ចុចជួរ** ជាមួយ **YouTube ពិត** (iframe, autoplay មានសំឡេងក្នុងព្រាង) | សាកជាមួយ `YT.Player` ក្លែង + `<video>` ពិត |
| 12 | **Windows ពិត** — ការកែ «Internal error ពេល Regenerate» (§3 #31) | ផ្ទៀងផ្ទាត់ដោយ simulation (`tests/winlock`) + Chromium៖ v1.12.0 ឲ្យ error ដូចរូបរបស់ម្ចាស់ ហើយ v1.13.0 ជោគជ័យ។ មិនទាន់រត់លើ Windows ពិត → សុំម្ចាស់សាក ហើយ paste **Details** បើនៅមាន error |
| 13 | **Safari / Firefox** ជាមួយ `MediaFile` (Range) · `If-Range` | សាកតែ Chromium; ក្បួន Range តាម RFC 7233 |
| 14 | **ការស្គាល់តួអង្គ** លើវីដេអូពិតច្រើនប្រភេទ (YouTube · Bilibili · ភាពយន្ត) | វាស់ជាមួយ FLEURS · LibriSpeech · Edge Neural (CHANGELOG)។ ក្នុងវីដេអូពិតរបស់ម្ចាស់ ១ តួអង្គត្រូវបានស្គាល់ជា «ស្រី» ហើយម្ចាស់ប្តូរទៅ «ប្រុស» ដោយ ⇄ (ទំនងជាសំឡេងប្រុសខ្ពស់ — ខុស ១ ករណីពិត) |
| 15 | **Clone តួអង្គ** (`vox:s:N`) ជាមួយ VoxCPM2 ពិត | សាកជាមួយ stub (ដឹងថាសំឡេងណាត្រូវបានប្រើ)។ គុណភាព Clone ជាមួយ clip ៣–២០ វិនាទីពីវីដេអូពិត មិនទាន់ស្តាប់ |

### ដែនកំណត់ដែលស្គាល់

ប្តូរ `max_height` = ទាញវីដេអូ YouTube ឡើងវិញ · dock បានតែមួយ, បិទក្រោម 1180 px · Google Translate (ឥតគិតថ្លៃ) អាច rate-limit (429) · YouTube ទប់ស្កាត់ IP data-center (ត្រូវ cookies ឬ paste transcript) · VoxCPM2 ត្រូវ ~8 GB VRAM/RAM · Edge TTS ត្រូវ internet · ពេលវេលា TikTok 10 នាទី / ~287 MB (iOS) / ~72 MB (Android) ជាតម្លៃពីគេហទំព័រដែលមិនត្រូវគ្នា → កម្មវិធីតែព្រមាន មិនបដិសេធ។ · **ការស្គាល់តួអង្គ (v1.13)**៖ ស្តាប់តែ**សំឡេង** — អ្នកនិទានម្នាក់អានគ្រប់តួអង្គ = ១ តួអង្គ (មិនអានអត្ថបទ) · ភេទដូចគ្នា ២ នាក់ភាគច្រើនត្រូវបញ្ចូលគ្នា (AUC ≈ 0.86) · ខុសចំពោះក្មេង · សំឡេងប្រុសខ្ពស់ ~250 Hz (jfk) · តន្ត្រី · ការច្រៀង · និយាយត្រួតគ្នា · តំបន់ 140–195 Hz ត្រឹមត្រូវ ≈ 81% · Edge មានសំឡេងខ្មែរតែ ២

### មិនទាន់សាងសង់ (បានស្នើទៅម្ចាស់ មិនទាន់មានចម្លើយ)

Burn-in **subtitle ខ្មែរ** លើវីដេអូ (សម្រាប់ TikTok) · HDR → SDR tone-mapping · Crop តាមមុខមនុស្ស · Encode GPU (NVENC / VideoToolbox) · **Gemini TTS** (គាំទ្រខ្មែរ, គ្មាន clone សំឡេង) · បកប្រែតាម Claude API key (ជម្រើស B)។ · ស្គាល់តួអង្គ**ពីអត្ថបទ** ដោយ Claude / LLM (អ្នកនិទាន · ប្រុស · ស្រី · ក្មេង ក្នុងមួយជួរ) សម្រាប់រឿងដែលអ្នកនិទានម្នាក់អានគ្រប់តួអង្គ · pitch / ល្បឿនផ្សេងគ្នារបស់ Edge ឲ្យតួអង្គភេទដូចគ្នាស្តាប់ខុសគ្នា (ទាំងពីរបានស្នើទៅម្ចាស់ ក្នុងចម្លើយសំណួរ v1.13; មិនទាន់មានចម្លើយ)

### Backlog បច្ចេកទេស (តាមអាទិភាព)

1. **Git + CI**៖ `git init`, commit មួយ, GitHub Actions រត់ suite offline (units, platform, tiktok A/B, ui, follow, layout)។ (ពេលនេះ project មិនទាន់ក្នុង git — ZIP ជាអ្នកដឹក។)
2. **ការផ្ទៀងផ្ទាត់ពិត** Windows + Mac (#1–#3 ខាងលើ) — សំខាន់បំផុតសម្រាប់អ្នកប្រើពិត។
3. **ប្រហោង test (នៅសល់)**៖ `translate.Translator` (batch / route / fail-fast / LLM — សាកតែតាម `test_api` ជាមួយ Google ពិត; គួរបន្ថែម test offline ជាមួយ HTTP ក្លែង) · `tts.Synth` (hybrid synth, retry, cache — សាកតែជាមួយ Edge ពិត) · `ytsource` (សាកតែជាមួយវីដេអូតែមួយ) · `vox_worker` ពិត។ (ពី 1.9.1 `test_core.py` គ្របដណ្តប់ text / glossary / transcript / audio សុទ្ធ។)
4. `app.js` 2,800 បន្ទាត់ក្នុង IIFE មួយ → បំបែកជា ES modules (`<script type="module">`, គ្មាន build) — ប្រយ័ត្ន state/bindings ចែករំលែក; README 128 KB → បំបែកតាមប្រធានបទ។
5. **Unused imports** (pyflakes)៖ `asr.py` (`faster_whisper` ជា probe — ចេតនា), `pipeline.py` `json`, `transcript.py` `LANGS`, `tts.py` `field` `Path` `SR` `has_khmer`, `ytsource.py` `time` → លុប រួចបើក pyflakes ពេញក្នុង `run_all.sh`។
6. ប្តូរឈ្មោះ field `en` → `src` (ត្រូវការ migration job.json ចាស់ + UI)។
7. key i18n ដែលមិនដែលប្រើ (~១៩១ មិនបានយោងដោយ literal — ភាគច្រើនជា key dynamic `err.*`) → ពិនិត្យ។

---

## 16. ប្រវត្តិកំណែ និងការសម្រេចចិត្ត

លម្អិត៖ `CHANGELOG.md`។ សង្ខេប (កំណែ → អ្វី → ការសម្រេចចិត្តសំខាន់)៖

| កំណែ | អ្វី | ការសម្រេចចិត្ត / ហេតុផល |
|---|---|---|
| 1.0.0 | YouTube / Paste → Google Translate → Edge TTS → MP3 + SRT; glossary រក្សាពាក្យ English | hybrid voice (Khmer + English) ព្រោះ Edge អាន “API” ខុស |
| 1.0.1 | Translate batch ១៦ + ៤ route + fail-fast | វីដេអូ ១៥ នាទីធ្លាប់ជាប់ ~២០ នាទី |
| 1.1.0 | **VoxCPM2** (Designed ×8, Clone, Original speaker) · Subtitle on/off | venv ដាច់ដោយឡែក + worker (torch ធ្ងន់) |
| 1.1.1 | GPU ៨ GB / RTX 50 (`cu128`) / retry OOM / CPU fallback | គាំទ្រ GPU ៨ GB (ឧ. RTX 5050 / 4060) |
| 1.1.2 | កែ៖ browser ប្រើ script ចាស់ | fingerprint asset + `no-cache` |
| 1.2.0 | Clone ប៉ុណ្ណោះ (Designed ត្រូវលុបតាមសំណើ) · **បិទសំឡេងដើមពេលនិយាយខ្មែរ** · Turbo ⚡ · Settings ស្អាត | សំណើម្ចាស់ #3 #4 |
| 1.3.0 | **中文 + 한국어** → ខ្មែរ; ស្គាល់ភាសាតាមអក្សរ; ជប៉ុនបដិសេធ | `cjkterms.py` ពាក្យ server/서버 → “server” |
| 1.4.0 | **Voice + Start/End ក្នុងមួយជួរ** · **Designed voices មកវិញ** · 🔊 ស្តាប់ឃ្លា | ម្ចាស់ប្តូរចិត្តវិញ (#2) |
| 1.5.0 | MP4 ≤ **1080p** · តារាងតាមវីដេអូ (follow playback) | #5 |
| 1.6.0 | ម៉ឺនុយ slide · វីដេអូ **dock** ខាងស្តាំ | #6 |
| 1.7.0 | **Claude copy/paste** (`manualtr.py`) | ជម្រើស A (Claude Pro គ្មាន API) |
| 1.8.0 | **Upload Video** + ប៊ូតុង Install Whisper | “just answer” → មិនសួរ |
| 1.9.0 | **TikTok 9:16** (`frame.py`) · **Mac + Windows** (launchers, MPS) | scope ជាការសម្រេច AI (#9) |
| 1.10.0 | **បិទបាំង Subtitle ដើម** (`hardsub.py`; Step 4 · ប្រអប់លទ្ធផល · Sync Preview) | សំណើម្ចាស់ #12 |
| 1.13.0 | **សំឡេងតាមតួអង្គ** (`speakers.py` + `autovoice.py`; ជំហាន `speakers`; ផ្ទាំងតួអង្គ; Clone តួអង្គ) · **កែ «Internal error» ពេល Regenerate លើ Windows** (`MediaFile` មិនទុកឯកសារបើក; `remove_file`; `FILE_IN_USE`; តារាងកែនៅតែនៅពេលបរាជ័យ) | សំណើម្ចាស់ #15 (៣ ចំណុច)។ ភេទ = F0 (មិនមែន AI model — មិនដំឡើងអ្វីថ្មី); ចូលចិត្តបញ្ចូលតួអង្គ ជាងបំបែក; Edge មានសំឡេងខ្មែរតែ ២។ Bug Windows បង្កើតឡើងវិញដោយ simulation (`tests/winlock`) |
| 1.12.0 | **ឈ្មោះ V_Heang Studio** · **My voices ច្រើនឯកសារ** (+ ✎, drop, `PATCH`) · **គ្មាន spec របស់ PC** ក្នុង UI · **ចុចជួរ → លេងវីដេអូ** (+ ព្រាងមានវីដេអូដើម) | សំណើម្ចាស់ #14 (៤ ចំណុច); identifier ខាងក្នុងមិនប្តូរ |
| 1.11.0 | **ដំឡើងជា App (PWA)**៖ manifest + service worker (ទំព័រ «មិនទាន់ដំណើរការ») + ប៊ូតុង + icons; `server.py` មិនបើកច្បាប់ចម្លងទី ២ | សំណើម្ចាស់ #13 (PWA; មិនទាន់ hosting) |
| 1.9.1 | **Dev Kit**៖ DEVELOPMENT.md · HANDOFF_PROMPT.md · `tests/` portable · `tools/` · `test_core` (46) · guard ថ្មី (i18n, ជប៉ុន, INTERRUPTED, cache headers, release tools) | សំណើម្ចាស់ #11; កម្មវិធីមិនប្តូរ |

---

## 17. បន្តក្នុង AI chat ថ្មី

1. **ឲ្យ AI ថ្មី**៖ ZIP (ឬថត project) + សារដំបូង = មាតិកា `HANDOFF_PROMPT.md`។ បើ AI មិនអាចអាន ZIP → paste `HANDOFF_PROMPT.md` + `DEVELOPMENT.md` (+ entry លើបំផុតនៃ `CHANGELOG.md`) ជាសារ។
2. **AI ថ្មីត្រូវធ្វើ (ជាមុន)**៖ អាន §2 §3 §13 → ស្តារ environment (§13) → `python3 tests/test_units.py` + `python3 tools/bump_version.py --check` → (បើអាច) `sh tests/run_all.sh` ដើម្បីដឹងស្ថានភាពចាប់ផ្តើម → សួរម្ចាស់ថាចង់ធ្វើអ្វី (បង្ហាញជម្រើសក្នុង §18 ម្តងមួយ)។
3. **AI គ្មាន shell**៖ ត្រូវប្រាប់ម្ចាស់ត្រង់ៗ; ស្នើ patch ជា diff តូចៗ; ឲ្យម្ចាស់រត់ `sh tests/run_all.sh` ហើយ paste `final_summary.log`។ **កុំអះអាងថា test ជាប់** ដោយមិនបានរត់។
4. **ចុងបញ្ចប់នៃ session**៖ bump កំណែ · CHANGELOG · README · កែ §11 §15 §16 §18 ក្នុងឯកសារនេះ · build ZIP · smoke test។
5. **ម្ចាស់ project ផ្សេង (មនុស្ស)**៖ ឯកសារនេះក៏ដូចគ្នា — បន្ថែម៖ `git init` ជាមុន (§15 backlog #1)។

---

## 18. សំណួរដែលនៅបើកចំហ (សួរម្ចាស់ម្តងមួយ)

1. **TikTok (v1.9.0)**៖ ម្ចាស់មិនទាន់ឆ្លើយ feedback។ លំនាំដើម “Blur ផ្ទៃខាងក្រោយ” ត្រឹមត្រូវទេ? ចង់បាន **Burn-in subtitle ខ្មែរ** លើវីដេអូទេ? (បានស្នើរួច)
2. **Mac / Windows ពិត**៖ `start.command` / `start.bat` ដំណើរការទេ? (សុំ paste កំហុស បើមាន)
3. **Claude copy/paste ពិត**៖ ចម្លើយរបស់ Claude ត្រូវ parse បានទេ? (បើមិនបាន សុំគំរូចម្លើយ)
4. **Gemini TTS** (គាំទ្រខ្មែរ, គ្មាន clone សំឡេង)៖ ចង់បានជាជម្រើសសំឡេងទេ? (បានស្នើរួច)
5. **Turbo ⚡** លើ GPU របស់ម្ចាស់៖ លឿនជាង ≈ ២× ដោយសំឡេងដូចដើមទេ?
6. **Upload Video (v1.8)**៖ ម្ចាស់មិនទាន់មាន feedback។
7. **បិទបាំង Subtitle ដើម (v1.10.0)**៖ ម្ចាស់មិនទាន់មាន feedback។ ចង់បាន **រកទីតាំង Subtitle ដោយស្វ័យប្រវត្តិ** (OCR / ការរកគែម) ឬ **burn-in Subtitle ខ្មែរ** លើ band នោះទេ? band មិនពេញទទឹង (ឧ. តែកណ្តាល) ចាំបាច់ទេ?
8. **PWA (v1.11.0)**៖ ម្ចាស់មិនទាន់មាន feedback។ ជំហានបន្ត (ជម្រើសដែលបានស្នើ)៖ script បង្កើត shortcut ចាប់ផ្តើមពេល login · `exe` / app ដាច់ដោយឡែក · ដាក់ online (ត្រូវ HTTPS + ការពារ API + ចំណាយ — មិនណែនាំ)។ App ដំឡើងបើកបានដោយ Chrome / Edge ឬ Safari ពិតទេ? (សុំ screenshot / កំហុស បើមាន)
9. មុខងារបន្ទាប់? (គំនិត៖ ដំណើរការច្រើនវីដេអូម្តង · YouTube playlist · រក្សាតន្ត្រីផ្ទៃខាងក្រោយ · ញែកអ្នកនិយាយ (speaker) ស្វ័យប្រវត្តិ — **មិនមែនសំណើរបស់ម្ចាស់**; សួរមុនធ្វើ)
10. **សំឡេងតាមតួអង្គ (v1.13.0)**៖ ម្ចាស់មិនទាន់មាន feedback។ ម្ចាស់សួរថា «ច្រើនតួអង្គក្នុងរឿងតែមួយ បញ្ចូលសំឡេងផ្សេងៗពីគ្នាបានទេ?» — ឆ្លើយរួច (ស្តាប់បានតែអ្វីដែលមានក្នុងសំឡេង; អ្នកនិទានម្នាក់ = ១ តួអង្គ)។ ចង់បាន **ស្គាល់តួអង្គពីអត្ថបទ** (Claude / LLM copy-paste ឬ API) សម្រាប់រឿងបែបនោះទេ? ឬ **pitch / ល្បឿនផ្សេងគ្នារបស់ Edge** ឲ្យតួអង្គភេទដូចគ្នាស្តាប់ខុសគ្នា? (បានស្នើរួច)
11. **Windows (v1.13.0)**៖ «Internal error ពេល Regenerate» ត្រូវបានកែ (simulation)។ សុំម្ចាស់សាកលើ Windows ពិត ហើយ paste **Details** បើនៅមាន error។

---

_ចប់។ ពេលកែឯកសារនេះ សូមរក្សារចនាប័ទ្ម (ខ្មែរ + English terms) និងកែកំណែនៅខាងលើ។_
