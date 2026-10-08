# Changelog

## v1.13.0 — សំឡេងតាមតួអង្គ (ប្រុស / ស្រី) ស្វ័យប្រវត្តិ · កែ «Internal error» ពេល Regenerate លើ Windows

**សំណើម្ចាស់ (៣)៖** ① កម្មវិធីខ្លួនឯងស្គាល់ថាអ្នកណានិយាយពីសំឡេងដើម — តួអង្គប្រុសប្រើសំឡេងប្រុស តួអង្គស្រីប្រើសំឡេងស្រី ដោយមិនបាច់បញ្ចូលដោយដៃម្តងមួយៗ (Voice ក្នុងមួយជួរនៅតែឈ្នះ) · ② រាយការណ៍ពី Windows៖ «ពេល Regenerate វាបង្ហាញថា internet error ប៉ុន្តែ Internet ខ្ញុំនៅដំណើរការធម្មតា … ខ្ញុំបានសាកល្បងច្រើន Video រួចហើយ app នៅតែបង្ហាញ internet error» (រូប៖ **Internal error.**) · ③ សំណួរ៖ «ប្រសិនបើក្នុង១រឿងមានច្រើនតួរអង្គ តើអ្នកមានសមត្ថភាពបញ្ចូលសំឡេងផ្សេងៗពីគ្នាបានដែរឬទេ» (**just answer** — ឆ្លើយត្រង់ៗ មិនសួរបំភ្លឺ)។
*(ការបកស្រាយ និងការសម្រេចចិត្តរបស់ AI — ម្ចាស់មិនបានបញ្ជាក់៖ **switch លំនាំដើមបើក** តែក្នុង Dub flow (YouTube / Upload មានសំឡេង; Paste Transcript គ្មានសំឡេង → សំឡេងតែមួយដូចមុន) · Edge៖ ♂ ពិសិដ្ឋ / ♀ ស្រីមុំ · VoxCPM2 **គោរពសំឡេងដែលអ្នកជ្រើសសម្រាប់ការងារ** (អ្នកនិយាយក្នុងវីដេអូ → Clone តួអង្គនីមួយៗពីជួរខ្លួនឯង; Designed / My voice → រក្សាសម្រាប់ភេទត្រូវ ភេទផ្សេង = Designed voice) · ប៊ូតុងជ្រើសសំឡេងប្រុស / ស្រី · **ភាពត្រឹមត្រូវរាយការណ៍តែអ្វីដែលបានវាស់**។ **Error**៖ សារក្នុងរូបគឺ «Internal» មិនមែន «Internet» — ជា bug ក្នុង App (ក្នុងរូប តារាង Segments កែ → ចុច Regenerate → ដំណាក់ TTS នៅ «Waiting»)។)*

**ថ្មី — សំឡេងតាមតួអង្គ**

- **ជំហានថ្មី «ស្គាល់តួអង្គ (ប្រុស / ស្រី)»** (`speakers`, ក្រោយ transcript)៖ `app/speakers.py` វាស់ **pitch (F0)** នៃជួរនីមួយៗពីសំឡេងដើម (YIN, ជួរ 72–380 Hz, ព្រំដែនប្រុស / ស្រី 165 Hz) — មិនមែន AI model ទេ ដូច្នេះ**មិនដំឡើងអ្វីថ្មី**។ ជួរស្រដៀងគ្នាចែករំលែកភស្តុតាង (kNN); ភេទតែ ១–២ ជួរដែលឃ្លាតពីអ្វីផ្សេង → ដើរតាមភាគច្រើន; តួអង្គ = ក្រុមជួរក្នុងភេទតែមួយ (≤ ៤ ក្នុងមួយភេទ; **ចូលចិត្តបញ្ចូលមនុស្សពីរនាក់ជាមួយគ្នា ជាងបំបែកមនុស្សម្នាក់ជាពីរ**)។ ស្តាប់ឮ < ២០% ឬ < ៣ វិនាទី (តន្ត្រី · ខ្សឹប) → **មិនស្មាន** ហើយប្រើ Voice ដែលបានជ្រើស (ការព្រមាន `SPEAKERS_UNSURE` / `SPEAKERS_NO_AUDIO` / `SPEAKERS_FAILED`)។ **មិនដែលធ្វើឲ្យការងារបរាជ័យ**។ សំឡេង ១ ម៉ោង ≈ ១៥ វិនាទី។
- **`app/autovoice.py`** — Voice ណាសម្រាប់ជួរណា៖ **Voice ក្នុងមួយជួរ › Voice ក្នុងមួយតួអង្គ › ស្វ័យប្រវត្តិតាមភេទ › Voice របស់ការងារ** (ក្បួនដូចគ្នាក្នុង `autovoice.plan` និង `autoPlan` របស់ JS)។ Edge៖ ♂ Piseth / ♀ Srey Mom (Edge មានសំឡេងខ្មែរតែ ២ → តួអង្គភេទដូចគ្នាប្រើសំឡេងដូចគ្នា)។ VoxCPM2៖ «អ្នកនិយាយក្នុងវីដេអូ» → **Clone តួអង្គនីមួយៗពីជួរច្បាស់បំផុតរបស់ខ្លួន** (`vox:s:N`, ឯកសារ `voice_ref_c<N>.wav` ឲ្យស្តាប់); Designed / សំឡេងរបស់ខ្ញុំ → រក្សាសម្រាប់ភេទត្រូវ ភេទផ្សេងទទួល Designed voice (`m_deep` · `f_warm` …; តួអង្គ pitch ឃ្លាត ≥ ៣ semitone → សំឡេងផ្សេងគ្នា)។ ប៊ូតុងជ្រើស «សំឡេងសម្រាប់ប្រុស / ស្រី»៖ voice មួយ · **My voices ត្រូវភេទ** · **Clone តួអង្គនីមួយៗ**។
- **UI**៖ switch «សំឡេងតាមតួអង្គ» ក្នុងកាត Voice (បើកលំនាំដើម) · ផ្ទាំង **តួអង្គ** ក្នុងលទ្ធផល (ស្លាក ♂ / ♀ · ឈ្មោះ · Voice · **⇄ ប្តូរភេទ** · ប៊ូតុង «ស្គាល់តួអង្គម្តងទៀត») · ស្លាកតួអង្គក្នុងជួរនីមួយៗ · ជម្រើសទីមួយក្នុង Voice «ស្វ័យប្រវត្តិ — ពិសិដ្ឋ» · ការកែតួអង្គរាប់ជា «បានកែ» ក្នុងប៊ូតុង Regenerate · ភេទ **My voices** ស្គាល់ពីសំឡេងដោយខ្លួនឯង (ប៊ូតុង ⇄)។
- **API**៖ `POST /api/jobs/{id}/speakers` (`400 NOT_DUB · NO_TIMING · NO_AUDIO_SOURCE · NO_AUDIO`; ការបោះបង់ទុកការងារ `done`) · `regenerate` ទទួល `characters:[{id, gender?, voice?, name?}]` និង `voice.auto{on, male, female}` · `PATCH /api/vox/voices/{id}` ទទួល `gender` · `GET /api/jobs/{id}/file/voice_ref_c<N>.wav`។ ការងារចាស់ (មុន v1.13) បើកបាន — ប៊ូតុង «ស្គាល់តួអង្គ» ដំណើរការលើពួកវា។

**កែ — «Internal error» ពេល Regenerate (Windows)**

- **មូលហេតុ (រកឃើញ និងបង្កើតឡើងវិញបាន)**៖ ពេលចុច *Regenerate audio* កម្មវិធីលុប `dubbed.mp4` ចាស់មុន។ **Windows មិនឲ្យលុបឯកសារដែលនៅបើកស្រាប់** (`PermissionError: [WinError 32]`) — ហើយ `<video>` ក្នុងទំព័រ (Sync Preview · MP4) ទុក request ពាក់កណ្តាលអាន ដូច្នេះ server (Starlette `FileResponse`) រក្សាឯកសារបើកអស់ពេលជាច្រើននាទី។ លទ្ធផល៖ ការងារបរាជ័យមុនដំណាក់ TTS ចាប់ផ្តើម (TTS / Mix / MP4 នៅ «Waiting») ជា «Internal error» — **មិនពាក់ព័ន្ធនឹង Internet ទេ**។ macOS / Linux មិនដែលបង្ហាញ (លុបឯកសារបើកបាន) ដូច្នេះ sandbox មិនដែលឃើញ។ v1.12.0 ក៏មាន bug នេះដែរ (បានសាកផ្ទាល់ — មើល «ចំណាំ»)។
- **ការជួសជុល**៖ ① **`app/mediafile.py` (`MediaFile`)** ជំនួស `FileResponse` សម្រាប់ audio / video៖ បើកឯកសារម្តងមួយបំណែក (256 KB) រួចបិទភ្លាម — ឯកសារមិនបើកនៅចន្លោះពីរបំណែក ទោះ browser អានយឺតប៉ុនណា; Range (seek) ដូចមុន; ឯកសារដែលត្រូវជំនួសពេលកំពុងផ្ញើ → ចប់មុនកំណត់ (មិនលាយចាស់ + ថ្មី) ② `audio.remove_file` (ព្យាយាមម្តងទៀត ១០ × 0.3 វិ ហើយ **មិនបរាជ័យការងារ** — MP4 ចាស់ត្រូវជំនួសពេល MP4 ថ្មីរួច ដោយ `replace_file`) ③ `Job.save` · `JobManager.delete` ព្យាយាមម្តងទៀត ④ `_guard`៖ `PermissionError` → កូដ **`FILE_IN_USE`** (សារច្បាស់ + ឈ្មោះឯកសារ ជំនួស «Internal error») ⑤ UI៖ `releaseMedia()` ដោះ player មុនសំណើ regenerate / remake (ពីមុន ដោះក្រោយសំណើ — យឺតពេល) ⑥ **សារ «Internal error»** ប្តូរជា «បញ្ហាខាងក្នុង App (មិនមែន Internet ទេ) — ចុច ព័ត៌មានលម្អិត ហើយផ្ញើអត្ថបទនោះមក»។
- **Regenerate ដែលបរាជ័យ / ត្រូវបោះបង់ មិនបំផ្លាញការងារ**៖ ពីមុន តារាងកែបាត់ (ម្ចាស់ត្រូវ Upload ហើយធ្វើវីដេអូទាំងមូលឡើងវិញ ចាប់ពី Whisper — ហើយជួបម្តងទៀត)។ ឥឡូវ ការកែត្រូវបានរក្សាទុកក្នុង job ហើយតារាងកែនៅតែនៅ ជាមួយសារ «Regenerate ចុងក្រោយមិនបានចប់ — សំឡេងខាងក្រោមជាសំឡេងមុនពេលកែ» → ចុច Regenerate audio ម្តងទៀត។

**ចម្លើយ «ច្រើនតួអង្គក្នុងរឿងតែមួយ»** (សំណួរ ③)៖ **បាន ប៉ុន្តែមានដែនកំណត់** — កម្មវិធី **ស្តាប់** ទើបដឹងថាអ្នកណានិយាយ ដូច្នេះបំបែកបានតែអ្វីដែលមាននៅក្នុង**សំឡេង**។ ① មនុស្សច្រើននាក់និយាយពិត (សន្ទនា · សម្ភាសន៍ · ភាពយន្ត) → ប្រុស / ស្រី ត្រឹមត្រូវ ≈ ៩៨% (សំឡេងស្អាត); ភេទដូចគ្នា (ប្រុស ២ នាក់) ភាគច្រើនត្រូវបញ្ចូលគ្នា។ ② **អ្នកនិទានម្នាក់អានគ្រប់តួអង្គ** (ដូចវីដេអូ Bilibili ក្នុងរូបរបស់ម្ចាស់) → សំឡេងមានតែ ១ → **១ តួអង្គ** (កម្មវិធីមិនអានអត្ថបទដើម្បីទាយអ្នកនិយាយទេ) → ជ្រើស Voice ក្នុងមួយជួរដោយដៃ។ ③ Edge មានសំឡេងខ្មែរតែ ២ → ភេទដូចគ្នាប្រើសំឡេងដូចគ្នា; **VoxCPM2** អាចឲ្យតួអង្គនីមួយៗសំឡេងផ្ទាល់ខ្លួន។ ជម្រើសបន្ត (មិនទាន់សាងសង់)៖ ស្គាល់តួអង្គ**ពីអត្ថបទ** ដោយ Claude / LLM (អ្នកនិទាន · ប្រុស · ស្រី · ក្មេង ក្នុងមួយជួរ) · ប្តូរ pitch / ល្បឿនរបស់ Edge ឲ្យតួអង្គភេទដូចគ្នាស្តាប់ខុសគ្នា។

**ភាពត្រឹមត្រូវនៃការស្គាល់ភេទ (វាស់ ពុំមែនសន្យា)**

| តេស្ត | លទ្ធផល |
|---|---|
| ឃ្លាពេញ FLEURS (ខ្មែរ · English · 中文 · 한국어) | **182 / 184 = 98.9%** (en 47/48 · zh 44/45 · ko 46/46 · km 45/45) |
| ជួរ ២–៦ វិនាទី មុនចែករំលែកភស្តុតាង | ស្អាត 96.6% · សំឡេងរំខាន 10 dB 94.3% · តន្ត្រី 10 dB 88.4% |
| អ្នកនិយាយ LibriSpeech | 39 / 39 (ប្រុស 93–159 Hz · ស្រី 179–242 Hz) |
| វីដេអូប្រមូលពីឃ្លា FLEURS (384 ជួរ) | ស្អាត 97.9% · សំឡេងរំខាន 95.6% · តន្ត្រី 10 dB 96.1% · តន្ត្រី 5 dB **77.9%** |
| ចំនួនតួអង្គ = ចំនួនភេទ | 91% / 88% / 86% (តាមសំណុំតេស្ត) |
| សំឡេង Microsoft Neural | 32 / 32 |
| dub ខ្មែរពី App នេះ ស្គាល់ឡើងវិញ | 24 / 24 |
| អ្នកនិយាយម្នាក់ វែង (9) | ៧ ទទួល ១ តួអង្គ · ២ ទទួល ២ |
| តំបន់ប្រផេះ 140–195 Hz | ≈ 81% |

**ដែលស្គាល់ថាខុស**៖ ក្មេង · អ្នកនិយាយប្រុសខ្ពស់ (~250 Hz — សំឡេង jfk ត្រូវអានជាស្រី) · តន្ត្រី · ការច្រៀង · មនុស្សនិយាយត្រួតគ្នា។ សំឡេងប្រុសខ្ពស់ / ស្រីទាបអាចខុស → ប៊ូតុង **⇄**។ ភេទដូចគ្នា ពីរនាក់ស្តាប់ដូចគ្នា (AUC ≈ 0.86) → ភាគច្រើនត្រូវបញ្ចូលគ្នា។

**ចំណាំ / ដែនកំណត់**

- **Windows ពិត មិនទាន់ផ្ទៀងផ្ទាត់** — ការកែ «Internal error» ត្រូវបានសាកជាមួយ **Python ដែលធ្វើត្រាប់តាមច្បាប់ចាក់សោឯកសាររបស់ Windows** (`tests/winlock`) + Chromium ពិត៖ **v1.12.0 ឲ្យលទ្ធផលដូចរូបរបស់ម្ចាស់ពិតប្រាកដ** (Fetch transcript / Translate «Done», TTS / Mix / MP4 «Waiting», «Internal error», `PermissionError: [WinError 32] … dubbed.mp4`) ហើយ v1.13.0 ចប់ជោគជ័យ។ បើនៅតែមាន error លើ Windows ពិត៖ ចុច **ព័ត៌មានលម្អិត** (Details) រួចផ្ញើអត្ថបទនោះ។
- សំឡេងតាមតួអង្គជាការ**ស្មានពី pitch** — មិនត្រឹមត្រូវ ១០០%; ប្តូរបានដោយ ⇄ ឬ Voice ក្នុងមួយតួអង្គ / ជួរ ឬបិទ switch។ Paste Transcript គ្មានសំឡេងដើម → មិនមានតួអង្គ។

