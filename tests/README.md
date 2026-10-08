# tests/ — Test suites របស់ V_Heang Studio

មិនមែនជាផ្នែកនៃកម្មវិធីទេ (អ្នកប្រើធម្មតាអាចលុបថតនេះបាន)។ ការពន្យល់ពេញលេញ (តារាង suite, fixtures, stubs, អន្ទាក់)៖ [`../DEVELOPMENT.md`](../DEVELOPMENT.md) §11។
សរសេរសម្រាប់ **Linux / macOS** (ប្រើ `sh`) — លើ Windows ប្រើ WSL។ Suite ដែលសម្គាល់ 🌐 ត្រូវការ internet (Google Translate, Microsoft Edge TTS, YouTube ពិត)។

```sh
pip install -r ../requirements.txt -r requirements-dev.txt
python -m playwright install chromium                  # Linux: បន្ថែម --with-deps

python3 test_units.py                                   # suite មួយ (វិនាទី)
ONLY=A,B python3 test_tiktok.py                         # តែផ្នែកខ្លះ (test_upload / test_tiktok / test_hardsub / test_pwa / test_platform)
sh run_all.sh                                           # ទាំងអស់ ≈ 15 នាទី — ល្អជាងរត់ក្នុង background៖
nohup sh run_all.sh > /dev/null 2>&1 &  ;  cat "${KDS_TEST_WORK:-${TMPDIR:-/tmp}/kds-tests}/final_summary.log"
```

| ប្រអប់ | ន័យ |
|---|---|
| `KDS_TEST_WORK` | ថតការងារ (វីដេអូ fixture, data, log, screenshot)។ លំនាំដើម `<temp>/kds-tests` — បើ `/tmp` ជា RAM តូច ត្រូវកំណត់ទៅថតលើ disk |
| `KDS_PROJECT` | project ដែលត្រូវសាកល្បង (លំនាំដើម = ថតមេនៃ `tests/`) |
| `PYTHON` | interpreter សម្រាប់ `run_all.sh` (លំនាំដើម `python3`) |

**Suites**៖ `test_units` · `test_core` (offline) · `test_api` 🌐 · `test_ui` · `test_follow` · `test_clickplay` (ចុចជួរ → លេងវីដេអូ — port 8071) · `test_layout` · `test_claude` 🌐 · `test_voices` (My voices ច្រើនឯកសារ · គ្មាន spec របស់ PC — port 8072) · `test_speakers` 🌐 (ស្គាល់តួអង្គ ប្រុស / ស្រី + សំឡេងតាមតួអង្គ — port 8073) · `test_winlock` 🌐 (**Windows**៖ ឯកសារដែល browser កំពុងបើក មិនត្រូវធ្វើឲ្យ Regenerate ខូច — server ដែលធ្វើត្រាប់តាម Windows ក្នុង `winlock/` — port 8074) · `test_upload` 🌐 · `test_tiktok` (+`test_tiktok_ui`) 🌐 · `test_hardsub` 🌐 (បិទបាំង Subtitle ដើម៖ units · ffmpeg pixel · API · browser) · `test_pwa` (ដំឡើងជា App៖ files · routes · server.py · browser — port 8066) · `test_platform` · `test_youtube` 🌐។
**ឯកសារជំនួយ**៖ `synthvoice.py` (បង្កើតសំឡេងប្រុស / ស្រីសម្រាប់ test_speakers ដោយ Edge TTS) · `winlock/sitecustomize.py` (ធ្វើឲ្យ Python លើ Linux / macOS ប្រព្រឹត្តដូច Windows ក្នុងរឿងមួយ៖ ឯកសារដែលនៅបើកស្រាប់ លុប / ជំនួសមិនបាន — បើក `PYTHONPATH` + `KDS_WINLOCK_SIM=1`)។
**ឧបករណ៍**៖ `shots.py` (screenshot ដើម្បីមើលដោយភ្នែក) · `check_preview.py [URL]` (dashboard ដែលកំពុងរត់) · `smoke_zip.py [zip]` (ZIP ដែលបានបង្កើត)។

⚠ កុំកែ `app/` `static/` `tests/` ពេល `run_all.sh` កំពុងរត់ (suite នីមួយៗអាន file ពេលចាប់ផ្តើម)។