**ផ្ទៀងផ្ទាត់** (sandbox Linux, Python 3.13)៖ **lint 0 · suite ទាំង ១៧ ជាប់ — 1,908 check ត្រូវ · 0 ខុស** (units 112, core 46, api 77, ui 150, follow 54, clickplay 46, layout 62, claude 169, voices 72, speakers 209, winlock 58, upload 252, tiktok 186, hardsub 186, pwa 90, platform 121, youtube 18; upload +10 ពេលមាន faster-whisper)។ **`test_speakers` ថ្មី** (A units · B សំឡេងដើមពិត — សន្ទនា ១២ ជួរ ប្រុស / ស្រី ដោយ Edge Neural · C browser) · **`test_winlock` ថ្មី** — A units (Range · `MediaFile` · ឯកសារមិនបើកចន្លោះបំណែក — ប្រៀបធៀបជាមួយ `FileResponse` ដែលបើកជានិច្ច · ឯកសារត្រូវជំនួសពេលផ្ញើ · `remove_file` · `_guard`) · B server ដែលធ្វើត្រាប់តាម Windows ជាមួយ pipeline ពិត៖ Regenerate ពេល ៣ download ពាក់កណ្តាលអាន · កម្មវិធីខាងក្រៅចាក់សោ MP4 មួយភ្លែត / ជារៀងរហូត (សារច្បាស់ + «ធ្វើវីដេអូម្តងទៀត» ជាផ្លូវត្រឡប់) · Regenerate បរាជ័យរក្សាសំឡេង + ការកែ · C Chromium៖ MP4 កំពុងចាក់ → កែបន្ទាត់ → Regenerate ជោគជ័យ; បោះបង់ / បរាជ័យ → តារាងកែនៅតែនៅ + អត្ថបទដែលបានវាយ។ ZIP៖ `smoke_zip` **55 / 0 (zip ពន្លាក្នុងថតថ្មី → start → dub ពិត → modes / line endings → unit suite)** · live preview៖ `check_preview` **23 / 0**។ **មិនទាន់ផ្ទៀងផ្ទាត់៖** Windows / macOS ពិត · សំឡេងតួអង្គជាមួយវីដេអូ YouTube ពិតជាច្រើនប្រភេទ (សាកជាមួយសំឡេងមនុស្សពិតពី FLEURS / LibriSpeech និង TTS) · Clone តួអង្គជាមួយ VoxCPM2 ពិត (សាកជាមួយ stub) · Safari / Firefox ជាមួយ `MediaFile` (Range ត្រូវតាម RFC 7233; សាកតែ Chromium)។

## v1.12.0 — ឈ្មោះ V_Heang Studio · My voices ច្រើនតួអង្គ · គ្មាន spec របស់ PC · ចុចជួរ → លេងវីដេអូ

**សំណើម្ចាស់ (៤)៖** ① «កែឈ្មោះពី khmerdub studio ទៅជា **V_Heang Studio**» · ② «ខ្ញុំចង់ឲ្យកន្លែង my voice អាច upload បានច្រើន sample voices ដើម្បីបញ្ចូលសំឡេងបានច្រើនតួរអង្គ» · ③ «លុបចោល ហើយមិនត្រូវបង្ហាញ Spec របស់ PC» (រូបភាព៖ កថាខណ្ឌ “Runs on your own computer (private, free, unlimited) · 8 designed voices · … · needs an NVIDIA GPU to be fast.”) · ④ «អាច press លើឃ្លានិយាយនៅលើពេលណាមួយនៃ Script ហើយ Video play ចាប់ពីពេលនោះដើម្បីងាយស្រួលកែ Subtitle script»។
*(ការបកស្រាយ និងការសម្រេចចិត្តរបស់ AI — ម្ចាស់មិនបានបញ្ជាក់៖ **ឈ្មោះ** — ប្តូរអ្វីដែលអ្នកប្រើឃើញ (ទំព័រ · App ដំឡើង · manifest · ផ្ទាំង Terminal · README); **មិនប្តូរ** identifier ខាងក្នុង៖ `KDS_*`, ឈ្មោះ folder / ZIP `khmer-dubbing-studio`, ថត VoxCPM2 `%LOCALAPPDATA%\KhmerDub\voxcpm` / `~/Library/KhmerDub/voxcpm` (ប្តូរ = ដំឡើង ១០ GB ម្តងទៀត)។ ប្រវត្តិក្នុងឯកសារនេះរក្សាឈ្មោះចាស់។ **My voices** — បានយល់ថា «ច្រើន sample = ច្រើនតួអង្គ» = ១ ឯកសារ ១ សំឡេង (VoxCPM2 ប្រើ clip យោងតែមួយ ដូច្នេះមិនលាយ clip ច្រើនជាសំឡេងតែមួយទេ)។ **Spec របស់ PC** — លុបកថាខណ្ឌនោះ និងអត្ថបទទាំងអស់ដែលដាក់ឈ្មោះ hardware; ការព្រមាននៅតែមានតែនិយាយថា «កុំព្យូទ័រនេះ»។ **ចុចជួរ** — ចុចគ្រប់កន្លែងក្នុងជួរ លើកលែងប៊ូតុង / ប្រអប់ម៉ោង / Voice / ធីក; ក្នុងប្រអប់ខ្មែរ ចុច «ចូល» ទើបចាក់។)*

**ថ្មី**

- **ឈ្មោះ V_Heang Studio**៖ ក្បាលទំព័រ · ម៉ឺនុយ · `<title>` · ជើងម៉ឺនុយ (`V_Heang v… · UI …`) · App ដំឡើង (`name` «V_Heang Studio», `short_name` «V_Heang») · ទំព័រ «មិនទាន់ដំណើរការទេ» · សារ Terminal (`server.py`, `start.*`; ចំណងជើងបង្អួច `start.bat`) · សារ UI (Rosetta, សារ «ដំឡើងរួច») · README / ឯកសារ។ រូបតំណាងគ្មានអក្សរ (រលក) — មិនប្តូរ។ (App ដែលដំឡើងរួចយកឈ្មោះថ្មីពី manifest ពេល browser ពិនិត្យ — `id` ដដែល ដូច្នេះមិនបង្កើត App ថ្មី។)
- **My voices — ច្រើនឯកសារក្នុងពេលតែមួយ**៖ ប៊ូតុង «បន្ថែមសំឡេង» ទទួលឯកសារច្រើន (`<input multiple>`) · ឬ **ទាញមកទម្លាក់** ក្នុងតំបន់ VoxCPM2 (`.engine-vox`)។ ១ ឯកសារ = ១ តួអង្គ (ឈ្មោះ = ឈ្មោះឯកសារ; ដូចគ្នា → `Boy 2`)។ upload ម្តងមួយឯកសារ (សារ «កំពុងបន្ថែមសំឡេង ២ / ៥») → សង្ខេប «បានបន្ថែមសំឡេង ៤ ក្នុងចំណោម ៥» + បញ្ជីឯកសារដែលខុស (ខ្លីពេក · មិនមែនសំឡេង · > 30 MB — ពិនិត្យនៅ browser មិនផ្ញើ) ដោយមិនឃាត់ឯកសារផ្សេង; សំឡេងចូលបញ្ជីភ្លាមៗ; លំដាប់ក្នុងបញ្ជី = លំដាប់ក្នុងប្រអប់ជ្រើសឯកសារ; ឯកសារតែមួយ → ប្រអប់សួរឈ្មោះដូចមុន ហើយសំឡេងត្រូវបានជ្រើស; ពេល batch កំពុងរត់ batch ទី ២ ត្រូវបដិសេធ («សូមរង់ចាំ»); ឯកសារទម្លាក់**មិនត្រូវ**ចាប់យកជាវីដេអូ Upload ទេ។ ប៊ូតុង **✎ ប្តូរឈ្មោះ** (ឈ្មោះតួអង្គ) ថ្មី។ **API ថ្មី**៖ `PATCH /api/vox/voices/{id}` `{"name"}` (≤ 60 តួ; `400 BAD_REQUEST` · `404 NOT_FOUND`; លំដាប់បញ្ជីមិនប្តូរ — `voxvoices.rename_custom` ស្តារអាយុរបស់ folder)។
- **គ្មាន spec របស់ PC**៖ **លុប** កថាខណ្ឌក្រោមប៊ូតុងជ្រើស engine (`voice.engine.hint.vox`)។ **លុប** ឈ្មោះ device / GPU ពី «Engine running (cuda · NVIDIA …)», ស្ថានភាព «Running · …» និង «Measured during install … (cuda)»។ ការព្រមាន (`vox.banner.nogpu`, `set.vox.hw.none / small / macram`, `set.vox.gpufail`, `err.VOX_OOM`, ពណ៌នា Turbo) សរសេរឡើងវិញជា «កុំព្យូទ័រនេះ» គ្មាន NVIDIA / VRAM / CUDA / RAM / ចំនួន GB; ជម្រើស «Automatic (GPU if available)» → «Automatic»; «runs on your CPU» (Whisper) → «runs on your computer»។ មិនប៉ះ៖ ព្រមាន Mac Intel / Rosetta (ហេតុផលដំឡើងមិនបាន), log ដំឡើង (Settings → Log — សម្រាប់ជួសជុល), `/api/vox/status` · `/api/system` (logic UI — មិនបង្ហាញ)។
- **ចុចលើជួរ → វីដេអូលេងពីទីនោះ**៖ ចុចអត្ថបទដើម · លេខម៉ោង · ចន្លោះទទេ ឬ**ចុចចូល**ប្រអប់ខ្មែរ → `playFromRow(i)`៖ ① Sync Preview បើកស្រាប់ → `seekTo` + `playVideo` (MP4 ឈប់) ② MP4 → `currentTime` + play ③ បើក Sync Preview ត្រង់ជួរនោះ (`openSync(kind, startAt)`; ចុចជួរផ្សេងពេលកំពុងផ្ទុក → ចាប់ផ្តើមត្រង់ជួរចុងក្រោយ; ការពារ player ពីរ) ④ គ្មានរូបភាព → សំឡេងខ្មែរ។ មិនចាក់ពី ប៊ូតុង / ប្រអប់ម៉ោង / ប្រអប់ Voice / ធីក / select អត្ថបទ; ចុចក្នុងប្រអប់ខ្មែរដដែល ឬ Tab ចូល → មិនចាក់។ ប៊ូតុង **ចុចជួរ → លេង** (`subs.clickplay`, លំនាំដើមបើក) + cursor «ដៃ» + hover។ ពេលវេលា = ពេលដែល «តាមវីដេអូ» រាប់ថាជួរចាប់ផ្តើម (`min(start, out_start)`)។
- **ព្រាង Claude មានវីដេអូដើម**៖ ព្រាងដែលមានវីដេអូ (YouTube / Upload) បង្ហាញប្លុក «មើលវីដេអូដើម» (មុនពេលនេះ មិនមាន) — Sync Preview ជាមួយ**សំឡេងដើមបើកជានិច្ច** (គ្មានសំឡេងខ្មែរ; `NO_AUDIO` ជំនួស `#dub-audio`) និងមានតែប៊ូតុង Subtitle ដើម។ ព្រាងគ្មានវីដេអូ (Transcript) → មិនមានអ្វី។

**ចំណាំ / ដែនកំណត់**

- ចុចជួរជាមួយ **YouTube ពិត** មិនទាន់ផ្ទៀងផ្ទាត់ (សាកជាមួយ `YT.Player` ក្លែង + `<video>` ពិត)។ Autoplay មានសំឡេងក្នុង iframe ព្រាង អាចត្រូវបាន browser ហាម → វីដេអូឈប់នៅជួរនោះ ចុច ▶ ម្តង។
- ឈ្មោះ folder / ZIP នៅ `khmer-dubbing-studio` — ចង់ប្តូរ៖ `tools/build_zip.py` + `tests/smoke_zip.py` (+ ឯកសារ)។
- My voices៖ ១ ឯកសារ = ១ សំឡេង (មិនលាយច្រើន clip ជាសំឡេងតែមួយ)។ Limit ១ ឯកសារ ≤ 30 MB (ដូចមុន)។

**ផ្ទៀងផ្ទាត់** (sandbox Linux, Python 3.13)៖ **lint 0 · suite ទាំង ១៥ ជាប់ — 1,631 check ត្រូវ · 0 ខុស** (units 112, core 46, api 77, ui 150, follow 54, clickplay 46, layout 62, claude 169, voices 72, upload 242, tiktok 186, hardsub 186, pwa 90, platform 121, youtube 18; upload +10 ពេលមាន faster-whisper)។ **`test_clickplay` ថ្មី 46** — MP4 (ចុចអត្ថបទដើម / គែមជួរ / ចូលប្រអប់ខ្មែរ; ប៊ូតុង · ប្រអប់ម៉ោង · Voice · ធីក · text selection មិនចាក់; ចុចម្តងទៀតក្នុងប្រអប់ដដែល ≠ ចាក់ឡើងវិញ; focus ដោយ keyboard ≠ ចាក់) · switch (រក្សាទុក, ទុកបន្ទាប់ពី reload) · YouTube player ក្លែង (បើក: `seekTo` + `playVideo`, MP4 ឈប់; បិទ: បើកត្រង់ជួរ; **កំពុងផ្ទុក**: player តែមួយ ចាប់ផ្តើមត្រង់ជួរចុងក្រោយ) · MP3 តែមួយ (សំឡេងខ្មែរចាក់តាម) · គ្មានរូបភាព (សំឡេងខ្មែរ; មិនឈប់ចុងជួរ) · **ព្រាង** (មានវីដេអូ + សំឡេងដើម `unMute`, មានតែប៊ូតុង Subtitle ដើម) · dock ដើម · ខ្មែរ។ **`test_voices` ថ្មី 72** — API (POST / PATCH / DELETE, ឈ្មោះ, ឈ្មោះទទេ → «My voice», លំដាប់មិនប្តូរ, ឯកសារខុស) · UI (៣ ឯកសារក្នុងពេលតែមួយ ជាលំដាប់ដើម គ្មានសំណួរ · ឈ្មោះដូចគ្នា `Boy 2` · ឯកសារខុសរាយឈ្មោះ · > 30 MB មិនផ្ញើ · ១ ឯកសារ + ប្រអប់សួរ + ជ្រើស · ✎ · drop (មិនក្លាយជាវីដេអូ Upload) · batch ទី ២ ត្រូវបដិសេធ · ខ្មែរ) · **គ្មាន spec របស់ PC**៖ ទំព័រ Dub / TTS / Settings × GPU ក្លែង (RTX 4090) · គ្មាន GPU · GPU តូច · Mac 8 GB × EN / KM — គ្មាន NVIDIA / GPU / VRAM / CUDA / RAM សោះ។ បន្ថែម៖ test_units +5 (i18n គ្មាន hardware · key ត្រូវលុប · ឈ្មោះចាស់ · title) · test_claude +2 · test_upload +8 (ចុចជួរជាមួយ MP4 · ព្រាងពី file Upload) · test_pwa / test_platform ដូចឈ្មោះ និងអត្ថបទថ្មី។ ZIP៖ `smoke_zip` **50 / 0 (zip ពន្លាក្នុងថតថ្មី → start → dub ពិត → modes / line endings → unit suite)** · live preview៖ `check_preview` **23 / 0**។ **មិនទាន់ផ្ទៀងផ្ទាត់៖** ចុចជួរជាមួយ YouTube iframe ពិត (autoplay មានសំឡេង) · Safari / Firefox · Windows / macOS ពិត · My voices ជាមួយសំឡេងមនុស្សពិត (សាកជាមួយសំឡេង sine) · App PWA ដែលបានដំឡើងរួច ទទួលឈ្មោះថ្មី។

## v1.11.0 — ដំឡើងជា App (PWA) · បើក KhmerDub ងាយស្រួលជាងមុន

**សំណើម្ចាស់៖** «តើមានវិធីណាដើម្បីឲ្យការបើក Website នេះងាយស្រួលជាងមុន?» → AI ផ្តល់ជម្រើស → ម្ចាស់ជ្រើស «**PWA** <Note: មិនទាន់ Hosting នៅលើ online server ទេ>»។
*(ការបកស្រាយ៖ កម្មវិធីនៅតែរត់ **local** (`start.bat` / `start.command`) — PWA ត្រូវដំណើរការជាមួយ server local នោះ ហើយមិនពឹងលើ domain / hosting (URL ទាំងអស់ជា relative) ដើម្បីឲ្យដំណើរការដដែលពេលមាន hosting ថ្ងៃក្រោយ។)*

**ថ្មី**

- **ប៊ូតុង «ដំឡើងជា App»** ក្នុងម៉ឺនុយខាងឆ្វេង (ក្រោម ការកំណត់)៖
    - Chrome / Edge៖ ចុច → ប្រអប់ install របស់ browser លោតឡើង (`beforeinstallprompt`)។ Safari (Mac) / browser ដែលគ្មានប្រអប់៖ ចុច → បង្ហាញជំហាន (*File → Add to Dock* …)។
    - **លាក់** ពេលនៅក្នុង App រួចហើយ (`display-mode: standalone` …), ពេលមិនមែន secure context (មិនមែន `localhost` / `127.0.0.1` / `https`), ក្នុង iframe, លើអេក្រង់ ≤ 900 px, និងបន្ទាប់ពីដំឡើង (`appinstalled` → សារ «បានដំឡើងជា App រួចហើយ»)។
- **App ដំឡើង**៖ ឈ្មោះ KhmerDub Studio · បង្អួចផ្ទាល់ខ្លួន (`display: standalone`) · រូបតំណាង 192 / 512 / maskable + Apple touch icon (គូរពី logo ដដែល ដោយ `tools/make_icons.py`) · ពណ៌ title bar តាម Dark / Light · **shortcuts** (ចុចស្តាំ / jump list)៖ Dubbing · TTS · Terms · History។
- **ទំព័រ «មិនទាន់ដំណើរការទេ»** (`/offline.html`, ខ្មែរ + English)៖ ពេល server មិនរត់ App (ឬ tab) បង្ហាញទំព័រនេះជំនួសទំព័រកំហុសរបស់ browser — ប្រាប់ឲ្យបើក `start.bat` / `start.command`, កុំបិទផ្ទាំងខ្មៅ, រក្សា port 8000 — ហើយ**បើក dashboard ដោយខ្លួនឯង**ពេល server ត្រៀមរួច (ពិនិត្យ `/api/health` រៀងរាល់ ២.៥ វិ)។ ពុម្ពអក្សរខ្មែរនៅ**ក្នុងទំព័រ** (data URI ដាក់ដោយ server) ដូច្នេះអក្សរខ្មែរមើលបានត្រឹមត្រូវពេល server ស្លាប់។
- **Service worker** (`/sw.js`, ដាក់ version ក្នុងឈ្មោះ cache)៖ ឆ្លើយ**តែ** GET navigation ទៅ `/` (`fetch` បរាជ័យ → `/offline.html`); **cache តែទំព័រ offline**; មិនប៉ះ API · សំឡេង · វីដេអូ (Range) · upload · download។ កំណែថ្មី → ឯកសារថ្មី → browser update ហើយលុប cache ចាស់ (`skipWaiting` + `clients.claim`)។ Register តែក្នុង secure context។
- **Routes ថ្មី (root)**៖ `GET /manifest.webmanifest` (`application/manifest+json`) · `GET /sw.js` (`Service-Worker-Allowed: /`) · `GET /offline.html` — ទាំងអស់ `Cache-Control: no-cache`; `/sw.js` ជំនួស `{{ver}}` ដោយ `__version__`។
- **`server.py`៖ មិនបើកច្បាប់ចម្លងទី ២** — បើមិនកំណត់ `PORT` ហើយ 8000 ជាប់ដោយ KhmerDub **កំណែដដែល** (ពិនិត្យតាម `/api/health`: `ok` + `assets` + version ដូចគ្នា) → បង្ហាញ «already running», បើក browser (លើកលែង `NO_BROWSER=1`) ហើយចេញ (exit 0) ជំនួសឲ្យចាប់ផ្តើមលើ 8001។ កំណែផ្សេង / កម្មវិធីផ្សេង → ប្រើ port បន្ទាប់ដូចមុន។ ហេតុផល៖ App ដំឡើងជាប់នឹង `http://127.0.0.1:8000` (origin)។
- **ឧបករណ៍**៖ `tools/make_icons.py` (Chromium គូរ PNG ពី logo) · **`tests/test_pwa.py`** ថ្មី (port 8066) · `smoke_zip.py` ពិនិត្យឯកសារ PWA ក្នុង ZIP។

**ចំណាំ / ដែនកំណត់**

- **PWA មិនអាចចាប់ផ្តើម server ឲ្យបានទេ** — ត្រូវរត់ `start.bat` / `start.command` ជាមុនដដែល។ (ចង់ឲ្យចាប់ផ្តើមពេល login → Windows `shell:startup` / Mac Login Items — ពន្យល់ក្នុង README។)
- App ជាប់នឹង **origin** `http://127.0.0.1:8000` — ដំឡើងពី address ដែល `start.bat` បើក; `localhost:8000` ជា origin ផ្សេង (settings `localStorage` ដាច់ដោយឡែក)។ បើប្តូរ port → ត្រូវដំឡើងម្តងទៀត។
- ទាមទារ secure context៖ `http://192.168.x.x:8000` (ម៉ាស៊ីនផ្សេង) ដំឡើងមិនបាន — ត្រូវ `https`។
- **មិនទាន់ផ្ទៀងផ្ទាត់៖** Safari (Add to Dock) · Firefox · ការដំឡើងពិតលើ Windows / macOS · YouTube iframe ក្នុងបង្អួច App។ (បានផ្ទៀងផ្ទាត់ក្នុង Chromium លើ Linux៖ browser ផ្ទាល់ប្រាប់ថា installable — CDP `getInstallabilityErrors` ទទេ — និងដំណើរការ offline → online ពិត។)

**ផ្ទៀងផ្ទាត់** (sandbox Linux, Python 3.13)៖ **`test_pwa` ថ្មី 90** — A ឯកសារ (manifest · icons PNG ទំហំ · sw · offline · `<head>` · i18n) · B routes + header + `server.running_instance` + `server.main()` (ប្រើឡើងវិញ / កំណែផ្សេង / PORT ដោយអ្នក / proxy) · C **Chromium ពិត** (browser ផ្ទាល់ប្រាប់ថា installable — `getInstallabilityErrors` ទទេ · service worker + cache · **server ស្លាប់ពិត → ទំព័រ offline → server ត្រឡប់ → dashboard បើកដោយខ្លួនឯង** · ប៊ូតុង (event ក្លែង) · standalone / មិនមែន secure / iframe / អេក្រង់តូច · theme-color · icons decode)។ **run_all ទាំងមូល៖ 1,498 check, 0 failed** (+ lint 0)៖ units 107 · core 46 · api 77 · ui 150 · follow 54 · layout 62 · claude 167 · upload 234 · tiktok 186 · hardsub 186 · **pwa 90** · platform 121 · youtube 18។ ZIP ត្រូវបានសាកល្បងដោយ `smoke_zip.py`។ មិនបានសាកល្បង៖ Safari · Firefox · Windows / Mac ពិត · YouTube iframe ក្នុងបង្អួច App។

## v1.10.0 — បិទបាំង Subtitle ដើម (Hide the original subtitles) លើ MP4

**សំណើម្ចាស់៖** «គ្រាន់តែបង្កើតមុខងារមួយដែលធ្វើឲ្យ Subtitle មើលមិនច្បាស់ ឬមាន Effect លើ subtitle» — ម្ចាស់ប្រាប់ថា កម្មវិធីនេះមិនមែនសម្រាប់អាជីវកម្ម ប៉ុន្តែសម្រាប់ build tool / Web ដោយប្រើ AI និងសាកល្បងសមត្ថភាព AI។
*(ការបកស្រាយ៖ Subtitle ដែល **បោះពុម្ពជាប់ក្នុងរូបភាព** វីដេអូដើម (hard-sub) ត្រូវធ្វើឲ្យមើលមិនច្បាស់។ Subtitle ខ្មែររបស់កម្មវិធី (SRT / track ក្នុង MP4) មិនត្រូវប៉ះពាល់ទេ។)*

**ថ្មី**

- **Step 4 · Output** (ពេលជ្រើស *MP3 + MP4 Video*) មានជួរ **បិទបាំង Subtitle ដើម** (switch — បិទជាលំនាំដើម)។ ពេលបើក៖
    - **Effect** ៤៖ **Blur** (លំនាំដើម) · **Mosaic** (ការ៉េធំៗ) · **ប្រអប់ងងឹត** (Dark box) · **កញ្ចក់ស្រអាប់** (Frosted = Blur + ងងឹតបន្តិច)។
    - **ផ្នែកដែលបាំង (band)** = ក្រុមបន្ទាត់ពេញទទឹងរូបភាព៖ **ចម្ងាយពីគែមក្រោម** (0–40 %, លំនាំដើម 3 %) · **កម្ពស់** (6–40 %, លំនាំដើម 16 %) · **កម្លាំង** (10–100, លំនាំដើម 50)។ ភាគរយវាស់លើ **កម្ពស់រូបភាពដើម** → ត្រូវទាំងវីដេអូ 360p និង 4K ហើយដំណើរការជាមួយ **TikTok 9:16** (band ធ្វើមុន ស៊ុម 9:16 ធ្វើក្រោយ — band ដើរតាមរូបភាព)។
    - **រូបតូចមើលជាមុន** (CSS សុទ្ធ៖ រូបពី YouTube link / ឯកសារ + Subtitle ក្លែង) បង្ហាញទីតាំង (ស៊ុមដាច់ៗ) និង Effect។
- **Sync Preview** បង្ហាញ band ដដែលពីលើ **វីដេអូពិត** (`backdrop-filter`)៖ ធ្វើតាម slider ភ្លាមៗ · Subtitle ខ្មែរ/English ក្នុង preview ស្ថិតពីលើ band · វីដេអូទទឹងជាង 16:9 (2.37:1) → band វាស់លើរូបភាព មិនមែនលើខ្សែខ្មៅ។
- **ប្តូរលើការងារស្រាប់** — ប្រអប់ក្នុងលទ្ធផល (ឥឡូវ «ទម្រង់ Video (TikTok) · Subtitle ដើម») ចាប់ផ្តើមពីអ្វីដែល MP4 មានពិត (បើក/បិទ, Effect, ទីតាំង) → *បង្កើត Video ឡើងវិញ*។ ជួរលេខ និងការសង្ខេបបង្ហាញ «Subtitle ដើម · Blur»។
- **API**៖ `output.hide_subs` · `hide_effect` · `hide_bottom` · `hide_height` · `hide_strength` ក្នុង `POST /api/jobs/dub`; `POST /api/jobs/{id}/video` ទទួលគ្រាប់ដូចគ្នា (តម្លៃខុស = កែដោយស្ងាត់; មិនផ្ញើ = រក្សាតាមការងារ)។ `job.meta.video.hide` = `{effect, bottom, height, strength}` ឬ `null`។
- **Code**៖ `app/hardsub.py` (ថ្មី — logic សុទ្ធ មិនបើក ffmpeg ដូច `frame.py`) · `audio.mux_video(…, hardsub=)` · `frame.FramePlan.graph_from(src)` · `pipeline` (`AudioCtx`, `_video_stage`, `run_remake_video`) · `main.remake_video`។
- **ក្រាហ្វ ffmpeg**៖ `split → crop band → gblur / (scale area → scale neighbor) / eq → overlay` (Dark box = `drawbox`)។ ទីតាំង band ជា expression នៃ `ih` ហើយជួរជាលេខគូ (chroma 4:2:0) → ត្រឹមត្រូវសម្រាប់វីដេអូ rotation · SAR · ទំហំសេស។ កម្លាំង Blur / Mosaic ជាភាគរយនៃកម្ពស់រូបភាព។

**ចំណាំ / ដែនកំណត់**

- ពេលបើក រូបភាព **ត្រូវ encode H.264 ឡើងវិញ** (យឺតជាង); ពេលបិទ MP4 នៅតែ **ចម្លង** រូបភាពដូចមុន (មាន test៖ ជួរ pixel ដូចគ្នាបេះបិទ)។
- កំណត់ band ដោយដៃ (មិនទាន់រកទីតាំង Subtitle ដោយស្វ័យប្រវត្តិ); band ពេញទទឹង។ HDR មិនទាន់បម្លែងពណ៌ (ដូច v1.9.0)។
- មុខងារនេះ **លាក់តែអក្សរលើអេក្រង់** — មិនប្តូរម្ចាស់សិទ្ធិវីដេអូ ហើយមិនធានាអ្វីអំពី copyright claim (សំឡេង និងរូបភាពដែលនៅសល់ មិនប្តូរ)។
- វីដេអូ YouTube នៅក្នុង Sync Preview ជា iframe (មិនដឹងទំហំរូបភាព) → ស្មានថា 16:9។

**ផ្ទៀងផ្ទាត់** (sandbox Linux, Python 3.13)៖ **`test_hardsub` ថ្មី 186** — A units 44 · B ffmpeg **pixel** 59 (ក្នុងវីដេអូសាកល្បង ២ pixel ជា «អក្សរ»៖ ជួរណា Blur / ជួរណាមិនប៉ះ — 4 effect · strength · ទីតាំង · TikTok blur/crop/bars · 1080p→720p · ទំហំសេស · SAR · rotation · សំឡេងដើម + mute mask · progress · ចម្លងធម្មតាពេលបិទ) · C API/jobs 29 · D browser 54។ Suite ចាស់ទាំងអស់នៅខៀវ៖ units 107 · core 46 · api 77 · ui 150 · follow 54 · layout 62 · claude 167 · upload 234 · tiktok 186 · hardsub 186 · platform 121 · youtube 18 (សរុប **1408** check, 0 failed; lint 0)។ `upload` = 234 ក្នុង sandbox នេះ ព្រោះមិនបានដំឡើង faster-whisper — ក្រុម D (Whisper ពិត) ១០ check រត់តែពេលដំឡើង (សរុប 244)។

## v1.9.1 — Dev Kit សម្រាប់អ្នកបន្តអភិវឌ្ឍ (Handoff) · កម្មវិធីមិនប្តូរ

**សំណើម្ចាស់៖** «ខ្ញុំចង់បានលំហូរការងារ… ឲ្យអ្នកផ្សេងអភិវឌ្ឍន៍បន្ត ឬបន្តលើ AI chat ថ្មី» → អ្វីៗទាំងអស់ដែលត្រូវការ ដាក់ក្នុង ZIP តែមួយ។ **`app/` និង `static/` មិនប្តូរ** (លើកលែងលេខកំណែ) — v1.9.1 ប្រព្រឹត្តដូច v1.9.0 ទាំងស្រុង។

**ថ្មី**

- **`DEVELOPMENT.md`** — ឯកសារតែមួយសម្រាប់អ្នកបន្តអភិវឌ្ឍ (ខ្មែរ + English terms)៖ ការណែនាំរបស់ម្ចាស់ (មិនត្រូវបំពាន) · Invariants (២៤) · Architecture · File map · `job.json` schema · Pipeline · API + error codes · Frontend · Platform + env vars · Tests · **Release workflow** · **របៀបធ្វើការជាមួយ AI agent (workflow v1.0 → v1.9)** · មេរៀន/អន្ទាក់ · ដែនកំណត់ + មិនទាន់ផ្ទៀងផ្ទាត់ + Backlog · ប្រវត្តិកំណែ · សំណួរបើកចំហ។
- **`HANDOFF_PROMPT.md`** — Prompt ត្រៀមរួច (Copy → Paste) សម្រាប់បើក AI chat ថ្មី ហើយបន្តការងារដោយមិនបាត់បរិបទ (ច្បាប់ភាសា, ច្បាប់ដែលមិនត្រូវបំពាន, លំហូរ, ស្ថានភាព)។
- **`tests/`** (ឥឡូវនៅក្នុង project) — suites ១១ + `lib.py` + stubs (`stubvox`, `stubnowhisper`, `fake_faster_whisper`) + `fixtures/jobs` (job គំរូ ៣) + `run_all.sh` (lint pyflakes + suites ទាំងអស់; ពេលវេលាក្នុង `final_summary.log`) + `requirements-dev.txt`។ **Portable**៖ path ទាក់ទងនឹង file (មិនមាន `/home/user` ទៀត), `KDS_TEST_WORK` / `KDS_PROJECT` / `PYTHON`; លេខកំណែអានពី `app/__init__.py` (គ្មានលេខកំណែក្នុង test)។ ដំណើរការពីថតណាក៏បាន ហើយក្នុងថតដែល unzip (`smoke_zip.py` ផ្ទៀងផ្ទាត់)។
    - **`test_core.py` ថ្មី** (offline, ~១ វិនាទី, 46 check)៖ `split_runs` / `split_sentences` · parse SRT/VTT, `merge_segments`, `to_srt` · `TermMatcher` protect/restore (រួមទាំងលេខខ្មែរ `X១X`) · ពាក្យ 中文 / 한국어 → English · `detect_lang` / `resolve_lang` · `time_stretch` / `soft_limit` / `mix_into` · `VoiceSettings` · config · `samples/` — ពីមុនត្រូវបានសាកតែតាម `test_api` (សេវាពិត)។
    - **Guard ថ្មី** — `test_units`៖ i18n km = en (គ្មានស្ទួន, គ្មាន key បាត់) · ភាសាជប៉ុនត្រូវបដិសេធ (`LANG_UNSUPPORTED`) · `INTERRUPTED` ពេល server restart; `test_api`៖ `Cache-Control` (`no-store` / `no-cache`) និង `?v=` លើ asset URL; `test_platform` ផ្នែក E៖ release tools។
    - **`shots.py`** (screenshot ៤ ទំហំ × ភាសា × theme សម្រាប់ពិនិត្យដោយភ្នែក) · **`check_preview.py`** (dashboard ដែលកំពុងរត់៖ ៥ ទំព័រ · គ្មាន raw key · គ្មាន JS error · បើក job) · **`smoke_zip.py`** (ZIP ដែលបានបង្កើត៖ unzip → start → dub ពិត → TikTok → exec bit / CRLF / LF → unit suite ក្នុងថតថ្មី)។
- **`tools/bump_version.py`** (កំណែ ៤ កន្លែងព្រមគ្នា · `--check`) និង **`tools/build_zip.py`** (បង្កើត ZIP ដោយ script៖ `.sh` / `.command` = 0755, `.bat` = CRLF, មិនដាក់ `data/`; **បដិសេធ** បើ line ending ខុស, មាន shell script ថ្មីដែលមិនបានចុះបញ្ជី ឬកំណែមិនត្រូវគ្នា)។

**ផ្ទៀងផ្ទាត់** (sandbox Linux, Python 3.13)៖ units 107 · core 46 · api 77 · ui 150 · follow 54 · layout 62 · claude 167 · upload 244 · tiktok 186 · platform 121 · youtube 18 = **1,232 check, 0 បរាជ័យ** (≈ ១៣ នាទី) · lint pyflakes 0។ **មិនទាន់ផ្ទៀងផ្ទាត់** (ដូច v1.9.0)៖ Mac ពិត / Windows ពិត · VoxCPM2 លើ Metal · Firefox / Safari — សូមមើល `DEVELOPMENT.md` §15។

## v1.9.0 — វីដេអូបញ្ឈរសម្រាប់ TikTok (9:16) + ដំណើរការលើ MacBook និង Windows

**ថ្មី (១) — TikTok / Instagram Reels / YouTube Shorts៖ បម្លែងវីដេអូផ្តេក (16:9) ទៅជា 9:16 បញ្ឈរ**
- **Step 4 · Output** (ពេលជ្រើស *MP3 + MP4 Video*) មានជួរ **ទម្រង់ Video (Aspect ratio)**៖ *ទម្រង់ដើម* ឬ **TikTok 9:16 (បញ្ឈរ)** → ទំហំ **1080×1920** (ឬ **720×1280** តាមប៊ូតុង 1080p / 720p) · H.264 + AAC stereo 48 kHz។
- **របៀបដាក់រូបភាព (Fit)** ៣៖ **Blur ផ្ទៃខាងក្រោយ** (លំនាំដើម៖ រូបទាំងមូលនៅកណ្តាល + រូបដដែល Blur ពង្រីកបំពេញខាងលើ–ក្រោម; Blur ធ្វើលើច្បាប់ចម្លងតូច ១/៨ ដូច្នេះលឿន) · **Crop ពេញអេក្រង់** + របារ **ផ្នែកដែលត្រូវរក្សា** (ឆ្វេង · កណ្តាល · ស្តាំ, ជំហាន ៥%) · **ខ្សែខ្មៅ**។ ក្រាហ្វ ffmpeg សរសេរជាកន្សោមនៃទំហំពិត (`iw`/`ih`) ដូច្នេះត្រូវសម្រាប់គ្រប់រូបរាង (16:9 · 4:3 · 1:1 · 21:9 · 20:9 · ទំហំសេស) ហើយលេខទាំងអស់ជាគូ (H.264 ត្រូវការ)។
- **រូបទូរស័ព្ទតូច** (CSS សុទ្ធ) បង្ហាញលទ្ធផលជាមុន — ប្រើរូប thumbnail ពី YouTube link / ឯកសារ Upload / ការងារ (មិនមាន → រូបគំរូ)។
- **ប្តូរទម្រង់លើការងារស្រាប់** — ប្រអប់ **ទម្រង់ Video (TikTok)** ក្នុងលទ្ធផល (`POST /api/jobs/{id}/video`)៖ បង្កើត **តែ MP4** ឡើងវិញ — សំឡេងខ្មែរ (`dub.mp3`) និងការកែមិនប៉ះពាល់ · ប្រអប់ចាប់ផ្តើមពីវីដេអូដែលមានស្រាប់ (Step 4 មិនប្តូរ; ការកំណត់ជា `state.s.remake`) · ការងារដែលមានតែ MP3 ក៏បង្កើត MP4 បាន។ MP4 សរសេរក្នុងឯកសារបណ្តោះអាសន្ន `dubbed.part.mp4` រួចជំនួស — **បរាជ័យ ឬ Cancel → MP4 ចាស់ និងការកំណត់របស់វានៅដដែល** (ការងារមិនក្លាយជា “cancelled”)។
- **Progress ពេល encode** (`audio.run_with_progress`, `ffmpeg -progress`)៖ “making the vertical video … 37%” · **Cancel** បញ្ឈប់ ffmpeg ភ្លាមៗ (kill — SIGTERM លើ ffmpeg 7 ចំណាយពេលស្មើនឹងវីដេអូទាំងមូល ដូច្នេះមិនប្រើ) ហើយលុបឯកសារបណ្តោះអាសន្ន។
- **វីដេអូដែលជា 9:16 រួចហើយ** (ក៏រួមទាំងថតពីទូរស័ព្ទជាមួយ “rotate”) → មិនកែរូបភាព (ចម្លង ឬប្រើក្បួនទំហំ ≤ 1080p ធម្មតា)។ វីដេអូថតពីទូរស័ព្ទដែលមាន rotate ត្រូវបានបង្វិលត្រឹមត្រូវមុនដាក់ក្នុងស៊ុម · pixel មិនការ៉េ (PAL SAR 16:15) ត្រូវបានកែ។
- **ព្រមាន** (`TIKTOK_LONG` > 10 នាទី · `TIKTOK_BIG` > 287 MB) + ឈ្មោះ Download `…_khmer_tiktok_9x16.mp4` + ឯកសារ MP4 ក្នុងលទ្ធផលបង្ហាញ `1080×1920 · TikTok 9:16 · ទំហំ`។ ម៉ាស៊ីនចាក់ក្នុង **dock** ខាងស្តាំជាទម្រង់បញ្ឈរ (ទំហំតាមកម្ពស់ទំព័រ — ១៣៦៦×៧៦៨ មិនមាន scrollbar ក្នុង dock)។
- ប្រភព៖ លក្ខខណ្ឌ TikTok (9:16 · 1080×1920 · MP4/H.264 · 10 នាទី · 287 MB/72 MB) យកពីគេហទំព័រ ៥ ក្នុងខែ Oct 2026 ហើយមិនត្រូវគ្នាទាំងអស់ → UI និយាយ “ប្រហែល” ហើយសារព្រមានផ្តោតតែលើកំណត់ធំៗ។

**ថ្មី (២) — ដំណើរការលើ MacBook និង Windows**
- **`start.command`** (macOS៖ ចុចពីរដង) · **`install-voxcpm.command`** · `start.sh` សរសេរឡើងវិញជា **POSIX `sh`** (ដំណើរការក្នុង bash 3.2 របស់ macOS, dash, zsh) — ស្វែងរក Python 3.10+ (`python3`, `python3.13` … `python3.10`, Homebrew `/opt/homebrew`, python.org `/Library/Frameworks/Python.framework`) · **រំលង stub `/usr/bin/python3`** ពេលមិនទាន់មាន Command Line Tools (បើមិនដូច្នោះ macOS បើកបង្អួចសុំដំឡើង) · សារកំហុសមានផ្លូវដំឡើង (python.org / `brew install python@3.12`) · `.venv` ដែលខូច ត្រូវបង្កើតថ្មី · `chmod +x` និងដក quarantine flag (macOS) លើកដំបូង · `start.command` រក្សាបង្អួចបើកពេលមានកំហុស។ `KDS_DRY_RUN=1` = ត្រឹមតែរាយការណ៍ Python (សម្រាប់ test)។
- **`start.bat`**៖ ស្គាល់ shortcut របស់ **Microsoft Store** (`python` ក្លែងក្លាយ) ហើយប្រាប់ឲ្យត្រូវ · ស្វែងរក `py -3` → `python` → `python3` · `PYTHONUTF8=1` (ឈ្មោះវីដេអូខ្មែរ/ចិនមិនធ្វើឲ្យ console crash)។
- **`server.py`**៖ port 8000 ជាប់ → ប្រើ 8001 … 8019 ដោយស្វ័យប្រវត្តិ (បើអ្នកកំណត់ `PORT` ហើយជាប់ → សារច្បាស់លាស់ មិនមែន traceback) · macOS ដែលគ្មាន certificate store (Python ពី python.org មុនរត់ *Install Certificates*) → ប្រើ `certifi` (Windows / Linux មិនប៉ះពាល់ — proxy ក្រុមហ៊ុនរស់ក្នុង store ផ្ទាល់ខ្លួន)។
- **VoxCPM2 លើ Mac** (`vox_setup.py`, `vox.py`, `vox_worker.py`)៖ ទីតាំង `~/Library/KhmerDub/voxcpm` (មិនក្នុង folder ដែលអាច sync iCloud · គ្មាន space) · ស្គាល់ **Apple Silicon / Intel / Rosetta** (`mac_arch()`) · **RAM** តាម `sysctl hw.memsize` (`os.sysconf` មិនមាន `SC_PHYS_PAGES` លើ macOS) · Apple Silicon៖ ពិនិត្យ **Metal (MPS)** ពិតៗ (tensor លើ `mps`) · self-test បរាជ័យលើ Metal → សាកល្បង CPU ហើយរក្សាទុក “CPU only” · `PYTORCH_ENABLE_MPS_FALLBACK=1` · `torch.mps.empty_cache()` · **Mac Intel** → `##ERROR INTEL_MAC` ភ្លាមៗ (PyTorch លែងមាន wheel — ពិនិត្យពី PyPI Oct 2026៖ torch 2.14 មានតែ `macosx_14_0_arm64`) · Python Rosetta → `##ERROR ROSETTA_PYTHON`។ voxcpm 2.0.3 គាំទ្រ MPS ដោយផ្ទាល់ (ប្រើ float32)។
- **ffmpeg ខ្វះ encoder** (build តូចពេក) → សារច្បាស់លាស់ + ផ្លូវដោះស្រាយ (`brew install ffmpeg` · `winget install ffmpeg`) — KhmerDub ប្រើ ffmpeg ក្នុង PATH មុន · **Windows**៖ MP4 ចាស់ត្រូវបានប្រើដោយកម្មវិធីផ្សេង (browser, antivirus) → ព្យាយាមជំនួសម្តងទៀត ៨ ដង រួចសារច្បាស់លាស់ (សំឡេងខ្មែរនៅដដែល)។
- **UI**៖ Settings → VoxCPM2 ព្រមាន Mac Intel / Rosetta (ប៊ូតុង Install ត្រូវបិទ) និង Mac RAM < 15 GB · បដា “No NVIDIA GPU” និងប៊ូតុង **Turbo** (ត្រូវការ NVIDIA) មិនបង្ហាញលើ Apple Silicon · រូបទូរស័ព្ទតូចប្រើរូបគំរូ បើ thumbnail ទាញមិនបាន · សារ *Ctrl+V* បង្ហាញជា **⌘V** លើ Mac · i18n +36 key (526 → 562; KM = EN)។

**បានសាកល្បង / មិនទាន់**
- ✔ **TikTok ថ្មី 186** (`test_tiktok.py`)៖ units (ជ្រើស/សម្អាត, ទំហំ canvas, ក្រាហ្វ, rotation / SAR, `-progress`, cancel ជាមួយ ffmpeg ក្លែងក្លាយ) · **ffmpeg ពិត + ពិនិត្យ pixel** (Blur / Crop ៥ ទីតាំង / ខ្សែខ្មៅ លើ 16:9 · 4:3 · 1:1 · 21:9 · 20:9 · 320×180 · 853×479 · PAL · វីដេអូផ្តេកថតពីទូរស័ព្ទ · MPEG-4 ដែល copy; សំឡេងលាយ + បិទសំឡេងដើម; cancel ពិត) · API ជាមួយ Google + Edge ពិត (`POST /video` គ្រប់ករណី: 400/404/409, cancel, បរាជ័យ, regenerate) · Chromium (Step 4, រូបទូរស័ព្ទ, ប្រអប់ក្នុងលទ្ធផល, dock ៣ ទំហំ, ទូរស័ព្ទ ៣៩០ px, ខ្មែរ/English, ក្តារចុច)។
- ✔ **Mac / Windows ថ្មី 104** (`test_platform.py`)៖ syntax ក្នុង `sh` · `dash` · `bash` · `bash --posix` · **shellcheck** · Python ក្លែងក្លាយ (Mac ចាស់ / Linux / Homebrew / stub / `python3.12` / ថតមានចន្លោះ + ខ្មែរ) · រត់ពេញ (`.venv` + pip + server; `.venv` ខូច; pip បរាជ័យ) · `server.py` (port, certificate) · Installer លើ Mac **ក្លែងក្លាយ** (Apple Silicon 8/16 GB, Intel, Rosetta, Metal មិនមាន, self-test fallback) · ការព្រមានក្នុង Chromium ជាមួយ `/api/vox/status` ក្លែងក្លាយ · ⌘V។
- ✔ ស្រាប់ៗ (ក្រោយកែ)៖ units 100 · API 74 · UI 150 · follow 54 · layout 62 · claude 167 · upload 244 · youtube 18។
- ✘ **មិនទាន់**៖ **Mac ពិត · Windows ពិត** (`start.bat` អានតែកូដ; pip ក្នុង `.venv`; ffmpeg build របស់ imageio លើ Mac — encoder `libx264` / `libmp3lame` ត្រូវមាន) · **VoxCPM2 លើ Metal** · Firefox / Safari · HDR → SDR · Subtitle ខ្មែរ burn-in · Crop តាមមុខ · ការបង្កើនល្បឿនដោយ GPU (NVENC / VideoToolbox)។

## v1.8.0 — Upload Video (Download វីដេអូពីកន្លែងផ្សេង រួច Upload មកបង្កើតសំឡេងខ្មែរ)

**ថ្មី — ប្រភពទី ៣៖ ផ្ទាំង “Upload Video”** (ក្បែរ *YouTube Link* និង *Paste Transcript*)
- **Upload** — អូសឯកសារមកក្នុងប្រអប់ ឬចុចជ្រើស (MP4 · MKV · MOV · WEBM · AVI · FLV · WMV · TS · MP3 · WAV · M4A · FLAC …)។ ក៏អូសទម្លាក់លើទំព័រ Dubbing Studio ត្រង់ណាក៏បាន ហើយប្រើបានដោយ keyboard (Enter / Space)។ មានរបារ progress (ល្បឿន · ពេលនៅសល់), ប៊ូតុង *បោះបង់*, thumbnail, ប្រវែង, ទំហំរូបភាព (វីដេអូថតបញ្ឈរក៏បង្ហាញត្រូវ) និងប៊ូតុង *ដកចេញ*។ ជ្រើសឯកសារថ្មី = ឯកសារចាស់ត្រូវលុប។
- **Server** (`POST /api/uploads?name=`)៖ body = ឯកសារដើម (**មិនមែន form**, មិនទុកក្នុង RAM — stream ចូល disk ជាដុំ ៤ MB) · ពិនិត្យ Content-Length មុន (`413 UPLOAD_TOO_LARGE`; លំនាំដើម 4 GB, `KDS_MAX_UPLOAD_MB`, `0` = គ្មានដែនកំណត់) និងពេលទទួល (chunked) · ពិនិត្យទំហំ disk (`507 DISK_FULL`) · extension ត្រូវមានក្នុងបញ្ជី (`BAD_FILE_TYPE`) · ffmpeg ត្រូវអានបាន (`NOT_MEDIA` — រូបភាព/ឯកសារក្លែងក្លាយត្រូវបដិសេធ) · **browser បោះបង់ = ឯកសារពាក់កណ្តាលត្រូវលុប** · `id` ត្រឹម ១២ តួ hex (ការពារ path) · ឯកសារដែលមិនបានប្រើលើសពី ២៤ ម៉ោងត្រូវលុប។
- **Subtitle ចំនួន ៣ ប្រភព** (តាមលំដាប់; កាតបង្ហាញភ្លាមៗថាប្រើអ្វី)៖ ① អត្ថបទដែលអ្នកដាក់ (SRT / VTT / Transcript ដែល Copy ពី YouTube / អត្ថបទធម្មតា — ឈ្នះគេ) ② **Subtitle ក្នុងឯកសារ** (`ffmpeg -i` → track SubRip · ASS · mov_text · WebVTT …; ជ្រើស track ត្រូវនឹង**ភាសាដែលជ្រើសក្នុងជំហាន 1**, បើ Auto = track ដំបូងក្នុង en / zh / ko, track គ្មានភាសា ប្រើបានជាជម្រើសចុងក្រោយ; track “forced” និង track រូបភាព (PGS / DVD) មិនប្រើ; ភាសាបារាំង/ជប៉ុន មិនត្រូវចាត់ទុកជា “មិនស្គាល់”) ③ **Whisper (AI)** ស្តាប់សំឡេង (progress ក្នុង step *Fetch transcript*, ឈប់បាន)។ បើ Whisper មាន និងឯកសារមាន track — ប៊ូតុង *“ប្រើ Subtitle ក្នុងឯកសារ / ឲ្យ Whisper ស្តាប់ជំនួស”*។
- **ប៊ូតុង Install Whisper** (`app/whisper_setup.py`, `GET /api/whisper/status`, `POST /api/whisper/install`)៖ រត់ `python -m pip install faster-whisper` ក្នុង background ជាមួយ Python ដែល server ប្រើ (Windows៖ `.venv`) — បង្ហាញ spinner, វិនាទី និង log; ចប់ហើយកាតប្តូរជា *“Whisper (AI) នឹងស្តាប់”* ដោយខ្លួនឯង ហើយ side panel ថា *Whisper: installed*។ ក៏មានក្នុង *Settings → Whisper*។ បរាជ័យ = ចុងក្រោយនៃ output របស់ pip ក្នុងសារ + ប៊ូតុង *ព្យាយាមម្តងទៀត*។ `KDS_VOX_DISABLE_INSTALL=1` / `KDS_DISABLE_INSTALL=1` (server ចែករំលែក) → បិទប៊ូតុង (`403`) ហើយបង្ហាញពាក្យបញ្ជា `pip install faster-whisper`។ `asr.whisper_installed()` មើលតែវត្តមាន package (មិន import) ហេតុនេះឃើញ package ដែលទើប install ភ្លាម។
- **ការងារ (job)**៖ `source: {type: "upload", upload_id, lang, text?, subs?}`។ ឯកសារត្រូវបាន **hard link** ចូល folder របស់ job (`upload.<ext>` + `thumb.jpg`; បើ disk មិនអាច link → copy) ដូច្នេះ job ជាម្ចាស់ផ្ទាល់ខ្លួន (Regenerate, MP4, Sync Preview) ហើយ upload នៅដដែលរហូត ២៤ ម៉ោង — *ជួសជុលហើយ Generate ម្តងទៀត* ដោយមិន Upload ថ្មី (ឧ. ក្រោយ install Whisper)។ លុប job = លុបវីដេអូនោះ។ `job.video = {id: null, upload: true, filename, thumbnail, …}`, `meta.upload`, `meta.transcript.source = "embedded"` (ថ្មី)។ ចំណងជើង = ឈ្មោះឯកសារ។ អត្ថបទដែលអ្នកដាក់មិនត្រូវរក្សាទុកក្នុង job (`<N chars>`)។
- **MP4 ពីឯកសាររបស់អ្នក** (គ្មានអ្វីត្រូវទាញយក)៖ H.264 / HEVC ដែលមិនធំជាង **1080p** (ឬ 720p) → *copy* (ភ្លាមៗ); ធំជាង (ឧ. 4K) → បន្ថយទំហំ + encode; format ផ្សេង → encode H.264។ ការប្រៀបធៀបតាម**ជ្រុងខ្លី** (1080×1920 បញ្ឈរ = 1080p) ហើយ**មិនពង្រីក**ទេ (`audio.mux_video(max_height=)`, `audio.needs_scale`)។ វីដេអូគ្មានសំឡេងក៏បាន MP4; ឯកសារសំឡេងតែប៉ុណ្ណោះ → MP3 ជាមួយការព្រមាន *NO_PICTURE*។ បិទសំឡេងដើមពេលសំឡេងខ្មែរនិយាយ (duck) ដំណើរការដូចការងារ YouTube។
- **Sync Preview ពីឯកសារ** — `<video>` ក្នុង browser ចាក់ `GET /api/jobs/{id}/source` (Range ✔) ជាមួយសំឡេងខ្មែរ + Subtitle, តារាងរំកិលតាម (Follow), បិទ/បើកសំឡេងដើម — **គ្មានការផ្ទុក YouTube player** (គ្មាន Internet)។ ប្រើ adapter តូចមួយដែលឆ្លើយ API ដូច YouTube player ដូច្នេះកូដ sync ដដែល។ ដាក់ក្នុង Dock ខាងស្តាំបានដូចគ្នា។ browser ដែលចាក់ format មិនបាន → សារជូនដំណឹង (MP4 នៅតែចាក់បាន)។
- **Original speaker (Clone)** ប្រើបានជាមួយឯកសារ Upload (សំឡេងត្រូវចម្លងពីសំឡេងក្នុងឯកសារ; គ្មានសំឡេង → សារច្បាស់លាស់) · **បកប្រែដោយ Claude** (ព្រាង → បញ្ចូលចម្លើយ → បង្កើតសំឡេង + MP4 ពីរូបភាពរបស់អ្នក) · Regenerate · Voice ក្នុងមួយជួរ ដំណើរការទាំងអស់។
- **Transcript ដែល Copy ពី YouTube** (`parse_stamped_text` ក្នុង `app/transcript.py`)៖ អត្ថបទដែលមានម៉ោង (`0:00` ក្នុងបន្ទាត់ឯង ឬនៅមុខអត្ថបទ; `[0:09]` · `(0:12)` · `1:02:03`) ត្រូវអានជា **មានម៉ោង** (ពីមុន៖ ម៉ោងត្រូវអានជាលេខ!) — ក្នុងផ្ទាំង Paste Transcript និង Upload Video ទាំងពីរ។ ត្រូវការ ≥ ៣ ម៉ោងដែលកើនឡើង និងយ៉ាងតិច ១/៥ នៃបន្ទាត់ — អត្ថបទធម្មតាដែលមានម៉ោងចៃដន្យមិនត្រូវបានយល់ច្រឡំ។ ថែមទាំងសម្អាតកូដ ASS `{\an8}` ដែលនៅសល់ក្នុង SRT។
- **ការព្រមាន**៖ អត្ថបទគ្មានម៉ោង + វីដេអូ → `UNTIMED_UPLOAD` (សំឡេងមិនតម្រឹមតាមរូបភាព); ឯកសារគ្មានសំឡេង និងគ្មាន Subtitle → `NO_AUDIO`; Whisper មិនឮសំដី → `NO_SPEECH` (ណែនាំជ្រើសភាសា); track ក្នុងឯកសារអានមិនបាន → ប្តូរទៅ Whisper (`EMBEDDED_SUBS_FAILED`)។
- **UI**៖ i18n +57 key (469 → 526; KM = EN) · កំហុសទាំងអស់មានអត្ថបទខ្មែរ · ក្រហម/ខៀវ chip តាមស្ថានភាព · សារ “Install Whisper” ត្រូវបានលាក់ពេល install រួច · រក្សាសភាពនៅ Mobile (chip បត់ជួរ)។
- **ជួសជុលតាមផ្លូវ**៖ `probe_media` អាន output របស់ ffmpeg ជា UTF-8 (title ខ្មែរ/ចិនក្នុង metadata មិនធ្វើឲ្យ crash លើ Windows ដែលប្រើ code page ចាស់) · `lib.Server` របស់តេស្ត អនុញ្ញាតឲ្យ override env។

**បានសាកល្បង / មិនទាន់**
- ✔ **Upload ថ្មី 244** (`test_upload.py`)៖ units (ffmpeg text, ជ្រើស track, ទំហំ MP4 ទាំងបញ្ឈរ/ផ្តេក, parser, installer) · API ជាមួយ Edge TTS + Google ពិត (stream ឯកសារ ~៤០ MB ដូចគ្នាបេះបិទ, បោះបង់កណ្តាលផ្លូវ, ដែនកំណត់ 1 MB ទាំង Content-Length និង chunked, prune, hard link, Range, MKV ៤ track, ព្រាង Claude, Regenerate, vox:original, NO_AUDIO …) · browser (Playwright: ផ្ទាំង, drop zone, progress ពិត (បន្ថយល្បឿន), cancel, drag & drop, Sync Preview ជាមួយ WebM ពិត, Khmer / Mobile, install Whisper ជាមួយ pip ក្លែង) · **Whisper ពិត** (`tiny`: Edge TTS និយាយ English → Whisper ស្តាប់ឮត្រូវ → បកប្រែ → សំឡេងខ្មែរ → MP4)។
- ✔ ស្រាប់ៗ៖ units 100 · API 74 · UI 150 · follow 54 · layout 62 · claude 167 · youtube 18 — ទាំងអស់ជាប់។
- ✘ **មិនទាន់**៖ **Windows ពិត** (hard link / pip ក្នុង `.venv` / ឯកសារធំ > 1 GB) · Firefox / Safari · Whisper `base` / `small` លើវីដេអូវែង (ពេលវេលា/RAM) · តួអក្សរ 中文 / 한국어 ក្នុង Whisper ពិត (បានសាកល្បងតែ English) · ឯកសារ Upload ពី e2b proxy (ដែនកំណត់ទំហំ/ពេល មិនស្គាល់)។

## v1.7.0 — បកប្រែដោយ Claude (Copy / Paste)

**ថ្មី — កន្លែង Copy subtitle ដើម ទៅ Claude ហើយ Paste ចម្លើយខ្មែរមកវិញ**
- ជំហាន 3 មានប៊ូតុងបើក **“បកប្រែដោយ Claude (Copy / Paste)”** (`translate.manual`, ចាំជម្រើស; ប៊ូតុង Engine ត្រូវងងឹតព្រោះមិនប្រើ)។ ពេលបើក ប៊ូតុងធំជា **ត្រៀមអត្ថបទសម្រាប់ Claude**៖ ការងារ (`translate.engine = "manual"`) ទាញយក + សម្អាត subtitle ដើម ហើយ**ឈប់** — មិនបកប្រែ មិនបង្កើតសំឡេង មិនទាញយកវីដេអូ (លឿន ហើយមិនខ្ជះខ្ជាយពេល VoxCPM2)។ លទ្ធផលជាការងារ **ព្រាង** (`meta.draft`) មាន `original.srt` ប៉ុណ្ណោះ; ជំហាន `translate` / `tts` / `mix` / `video` = រំលង។ Text to Speech មិនប៉ះពាល់ (UI មិនផ្ញើ `manual` ទៅទីនោះ; server ចាត់ទុកដូច Google)។
- **កាតលទ្ធផលនៃព្រាង**៖ បដា “Subtitle ដើមរួចរាល់ — សូមបកប្រែជាមួយ Claude” (+ ប៊ូតុងទាញយក SRT ដើម) · ប្រអប់ Claude បើកស្រាប់ · តារាង Segments ក្រឡាខ្មែរទទេ (គ្មានប៊ូតុង ▶ / Follow / MP4 / Sync ព្រោះមិនទាន់មានសំឡេង) · របារខាងក្រោម “មិនទាន់មានអត្ថបទខ្មែរ N / M ជួរ” ហើយប៊ូតុង **បង្កើតសំឡេង** (= `regenerate`)។ **History** មានស្លាក **ព្រាង**។
- **ប្រអប់ “បកប្រែជាមួយ Claude (Copy / Paste)”** (ក៏មានក្នុងលទ្ធផលធម្មតា — បិទជាលំនាំដើម ដើម្បី “បកប្រែឡើងវិញ” ជាមួយ Claude)៖
  - ① **Copy ទៅ Claude** — `Copy ទៅ Claude` (ការណែនាំ + ជួរ) · `ឬ Copy តែ៖ ការណែនាំ / ជួរមានលេខ` (សម្រាប់ Claude Project ដែលមានការណែនាំរួច) · `បើក claude.ai` (ផ្ទាំងថ្មី, `noopener`) · មើល/ជ្រើសអត្ថបទដោយដៃបាន (បើ Clipboard API ត្រូវហាម)។
  - **ចែកជាផ្នែក**៖ 20 · 40 · 80 · ទាំងអស់ ជួរក្នុងមួយដង (លំនាំដើម 40; ចាំ) + ◀ ▶ ប្តូរផ្នែក។ ជួរមានលេខដូចក្នុងតារាង (`idx + 1`)។ **ឈ្មោះមនុស្ស**៖ Latin (លំនាំដើម) ឬ អក្សរខ្មែរ។
  - ② **Paste ចម្លើយ** — `Paste ពី Clipboard` (អាន + បញ្ចូលក្នុងចុចតែម្តង) ឬ Paste ក្នុងប្រអប់ រួចចុច `បញ្ចូលក្នុងតារាង`។ ពេលផ្នែកមួយពេញ → ផ្នែកបន្ទាប់ត្រៀមខ្លួន (ប្រអប់សម្អាត)។ ចម្លើយអាចមកជាច្រើនដុំ — ជួរដែលបានបញ្ចូលនៅដដែល (រាប់ជាសំណុំ)។
  - **របាយការណ៍ភ្លាមៗ**៖ បានបញ្ចូល N ជួរ · ជួរខ្វះ (ឧ. 30, 31) · ចម្លើយ**ដាច់** (“ប្រាប់ Claude ថា បន្តពីជួរ 39”) · ជួរ**គ្មានអក្សរខ្មែរ** · លេខ**ស្ទួន** (យកចុងក្រោយ) · លេខមិនមាន (រំលង) · “តាមលំដាប់” បើគ្មានលេខ។
  - **ព្រាង**៖ ជួរដែលបញ្ចូល**រក្សាទុកក្នុង job ភ្លាមៗ** (`POST /translation/save`; គ្មានសំឡេងដូច្នេះមិនមានអ្វីហួសសម័យ) — reload / browser គាំង ក៏មិនបាត់; ប្តូរភាសា UI ក៏មិនបាត់ (ប្រអប់ចាំផ្នែកដែលកំពុងធ្វើ)។ **ការងារធម្មតា**៖ ជួរដែលបញ្ចូលជា “ការកែ” (ខ្សែលឿង) ចាំចុច **បង្កើតសំឡេងឡើងវិញ** — ដូចការកែដោយដៃ។
  - **បង្កើតសំឡេង** ពីព្រាង៖ ជួរខ្វះ → កម្មវិធីសួរ (“N ជួរគ្មានអត្ថបទខ្មែរ នឹងស្ងាត់ — បន្ត?”); ទទេទាំងអស់ → សារ មិនផ្ញើ។ Server ក៏ការពារ (`400 NO_KHMER_TEXT`)។
- **ព្រាង = “មិនទាន់មានសំឡេង”** — `meta.draft` បិទតែពេល `dub.mp3` មានរួច។ បើការបង្កើតលើកដំបូងបរាជ័យ/បោះបង់ (ឧ. Edge ដាច់, server restart) ការងារនៅជាព្រាង **ហើយកាតលទ្ធផលនៅតែបង្ហាញ** (បដា “បង្កើតសំឡេងមិនបានសម្រេច — អត្ថបទខ្មែររបស់អ្នកនៅដដែល”) ដូច្នេះការបកប្រែដែលបានធ្វើមិនបាត់។ (ការងារធម្មតាដែល Regenerate បរាជ័យ នៅដូចមុន។)
- **ការណែនាំ (prompt) ដែល Copy** (`app/manualtr.py`, ថ្មី, មិនប្រើ network)៖ English សម្រាប់ AI — បកប្រែជាខ្មែរនិយាយធម្មជាតិសម្រាប់សំឡេង · លេខជួរដដែល មិនបញ្ចូល/បំបែក/រំលង · **រក្សាពាក្យបច្ចេកទេស ឈ្មោះ product acronym លេខ ជា English** + បញ្ជីពាក្យដែលរកឃើញក្នុងផ្នែកនោះ (Technical Terms របស់អ្នក + រកស្វ័យប្រវត្តិ; 中文 / 한국어 ជា “服务器 → server”) · ខ្លីប្រហាក់ប្រហែលនឹងដើម · ដោះស្រាយ caption ស្វ័យប្រវត្តិដែលមានកំហុស · ឆ្លើយជា code block តែមួយ។ បើអ្នកបិទ “រក្សាពាក្យបច្ចេកទេសជា English” → “បកប្រែទាំងអស់”។ ឈ្មោះវីដេអូ (មិនដាក់ “1” ពី SRT គ្មានចំណងជើង)។
- **អានចម្លើយ** (`parse_reply`)៖ code block (រួមទាំងមិនបានបិទ) ឬអត្ថបទធម្មតា · `1.` `1)` `1:` `1 -` `[1]` `(1)` `**1.**` `Line 1:` `ជួរទី 1:` · លេខខ្មែរ/ពេញទទឹង · ជួរវែងដែលបំបែកត្រូវភ្ជាប់ (មិនភ្ជាប់ពាក្យក្រោមបន្ទាត់ទទេ) · លុប Markdown (`__init__` នៅដដែល) · `1.5 លាន` មិនមែនជួរទី 1 · គ្មានលេខតែចំនួនបន្ទាត់ត្រូវ → តាមលំដាប់។
- **API**៖ `POST /api/jobs/{id}/translation/prompt` (`part`, `size`, `names` → `text`, `instructions`, `lines_text`, `parts`, `first`, `last`, `terms` …) · `/translation/parse` (`text`, `first?`, `last?` → `items`, `missing`, `unknown`, `duplicates`, `no_khmer`, `positional`) · `/translation/save` (ព្រាងប៉ុណ្ណោះ; `409 NOT_DRAFT`) · `translate.engine = "manual"`។ i18n +61 key ក្នុងភាសានីមួយៗ (408 → 469; ភាគច្រើនក្រុម `cl.*`)។

**បានសាកល្បង / មិនទាន់**
- ✔ **Claude ថ្មី ១៦៧** (`test_claude.py`)៖ parser + prompt (ចម្លើយច្រើនទម្រង់) · API (ព្រាងបញ្ចប់ដោយខ្លួនឯង, prompt/parse/save, `NO_KHMER_TEXT`, `NOT_DRAFT`, ការងារព្រាងបរាជ័យ → នៅតែចូលបាន → ព្យាយាមម្តងទៀតជោគជ័យ, Edge ពិត) · UI (ប្តូរ Step 3, ព្រាង ៥០ ជួរ ចែក ៣ ផ្នែក, Copy ទៅ Clipboard ពិត, Paste ពី Clipboard, ជួរខ្វះ/ដាច់/ស្ទួន, reload មិនបាត់, ប្តូរភាសាខ្មែរ, History, សំឡេងពិតពីព្រាង, លទ្ធផលធម្មតា + Regenerate, Mobile)។
- ✔ ការងារព្រាង **YouTube ពិត** → គ្មានការទាញយកវីដេអូ → “បង្កើតសំឡេង” បង្កើត MP3 + MP4 ≤ 480p (`test_youtube.py`)។
- ✘ **មិនទាន់**៖ ការណែនាំ (prompt) ជាមួយ **Claude ពិត** (មិនអាចចូល claude.ai ពី sandbox — អានចម្លើយសាកល្បងតែជាមួយចម្លើយសំយោគ; សូមសាកល្បង ២០ ជួរ ហើយប្រាប់មក ដើម្បីកែ prompt) · Clipboard ក្នុង Firefox / Safari (បានសាកក្នុង Chromium) · ChatGPT / Gemini ពិត។

## v1.6.0 — ម៉ឺនុយរុញចេញចូល · វីដេអូ Fixed នៅខាងស្តាំ (Sync Preview + MP4)

**ថ្មី — ម៉ឺនុយខាងឆ្វេងរុញចេញចូលបាន**
- ប៊ូតុង ☐ (`#side-toggle`) ខាងឆ្វេងចំណងជើង៖ ចុចម្តង = ម៉ឺនុយ**រុញចេញ** (animation ~0.26 វិនាទី) ហើយមាតិកាប្រើទទឹងពេញ; ចុចម្តងទៀត = **រុញចូលមកវិញ**។ Tooltip / `aria-expanded` តាមភាសា UI (ខ្មែរ / English)។
- ចាំជម្រើសក្នុង browser (`localStorage` `kds_side`) ហើយ**ប្រើមុនគូសទំព័រលើកដំបូង** (script តូចក្នុង `<head>`) — ដូច្នេះបើក Dashboard ម៉ឺនុយនៅដូចដែលទុក មិនលោត។ Animation បើកក្រោយទំព័រគូសរួច។
- ម៉ឺនុយដែលលាក់ជា `visibility: hidden` — ប៊ូតុងក្នុងម៉ឺនុយ**មិនអាចចូលដោយ Tab** ទេ។ លើ Mobile / បង្អួច ≤ 900 px ម៉ឺនុយជាបន្ទាត់ខាងលើ ហើយគ្មានប៊ូតុងនេះ (ជម្រើសដែលចាំមិនលាក់វាទេ)។

**ថ្មី — វីដេអូ Fixed នៅខាងស្តាំ (Dock)**
- **Sync Preview (YouTube)** និង **MP4 video** (`<video>`) ត្រូវបាន `position: fixed` នៅខាងស្តាំអេក្រង់ (ឃ្លាតពីគែម 18 px, ក្រោមចំណងជើង, ទទឹង `clamp(340px, 27vw, 460px)`)។ រំកិលទំព័រទៅតារាង Segments ឆ្ងាយប៉ុនណា វីដេអូ + Subtitle (EN / ខ្មែរ) + ប៊ូតុង *សំឡេងដើម* / *បិទសំឡេងដើម ពេលនិយាយខ្មែរ* នៅតែឃើញ។ ទំព័រទុក `padding-right` ឲ្យ ដូច្នេះតារាងមិនរត់ក្រោមវីដេអូ។
- ដោះត្រឹមតែ**មួយក្នុងមួយពេល**៖ ពេលបើក *Sync Preview* វាយកកន្លែង ហើយ MP4 video ត្រឡប់មកក្នុងទំព័រ (`dock-wait`); ពេលបិទ Sync Preview (✕) MP4 video ត្រឡប់ទៅ Fixed វិញ។ ការងារ MP3 (គ្មាន MP4) → ផ្ទាំង Fixed មានតែពេលបើក Sync Preview។
- ប៊ូតុងក្នុងក្បាលផ្ទាំង៖ **–** បង្រួម (នៅតែរបារចំណងជើង) · **📌** ដោះចេញ/Fixed វិញ · **✕** បិទ Sync Preview។ ចាំក្នុង `kds_settings.ui` (`{dock: true, dockMin: false}`; profile ចាស់ពី v1.5 ទទួលលំនាំដើម = Fixed)។
- ត្រូវការទទឹង ≥ **1180 px** (តូចជាងនេះ និងលើ Mobile វីដេអូនៅក្នុងទំព័រដូចមុន — ប្តូរទទឹងបង្អួចទៅមក ផ្ទាំងប្តូរតាមភ្លាមៗ)។ បើបង្អួចទាបជាងវីដេអូ ផ្ទាំងអាចរំកិលក្នុងខ្លួនវា (`max-height`)។
- **Follow playback**៖ ផ្ទាំង Fixed មិនចេញពីអេក្រង់ទេ ដូច្នេះតារាងតាមវីដេអូជានិច្ច (ចំណុច “មិនរំកិលពេលវីដេអូនៅលើអេក្រង់” ប្រើតែពេលវីដេអូនៅក្នុងទំព័រ)។ ពេល Regenerate (កាតលទ្ធផលបាត់បណ្តោះអាសន្ន) ទំព័របានទទឹងពេញវិញ។

**កែលម្អ — ប្លង់**
- **របារចំណងជើង (title bar)**៖ គូសដូចផ្ទៃខាងក្រោយទំព័រ (មិនឃើញជាប្លុកមានគែម) ហើយរលាយតែនៅគែមក្រោម — អត្ថបទដែលរំកិលចូលក្រោមរបារលែងត្រួតលើអក្សរចំណងជើង (ពីមុនពេលចំណងជើង 2 បន្ទាត់ អក្សរពីរត្រួតគ្នា)។ ពេលមានផ្ទាំង Fixed របារនៅទទឹងពេញ — ប៊ូតុងភាសា/Theme នៅខាងស្តាំបំផុតដូចទំព័រផ្សេង។
- ពេលជួរមាតិកាតូចជាង ~880 px (ម៉ឺនុយបើក + វីដេអូ Fixed លើអេក្រង់ < ~1690 px; ម៉ឺនុយលាក់ + វីដេអូ Fixed លើអេក្រង់ < ~1370 px) ប្រអប់ *2 · ជ្រើស Voice* និង *3 · ការបកប្រែ* រៀបចុះក្រោមគ្នា (ជាជាងពីរជួរតូចៗ)។ ម៉ឺនុយលាក់ឲ្យតារាង Segments ទទឹងបន្ថែម ~264 px → ប្តូរពីទ្រង់ទ្រាយ “ជង់” ទៅទ្រង់ទ្រាយទទឹង (ម៉ោង · ភាសាដើម · ខ្មែរ ក្នុងមួយជួរ)។
- **បញ្ហាដែលរកឃើញដោយការសាកល្បង (ដោះស្រាយរួច)**៖ animation ចូលរបស់ទំព័រ (`fadeUp`) ទុក `transform` មួយនៅលើ `.page` ដែលធ្វើឲ្យ `.page` ក្លាយជា “containing block” របស់ `position: fixed` — វីដេអូរំកិលចេញជាមួយទំព័រ។ ឥឡូវ animation ទំព័រប្រើតែ `opacity`។

**បានសាកល្បង / មិនទាន់**
- ✔ Unit ១០០ · API ៧៤ · UI ១៥០ · Follow + គុណភាព ៥៤ · **Layout ៦២ (ថ្មី៖ ម៉ឺនុយ + Dock)** · YouTube ពិត ១៣។ Layout៖ ម៉ឺនុយរុញចេញ/ចូល (ទទឹង, ចាំ, គ្មាន flash ពេល reload, Tab មិនចូល, Khmer tooltip, Mobile), Dock MP4 (Fixed, ទីតាំង, `padding`, រំកិល ៤ ទីតាំង → មិនរើ, បង្រួម, ដោះចេញ, ចាំ), profile ចាស់, Sync Preview Fixed (YouTube player ក្លែង) + ផ្លាស់ជាមួយ MP4, តារាងតាមវីដេអូនៅពេល Fixed, Settings/ត្រឡប់មក Dubbing, បង្អួច ១១០០ px និង Mobile, ប្តូរទទឹងបង្អួចឆ្លងកាត់ 1180 px, Regenerate។ ពិនិត្យរូបថតទាំង Dark / Light / ខ្មែរ។
- ✘ **មិនទាន់**៖ YouTube iframe ពិត (បានសាកជាមួយ player ក្លែង) · ការចាក់ MP4 H.264 ក្នុង browser ពិត (Chromium សាកល្បងមិនមាន decoder H.264 — បានសាកជាមួយ WebM) · browser ផ្សេងក្រៅ Chromium (Firefox / Safari) · អេក្រង់ HiDPI/ទទឹងផ្សេងៗលើ Windows ពិត។

## v1.5.0 — MP4 រហូតដល់ 1080p · តារាងតាមវីដេអូ (Follow playback)

**ថ្មី — MP4 រហូតដល់ 1080p**
- ពីមុន MP4 ទាញយកវីដេអូ ≤ **720p**; ឥឡូវ **1080p** (លំនាំដើម) ឬ 720p។ ក្នុង *Output* ពេលជ្រើស *MP3 + MP4 Video* មានប៊ូតុង **1080p / 720p** ហើយអត្ថបទពន្យល់ប្តូរតាម (`Downloads the YouTube video (≤1080p) …`)។ API៖ `output.max_height` = `480` · `720` · `1080` (អ្វីផ្សេង → `1080`; ការងារដែលមិនផ្ញើវា រក្សាជម្រើសចុងក្រោយនៃការងារនោះ)។
- ប្រព័ន្ធចងចាំនូវអ្វីដែលបានទាញយក (`source.json` ក្នុង `jobs/<id>/video/`)។ ពេល *Regenerate*៖ កម្ពស់ដូចគ្នា → ប្រើឡើងវិញ (លឿន); កម្ពស់ខុស (1080p ↔ 720p) → **ទាញយកម្តងទៀត** ដើម្បីឲ្យ MP4 ត្រូវតាមជម្រើស។ ការទាញយកចាស់ (v1.3 និងមុន; គ្មាន `source.json`) ត្រូវបានចាត់ទុកជា 720p។ **កែផងដែរ**៖ វីដេអូដែលបានទាញយកដោយគ្មានសំឡេង (Original video audio = 0) មិនត្រូវបានប្រើឡើងវិញ ពេលក្រោយត្រូវការសំឡេងដើម (ពីមុន mux បរាជ័យ)។
- Log បង្ហាញទំហំពិត៖ `Video: 1920×1080 h264 (limit 1080p)` (និងការប្រុងប្រយ័ត្ន បើនឹង encode ឡើងវិញ); លទ្ធផលបង្ហាញ *MP4 1080p*។ `job.meta.video` = `{width, height, codec, limit}`។
- 1080p ធំជាង និងយឺតជាង 720p ប្រហែល ២–៣× (គំរូ ៣.៥ នាទី៖ MP4 83 MB vs 29 MB; វីដេអូ H.264 ត្រូវ copy ដោយមិន encode ឡើងវិញ; បើមិនមែន H.264 ត្រូវ encode — យឺតជាង)។

**ថ្មី — តារាងតាមវីដេអូ (Follow playback)**
- ពេលចាក់ **MP4 video**, **Sync Preview (YouTube)** ឬ **Dubbed audio** នៅនាទីណាក៏ដោយ ជួរ (script) ក្នុងតារាង Segments ដែលបានដល់ត្រូវបាន**គូសស៊ុមពណ៌ស្វាយ + ▶** (`aria-current`) ហើយតារាង **រំកិលទៅរកជួរនោះ** ដោយស្វ័យប្រវត្តិ។ “បានដល់” = ពេល Caption ឬសំឡេងខ្មែររបស់ជួរចាប់ផ្តើម (ក្នុងចន្លោះឃ្លា ជួរចុងក្រោយនៅតែគូស)។ ការទាញ/ចុច (seek) រំកិលតារាងភ្លាមៗ។
- ប៊ូតុង **តាមវីដេអូ** (បើកជាលំនាំដើម, ចាំជម្រើស) ក្បែរ Subtitle ដើម។ **មិនរំខាន**៖ ពេលវីដេអូ (MP4 ឬ YouTube Preview) **នៅលើអេក្រង់** (> ៤០% មើលឃើញ — អ្នកកំពុងមើលវា) តារាង**មិនរំកិល**ទាញរូបភាពចេញទេ (ជួរនៅតែត្រូវបានគូស + ប៊ូតុងក្នុងរបារប្រាប់ជួរ); បើអ្នករំកិលដោយដៃ → ផ្អាកការតាម ៨ វិនាទី (ការទាញវីដេអូ ឬប៊ូតុងខាងក្រោមបន្តវាម្តងទៀត); កំពុងវាយក្នុងតារាង → មិនរំកិល; ជួរដែលមើលឃើញរួចហើយ → មិនរំកិល។
- របារ sticky ខាងក្រោមមានប៊ូតុង **“កំពុងលេង៖ ជួរទី 7 / 96 · 0:41”** — ចុចដើម្បីរំកិលទៅជួរនោះ ទោះការតាមត្រូវបានបិទក៏ដោយ។
- **▶ ក្នុងជួរ** ចាក់ជួរនោះក្នុង player ដែលកំពុងប្រើ (Sync Preview បើបើក · បើមិនដូច្នោះ MP4 video ឬ Dubbed audio តាមអ្វីដែលបានចុច play ចុងក្រោយ)។ ចាក់ MP4 video → Dubbed audio ឈប់ (និងផ្ទុយមកវិញ) កុំឲ្យឮពីរ។
- ក្នុង Sync Preview សំឡេងជំនួយ (audio) មិនបង្កើតការ “seek” ក្លែងក្លាយទៀតទេ; ម៉ោងមកពី YouTube player។

**បានសាកល្បង / មិនទាន់**
- ✔ Unit ១០០ (រួមទាំងការទាញយក ១០៨០/៧២០/៤៨០, marker, ការប្រើឡើងវិញ/ទាញយកម្តងទៀត, `probe_media` ដឹងទំហំ ១៩២០×១០៨០) · API ៧៤ · UI ១៥០ · **Follow + គុណភាព ៥៤** (សំឡេង, MP4 video ពិត (WebM), YouTube player ក្លែងក្លាយ ដែលគ្រប់គ្រងម៉ោងបាន៖ គូសជួរត្រូវ, រំកិល, ផ្អាកពេលរំកិលដោយដៃ, ប៊ូតុង *កំពុងលេង*, ▶ ក្នុង player ត្រូវ, ប៊ូតុង 1080p/720p, ការផ្ញើ `max_height`)។
- ✔ **YouTube ពិត** (វីដេអូដែល sandbox ចូលបានមួយ) + Google + Edge ពិត៖ ការងារ MP4 → ទាញយក **1920×1080 h264** (៨៤ MB), MP4 ចេញមក 1080p មានសំឡេង; *Regenerate* ជា 720p → ទាញយកម្តងទៀត → MP4 720p; ម្តងទៀត 1080p ✔។
- ✘ **មិនទាន់**៖ ការចាក់ MP4 H.264 ក្នុង browser ពិត (Chromium សាកល្បងមិនមាន decoder H.264 — បានសាកល្បងជាមួយ WebM); YouTube iframe player ពិត (បានសាកជាមួយ player ក្លែងក្លាយ); វីដេអូវែង/ធំពិតៗ លើ Windows។

## v1.4.0 — Voice + Start/End ក្នុងមួយជួរ · Designed voices មកវិញ

**ថ្មី — តារាង Segments (កែក្រោយបង្កើតរួច)**
- **Voice ក្នុងមួយជួរ**៖ ប្រអប់ជ្រើស Voice ក្នុងគ្រប់ជួរ — *ដូចខាងលើ* (លំនាំដើម) · ស្រីមុំ · ពិសិដ្ឋ · (បើដំឡើង VoxCPM2) **Designed voices ៨** · My voices · Original speaker (ពេលមាន YouTube video)។ Edge និង VoxCPM2 **លាយក្នុងការងារតែមួយបាន**៖ គ្រប់ Voice ត្រូវបានរៀបចំម្តងគត់ តាមលំដាប់ដែលប្រើមុនគេ។ Regenerate នៅតែលឿន — ឃ្លាដែលមិនប្តូរមកពី cache (key មាន Voice)។
- **ដាក់ Voice ឲ្យច្រើនជួរម្តង**៖ ប្រអប់ធីកក្នុងជួរនីមួយៗ (Shift + ចុច = ជ្រើសជាចន្លោះ, *ជ្រើសទាំងអស់*) + របារខាងលើតារាង *ដាក់ Voice* / *ដោះការជ្រើស*។
- **🔊 ស្តាប់តែឃ្លានេះ**៖ ប៊ូតុងក្បែរ Voice ក្នុងជួរ — និយាយអត្ថបទដែលកំពុងកែ ជាមួយ Voice ដែលបានជ្រើសសម្រាប់ជួរនោះ (Edge៖ ភ្លាមៗ · VoxCPM2៖ តាម preview job)។ `GET /api/voices/preview?text=` និង `POST /api/vox/preview {text}` (≤ ៦០០ តួ)។ Original speaker ស្តាប់បានតែក្រោយ Regenerate។
- **Start / End ក្នុងមួយជួរ**៖ ប្រអប់ម៉ោងពីរក្នុងជួរនីមួយៗ (`2:14.5` · `134.5` · ↑/↓ = ±0.1 វិនាទី, Shift = ±1)។ ម៉ោងដែលកែមានស៊ុមពណ៌; ↺ ត្រឡប់ទៅម៉ោង Caption។ ជួរដែលមិនកំណត់ End ប្រើពេលរហូតដល់ *Start នៃជួរបន្ទាប់ − 0.1 វិនាទី* (ដូច v1.3) — ដូច្នេះការដាក់ Start នៃជួរបន្ទាប់ឲ្យយឺតជាងមុន ផ្តល់ពេលដល់ជួរមុនដោយស្វ័យប្រវត្តិ។ End ដែលកំណត់ជា **deadline**។
- **ពណ៌នៃល្បឿនភ្លាមៗ**៖ បៃតង ≤ ×1.15 · លឿង (លឿនជាងនេះ តែក្នុងដែនកំណត់) · ក្រហម ✕ (មិនគ្រប់ទោះល្បឿនអតិបរមា ×1.40 ឬតាម Settings)។ គណនាពីប្រវែងធម្មជាតិនៃឃ្លា (`dur`) និងរូបមន្តដូច server (`need × 1.03`); “≈” បន្ទាប់ពីកែអត្ថបទ។ ក្រោយ Regenerate ជួរដែលនៅតែវែងពេកមានស្លាក **វែងពេក** (ជាមួយ **យឺត** ដូចមុន)។
- **↔ ពង្រីកពេល**៖ ប្រើពេលទំនេរក្រោយជួរ (រហូតដល់ជួរបន្ទាប់) រួចពេលទំនេរមុនជួរ (ក្រោយជួរមុននិយាយរួច + ០.១២ s) ដោយមិនប៉ះជួរជិតខាង ហើយប្រាប់ល្បឿន មុន → ក្រោយ។
- កែប្រែដែលមិនទាន់ Regenerate **មិនបាត់** ពេលប្តូរភាសា UI (draft)។ ការជូនដំណឹង ពេល Sync = *ធម្មជាតិ* (ម៉ោងមិនត្រូវបានប្រើ)។
- **API**៖ `POST /api/jobs/{id}/regenerate` ទទួល `segments: [{idx, km?, voice?, t0?, t1?}]` — ត្រួតពិនិត្យមុនចាប់ផ្តើម (`400 BAD_REQUEST` + សារ៖ Voice មិនស្គាល់, ជួរមិនមាន, ម៉ោងមិនមែនលេខ/ចេញក្រៅដែន, End < Start + 0.3 s)។ `voice` `""`/`null` = ដូច Voice ខាងលើ; `t0`/`t1` `null` = ម៉ោង Caption។ ការស្នើ `{idx, km}` ចាស់នៅដំណើរការ។ ផ្នែកថ្មីក្នុងគ្រប់ segment៖ `voice`, `t0`, `t1` (ដែលអ្នកកំណត់) និង `slot` (ម៉ោង [Start, deadline] ដែលបានប្រើ), `dur` (ប្រវែងធម្មតា); `warn` = `late` និង/ឬ `long`; `meta.row_voices`, `meta.row_times`, `meta.vox.voices`។
- ម៉ោងដែលអ្នកកំណត់ **មិនប្តូរ** SRT ភាសាដើម (`original.srt`) ទេ — វាប្តូរតែ `khmer.srt`, សំឡេង, MP4 និងបង្អួចបិទសំឡេងដើម។ ជាមួយ Sync = *ធម្មជាតិ* ម៉ោងត្រូវបានមិនអើពើ (និងសរសេរក្នុង log)។

**ថ្មី — Designed voices ៨ មកវិញ (VoxCPM2)**
- ស្រី ៤ (*អ្នកនិទាន កក់ក្តៅ · ស្រីវ័យក្មេង · ស្រីស្ងប់ស្ងាត់ · អ្នកធ្វើបទបង្ហាញ*) និងប្រុស ៤ (*អ្នកនិទាន សំឡេងក្រាស់ · ប្រុសវ័យក្មេង · បុរសចំណាស់ · អ្នកអានព័ត៌មាន*) — ក្នុងផ្នែក Voice (Dubbing Studio **និង** Text to Speech) ហើយក្នុង Voice ក្នុងមួយជួរ។ មិនត្រូវការ tick យល់ព្រម (មិនមែន Clone មនុស្សពិត)។
- **បង្កើតម្តងគត់ រួច Clone**៖ ពេលប្រើលើកដំបូង VoxCPM2 និយាយប្រយោគខ្មែរ ~១០ វិនាទី ក្នុងស្ទីលដែលបានពិពណ៌នា (`voices/preset-<key>-v<n>.wav` ក្នុង VoxCPM2 home) រួចគ្រប់ឃ្លា Clone clip នោះ — សំឡេងមិនប្តូរពីឃ្លាដល់ឃ្លា។ 🎲 **Re-roll** = seed ថ្មី = មនុស្សថ្មីក្នុងស្ទីលដូចគ្នា (`POST /api/vox/presets/{key}/reroll`; បង្កើតពេលប្រើលើកក្រោយ ហើយស្តាប់ភ្លាមៗ); anchor ចាស់ ១ ត្រូវរក្សាទុក ក្នុងករណីការងារកំពុងរត់ប្រើវា។
- **ចំណាំអំពីការត្រឡប់មកវិញ**៖ v1.2 បានលុប Designed voices ហើយលុប `presets.json` / `preset-*.wav` ទាំងអស់ពេល server ចាប់ផ្តើម។ v1.4 លែងលុប (ឯកសារប្រើទ្រង់ទ្រាយថ្មី `preset-<key>-v<n>.wav`)។ ការពិពណ៌នា ៨ ត្រូវបានសរសេរឡើងវិញ — **មិនអាចទទួលបានមកវិញ** ការពិពណ៌នាដើមនៃ v1.1 (វាត្រូវបានលុបជាមួយកូដ) ដូច្នេះសំឡេងអាចខុសពីពេលមុន។
- Text to Speech៖ ជាមួយ VoxCPM2 អាចប្រើ Designed voices **និង** My voices (មិនមែនតែ My voices ទៀតទេ)។ សារ `VOX_NEED_VOICE` និង `VOX_VOICE_GONE` ត្រូវបានកែ។

**កែ**
- បញ្ជី Voice ក្នុងតារាងតាមស្ថានភាពពិត (VoxCPM2 ដំឡើងរួច/មិនទាន់, My voices ថ្មី) ទោះតារាងបានគូរហើយ។
- តារាង Segments ប្រើ *container query* — ខ្លឹមសារតាមទំហំតារាងពិត (មិនមែន viewport)៖ ធម្មតា = Voice នៅក្រោមអត្ថបទខ្មែរ; តូច/ទូរស័ព្ទ = ១ ជួរក្នុងមួយជួរ ដោយ Start/End នៅជាប់គ្នា។
- Listeners របស់តារាងត្រូវបានដោះចេញពេលគូរថ្មី (ការចុចក្រោយប្តូរភាសា/Regenerate មិនហៅ handler ចាស់ទៀត)។

**បានសាកល្បង / មិនទាន់**
- ✔ Unit ៧៩ (បញ្ជី Designed voices, ត្រួតពិនិត្យ edits, `row_settings`, ម៉ោង/slot ដូច v1.3 ១០០% ពេលគ្មានការកំណត់, `_build_track`, ការចែក engine/voice)។
- ✔ API ៧៤ ជាមួយ **Google Translate និង Microsoft Edge ពិត** + VoxCPM2 worker **ក្លែងក្លាយ** (សំឡេងខុសគ្នាតាម Voice)៖ anchor បង្កើតម្តងគត់ (ទោះសំណើ ៣ ក្នុងពេលតែមួយ), ឃ្លា ២ ប្រើសំឡេងដូចគ្នា, Re-roll ប្តូរសំឡេង, លាយ Edge + Designed ក្នុងការងារតែមួយ, cache, ការត្រួតពិនិត្យ ៦ ករណី, consent, TTS tab។ ក្នុងចំណោមនោះ ការវាស់ **pitch នៃសំឡេង Edge ពិត**៖ ជួរដែលប្តូរទៅ ពិសិដ្ឋ ទាបជាងមុនយ៉ាងច្បាស់ ហើយជួរផ្សេងនៅជាសំឡេងស្រីមុំដដែល។
- ✔ UI ១៥០ (Playwright Chromium)៖ តារាង, Voice, ជ្រើសច្រើនជួរ (Shift), Start/End, ព្រួញ, reset, **extend ជាមួយលេខច្បាស់លាស់** (ពេលទំនេរមុន/ក្រោយ/គ្មាន/គ្រប់ហើយ), payload ពិតរបស់ Regenerate (មានតែជួរ/ផ្នែកដែលបានកែ), ជាប់ draft ពេលប្តូរភាសា, ស្តាប់ឃ្លា, Designed cards, Re-roll, TTS tab, layout ៤ ទំហំ, ការងារ v1.3 ចាស់, 中文, ការងារគ្មាន timestamp, **ដំណើរការពេញលេញក្នុង browser** (Paste SRT → Generate → កែ → Regenerate → Text to Speech)។
- ✘ **មិនទាន់**៖ model VoxCPM2 ពិត (គុណភាព/ភាពស្ថិតស្ថេរនៃ Designed voices ជាមួយ model ពិត, ល្បឿន), GPU, Windows ពិត, YouTube ពិតជាមួយ Original speaker ក្នុងមួយជួរ។

## v1.3.0 — ភាសាចិន 中文 និងកូរ៉េ 한국어 → ខ្មែរ

**ថ្មី**
- **ភាសាប្រភពថ្មី៖ 中文 (Chinese) និង 한국어 (Korean)** ក្រៅពី English — Dubbing Studio (YouTube link + Paste Transcript / SRT) និង Text to Speech (*中文 → ខ្មែរ*, *한국어 → ខ្មែរ*)។
- ជំហាន 1 មាន **ភាសាក្នុងវីដេអូ**៖ *Auto-detect* (លំនាំដើម) · *English* · *中文* · *한국어* (ចាំជម្រើស)។ ប្រព័ន្ធបង្ហាញ chip *captions* នៃភាសាដែលនឹងប្រើ (រួមទាំងស្ថានភាព manual / auto-generated និងភាសាដែលមាន)។
- **Caption track ត្រឹមត្រូវ**៖ Auto ស្គាល់ភាសាពី auto-generated captions (ជាភាសានិយាយជានិច្ច); បើមានតែ manual captions ច្រើនភាសា → ចំណងជើងវីដេអូជួយសម្រេច។ មិនប្រើ track ដែល YouTube បកប្រែដោយម៉ាស៊ីន (yt-dlp `en-ko`, ឬ translation ទៅគ្រប់ភាសា) ជា “ប្រភព” ទេ។ ចិន៖ 简体 មុន 繁體។
- **ស្គាល់ភាសាតាមអក្សរ** (Hangul → ko, Han → zh, Latin → en)៖ អក្សរនៃអត្ថបទឈ្នះជម្រើសរបស់អ្នក (ជ្រើស English តែ paste 한국어 → ប្រើ Korean ហើយសរសេរក្នុង log)។ ភាសាជប៉ុន (kana) ត្រូវបានបដិសេធដោយសារ `LANG_UNSUPPORTED` ជំនួសឲ្យបកខុស។
- **Whisper**៖ `zh` / `ko` / `auto` (ស្គាល់ភាសាខ្លួនឯង) · 中文 ប្រើ prompt “以下是普通话的句子。” · model `tiny`/`base` ត្រូវប្តូរទៅ `small` សម្រាប់ចិន/កូរ៉េ · បើ Auto ឮភាសាមិនគាំទ្រ ឈប់មុន transcribe · Settings មានជម្រើស `medium`។
- **សម្អាត & បញ្ចូលឃ្លា** តាមភាសា៖ `[音乐]` `【掌声】` `（笑）` `[음악]` `(박수)` ត្រូវលុប; `。！？`; ប្រវែងឃ្លាអតិបរមា English 230 · 中文 80 · 한국어 125 តួ (≤ ~12 វិនាទី); មិនដាក់ចន្លោះរវាងអក្សរចិន; អត្ថបទគ្មាន timestamp ប្រើល្បឿននិយាយតាមភាសា (14 / 4.6 / 7.5 តួក្នុងមួយវិនាទី)។
- **បកប្រែ**៖ Google `sl` = `en` / `zh-CN` / `ko`; AI / LLM ត្រូវបានប្រាប់ភាសាប្រភព (និងគំរូពាក្យ) ហើយ payload ប្រើ key តាមភាសា (`"en"` / `"zh"` / `"ko"`)។ Cache បកប្រែ English មិនប្រែ (ការបកចិន/កូរ៉េមាន key ដាច់ដោយឡែក)។
- **ពាក្យបច្ចេកទេសជា English សម្រាប់ 中文 / 한국어**៖ តារាងភ្ជាប់មកជាមួយ ~៤៨០ ពាក្យ (`app/cjkterms.py`) — នាម និងឈ្មោះ៖ 服务器 → *server*, 数据库 → *database*, 机器学习 → *machine learning*, 谷歌 → *Google*; 서버 → *server*, 머신러닝 → *machine learning*, 유튜브 → *YouTube*, 파이썬 → *Python*, 챗GPT → *ChatGPT*។ ពាក្យ English ក្នុងអត្ថបទ (Docker, GPT-4) ត្រូវបានការពារដូចដើម។ បន្ថែមខ្លួនឯងក្នុង *ពាក្យបច្ចេកទេស*៖ `机器学习 => machine learning`។ ភាសាកូរ៉េ៖ ស្គាល់ particle (서버를, 서버에서는), មិនប៉ះពាក្យវែងជាង (서버리스 ≠ 서버), ចន្លោះជាជម្រើស (머신 러닝 = 머신러닝)។
- **ឯកសារគំរូ** `samples/technical-tutorial.zh.srt` និង `.ko.srt`។

**កែប្រែ**
- `english.srt` → **`original.srt`** (មាន `…_chinese.srt` / `…_korean.srt` / `…_english.srt` ពេលទាញយក)។ ការងារចាស់នៅបើកបាន; *Regenerate* ប្តូរទៅឈ្មោះថ្មី។ ស្លាកក្នុង UI (Subtitle ដើម, ជួរតារាង, ប៊ូតុង SRT, `<track>` ក្នុង MP4 preview) បង្ហាញភាសាពិត។
- ចំណងជើង/ពាក្យពណ៌នា ក្នុង UI និង README ប្តូរពី “English → Khmer” ជា “English · 中文 · 한국어 → Khmer”។
- Heuristic រកឃើញ URL / email / `.NET` ប្រើ ASCII តែប៉ុណ្ណោះ (ពីមុន `\w` / `[^\s]` លេបអក្សរចិន/កូរ៉េជុំវិញ ពីព្រោះគ្មានចន្លោះ)។ URL / email ត្រូវបានរកមុនពាក្យក្នុងបញ្ជី (មិនបំបែក `https` + `example.com` ទៀតទេ)។
- បញ្ជី *ពាក្យបច្ចេកទេស*៖ បន្ទាត់ `ពាក្យដើម => English` មិនរាប់ជា “ពាក្យ” ទេ (មានរាប់ដាច់ដោយឡែក)។
- ការសម្អាត៖ ឃ្លាដែលមានតែអក្សរចិន/កូរ៉េមិនត្រូវបានលុបចោលទៀតទេ (regex ចាស់ទទួលតែ Latin / digit / Khmer)។
- `/api/translate` ទទួល `lang` (`en` · `zh` · `ko`)។ `/api/video/info` → `captions` = `{langs: {en, zh, ko}, detected, languages, english}` (field `english` នៅដដែលសម្រាប់ភាពត្រូវគ្នា)។
- បន្ទាត់ `.srt` ចិន/កូរ៉េ៖ font fallback (Microsoft YaHei / Malgun Gothic / Noto CJK) និង `lang` attribute ក្នុងតារាង Segments។

**បានសាកល្បង / មិនទាន់**
- ✔ ការបកប្រែ 中文 និង 한국어 → ខ្មែរ ជាមួយ Google ពិត + សំឡេង Edge ពិត (SRT គំរូទាំងបី end-to-end; terms ត្រូវបានរក្សា; គ្មាន placeholder លេចចេញ); `/api/translate`; TTS tab; ការងារចាស់ (`english.srt`) + Regenerate; UI (Playwright 44+ checks, KM/EN, mobile); ការជ្រើស caption track ជាមួយបញ្ជី track YouTube ពិត (dQw4w9WgXcQ) និងជាមួយ mock (ko/zh/en/ja, yt-dlp `-orig`)។
- ✘ **មិនទាន់**៖ វីដេអូ YouTube ភាសាចិន/កូរ៉េពិតៗ (YouTube ទប់ស្កាត់ IP ផ្សេងពី video សាកល្បង) · Whisper ជាមួយសំឡេងចិន/កូរ៉េពិត (ប្រើតែ fake module ដើម្បីសាកល្បងការហៅ)។

## v1.2.0 — Clone ប៉ុណ្ណោះ · បិទសំឡេងដើមពេលនិយាយខ្មែរ · Turbo ⚡ · Settings ស្អាតជាងមុន

**ថ្មី**
- **បិទសំឡេងដើម ពេលសំឡេងខ្មែរកំពុងនិយាយ** — ប៊ូតុងថ្មីក្នុង *Output* (ក្បែរ *Original video audio*) និងក្នុង *Sync Preview*។ ក្នុងរយៈពេលដែលអ្នកនិយាយដើម **ឬ** សំឡេងខ្មែរកំពុងនិយាយ សំឡេងដើមត្រូវបិទទាំងស្រុង (0) ហើយត្រឡប់មកវិញក្នុងចន្លោះឃ្លា តាមកម្រិតដែលបានកំណត់។ មាន padding (មុន ០.១០ s · ក្រោយ ០.២២ s), បញ្ចូលចន្លោះខ្លីជាងកន្លះវិនាទី និង fade ខ្លី (គ្មាន “click”)។ caption ដែលគ្មានអត្ថបទខ្មែរ (ឧ. `[Music]`) មិនត្រូវបានបិទទេ។ បើកជាលំនាំដើម។ MP4 ប្រើ gain envelope តូចមួយគុណនឹងសំឡេងដើមក្នុង ffmpeg (គ្មានដែនកំណត់ចំនួនឃ្លា); បើវាបរាជ័យ MP4 នៅតែត្រូវបានបង្កើត (កម្រិតថេរ) ជាមួយការព្រមាន។
- **Turbo ⚡ (ពិសោធន៍ · បិទជាលំនាំដើម)** — Settings → VoxCPM2។ កត់ត្រាជំហាន diffusion ជា CUDA graph ដើម្បីកាត់បន្ថយការងាររបស់ CPU (ពេលនេះ GPU កណ្តាលរង់ចាំ CPU ~៥០% នៃពេល)។ អាចលឿនជាង ≈ ២× ដោយសំឡេងដូចដើម។ ផ្ទៀងផ្ទាត់ជាមួយលទ្ធផលធម្មតាមុនប្រើ; បើមានបញ្ហាអ្វីក៏ដោយ ត្រឡប់ទៅរបៀបធម្មតាដោយខ្លួនឯង ហើយ Settings បង្ហាញមូលហេតុ; បើ engine គាំងពេលកត់ត្រា Turbo ត្រូវបានរំលងរហូតដល់អ្នកបិទ/បើកម្តងទៀត។ **មិនទាន់បានសាកល្បងលើ GPU ពិត** (បានសាកល្បងតែ logic លើ CPU ជាមួយ sampler ពិតរបស់ voxcpm)។
- ជ្រើស **VoxCPM2** engine → model ចាប់ផ្តើមផ្ទុកក្នុង background ភ្លាម និងធ្វើ *warm-up* មួយឃ្លា (ឃ្លាដំបូងមិនយឺតទៀត)។
- ក្រោមប៊ូតុងគុណភាពមានការប៉ាន់ស្មានពេលបង្កើត (ពីល្បឿនវាស់ពេលដំឡើង): *លឿន ≈ 0.7× · មធ្យម ≈ 1.0× · ខ្ពស់ ≈ 1.7×* នៃរយៈពេលសំឡេង។

**លុបចេញ**
- **Designed voices (៨)** និងប៊ូតុង Re-roll (`/api/vox/presets/{id}/reroll`)។ VoxCPM2 នៅសល់ **Speaker in the video (Clone)** និង **My voices**។ Setting ចាស់ដែលជ្រើស Designed voice ប្តូរទៅ *Speaker in the video* ដោយស្វ័យប្រវត្តិ ហើយ clip ដែលបានបង្កើតសម្រាប់វា (`voices/preset-*.wav`) ត្រូវបានលុប។ ក្នុង *Text to Speech* (គ្មានវីដេអូ) VoxCPM2 ប្រើបានតែ *My voices*។
- **Settings៖** កន្លែងបង្ហាញព័ត៌មានដែលមិនចាំបាច់ — ការពិពណ៌នា VoxCPM2, “កុំព្យូទ័ររបស់អ្នក” (GPU / VRAM / CUDA / RAM), ថតដំឡើង និងកាត **System** ទាំងមូល។ នៅសល់៖ ចំណុចស្ថានភាព និង version ក្នុង sidebar; ការព្រមានតែពេលចាំបាច់ (គ្មាន NVIDIA GPU ឬ VRAM < 8 GB)។ ព័ត៌មានលម្អិតនៅ `/api/system`។

**កែ**
- ពេល paste transcript ហើយជ្រើស *Speaker in the video* ប្រព័ន្ធបង្ហាញសារ “ត្រូវការ YouTube link” មុនសារ consent។

## v1.1.2 — ជួសជុល៖ browser ប្រើ script ចាស់ (ប៊ូតុង «ដំឡើង VoxCPM2» ចុចមិនកើត)

**បញ្ហា**៖ ក្នុង Settings បង្ហាញឈ្មោះដើម (`set.vox.install` …) ជំនួសឱ្យអក្សរខ្មែរ ហើយចុចប៊ូតុងមិនមានអ្វីកើតឡើង។ មូលហេតុ៖ browser បន្តប្រើ `app.js` / `i18n.js` **ចាស់** ពី cache ទោះ file លើថាសថ្មីហើយក៏ដោយ — URL ដូចគ្នា ដូច្នេះ browser មិនសួរ server ទេ (terminal មិនបង្ហាញ `GET /static/...` សោះ)។ បានចម្លងបញ្ហានេះក្នុង Chromium ហើយបញ្ជាក់ថាជួសជុលរួច។

**ជួសជុល**
- URL របស់ script / CSS ឥឡូវមាន fingerprint ពី *មាតិកា file* + កំណែកម្មវិធី (`?v=1.1.2-xxxxxxxxxx`) ជំនួសពេលវេលាកែ file (ដែលអាចដូចគ្នារវាងកំណែ)។
- Server ផ្ញើ `Cache-Control: no-cache` សម្រាប់ UI files (revalidate រាល់ពេល — លឿន ព្រោះ local) និង `no-store` សម្រាប់ទំព័រ HTML។
- Tab ចាស់ដែលបើកទុក ជាមួយ server ថ្មី ⇒ ទំព័រ reload **ម្តងដោយស្វ័យប្រវត្តិ** (មិន loop)។
- UI files មកពីកំណែផ្សេង (extract មិនគ្រប់) ⇒ **ផ្ទាំងក្រហម** នៅលើទំព័រ + ព្រមានក្នុង console។ `/api/health` មាន `assets` និង `ui_ok`។
- ជ្រុងខាងឆ្វេងខាងក្រោមបង្ហាញ `KhmerDub v… · UI …` (បើ UI ជា `?` មានន័យថា script មិនបាន load)។
- README៖ ជួរ Troubleshooting ថ្មី (script ចាស់ · `WinError 126` / Visual C++ Redistributable)។

**Installer (ត្រូវបានសាកល្បងពិតលើ Linux CPU)**
- បើបិទ/restart dashboard ពេលកំពុងដំឡើង (installer នៅតែដំណើរការក្នុង background) → dashboard ថ្មីបង្ហាញដំណើរការដដែល ហើយ**មិនចាប់ផ្តើម installer ទីពីរ**ពីលើទីមួយទេ (heartbeat file `setup.alive`) · ប៊ូតុង Cancel ក៏បញ្ឈប់បានដែរ។
- បើការដំឡើងពីមុនត្រូវបានបញ្ឈប់កណ្តាលដំណើរ (environment ពាក់កណ្តាល, pip ខូច) → installer ស្គាល់ ហើយបង្កើត environment ឡើងវិញដោយស្វ័យប្រវត្តិ (មុននេះបរាជ័យ `TORCH_FAILED`)។
- pip cache បណ្តោះអាសន្ន (≈ ៣ GB) ត្រូវលុបបន្ទាប់ពីដំឡើង package រួច មុនទាញយក model (មិនទុកលាក់លើ drive C: ជារៀងរហូតទេ)។
- បង្ហាញ phase (`៤/៦ …`) ត្រឹមត្រូវ ទោះ pip បញ្ចេញ log រាប់រយបន្ទាត់ (មុននេះ phase អាចបាត់បន្តិច)។

## v1.1.1 — សម្រាប់ GPU ៨ GB (ឧ. RTX 5050 / 4060) និង RTX 50-series

- **Installer** ជ្រើស PyTorch `cu128` សម្រាប់ RTX 50-series (Blackwell) ដោយស្វ័យប្រវត្តិ (driver ត្រូវមាន CUDA ≥ 12.8) ហើយពិនិត្យថា GPU ដំណើរការពិត (bf16) មុនទទួលយក។
- **ការសាកល្បងចុងក្រោយ**៖ បើ GPU អស់ memory ពេលសាកល្បង installer សាកល្បងលើ **CPU** ជំនួស ហើយជ្រើស “CPU only” ដោយស្វ័យប្រវត្តិ (មានចំណាំក្នុង Settings) — មិនទុកឲ្យអ្នកជាប់គាំងទេ។
- **Worker** សម្រាប់ GPU ≤ ១០ GB៖ បង្កើនប្រសិទ្ធភាព memory (allocator), សម្អាត cache ក្រោយគ្រប់ឃ្លា, ហើយបើឃ្លាមួយអស់ memory វាព្យាយាមម្តងទៀតម្តងដោយ cache ស្អាត មុនបរាជ័យ។

## v1.1.0 — VoxCPM2 (សំឡេងច្រើន + Clone) និង Subtitle on/off

**ថ្មី**

- **Engine VoxCPM2 (ជម្រើស · local · ឥតគិតថ្លៃ)** — ជ្រើសក្នុងផ្នែក *Voice* ក្បែរ Edge (ស្រីមុំ/ពិសិដ្ឋ) ដែលនៅដដែល៖
  - **Designed voices ៨** (ស្រី ៤ · ប្រុស ៤) + ប៊ូតុង 🎲 Re-roll បង្កើតសំឡេងថ្មីក្នុងស្ទីលដូចគ្នា។
  - **My voices** — Upload clip ៨–២៥ វិនាទី → Clone សំឡេង។
  - **Original speaker** — កាត់ clip ស្អាតពីសំឡេងវីដេអូដើម (YouTube) រួច Clone ឲ្យនិយាយខ្មែរ។ ជម្រើស “ចាប់ផ្តើមកាត់សំឡេងគំរូនៅ” និងស្តាប់ clip ដែលបានប្រើក្នុងលទ្ធផល។
  - ពាក្យ English ក្នុងប្រយោគខ្មែរអានដោយសំឡេងតែមួយ។
  - ត្រូវ tick “ខ្ញុំជាម្ចាស់សំឡេង ឬមានការអនុញ្ញាត” មុនប្រើ Clone។
  - គុណភាព *លឿន / មធ្យម / ខ្ពស់*, Speed, Volume; ETA ក្នុង progress; ឃ្លា cache; Cancel ដំណើរការទោះ CPU យឺត។
- **Settings → VoxCPM2** — ដំឡើងដោយចុចតែម្តង (រកឃើញ GPU, Python 3.11 ដាច់ដោយឡែក តាម `uv` បើចាំបាច់, PyTorch GPU/CPU, `voxcpm`, model ៥ GB, សាកល្បងជាក់ស្តែង + វាស់ល្បឿន) · Start/Stop · សាកល្បងសំឡេង · CPU only · log។ ក៏មាន `install-voxcpm.bat/.sh`។
- **Subtitle on/off** — ក្នុង Sync Preview៖ **Subtitle ដើម (EN)**, **Subtitle ខ្មែរ**, **សំឡេងដើម**; ក្នុង MP4 Preview៖ EN / ខ្មែរ (WebVTT)។ ចងចាំជម្រើស។
- ជ្រុងខាងឆ្វេងខាងក្រោម៖ ស្ថានភាព VoxCPM2។

**ស្ថាបត្យកម្ម** — VoxCPM2 រត់ក្នុង environment ដាច់ដោយឡែក និង process worker (`127.0.0.1` + token) ដូច្នេះ dashboard នៅតែស្រាល (គ្មាន dependency ថ្មី) ហើយ Python ណាក៏ដោយ (3.10+) ប្រើបាន។

**សម្គាល់** — ការសាកល្បងរបស់ខ្ញុំ (Linux, គ្មាន GPU) បានបញ្ជាក់ថា installer, worker, API និង UI ដំណើរការជាមួយ package `voxcpm` ពិត (model តូចចៃដន្យ) ប៉ុន្តែ **មិនទាន់បានសាកល្បង model ៥ GB ពិត, GPU/CUDA, ឬ Windows ទេ**។

## v1.0.1 — ដោះស្រាយការ Translate ជាប់ជាយូរ

**បញ្ហា**៖ ពេល Google Translate (ឥតគិតថ្លៃ) មិនឆ្លើយតប (HTTP 429 ឬ network ជាប់) ប្រព័ន្ធបានព្យាយាមម្តងហើយម្តងទៀតដោយស្ងៀមស្ងាត់។ Progress នៅ 0% ជាង ១០ នាទី (វីដេអូ ១៥ នាទី = 96 segments → ប្រហែល ២០ នាទី) មុនបង្ហាញកំហុស ហើយមិនមាន log ប្រាប់អ្វីទាំងអស់។

**ការកែ**

- **Translate ជា batch** — ១៦ ជួរក្នុងមួយ request។ 96 segments ប្រើ 6 requests ជំនួស 96+ (វាស់ក្នុង sandbox ជាមួយអត្ថបទថ្មី៖ ~២៨ វិនាទី → ~២.៥ វិនាទី; លទ្ធផលបកប្រែដូចគ្នា ១០០%)។
- **៤ route របស់ Google** ត្រូវសាកល្បងជាបន្តបន្ទាប់ ហើយប្រព័ន្ធចងចាំ route ដែលដំណើរការ។ បើមាន System Proxy / VPN ក៏សាកល្បងភ្ជាប់ត្រង់ផងដែរ។
- **Fail fast** — បើ Google មិនឆ្លើយ ប្រព័ន្ធឈប់ក្នុងរយៈពេលប្រហែល ៣០–៦០ វិនាទី (ជំនួស ~២០ នាទី) ជាមួយសារច្បាស់លាស់ (rate limit 429 ឬ network) ហើយ Cancel ដំណើរការភ្លាមៗ។
- **បង្ហាញបញ្ហា** — retry និងមូលហេតុបង្ហាញនៅក្បែរ Progress bar និងក្នុង Detailed log។
- **Settings → សាកល្បង Google Translate** — បង្ហាញថា route ណាដំណើរការ និងលឿនប៉ុណ្ណា (`GET /api/translate/diagnose`)។
- **Edge TTS** — retry បង្ហាញក្នុង log; timeout ខ្លីជាងមុន (កំហុសមកក្នុង ~១២ វិនាទី ជំនួសរង់ចាំជាច្រើននាទី)។
- **AI / LLM** — batch ដំណើរការស្របគ្នា ៣; preset Gemini ប្តូរទៅ `gemini-3.8-flash`; ពន្យល់កំហុស 400/404 ឱ្យច្បាស់។
- **ជ្រុងខាងឆ្វេងខាងក្រោម** — `Whisper (ជម្រើស): មិនទាន់ install` ប្រើ icon ទទេ (មិនមែនពណ៌លឿងដូចកំហុស) ហើយមាន tooltip ពន្យល់។

## v1.0.0

ការចេញផ្សាយដំបូង។
