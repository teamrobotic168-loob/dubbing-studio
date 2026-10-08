/* V_Heang Studio – dashboard logic (vanilla JS, no build step) */
(() => {
'use strict';
const KDS_UI_VERSION = '1.13.0';   // must equal app.__version__ (the server shows a warning when the UI files are from another version)

/* ============================================================ helpers */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const getPath = (o, p) => p.split('.').reduce((a, k) => (a == null ? a : a[k]), o);
const setPath = (o, p, v) => { const ks = p.split('.'); const last = ks.pop(); const t = ks.reduce((a, k) => (a[k] ??= {}), o); t[last] = v; };
const deepMerge = (base, extra) => {
  if (!extra || typeof extra !== 'object') return base;
  for (const k of Object.keys(base)) {
    if (base[k] && typeof base[k] === 'object' && !Array.isArray(base[k])) deepMerge(base[k], extra[k]);
    else if (extra[k] !== undefined) base[k] = extra[k];
  }
  return base;
};
const fmtTime = (sec) => {
  sec = Math.max(0, Math.round(Number(sec) || 0));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
};
/* m:ss.s - the editable Start / End of a line */
const fmtClock = (sec) => {
  const tenths = Math.max(0, Math.round((Number(sec) || 0) * 10));
  const h = Math.floor(tenths / 36000), m = Math.floor((tenths % 36000) / 600), s = (tenths % 600) / 10;
  const ss = s.toFixed(1).padStart(4, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
};
const parseClock = (v) => {
  const x = String(v ?? '').trim().replace(',', '.');
  if (!x) return null;
  if (/^\d+(\.\d+)?$/.test(x)) return Number(x);
  const m = x.match(/^(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:\.\d+)?)$/);
  if (!m || Number(m[2]) >= 60 || Number(m[3]) >= 60) return null;
  return Number(m[1] || 0) * 3600 + Number(m[2]) * 60 + Number(m[3]);
};

/* ============================================================ icons */
const ICONS = {
  logo: '<g stroke-width="2.6"><path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/></g>',
  dub: '<rect x="2" y="4" width="20" height="16" rx="3.5"/><path d="M10 9l5 3-5 3z"/>',
  mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4M8 22h8"/>',
  terms: '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
  history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  settings: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  youtube: '<path d="M22 8.2a3 3 0 0 0-2.1-2.1C18 5.6 12 5.6 12 5.6s-6 0-7.9.5A3 3 0 0 0 2 8.2 31 31 0 0 0 1.6 12a31 31 0 0 0 .4 3.8 3 3 0 0 0 2.1 2.1c1.9.5 7.9.5 7.9.5s6 0 7.9-.5a3 3 0 0 0 2.1-2.1c.4-1.3.4-3.8.4-3.8s0-2.5-.4-3.8z"/><path d="M10 15l5-3-5-3z" fill="currentColor"/>',
  doc: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  paste: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
  wand: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  sparkle: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  x: '<path d="M18 6L6 18M6 6l12 12"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  alert: '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/>',
  save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
  reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  plug: '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0zM12 18v4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  play: '<path d="M8 5v14l11-7z"/>',
  pause: '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>',
  spinner: '<path d="M21 12a9 9 0 1 1-6.2-8.6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/>',
  video: '<rect x="2" y="5" width="14" height="14" rx="3"/><path d="M16 10l6-3v10l-6-3z"/>',
  chip: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  cc: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10.5 10.2a2.4 2.4 0 1 0 0 3.6M17.5 10.2a2.4 2.4 0 1 0 0 3.6"/>',
  volume: '<path d="M11 5L6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
  volmute: '<path d="M11 5L6 9H3v6h3l5 4z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>',
  dice: '<rect x="3" y="3" width="18" height="18" rx="4.5"/><g fill="currentColor" stroke="none"><circle cx="8.2" cy="8.2" r="1.35"/><circle cx="15.8" cy="8.2" r="1.35"/><circle cx="12" cy="12" r="1.35"/><circle cx="8.2" cy="15.8" r="1.35"/><circle cx="15.8" cy="15.8" r="1.35"/></g>',
  extend: '<path d="M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
  follow: '<circle cx="12" cy="12" r="3"/><path d="M12 3v4M12 17v4M3 12h4M17 12h4"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
  pin: '<path d="M12 17v5"/><path d="M9 10.8a2 2 0 0 1-1.1 1.8l-1.8.9A2 2 0 0 0 5 15.2V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.8a2 2 0 0 0-1.1-1.8l-1.8-.9A2 2 0 0 1 15 10.8V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
  minus: '<path d="M5 12h14"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2.5"/><path d="M4 16V5.5A2.5 2.5 0 0 1 6.5 3H16"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/><path d="M9 11h6M9 14h4"/>',
  left: '<path d="M15 6l-6 6 6 6"/>',
  right: '<path d="M9 6l6 6-6 6"/>',
  install: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17.2" cy="9" r="2.7"/><path d="M16.6 14.3A5.6 5.6 0 0 1 21.5 20"/>',
  swap: '<path d="M4 8h14M14 4l4 4-4 4M20 16H6M10 12l-4 4 4 4"/>',
};
const icon = (name, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;
const hydrateIcons = (root = document) => $$('i[data-icon]', root).forEach((el) => { el.outerHTML = icon(el.dataset.icon); });

/* ============================================================ state */
const PRESETS = {
  openai: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  gemini: { base_url: 'https://generativelanguage.googleapis.com/v1beta/openai', model: 'gemini-3.8-flash' },
  openrouter: { base_url: 'https://openrouter.ai/api/v1', model: 'openai/gpt-4o-mini' },
  groq: { base_url: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile' },
};
const DEFAULTS = () => ({
  voice: {
    id: 'km-KH-SreymomNeural', rate: 0, pitch: 0, volume: 0, term_mode: 'english_voice', en_voice: '',
    engine: 'edge', vox: { id: 'vox:original', quality: 'balanced', ref_start: '', consent: false },
    auto: { on: true, male: '', female: '' },          // voices by character: men -> a male voice, women -> a female voice (found from the sound of the video)
  },
  translate: { engine: 'google', manual: false, keep_terms: true, auto_detect: true, llm: { preset: 'openai', base_url: PRESETS.openai.base_url, api_key: '', model: PRESETS.openai.model } },
  output: { sync: 'fit', format: 'audio', orig_volume: 0, duck: true, max_speedup: 1.4, max_height: 1080, aspect: 'original', fit: 'blur', crop_x: 50,
    hide_subs: false, hide_effect: 'blur', hide_bottom: 3, hide_height: 16, hide_strength: 50 },
  remake: { aspect: 'original', fit: 'blur', crop_x: 50, max_height: 1080,      // the 'video shape' panel of a finished job (starts from that job)
    hide_subs: false, hide_effect: 'blur', hide_bottom: 3, hide_height: 16, hide_strength: 50 },
  source: { lang: 'auto' },
  youtube: { cookies_browser: '', proxy: '', whisper: true, whisper_model: 'base' },
  tts: { input_lang: 'km' },
  subs: { en: true, km: false, orig: false, follow: true, clickplay: true },
  ui: { dock: true, dockMin: false },
  claude: { size: 40, names: 'latin' },          // copy / paste translation: lines per part, how names are written
});
const loadSettings = () => {
  try { return deepMerge(DEFAULTS(), JSON.parse(localStorage.getItem('kds_settings') || '{}')); } catch { return DEFAULTS(); }
};
const state = {
  lang: localStorage.getItem('kds_lang') || 'km',
  theme: localStorage.getItem('kds_theme') || 'dark',
  page: 'dub',
  s: loadSettings(),
  voices: { khmer: [], english: [], vox: { custom: [] } },
  vox: null,
  sourceTab: 'youtube',
  video: null,
  videoUrl: '',
  jobs: { dub: null, tts: null },
  tracking: { dub: null, tts: null },
  system: null,
  termsDirty: false,
};
/* Source languages of the video: English, Chinese, Korean (the internal segment field `en` = "source text" in any of them). */
const LANG_NAME = { en: 'English', zh: '中文', ko: '한국어' };
const LANG_HTML = { en: 'en', zh: 'zh-Hans', ko: 'ko' };
const LANG_ALL = 'English / 中文 / 한국어';
const srcLangOf = (job) => { const l = job && job.meta && job.meta.src_lang; return LANG_NAME[l] ? l : 'en'; };
const saveSettings = debounce(() => localStorage.setItem('kds_settings', JSON.stringify(state.s)), 200);

/* ============================================================ i18n */
const IS_MAC = /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent || '');       // a Mac types ⌘V, not Ctrl+V
const t = (key, vars) => {
  let s = (I18N[state.lang] && I18N[state.lang][key]) ?? I18N.en[key] ?? key;
  if (vars) for (const k of Object.keys(vars)) s = s.split(`{${k}}`).join(vars[k]);
  return IS_MAC ? s.replace(/Ctrl\+([A-Za-z])/g, '⌘$1') : s;
};
const applyI18n = (root = document) => {
  $$('[data-i18n]', root).forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $$('[data-i18n-ph]', root).forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  document.documentElement.lang = state.lang;
};
const errText = (e) => {
  const code = e && e.code;
  const key = 'err.' + code;
  if (code && I18N[state.lang][key]) return t(key);
  return (e && e.message) || t('err.generic');
};

/* ============================================================ api / toast */
async function api(path, { method = 'GET', body } = {}) {
  const r = await fetch(path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await r.json(); } catch { /* not json */ }
  if (!r.ok) {
    const d = (data && data.detail) || {};
    const err = new Error(typeof d === 'string' ? d : d.message || r.statusText);
    err.code = d.code; err.status = r.status;
    throw err;
  }
  return data;
}
function toast(msg, type = '') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `${type === 'bad' ? icon('alert') : type === 'ok' ? icon('check') : icon('info')}<div>${esc(msg)}</div>`;
  $('#toasts').append(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 350); }, type === 'bad' ? 7000 : 3500);
}
const noticeHtml = (kind, text, details) => `
  <div class="notice ${kind}">${icon(kind === 'bad' || kind === 'warn' ? 'alert' : 'info')}
    <div class="n-body">${esc(text)}${details ? `<details><summary>${esc(t('err.details'))}</summary><pre>${esc(details)}</pre></details>` : ''}</div></div>`;

/* ============================================================ theme / language */
function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  $('#theme-btn').innerHTML = icon(state.theme === 'dark' ? 'sun' : 'moon');
  const tc = document.querySelector('meta[name="theme-color"]');                       // the title bar of the installed app follows the theme
  if (tc) tc.setAttribute('content', state.theme === 'dark' ? '#090d1a' : '#f3f5fc');
}
function setLang(l) {
  state.lang = l;
  localStorage.setItem('kds_lang', l);
  $$('#lang-switch button').forEach((b) => b.classList.toggle('active', b.dataset.lang === l));
  applyI18n();
  applySide(document.documentElement.classList.contains('side-collapsed'), false);
  populateEnVoices();
  renderVoiceCards();
  renderVoxVoices();
  renderVoxBanners();
  renderVox();
  updatePageHeader();
  updateDerived();
  updateCounters();
  if (state.video) renderVideoCard(state.video);
  renderUpload();
  renderWhisperBoxes();
  ['dub', 'tts'].forEach((k) => state.jobs[k] && renderJob(k, true));
  if (state.page === 'history') loadHistory();
  renderSystem();
  if (state.gt) renderGtResult(state.gt);
  updateTermsState();
}
function updatePageHeader() {
  $('#page-title').textContent = t(`page.${state.page}.title`);
  $('#page-sub').textContent = t(`page.${state.page}.sub`);
}

/* ============================================================ bindings */
const fmtOut = (v, fmt) => {
  v = Number(v);
  switch (fmt) {
    case 'pct': return `${v >= 0 ? '+' : ''}${v}%`;
    case 'pct0': return `${v}%`;
    case 'hz': return `${v >= 0 ? '+' : ''}${v} Hz`;
    case 'x': return `×${v.toFixed(2)}`;
    default: return String(v);
  }
};
function syncBindings(root = document) {
  $$('[data-bind]', root).forEach((el) => {
    const v = getPath(state.s, el.dataset.bind);
    if (el.classList.contains('seg')) {
      $$('button', el).forEach((b) => b.classList.toggle('active', b.dataset.value === String(v)));
    } else if (el.type === 'checkbox') {
      el.checked = !!v;
    } else if (el.type === 'range') {
      if (Number(el.value) !== Number(v)) el.value = v;
      const mn = Number(el.min || 0), mx = Number(el.max || 100);
      el.style.setProperty('--p', `${((Number(v) - mn) / (mx - mn)) * 100}%`);
    } else if (document.activeElement !== el) {
      el.value = v ?? '';
    }
  });
  $$('[data-out]', root).forEach((o) => { o.textContent = fmtOut(getPath(state.s, o.dataset.out), o.dataset.fmt); });
}
function updateDerived() {
  const s = state.s;
  const video = s.output.format === 'video';
  $('#orig-vol-row').classList.toggle('hidden', !video);
  $('#video-hint').classList.toggle('hidden', !video);
  $('#vq-row').classList.toggle('hidden', !video);
  $('#frame-row').classList.toggle('hidden', !video);
  $('#hs-row').classList.toggle('hidden', !video);
  updateFrameMocks();
  $('#video-hint').textContent = t(state.sourceTab === 'upload' ? 'out.video.hint.upload' : 'out.video.hint', { h: Number(s.output.max_height) === 720 ? 720 : 1080 });
  const duckRow = $('#duck-row');
  duckRow.classList.toggle('hidden', !video);
  duckRow.classList.toggle('dim', !(Number(s.output.orig_volume) > 0));   // nothing to mute while the original level is 0
  $$('[data-sub="duck"]').forEach((b) => b.setAttribute('aria-pressed', s.output.duck ? 'true' : 'false'));
  const manual = !!s.translate.manual;                                    // copy / paste with Claude (Dubbing Studio only)
  const llmMissing = s.translate.engine === 'llm' && !s.translate.llm.api_key.trim();
  $$('[data-llm-warn]').forEach((el) => el.classList.toggle('hidden', !llmMissing || (manual && !!el.closest('#card-translate'))));
  { const mh = $('#manual-hint'); if (mh) mh.classList.toggle('hidden', !manual); }
  { const eng = $('#card-translate .seg[data-bind="translate.engine"]'); if (eng) eng.classList.toggle('dim', manual); }
  { const gb = $('#btn-generate span'); if (gb) { const k = manual ? 'btn.prepare' : 'btn.generate'; gb.dataset.i18n = k; gb.textContent = t(k); } }
  $$('[data-envoice]').forEach((el) => el.classList.toggle('hidden', s.voice.term_mode !== 'english_voice'));
  const ttsLang = LANG_NAME[s.tts.input_lang] ? s.tts.input_lang : 'km';      // km | en | zh | ko
  $('#tts-engine-box').classList.toggle('hidden', ttsLang === 'km');            // translation engine: only when the text is translated
  $('#tts-text').placeholder = t(ttsLang === 'km' ? 'tts.ph' : `tts.ph.${ttsLang}`);
  $$('.voice-card[data-voice]').forEach((c) => {
    const on = c.dataset.voice === s.voice.id;
    c.classList.toggle('selected', on);
    c.setAttribute('aria-checked', on ? 'true' : 'false');
  });
  // ---- engine: Microsoft Edge voices  vs  local VoxCPM2
  const isVox = s.voice.engine === 'voxcpm';
  const vid = (s.voice.vox && s.voice.vox.id) || '';
  const cloneSel = isVox && (vid === 'vox:original' || vid.startsWith('vox:c:'));
  $$('.engine-edge').forEach((el) => el.classList.toggle('hidden', isVox));
  $$('.engine-vox').forEach((el) => el.classList.toggle('hidden', !isVox));
  $$('[data-edge-only]').forEach((el) => el.classList.toggle('hidden', isVox));
  $$('[data-vox-only]').forEach((el) => el.classList.toggle('hidden', !isVox));
  $$('[data-engine-hint]').forEach((el) => { el.textContent = isVox ? '' : t('voice.engine.hint.edge'); el.classList.toggle('hidden', isVox); });      // VoxCPM2: no text about the computer
  $$('.vox-consent').forEach((el) => el.classList.toggle('hidden', !cloneSel));
  $$('.vox-original-opts').forEach((el) => el.classList.toggle('hidden', !(isVox && vid === 'vox:original')));
  { const qh = voxQualityHint(); $$('.vox-quality-hint').forEach((el) => { el.textContent = qh; }); }
  $$('.voice-card.vox').forEach((c) => {
    const on = c.dataset.voxvoice === vid;
    c.classList.toggle('selected', on);
    c.setAttribute('aria-checked', on ? 'true' : 'false');
  });
  refreshVoiceSelects();
  { // ---- voices by character
    const a = s.voice.auto || {};
    $$('[data-auto-opts]').forEach((el) => el.classList.toggle('hidden', !a.on));
    populateAutoVoices();
    const needConsent = !!a.on && [a.male, a.female].some((x) => x === 'vox:s' || x === 'vox:mine' || String(x || '').startsWith('vox:c:'));
    $$('[data-auto-consent]').forEach((el) => el.classList.toggle('hidden', !needConsent));
    $$('#chars-panel').forEach((el) => el.classList.toggle('off', !a.on));
    paintAutoLabels();
  }
  const preset = $('#llm-preset');
  if (preset && document.activeElement !== preset) preset.value = s.translate.llm.preset || 'custom';
  const gh = $('#llm-gemini-hint');
  if (gh) gh.classList.toggle('hidden', !(s.translate.llm.preset === 'gemini' || /generativelanguage\.googleapis\.com/.test(s.translate.llm.base_url || '')));
}
document.addEventListener('input', (e) => {
  const el = e.target.closest && e.target.closest('[data-bind]');
  if (!el || el.classList.contains('seg')) return;
  let v;
  if (el.type === 'checkbox') v = el.checked;
  else if (el.type === 'range' || el.type === 'number') v = Number(el.value);
  else v = el.value;
  setPath(state.s, el.dataset.bind, v);
  if (el.dataset.bind.startsWith('translate.llm.') && el.dataset.bind !== 'translate.llm.preset') {
    // manual edits switch the preset to "custom" unless they still match it
    const l = state.s.translate.llm;
    const p = PRESETS[l.preset];
    if (!p || p.base_url !== l.base_url || p.model !== l.model) l.preset = 'custom';
  }
  saveSettings();
  syncBindings();
  updateDerived();
});
document.addEventListener('click', (e) => {
  const b = e.target.closest('.seg[data-bind] button');
  if (b) {
    setPath(state.s, b.parentElement.dataset.bind, b.dataset.value);
    saveSettings(); syncBindings(); updateDerived(); updateCounters();
    if (b.parentElement.dataset.bind === 'voice.engine' && b.dataset.value === 'voxcpm') prewarmVox();
    if (b.parentElement.dataset.bind === 'source.lang') { if (state.video) renderVideoCard(state.video); refreshUploadInfo(); }
    return;
  }
  const go = e.target.closest('[data-goto]');
  if (go) { e.preventDefault(); showPage(go.dataset.goto); return; }
  const act = e.target.closest('[data-action]');
  if (act && act.dataset.action === 'reset-voice') {
    Object.assign(state.s.voice, { rate: 0, pitch: 0, volume: 0 });
    saveSettings(); syncBindings();
  }
});

/* ============================================================ voices */
const avatarSvg = () => icon('user');
function voiceCardHtml(v) {
  const female = v.gender === 'Female';
  return `
  <div class="voice-card" role="radio" tabindex="0" data-voice="${esc(v.id)}" aria-checked="false">
    <span class="tick">${icon('check')}</span>
    <div class="avatar ${female ? 'f' : 'm'}">${avatarSvg()}</div>
    <div>
      <div class="voice-name">${esc(v.name)}<span class="native">${esc(v.native)}</span></div>
      <div class="voice-sub"><span class="chip">${t(female ? 'voice.female' : 'voice.male')}</span><span class="chip">km-KH · Neural</span><span class="chip accent">Microsoft Edge</span></div>
    </div>
    <button class="play-btn" type="button" data-preview="${esc(v.id)}" aria-label="${esc(t('voice.preview'))}" title="${esc(t('voice.preview'))}">${icon('play')}</button>
  </div>`;
}
function renderVoiceCards() {
  $$('.engine-edge .voice-picker').forEach((el) => { el.innerHTML = state.voices.khmer.map(voiceCardHtml).join(''); });
  updateDerived();
}
function populateEnVoices() {
  $$('[data-envoice-select]').forEach((sel) => {
    const cur = state.s.voice.en_voice || '';
    const group = (g, label) => `<optgroup label="${label}">${state.voices.english.filter((v) => v.gender === g).map((v) => `<option value="${esc(v.id)}">${esc(v.name)} (${esc(v.id.replace('Neural', ''))})</option>`).join('')}</optgroup>`;
    sel.innerHTML = `<option value="">${esc(t('tr.envoice.auto'))}</option>${group('Female', t('voice.female'))}${group('Male', t('voice.male'))}`;
    sel.value = cur;
  });
}
document.addEventListener('click', (e) => {
  const pb = e.target.closest('[data-preview]');
  if (pb) { e.stopPropagation(); previewVoice(pb.dataset.preview, pb); return; }
  const card = e.target.closest('.voice-card');
  if (card && card.dataset.voice) {
    state.s.voice.id = card.dataset.voice;
    saveSettings(); updateDerived();
  }
});
document.addEventListener('keydown', (e) => {
  const card = e.target.closest && e.target.closest('.voice-card');
  if (card && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); card.click(); }
});
let previewAudio = null, previewBtn = null;
function stopPreview() {
  if (previewAudio) { previewAudio.pause(); previewAudio = null; }
  if (previewBtn) { previewBtn.classList.remove('playing'); previewBtn.innerHTML = icon(previewBtn.dataset.ico || 'play'); previewBtn = null; }
}
async function previewVoice(voiceId, btn) {
  const wasThis = previewBtn === btn;
  stopPreview();
  if (wasThis) return;
  const v = state.s.voice;
  const q = new URLSearchParams({ voice: voiceId, rate: v.rate, pitch: v.pitch, volume: v.volume, term_mode: v.term_mode, en_voice: v.en_voice || '' });
  btn.innerHTML = icon('spinner', 'spin');
  previewBtn = btn;
  const a = new Audio(`/api/voices/preview?${q}`);
  previewAudio = a;
  a.addEventListener('ended', stopPreview);
  a.addEventListener('error', () => { if (previewAudio === a) { stopPreview(); toast(t('err.TTS_FAILED'), 'bad'); } });
  try {
    await a.play();
    if (previewAudio === a) { btn.classList.add('playing'); btn.innerHTML = icon('pause'); }
  } catch (err) {
    if (previewAudio === a) { stopPreview(); toast(t('err.TTS_FAILED'), 'bad'); }
  }
}

/* ============================================================ voices by character (the same rules as app/autovoice.py) */
const AUTO_EDGE = { male: 'km-KH-PisethNeural', female: 'km-KH-SreymomNeural' };
const AUTO_DESIGNED = {
  male: { 1: ['m_deep'], 2: ['m_deep', 'm_young'], 3: ['m_deep', 'm_anchor', 'm_young'], 4: ['m_deep', 'm_elder', 'm_anchor', 'm_young'] },
  female: { 1: ['f_warm'], 2: ['f_warm', 'f_bright'], 3: ['f_calm', 'f_warm', 'f_bright'], 4: ['f_calm', 'f_warm', 'f_pro', 'f_bright'] },
};
const designedFor = (g, n) => { const sets = AUTO_DESIGNED[g]; return (sets[n] || Array.from({ length: n }, (_, i) => sets[4][i % 4])).map((k) => `vox:p:${k}`); };
/* Characters of one gender (lowest pitch first) whose pitch is within 3 semitones share one "voice": telling such people apart from the sound is a guess. */
function voiceGroups(mine) {
  const out = [];
  let ref = null;
  for (const c of mine) {
    const f = Number(c.f0) || 0;
    if (ref === null || (f > 0 && ref > 0 && Math.log2(f / ref) > 0.25)) { out.push(out.length ? out[out.length - 1] + 1 : 0); ref = f; } else out.push(out[out.length - 1]);
  }
  return out;
}
/* character id -> the voice its lines are spoken with ('' = the voice of the job).  chars: [{id, gender, f0, voice, ref}] (voice '' = automatic, 'vox:s' = its own voice
   from the video; ref = it has a clear line to copy).  VoxCPM2: "Speaker in the video" -> every character cloned from its own lines; a designed / saved voice -> the
   characters it fits keep it, the other gender gets a designed voice. */
function autoPlan(chars) {
  const v = state.s.voice, a = v.auto || {}, engine = v.engine === 'voxcpm' ? 'voxcpm' : 'edge', out = {};
  const jobVoice = engine === 'voxcpm' ? ((v.vox || {}).id || '') : '';
  let jobGender = '';
  if (jobVoice.startsWith('vox:p:')) { const pr = ((state.voices.vox || {}).presets || []).find((x) => x.id === jobVoice); jobGender = pr ? (pr.gender === 'Female' ? 'female' : 'male') : ''; }
  else if (jobVoice.startsWith('vox:c:')) { const cv = voxAll().find((x) => x.id === jobVoice); jobGender = cv && cv.gender === 'Female' ? 'female' : cv && cv.gender === 'Male' ? 'male' : ''; }
  for (const g of ['male', 'female']) {
    const mine = chars.filter((c) => c.gender === g).sort((p, q) => ((p.f0 || 0) - (q.f0 || 0)) || (p.id - q.id));
    if (!mine.length) continue;
    const pref = (g === 'male' ? a.male : a.female) || '';
    const pool = voxAll().filter((x) => x.gender === (g === 'male' ? 'Male' : 'Female')).map((x) => x.id);
    const grp = voiceGroups(mine), nv = grp[grp.length - 1] + 1;
    let fallback;                                                   // one voice per "voice group"; null = every character is cloned from its own lines
    if (engine !== 'voxcpm') fallback = Array.from({ length: nv }, () => AUTO_EDGE[g]);
    else if (jobVoice === 'vox:original') fallback = null;
    else if (jobVoice && jobVoice !== 'vox:default' && (jobGender === '' || jobGender === g)) fallback = Array.from({ length: nv }, () => jobVoice);
    else fallback = designedFor(g, nv);
    mine.forEach((c, k) => {
      const own = c.voice || '', canClone = !!c.ref, fb = fallback ? fallback[grp[k]] : '';
      let vv;
      if (own === 'vox:s' || (!own && pref === 'vox:s')) vv = canClone ? `vox:s:${c.id}` : fb;
      else if (own) vv = own;
      else if (pref === 'vox:mine') vv = pool.length ? pool[grp[k] % pool.length] : (fallback ? fb : (canClone ? `vox:s:${c.id}` : ''));
      else if (pref) vv = pref;
      else if (fallback === null) vv = canClone ? `vox:s:${c.id}` : '';
      else vv = fb;
      out[c.id] = vv;
    });
  }
  return out;
}
/* the two pickers of the settings block (rebuilt only when what they list has changed) */
let autoSig = '';
function populateAutoVoices() {
  const sels = $$('[data-auto-select]');
  if (!sels.length) return;
  const a = state.s.voice.auto || {}, vx = !!(state.vox && state.vox.installed), pres = (state.voices.vox || {}).presets || [], cust = voxAll();
  const sig = [state.lang, vx ? 1 : 0, state.s.voice.engine, (state.s.voice.vox || {}).id, pres.map((x) => x.id).join(), cust.map((x) => `${x.id}:${x.gender}:${x.name}`).join(), (state.voices.khmer || []).length, a.male, a.female].join('|');
  if (sig === autoSig) return;
  autoSig = sig;
  sels.forEach((sel) => {
    const g = sel.dataset.autoSelect, G = g === 'male' ? 'Male' : 'Female', cur = (g === 'male' ? a.male : a.female) || '';
    const have = new Set(['']);
    const opt = (v, label) => { have.add(v); return `<option value="${esc(v)}">${esc(label)}</option>`; };
    const edge = (state.voices.khmer || []).filter((v) => v.gender === G);
    const auto = state.s.voice.engine !== 'voxcpm' ? t('auto.pick.auto', { name: voiceName(AUTO_EDGE[g]) }) : t(((state.s.voice.vox || {}).id === 'vox:original') ? 'auto.pick.auto.vox.clone' : 'auto.pick.auto.vox');
    let h = `<option value="">${esc(auto)}</option>`;
    h += `<optgroup label="${esc(t('seg.voice.group.edge'))}">${edge.map((v) => opt(v.id, `${v.name} (${v.native})`)).join('')}</optgroup>`;
    if (vx) {
      const dp = pres.filter((x) => x.gender === G);
      if (dp.length) h += `<optgroup label="${esc(t('vox.group.designed'))}">${dp.map((x) => opt(x.id, voiceName(x.id))).join('')}</optgroup>`;
      const mine = cust.filter((x) => !x.gender || x.gender === G);
      h += `<optgroup label="${esc(t('seg.voice.group.clone'))}">${opt('vox:mine', t('auto.pick.mine'))}${opt('vox:s', t('auto.pick.clone'))}${mine.map((x) => opt(x.id, x.name)).join('')}</optgroup>`;
    } else {
      h += `<optgroup label="VoxCPM2"><option value="__none" disabled>${esc(t('seg.voice.needvox'))}</option></optgroup>`;
    }
    if (cur && !have.has(cur)) h += `<option value="${esc(cur)}">${esc(t('seg.voice.missing', { name: voiceName(cur) }))}</option>`;
    sel.innerHTML = h;
    sel.value = cur;
  });
}
/* "Automatic - Piseth" ...: what the first choice of every voice picker of a finished job really means right now.
   The page is the source of truth: the characters panel (gender / voice as they are on the screen), the badge of every line. */
function paintAutoLabels() {
  const lines = $$('#dub-result .seg-row');
  if (!lines.length) return;
  const on = !!(state.s.voice.auto || {}).on, panel = $('#chars-panel');
  const chars = panel ? $$('.char-row', panel).map((r) => ({ id: Number(r.dataset.char), gender: r.dataset.gender, f0: Number(r.dataset.f0) || 0, ref: r.dataset.ref === '1', voice: $('.char-voice', r).value })) : [];
  const plan = on ? autoPlan(chars) : {};
  const byId = new Map(chars.map((c) => [c.id, c]));
  const same = t('seg.voice.same', { name: globalVoiceName() });
  if (panel) $$('.char-row', panel).forEach((r) => {
    const o = $('.char-voice option[value=""]', r), id = Number(r.dataset.char);
    if (o) o.textContent = on && plan[id] ? t('chars.voice.auto', { name: voiceName(plan[id]) }) : same;
    const b = $('.cb', r);
    if (b) { b.className = `cb ${r.dataset.gender === 'female' ? 'f' : 'm'}${b.dataset.unsure ? ' unsure' : ''}`; b.textContent = `${r.dataset.gender === 'female' ? '♀' : '♂'}${id}`; }
    const fl = $('[data-flip]', r);
    if (fl) { const to = genderName(r.dataset.gender === 'female' ? 'male' : 'female'); fl.title = t('chars.flip', { g: to }); fl.setAttribute('aria-label', t('chars.flip', { g: to })); }
  });
  lines.forEach((r) => {
    const cid = Number(r.dataset.char), o = $('.vsel option[value=""]', r), c = byId.get(cid);
    if (o) o.textContent = on && plan[cid] ? t('seg.voice.auto', { name: voiceName(plan[cid]) }) : same;
    const b = $('.cb', r);
    if (b && c) {
      b.className = `cb ${c.gender === 'female' ? 'f' : 'm'}${b.dataset.unsure ? ' unsure' : ''}`;
      b.textContent = `${c.gender === 'female' ? '♀' : '♂'}${cid}`;
      b.title = t(b.dataset.unsure ? 'chars.badge.unsure' : 'chars.badge', { n: cid, g: genderName(c.gender) });
    }
  });
  const bo = $('#bulk-voice option[value=""]');
  if (bo) bo.textContent = on && chars.length ? t('seg.voice.follow') : same;
}

/* ============================================================ navigation */
function showPage(p) {
  if (!$(`#page-${p}`)) p = 'dub';
  state.page = p;
  if (location.hash !== `#${p}`) history.replaceState(null, '', `#${p}`);
  $$('.page').forEach((s) => s.classList.toggle('active', s.id === `page-${p}`));
  $$('#nav button').forEach((b) => b.classList.toggle('active', b.dataset.page === p));
  updatePageHeader();
  updateDock();
  if (p === 'history') loadHistory();
  if (p === 'terms') loadTerms();
  if (p === 'settings') { loadSystem(); loadVox(); loadWhisper(); }
  window.scrollTo({ top: 0 });
}

/* ============================================================ source / video */
const YT_RE = /(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/i;
const looksLikeYouTube = (u) => YT_RE.test(u) && /[A-Za-z0-9_-]{11}/.test(u);
const ytOpts = () => ({ cookies_browser: state.s.youtube.cookies_browser, proxy: state.s.youtube.proxy });

function setSourceTab(tab) {
  state.sourceTab = tab;
  $$('#src-tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  $('#src-youtube').classList.toggle('hidden', tab !== 'youtube');
  $('#src-upload').classList.toggle('hidden', tab !== 'upload');
  $('#src-transcript').classList.toggle('hidden', tab !== 'transcript');
  updateDerived();                                                       // the MP4 hint differs: downloaded from YouTube / taken from your file
}
function renderVideoCard(info) {
  try { renderVideoCardInner(info); } finally { updateFrameMocks(); }   // ... and the picture of the YouTube video
}
function renderVideoCardInner(info) {
  const box = $('#video-box');
  const caps = info.captions;
  const sel = (state.s.source && state.s.source.lang) || 'auto';
  let capChip, none = false;
  if (!caps) capChip = `<span class="chip warn">${icon('alert')}${t('video.cap.unknown')}</span>`;
  else {
    // the language that WILL be used: the one chosen in step 1, or (Auto) the one detected from the caption tracks
    const langs = caps.langs || { en: caps.english || null, zh: null, ko: null };
    const use = sel === 'auto' ? caps.detected : sel;
    const kind = use ? langs[use] : null;
    if (use && kind) capChip = `<span class="chip ok">${icon('check')}${t(kind === 'manual' ? 'video.cap.manual' : 'video.cap.auto', { lang: LANG_NAME[use] })}</span>`;
    else { none = true; capChip = `<span class="chip bad">${icon('x')}${t('video.cap.none', { lang: use ? LANG_NAME[use] : LANG_ALL })}</span>`; }
  }
  const langs = caps && none && caps.languages && caps.languages.length ? `<div class="hint" style="margin:0">${esc(t('video.langs'))}${esc(caps.languages.join(', '))}</div>` : '';
  const blocked = info.blocked || (!caps && (info.notes || []).some((n) => /sign in|bot|block|429/i.test(n)));
  box.innerHTML = `
    <div class="video-card">
      <div class="thumb"><img src="${esc(info.thumbnail)}" alt="" referrerpolicy="no-referrer" onerror="this.style.display='none'">${info.duration ? `<span class="dur">${fmtTime(info.duration)}</span>` : ''}</div>
      <div class="meta">
        <div class="vt">${esc(info.title || info.id)}</div>
        <div class="vc">${esc(info.channel || '')}</div>
        <div class="chips">${capChip}<span class="chip">${icon('youtube')}${esc(info.id)}</span></div>
        ${langs}
      </div>
    </div>
    ${blocked ? `<div style="margin-top:12px">${noticeHtml('warn', t('video.blocked'))}</div>` : ''}`;
}
async function checkVideo() {
  const url = $('#yt-url').value.trim();
  if (!url) { toast(t('gen.need_url'), 'bad'); return; }
  const box = $('#video-box');
  box.innerHTML = `<div class="video-card"><div class="thumb skeleton"></div><div class="meta"><div class="skeleton" style="height:22px;width:80%"></div><div class="skeleton" style="height:16px;width:40%"></div><div class="muted small">${esc(t('video.checking'))}</div></div></div>`;
  const btn = $('#btn-check');
  btn.disabled = true;
  try {
    const info = await api('/api/video/info', { method: 'POST', body: { url, youtube: ytOpts() } });
    state.video = info; state.videoUrl = url;
    renderVideoCard(info);
  } catch (e) {
    state.video = null;
    box.innerHTML = `<div style="margin-top:14px">${noticeHtml(e.code === 'YT_BLOCKED' ? 'warn' : 'bad', errText(e), e.message)}</div>`;
  } finally { btn.disabled = false; }
}
const autoCheck = debounce(() => {
  const v = $('#yt-url').value.trim();
  if (looksLikeYouTube(v) && v !== state.videoUrl) checkVideo();
  else if (!v) { $('#video-box').innerHTML = ''; state.video = null; state.videoUrl = ''; }
}, 650);

async function pasteInto(input, after) {
  try {
    const txt = await navigator.clipboard.readText();
    if (txt) { input.value = txt.trim(); input.dispatchEvent(new Event('input', { bubbles: true })); if (after) after(); }
  } catch { toast(t('toast.paste_failed'), 'bad'); input.focus(); }
}

/* ============================================================ upload a video from the computer (v1.8) */
const UP_EXT = /\.(mp4|m4v|mov|mkv|webm|avi|flv|wmv|ts|mts|m2ts|mpg|mpeg|3gp|ogv|mp3|wav|m4a|aac|ogg|opus|flac|wma|aiff|aif)$/i;
const fmtBytes = (n) => {
  n = Number(n) || 0;
  if (n >= 1073741824) return `${(n / 1073741824).toFixed(2)} GB`;
  if (n >= 1048576) return `${(n / 1048576).toFixed(n >= 104857600 ? 0 : 1)} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
};
const upIdle = () => ({ status: 'idle', name: '', size: 0, loaded: 0, t0: 0, xhr: null, info: null, error: null, subs: 'auto', paintAt: 0 });
state.upload = upIdle();                                     // the file chosen in the "Upload Video" tab
state.whisper = { installed: false, state: 'idle', error: '', log: [], elapsed: 0, disabled: false };
const whisperModelFor = (lang, m) => ((lang === 'zh' || lang === 'ko') && (m === 'tiny' || m === 'base') ? 'small' : (m || 'base'));

/* Where the subtitles will come from - the same order the server uses: the text you gave > a track inside the file > Whisper. */
function upPlan() {
  const u = state.upload, i = u.info;
  if (!i) return { kind: 'none' };
  if (($('#up-text') || {}).value && $('#up-text').value.trim()) return { kind: 'text' };
  if (u.subs !== 'whisper' && i.pick != null) return { kind: 'embedded', label: i.pick_label || '' };
  if (!i.has_audio) return { kind: 'noaudio' };
  return { kind: (i.whisper || state.whisper.installed) ? 'whisper' : 'nowhisper' };
}
function whisperBoxHtml(all) {
  const w = state.whisper;
  const open = !!document.querySelector('.whisper-note details[open]');
  const log = (w.log || []).slice(-14).join('\n');
  const det = (txt) => (txt ? `<details${open ? ' open' : ''}><summary>${esc(t('whisper.log'))}</summary><pre>${esc(txt)}</pre></details>` : '');
  if (w.state === 'installing') return `<div class="notice info whisper-note">${icon('spinner', 'spin')}<div class="n-body"><b>${esc(t('whisper.installing', { s: Math.round(w.elapsed || 0) }))}</b>${det(log)}</div></div>`;
  if (w.installed) return all && w.state === 'done' ? `<div class="notice info whisper-note">${icon('check')}<div class="n-body"><b>${esc(t('whisper.done'))}</b></div></div>` : '';
  const failed = w.state === 'error';
  const cmd = `<span class="wn-cmd">${esc(t('whisper.manual'))}</span>`;
  const act = w.disabled ? `<span class="wn-cmd">${esc(t('whisper.disabled'))}</span>`
    : `<button class="btn btn-sm btn-primary" type="button" data-whisper="install">${icon('download')}<span>${esc(t(failed ? 'whisper.retry' : 'whisper.install'))}</span></button>${cmd}`;
  return `<div class="notice ${failed ? 'bad' : 'warn'} whisper-note">${icon('alert')}<div class="n-body"><b>${esc(t(failed ? 'whisper.failed' : 'whisper.title'))}</b>`
    + `${failed ? '' : `<br>${esc(t('whisper.desc'))}`}${failed ? det(`${w.error || ''}\n${log}`.trim()) : ''}<div class="wn-act">${act}</div></div></div>`;
}
function renderWhisperBoxes() {
  $$('[data-whisper-box]').forEach((el) => { el.innerHTML = whisperBoxHtml(true); });
  if (state.upload.status === 'ready') renderUpload();
}
async function loadWhisper() {
  try { Object.assign(state.whisper, await api('/api/whisper/status')); } catch { /* offline */ }
  renderWhisperBoxes();
  return state.whisper;
}
let whisperTimer = null;
async function pollWhisper() {
  clearTimeout(whisperTimer);
  const w = await loadWhisper();
  if (w.state === 'installing') { whisperTimer = setTimeout(pollWhisper, 1500); return; }
  if (w.installed) { toast(t('whisper.done'), 'ok'); if (state.system) state.system.whisper = true; renderSystem(); await refreshUploadInfo(); }
  else if (w.state === 'error') toast(t('whisper.failed'), 'bad');
}
async function installWhisper() {
  try {
    const r = await api('/api/whisper/install', { method: 'POST' });
    if (r.installed) { await loadWhisper(); await refreshUploadInfo(); return; }
  } catch (e) {
    toast(errText(e), 'bad');
    if (e.code === 'WHISPER_INSTALL_DISABLED') { state.whisper.disabled = true; renderWhisperBoxes(); }
    return;
  }
  state.whisper.state = 'installing'; state.whisper.elapsed = 0; state.whisper.log = [];
  renderWhisperBoxes();
  pollWhisper();
}

function upProgressText(u) {
  if (u.loaded >= u.size && u.size) return t('up.checking');
  const dt = (performance.now() - u.t0) / 1000, rate = dt > 0.3 ? u.loaded / dt : 0;
  return t('up.progress', { done: fmtBytes(u.loaded), total: fmtBytes(u.size), speed: fmtBytes(rate), eta: rate > 0 ? fmtTime((u.size - u.loaded) / rate) : '…' });
}
function renderUpload() {
  try { renderUploadCard(); } finally { updateFrameMocks(); }          // the little phone in Step 4 shows the picture of the file
}
function renderUploadCard() {
  const box = $('#up-box');
  if (!box) return;
  const u = state.upload;
  const drop = $('#up-drop');
  drop.classList.toggle('compact', u.status !== 'idle');
  { const lab = $('b', drop); if (lab) lab.textContent = t(u.status === 'idle' ? 'up.drop' : 'up.drop.more'); }
  if (u.status === 'idle') { box.innerHTML = ''; return; }
  if (u.status === 'uploading') {
    const pct = u.size ? Math.min(100, Math.round((u.loaded / u.size) * 100)) : 0;
    box.innerHTML = `<div class="video-card up-card is-busy"><div class="thumb up-thumb">${icon('upload')}<span class="dur" data-up-pct>${pct}%</span></div>`
      + `<div class="meta"><div class="vt">${esc(u.name)}</div><div class="bar"><i data-up-bar style="width:${pct}%"></i></div><div class="vc" data-up-text>${esc(upProgressText(u))}</div>`
      + `<div class="chips"><button class="btn btn-sm" type="button" data-up="cancel">${icon('x')}<span>${esc(t('up.cancel'))}</span></button></div></div></div>`;
    return;
  }
  if (u.status === 'error') {
    box.innerHTML = `<div style="margin-top:14px">${noticeHtml('bad', errText(u.error), u.error && u.error.message)}</div>`;
    return;
  }
  const i = u.info, plan = upPlan();
  const dims = i.has_video && i.width && i.height ? `${i.width}×${i.height}` : '';
  const thumb = i.thumbnail ? `<img src="${esc(i.thumbnail)}" alt="" onerror="this.style.display='none'">` : icon(i.has_video ? 'video' : 'mic');
  const chipOf = { text: ['ok', 'check', t('up.plan.text')], embedded: ['ok', 'check', t('up.plan.embedded', { lang: plan.label })],
    whisper: ['accent', 'wand', t('up.plan.whisper', { model: whisperModelFor(state.s.source.lang, state.s.youtube.whisper_model) })],
    nowhisper: ['bad', 'alert', t('up.plan.nowhisper')], noaudio: ['bad', 'alert', t('up.plan.noaudio')] }[plan.kind];
  const planChip = chipOf ? `<span class="chip ${chipOf[0]}" data-up-plan="${plan.kind}">${icon(chipOf[1])}${esc(chipOf[2])}</span>` : '';
  const choose = i.pick != null && (i.whisper || state.whisper.installed) && plan.kind !== 'text'
    ? `<div class="up-switch"><span class="label">${esc(t('up.subs.source'))}</span><div class="seg" data-upsubs>`
      + `<button type="button" data-value="auto" class="${u.subs !== 'whisper' ? 'active' : ''}">${esc(t('up.subs.src.auto'))}</button>`
      + `<button type="button" data-value="whisper" class="${u.subs === 'whisper' ? 'active' : ''}">${esc(t('up.subs.src.whisper'))}</button></div></div>` : '';
  box.innerHTML = `<div class="video-card up-card is-ready"><div class="thumb">${thumb}${i.duration ? `<span class="dur">${fmtTime(i.duration)}</span>` : ''}</div>`
    + `<div class="meta"><div class="vt">${esc(i.name)}</div><div class="vc">${esc([i.duration ? fmtTime(i.duration) : '', dims, fmtBytes(i.size)].filter(Boolean).join(' · '))}</div>`
    + `<div class="chips">${planChip}${i.has_video ? '' : `<span class="chip">${icon('mic')}${esc(t('up.meta.audio'))}</span>`}${i.has_audio ? '' : `<span class="chip warn">${icon('alert')}${esc(t('up.meta.noaudio'))}</span>`}</div>`
    + `${choose}<div class="chips"><button class="btn btn-sm btn-ghost" type="button" data-up="remove">${icon('trash')}<span>${esc(t('up.remove'))}</span></button></div></div></div>`
    + (plan.kind === 'nowhisper' ? whisperBoxHtml(false) : '');
}
function paintUploadProgress() {
  const u = state.upload, box = $('#up-box');
  if (!box || u.status !== 'uploading') return;
  const pct = u.size ? Math.min(100, Math.round((u.loaded / u.size) * 100)) : 0;
  const bar = $('[data-up-bar]', box), pc = $('[data-up-pct]', box), tx = $('[data-up-text]', box);
  if (bar) bar.style.width = `${pct}%`;
  if (pc) pc.textContent = `${pct}%`;
  if (tx) tx.textContent = upProgressText(u);
}
function resetUpload(deleteRemote = true) {
  const u = state.upload;
  if (u.xhr) { try { u.xhr.abort(); } catch { /* already finished */ } }
  if (deleteRemote && u.info && u.info.id) fetch(`/api/uploads/${u.info.id}`, { method: 'DELETE' }).catch(() => {});
  state.upload = upIdle();
  renderUpload();
}
function startUpload(file) {
  if (!file) return;
  if (!UP_EXT.test(file.name)) { toast(t('up.badtype'), 'bad'); return; }
  resetUpload(true);                                         // a new file replaces the old one
  const u = state.upload = { ...upIdle(), status: 'uploading', name: file.name, size: file.size, t0: performance.now() };
  const xhr = new XMLHttpRequest();
  u.xhr = xhr;
  xhr.open('POST', `/api/uploads?name=${encodeURIComponent(file.name)}`);
  xhr.setRequestHeader('Content-Type', 'application/octet-stream');
  xhr.upload.onprogress = (e) => {
    u.loaded = e.loaded;
    if (e.loaded >= file.size || performance.now() - u.paintAt > 200) { u.paintAt = performance.now(); paintUploadProgress(); }
  };
  xhr.onload = () => {
    if (state.upload !== u) return;
    let data = null;
    try { data = JSON.parse(xhr.responseText); } catch { /* not json */ }
    u.xhr = null;
    if (xhr.status >= 200 && xhr.status < 300 && data && data.id) { u.status = 'ready'; u.info = data; refreshUploadInfo(); }
    else {
      const d = (data && data.detail) || {};
      u.status = 'error'; u.error = { code: d.code, message: d.message || xhr.statusText || 'Upload failed' };
    }
    renderUpload();
  };
  xhr.onerror = () => { if (state.upload !== u) return; u.xhr = null; u.status = 'error'; u.error = { code: 'UPLOAD_NETWORK', message: t('up.neterr') }; renderUpload(); };
  renderUpload();
  xhr.send(file);
}
/* Which subtitle track would be used depends on the language chosen in step 1, so the server is asked again when it changes. */
async function refreshUploadInfo() {
  const u = state.upload;
  if (u.status !== 'ready' || !u.info) return;
  try {
    const info = await api(`/api/uploads/${u.info.id}?lang=${encodeURIComponent(state.s.source.lang || 'auto')}`);
    if (state.upload === u) { u.info = info; renderUpload(); }
  } catch (e) { if (state.upload === u && e.code === 'UPLOAD_GONE') resetUpload(false); }
}
const filesIn = (e) => !!(e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files'));
function wireUpload() {
  const drop = $('#up-drop');
  ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { if (filesIn(e)) { e.preventDefault(); drop.classList.add('drag'); } }));
  ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('drag')));
  drop.addEventListener('drop', (e) => { e.preventDefault(); const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]; if (f) startUpload(f); });
  drop.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#up-file').click(); } });
  $('#up-file').addEventListener('change', (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) startUpload(f); });
  // a video dropped anywhere on the Dubbing Studio opens the Upload tab (the browser must not open - and leave the dashboard for - the file)
  window.addEventListener('dragover', (e) => { if (filesIn(e)) e.preventDefault(); });
  window.addEventListener('drop', (e) => {
    if (!filesIn(e)) return;
    e.preventDefault();
    if (e.target.closest && e.target.closest('#up-drop, .engine-vox')) return;
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f && UP_EXT.test(f.name) && state.page === 'dub') { setSourceTab('upload'); startUpload(f); }
  });
  $('#up-box').addEventListener('click', (e) => {
    const b = e.target.closest('[data-up]');
    if (b) { resetUpload(true); return; }                                  // cancel the upload / remove the file
    const sb = e.target.closest('[data-upsubs] button');
    if (sb) { state.upload.subs = sb.dataset.value; renderUpload(); }
  });
  const repaint = debounce(() => { updateCounters(); if (state.upload.status === 'ready') renderUpload(); }, 150);
  $('#up-text').addEventListener('input', repaint);
  $('#up-subfile').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    $('#up-text').value = await f.text(); $('#up-subs').open = true;
    e.target.value = ''; repaint();
  });
  $('#up-subclear').addEventListener('click', () => { $('#up-text').value = ''; repaint(); });
  document.addEventListener('click', (e) => { if (e.target.closest('[data-whisper="install"]')) installWhisper(); });
}

/* ============================================================ request builders */
const parseTime = (v) => {
  if (v === null || v === undefined || String(v).trim() === '') return null;
  const x = String(v).trim();
  if (/^\d+(\.\d+)?$/.test(x)) return Number(x);
  const m = x.match(/^(?:(\d+):)?(\d{1,2}):(\d{1,2})$/);
  return m ? Number(m[1] || 0) * 3600 + Number(m[2]) * 60 + Number(m[3]) : null;
};
const voiceBody = () => {
  const v = state.s.voice, x = v.vox || {};
  return {
    id: v.id, rate: v.rate, pitch: v.pitch, volume: v.volume, term_mode: v.term_mode, en_voice: v.en_voice,
    engine: v.engine === 'voxcpm' ? 'voxcpm' : 'edge',
    vox: { id: x.id, quality: x.quality, consent: !!x.consent, ref_start: parseTime(x.ref_start) },
    auto: { on: !!(v.auto || {}).on, male: (v.auto || {}).male || '', female: (v.auto || {}).female || '' },
  };
};
function voxPreflight(kind) {
  const v = state.s.voice, a = v.auto || {};
  if (kind === 'dub' && a.on) {                                   // the by-character pickers may name a VoxCPM2 voice, whatever the engine of the job is
    const picks = [a.male, a.female].filter((x) => x && x.startsWith('vox:'));
    if (picks.length) {
      if (state.vox && !state.vox.installed) { toast(t('err.VOX_NOT_INSTALLED'), 'bad'); showPage('settings'); return false; }
      if (picks.includes('vox:s') && !['youtube', 'upload'].includes(state.sourceTab)) { toast(t('err.VOX_NO_ORIGINAL'), 'bad'); return false; }
      if (picks.some((x) => x === 'vox:s' || x === 'vox:mine' || x.startsWith('vox:c:')) && !v.vox.consent) { toast(t('err.VOX_CONSENT_REQUIRED'), 'bad'); return false; }
    }
  }
  if (v.engine !== 'voxcpm') return true;
  if (state.vox && !state.vox.installed) { toast(t('err.VOX_NOT_INSTALLED'), 'bad'); showPage('settings'); return false; }
  const id = (v.vox && v.vox.id) || '';
  const clone = id === 'vox:original' || id.startsWith('vox:c:');
  // which voices can be used here at all (first), then the consent tick
  if (kind === 'tts' && id === 'vox:original') { toast(t('err.VOX_NEED_VOICE'), 'bad'); return false; }   // no video here -> designed voices and My voices only
  if (id === 'vox:original' && (kind !== 'dub' || !['youtube', 'upload'].includes(state.sourceTab))) { toast(t('err.VOX_NO_ORIGINAL'), 'bad'); return false; }
  if (clone && !v.vox.consent) {
    toast(t('err.VOX_CONSENT_REQUIRED'), 'bad');
    const box = $$('.vox-consent input').find((el) => el.offsetParent !== null);
    if (box) box.focus();
    return false;
  }
  return true;
}
const translateBody = (dub = false) => ({
  engine: dub && state.s.translate.manual ? 'manual' : state.s.translate.engine,      // 'manual' = copy / paste with Claude: the job stops after the subtitles are ready
  keep_terms: state.s.translate.keep_terms,
  auto_detect: state.s.translate.auto_detect,
  llm: { base_url: state.s.translate.llm.base_url, api_key: state.s.translate.llm.api_key, model: state.s.translate.llm.model },
});
const outputBody = () => ({
  sync: state.s.output.sync,
  video: state.s.output.format === 'video',
  orig_volume: state.s.output.orig_volume,
  duck: !!state.s.output.duck,
  max_speedup: state.s.output.max_speedup,
  max_height: Number(state.s.output.max_height) === 720 ? 720 : 1080,      // tallest picture of the MP4 export
  aspect: state.s.output.aspect === '9:16' ? '9:16' : 'original',          // TikTok / Reels / Shorts: a vertical frame
  fit: FRAME_FITS.includes(state.s.output.fit) ? state.s.output.fit : 'blur',
  crop_x: Math.max(0, Math.min(100, Number(state.s.output.crop_x) || 0)),
  ...hsClean(state.s.output),                                                // hide the subtitles that are burned into the original picture
});
const youtubeBody = () => ({ ...state.s.youtube });

function checkLlm(dub = false) {
  if (dub && state.s.translate.manual) return true;                   // no translation engine is used
  if (state.s.translate.engine === 'llm' && !state.s.translate.llm.api_key.trim()) {
    toast(t('tr.llm.missing'), 'bad');
    return false;
  }
  return true;
}

/* ============================================================ vertical video for TikTok / Reels / Shorts (v1.9) */
const FRAME_FITS = ['blur', 'crop', 'bars'];
const frameDims = (h) => { const w = Number(h) === 720 ? 720 : 1080; return { w, h: Math.round((w * 16) / 9 / 2) * 2 }; };      // 1080 -> 1080x1920, 720 -> 720x1280
const FRAME_SAMPLE = `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6d5dfc"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs><rect width="320" height="180" fill="url(#g)"/><circle cx="160" cy="90" r="30" fill="rgba(255,255,255,.88)"/><path d="M151 74l26 16-26 16z" fill="#4338ca"/></svg>')}`;
/* The picture the little phone shows: the video of the job, or the one being prepared (YouTube link / uploaded file); a sample when there is none. */
function frameThumbUrl(job) {
  let u = '';
  if (job) u = (job.video && job.video.thumbnail) || '';
  else if (state.sourceTab === 'youtube') u = (state.video && state.videoUrl === ($('#yt-url').value || '').trim() && state.video.thumbnail) || '';
  else if (state.sourceTab === 'upload') u = (state.upload && state.upload.info && state.upload.info.thumbnail) || '';
  return u ? u.replace('hqdefault', 'mqdefault') : FRAME_SAMPLE;
}
/* the same controls are used in Step 4 and in the result card: both change state.s.output.aspect / fit / crop_x / max_height */
const frameControlsHtml = (where) => { const k = where === 'result' ? 'remake' : 'output'; return `
  <div class="frame-ctl" data-frame-ctl="${where}">
    <div class="seg block" data-bind="${k}.aspect">
      <button type="button" data-value="original" data-i18n="out.shape.orig"></button>
      <button type="button" data-value="9:16" data-i18n="out.shape.tiktok"></button>
    </div>
    <div class="frame-vertical hidden" data-frame-vertical>
      <span class="small-label" data-i18n="out.fit"></span>
      <div class="seg block" data-bind="${k}.fit">
        <button type="button" data-value="blur" data-i18n="out.fit.blur"></button>
        <button type="button" data-value="crop" data-i18n="out.fit.crop"></button>
        <button type="button" data-value="bars" data-i18n="out.fit.bars"></button>
      </div>
      <div class="range-row hidden" data-frame-crop>
        <span class="label" data-i18n="out.cropx"></span>
        <output data-frame-cropx></output>
        <input type="range" min="0" max="100" step="5" data-bind="${k}.crop_x">
      </div>
      <div class="frame-grid">
        <div class="frame-hints">
          <p class="hint" data-frame-hint="fit"></p>
          <p class="hint" data-frame-hint="note"></p>
          ${where === 'step4' ? '<p class="hint" data-frame-hint="limits"></p>' : ''}
        </div>
        <div class="frame-mock" data-frame-mock data-fit="blur" aria-hidden="true">
          <div class="fm-phone"><div class="fm-bg"></div><img class="fm-img" alt=""></div>
          <span class="fm-cap"></span>
        </div>
      </div>
    </div>
  </div>`; };
function mountFrameControls() {
  $$('[data-frame-controls]').forEach((el) => { el.innerHTML = frameControlsHtml(el.dataset.frameControls); });
  $$('[data-hs-controls]').forEach((el) => { el.innerHTML = hsControlsHtml(el.dataset.hsControls); });
}
function updateFrameMocks() {
  $$('[data-frame-ctl]').forEach((root) => {
    const o = root.dataset.frameCtl === 'result' ? state.s.remake : state.s.output;
    const vertical = o.aspect === '9:16';
    const fit = FRAME_FITS.includes(o.fit) ? o.fit : 'blur';
    const cx = Math.max(0, Math.min(100, Number(o.crop_x) || 0));
    const d = frameDims(o.max_height);
    $$('[data-frame-vertical]', root).forEach((el) => el.classList.toggle('hidden', !vertical));
    $$('[data-frame-crop]', root).forEach((el) => el.classList.toggle('hidden', !(vertical && fit === 'crop')));
    const mock = $('[data-frame-mock]', root);
    if (mock) {
      mock.dataset.fit = fit;
      mock.style.setProperty('--cx', `${cx}%`);
      const url = frameThumbUrl(root.dataset.frameCtl === 'result' ? state.jobs.dub : null);
      const img = $('.fm-img', mock), bg = $('.fm-bg', mock);
      if (img.dataset.want !== url) {                                          // (the picture is only swapped when it changed; a picture that cannot be loaded -> the sample)
        img.dataset.want = url;
        img.onerror = () => { img.onerror = null; img.setAttribute('src', FRAME_SAMPLE); bg.style.backgroundImage = `url("${FRAME_SAMPLE}")`; };
        img.setAttribute('src', url);
        bg.style.backgroundImage = `url("${url}")`;
      }
      $('.fm-cap', mock).textContent = `${d.w}×${d.h}`;
    }
    const txt = { fit: t(`out.fit.hint.${fit}`), note: t('out.shape.note', { w: d.w, h: d.h }), limits: t('out.shape.limits') };
    $$('[data-frame-hint]', root).forEach((el) => { el.textContent = txt[el.dataset.frameHint] || ''; });
    const co = $('[data-frame-cropx]', root);
    if (co) co.textContent = cx === 0 ? t('out.cropx.left') : cx === 100 ? t('out.cropx.right') : cx === 50 ? t('out.cropx.center') : `${cx}%`;
  });
  updateHsUi();
}
/* ============================================================ hide the ORIGINAL subtitles - the ones burned into the picture (v1.10) */
const HS_FX = ['blur', 'mosaic', 'dark', 'frost'];
const hsNum = (v, d, lo, hi) => { const x = Number(v); return Number.isFinite(x) ? Math.max(lo, Math.min(hi, x)) : d; };
const hsClean = (o = {}) => ({
  hide_subs: o.hide_subs === true,
  hide_effect: HS_FX.includes(o.hide_effect) ? o.hide_effect : 'blur',
  hide_bottom: hsNum(o.hide_bottom, 3, 0, 40),
  hide_height: hsNum(o.hide_height, 16, 6, 40),
  hide_strength: Math.round(hsNum(o.hide_strength, 50, 10, 100)),
});
/* the same formulas as app/hardsub.py: the blur is a share of the picture height; the dark box gets blacker with the strength */
const hsSigma = (s) => 0.004 + Number(s) * 0.00046;
const hsDark = (s) => Math.min(1, 0.55 + Number(s) * 0.0075);
const hsControlsHtml = (where) => { const k = where === 'result' ? 'remake' : 'output'; return `
  <div class="hs-ctl" data-hs-ctl="${where}">
    <div class="field-row hs-switch">
      <div class="txt"><b data-i18n="hs.title"></b><span data-i18n="hs.desc"></span></div>
      <label class="switch"><input type="checkbox" data-bind="${k}.hide_subs"><i></i></label>
    </div>
    <div class="hs-body hidden" data-hs-body>
      <span class="small-label" data-i18n="hs.fx"></span>
      <div class="seg block" data-bind="${k}.hide_effect">
        <button type="button" data-value="blur" data-i18n="hs.fx.blur"></button>
        <button type="button" data-value="mosaic" data-i18n="hs.fx.mosaic"></button>
        <button type="button" data-value="dark" data-i18n="hs.fx.dark"></button>
        <button type="button" data-value="frost" data-i18n="hs.fx.frost"></button>
      </div>
      <div class="range-row"><span class="label" data-i18n="hs.bottom"></span><output data-out="${k}.hide_bottom" data-fmt="pct0"></output>
        <input type="range" min="0" max="40" step="1" data-bind="${k}.hide_bottom"></div>
      <div class="range-row"><span class="label" data-i18n="hs.height"></span><output data-out="${k}.hide_height" data-fmt="pct0"></output>
        <input type="range" min="6" max="40" step="1" data-bind="${k}.hide_height"></div>
      <div class="range-row"><span class="label" data-i18n="hs.strength"></span><output data-out="${k}.hide_strength" data-fmt="pct0"></output>
        <input type="range" min="10" max="100" step="5" data-bind="${k}.hide_strength"></div>
      <div class="hs-grid">
        <div class="hs-hints">
          <p class="hint" data-hs-hint></p>
          <p class="hint" data-i18n="hs.hint"></p>
          <p class="hint" data-i18n="hs.slow"></p>
        </div>
        <div class="hs-mock" data-hs-mock aria-hidden="true"><img class="hs-img" alt=""><span class="hs-fake">示例字幕 · Sample subtitle</span><i class="hs-fx" data-fx="blur"></i></div>
      </div>
    </div>
  </div>`; };
/* the band: where it is, how high, which effect (CSS custom properties; the same element shows the effect in the little picture and over the real video) */
function hsPaint(el, o) {
  const band = $('.hs-fx', el);
  if (!band) return;
  band.dataset.fx = o.hide_effect;
  el.style.setProperty('--hs-bottom', `${o.hide_bottom}%`);
  el.style.setProperty('--hs-height', `${o.hide_height}%`);
  el.style.setProperty('--hs-sigma', String(hsSigma(o.hide_strength)));
  el.style.setProperty('--hs-dark', hsDark(o.hide_strength).toFixed(3));
}
function updateHsUi() {
  $$('[data-hs-ctl]').forEach((root) => {
    const where = root.dataset.hsCtl;
    const o = hsClean(where === 'result' ? state.s.remake : state.s.output);
    $$('[data-hs-body]', root).forEach((el) => el.classList.toggle('hidden', !o.hide_subs));
    const mock = $('[data-hs-mock]', root);
    if (mock) {
      hsPaint(mock, o);
      const url = frameThumbUrl(where === 'result' ? state.jobs.dub : null);
      const img = $('.hs-img', mock);
      if (img.dataset.want !== url) {                                      // (the picture is only swapped when it changed; one that cannot be loaded -> the sample)
        img.dataset.want = url;
        img.onerror = () => { img.onerror = null; img.setAttribute('src', FRAME_SAMPLE); };
        img.setAttribute('src', url);
      }
    }
    const hint = $('[data-hs-hint]', root);
    if (hint) hint.textContent = t(`hs.fx.hint.${o.hide_effect}`);
  });
  const live = $('[data-hs-live]');                                         // the same band over the real video in the Sync Preview
  if (live) {
    const o = hsClean(state.s.remake);
    live.classList.toggle('hidden', !o.hide_subs);
    hsPaint(live, o);
    /* a picture wider than the 16:9 frame (2.39:1 ...) is shown with black bars above and below: the band is measured on the PICTURE, so the layer is only as high as the picture */
    const job = state.jobs.dub, v = (job && job.video) || {}, mv = (job && job.meta && job.meta.video) || {};
    const pw = Number(mv.width || v.width), ph = Number(mv.height || v.height);
    const a = pw > 0 && ph > 0 ? pw / ph : 0;
    const keep = a > 16 / 9 + 0.01 ? (16 / 9) / a : 1;
    live.style.setProperty('--hs-pad', `${(((1 - keep) / 2) * 100).toFixed(2)}%`);
  }
}
/* result card: "make the video again" in another shape - only the MP4, the Khmer voice and the edits stay */
const canRemakeVideo = (job) => !!(job && job.video && (job.video.id || (job.video.upload && job.video.has_video)) && (job.outputs || {})['dub.mp3'] && !(job.meta && job.meta.draft));
/* the panel starts from the video the job has now (a job without an MP4 starts from the Step 4 settings) */
function initRemake(job) {
  const mv = (job.meta && job.meta.video) || {};
  const po = (job.params && job.params.output) || {};
  const has = !!(job.outputs || {})['dubbed.mp4'];
  const src = has ? { aspect: mv.aspect || po.aspect, fit: mv.fit || po.fit, crop_x: mv.crop_x ?? po.crop_x, max_height: po.max_height } : state.s.output;
  const r = state.s.remake;
  r.aspect = src.aspect === '9:16' ? '9:16' : 'original';
  r.fit = FRAME_FITS.includes(src.fit) ? src.fit : (FRAME_FITS.includes(state.s.output.fit) ? state.s.output.fit : 'blur');
  r.crop_x = src.crop_x === null || src.crop_x === undefined || !Number.isFinite(Number(src.crop_x)) ? 50 : Math.max(0, Math.min(100, Number(src.crop_x)));
  r.max_height = Number(src.max_height) === 720 ? 720 : 1080;
  if (!has) Object.assign(r, hsClean(state.s.output));
  else if (mv.hide) Object.assign(r, hsClean({ hide_subs: true, hide_effect: mv.hide.effect, hide_bottom: mv.hide.bottom, hide_height: mv.hide.height, hide_strength: mv.hide.strength }));
  else Object.assign(r, hsClean(po), { hide_subs: false });                  // an MP4 whose old subtitles are visible: the panel starts 'off'
}
function remakePanelHtml(job) {
  initRemake(job);
  const mv = (job.meta && job.meta.video) || {};
  const has = !!(job.outputs || {})['dubbed.mp4'];
  const fitName = { blur: t('out.fit.blur'), crop: t('out.fit.crop'), bars: t('out.fit.bars') };
  const dims = mv.out_width && mv.out_height ? `${mv.out_width}×${mv.out_height}` : (mv.height ? `${mv.height}p` : '');
  const what = has ? [t(mv.aspect === '9:16' ? 'rf.what.tiktok' : 'rf.what.orig'), dims, mv.aspect === '9:16' ? fitName[mv.fit] : '',
    mv.hide ? t('rf.what.hide', { fx: t(`hs.fx.${HS_FX.includes(mv.hide.effect) ? mv.hide.effect : 'blur'}`) }) : ''].filter(Boolean).join(' · ') : t('rf.none');
  return `<details class="reframe-box" id="reframe-box">
    <summary>${icon('video')}<span>${esc(t('rf.title'))}</span><small>${esc(t('rf.now', { what }))}</small></summary>
    <div class="rf-body">
      ${frameControlsHtml('result')}
      ${hsControlsHtml('result')}
      <div class="field"><label>${esc(t('out.quality'))}</label>
        <div class="seg block" data-bind="remake.max_height"><button type="button" data-value="1080">1080p</button><button type="button" data-value="720">720p</button></div></div>
      <div class="row"><button class="btn btn-primary" id="btn-reframe" type="button">${icon('reset')}<span>${esc(t(has ? 'rf.btn' : 'rf.btn.new'))}</span></button>
        <span class="hint" style="margin:0">${esc(t('rf.note'))}</span></div>
    </div></details>`;
}
/* Let go of the players of the result BEFORE the server rewrites its files: on Windows a file that the browser is still reading cannot be
   replaced.  (The server does not keep a file open between two chunks any more - app/mediafile.py - this only stops the downloads at once.)
   Returns a function that puts the players back (when the server refuses the request they must keep working). */
function releaseMedia() {
  const held = [];
  $$('#dub-result audio, #dub-result video').forEach((m) => {
    const src = m.getAttribute('src');
    if (!src) return;
    held.push([m, src]);
    m.pause(); m.removeAttribute('src'); m.load();
  });
  return () => held.forEach(([m, src]) => { if (m.isConnected) m.setAttribute('src', src); });
}

async function remakeVideo(job) {
  const r = state.s.remake;
  const o = { aspect: r.aspect === '9:16' ? '9:16' : 'original', fit: FRAME_FITS.includes(r.fit) ? r.fit : 'blur', crop_x: Math.max(0, Math.min(100, Number(r.crop_x) || 0)), max_height: Number(r.max_height) === 720 ? 720 : 1080 };
  const restore = releaseMedia();
  try {
    closeSync();
    await api(`/api/jobs/${job.id}/video`, { method: 'POST', body: { aspect: o.aspect, fit: o.fit, crop_x: o.crop_x, max_height: o.max_height, ...hsClean(r) } });
    toast(t('rf.started'));
    $('#dub-result').classList.add('hidden');
    updateDock();
    trackJob('dub', job.id);
  } catch (e) { restore(); toast(errText(e), 'bad'); }
}

/* ============================================================ jobs */
const STEP_LABEL = { transcript: 'step.transcript', speakers: 'step.speakers', translate: 'step.translate', tts: 'step.tts', mix: 'step.mix', video: 'step.video' };
const DONE = ['done', 'error', 'cancelled'];

async function startDub() {
  let source, video = null;
  if (state.sourceTab === 'youtube') {
    const url = $('#yt-url').value.trim();
    if (!url) { toast(t('gen.need_url'), 'bad'); $('#yt-url').focus(); return; }
    source = { type: 'youtube', url, lang: state.s.source.lang };
    if (state.video && state.videoUrl === url) {
      const { id, url: u, title, channel, thumbnail, duration } = state.video;
      video = { id, url: u, title, channel, thumbnail, duration };
    }
  } else if (state.sourceTab === 'upload') {
    const u = state.upload;
    if (u.status === 'uploading') { toast(t('up.wait'), 'bad'); return; }
    if (u.status !== 'ready' || !u.info) { toast(t('gen.need_file'), 'bad'); $('#up-drop').focus(); return; }
    const plan = upPlan();
    if (plan.kind === 'nowhisper' || plan.kind === 'noaudio') { toast(t(plan.kind === 'nowhisper' ? 'err.NO_SUBTITLES_NO_WHISPER' : 'err.NO_AUDIO'), 'bad'); return; }
    source = { type: 'upload', upload_id: u.info.id, lang: state.s.source.lang, subs: u.subs === 'whisper' ? 'whisper' : 'auto' };
    const typed = $('#up-text').value.trim();
    if (typed) source.text = typed;
  } else {
    const text = $('#tr-text').value.trim();
    if (!text) { toast(t('gen.need_text'), 'bad'); $('#tr-text').focus(); return; }
    source = { type: 'transcript', text, title: $('#tr-title').value.trim(), lang: state.s.source.lang };
  }
  if (!checkLlm(true)) return;
  if (!voxPreflight('dub')) return;
  const body = { source, video, voice: voiceBody(), translate: translateBody(true), output: outputBody(), youtube: youtubeBody() };
  try {
    const { id } = await api('/api/jobs/dub', { method: 'POST', body });
    state.dirty = {};
    trackJob('dub', id);
  } catch (e) {
    toast(errText(e), 'bad');
    if (e.code === 'UPLOAD_GONE') resetUpload(false);              // the file was cleaned up on the server: choose it again
  }
}
async function startTts() {
  const text = $('#tts-text').value.trim();
  if (!text) { toast(t('tts.empty'), 'bad'); $('#tts-text').focus(); return; }
  if (state.s.tts.input_lang !== 'km' && !checkLlm()) return;
  if (!voxPreflight('tts')) return;
  const body = { text, input_lang: state.s.tts.input_lang, voice: voiceBody(), translate: translateBody() };
  try {
    const { id } = await api('/api/jobs/tts', { method: 'POST', body });
    trackJob('tts', id);
  } catch (e) { toast(errText(e), 'bad'); }
}

async function trackJob(kind, id) {
  state.tracking[kind] = id;
  state.jobs[kind] = { id, kind, status: 'queued', steps: [], logs: [], outputs: {}, segments: [] };
  closeSync();
  // destroy the previous result (and its <audio>/<video>) so no stale range requests hit files that are being rewritten
  const oldRes = $(kind === 'dub' ? '#dub-result' : '#tts-result');
  oldRes.querySelectorAll('audio,video').forEach((m) => { m.pause(); m.removeAttribute('src'); m.load(); });
  oldRes.classList.add('hidden');
  oldRes.innerHTML = '';
  renderJob(kind, true);
  const prog = $(kind === 'dub' ? '#dub-progress' : '#tts-progress');
  prog.scrollIntoView({ behavior: 'smooth', block: 'start' });
  let fails = 0;
  for (;;) {
    if (state.tracking[kind] !== id) return; // superseded by another job
    let job;
    try { job = await api(`/api/jobs/${id}`); fails = 0; } catch (e) {
      if (e.status === 404 || ++fails > 8) { toast(errText(e), 'bad'); return; }
      await sleep(1500); continue;
    }
    state.jobs[kind] = job;
    renderJob(kind, false);
    if (DONE.includes(job.status)) break;
    await sleep(900);
  }
  renderJob(kind, true);
  const job = state.jobs[kind];
  if (job.status === 'done') {
    if (job.meta && job.meta.draft) { toast(t('cl.toast.ready'), 'ok'); const cb = $('#claude-box'); if (cb) cb.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    else toast(t('toast.done'), 'ok');
  }
  else if (job.status === 'error') { toast(t('toast.failed'), 'bad'); }
  refreshHistoryBadge();
}

async function cancelJob(kind) {
  const job = state.jobs[kind];
  if (job) { try { await api(`/api/jobs/${job.id}/cancel`, { method: 'POST' }); } catch { /* ignore */ } }
}

function stepHtml(s, i) {
  const ico = s.status === 'done' ? icon('check') : s.status === 'error' ? icon('x') : s.status === 'running' ? icon('spinner', 'spin') : s.status === 'skipped' ? '–' : String(i + 1);
  return `
  <div class="step ${s.status}">
    <div class="s-ico">${ico}</div>
    <div>
      <div><span class="s-title">${esc(t(STEP_LABEL[s.key] || s.key))}</span><span class="s-detail">${esc(s.detail || '')}</span></div>
      ${s.status === 'running' ? `<div class="bar"><i style="width:${Math.round((s.progress || 0) * 100)}%"></i></div>` : ''}
    </div>
    <div class="s-state">${esc(t('state.' + s.status))}</div>
  </div>`;
}
const statusChip = (st) => {
  const cls = st === 'done' ? 'ok' : st === 'error' ? 'bad' : st === 'cancelled' ? 'warn' : 'accent';
  return `<span class="chip ${cls}">${st === 'running' || st === 'queued' ? icon('spinner', 'spin') : ''}${esc(t('status.' + st))}</span>`;
};

function renderJob(kind, full) {
  const job = state.jobs[kind];
  if (!job) return;
  const progEl = $(kind === 'dub' ? '#dub-progress' : '#tts-progress');
  const resEl = $(kind === 'dub' ? '#dub-result' : '#tts-result');
  const active = !DONE.includes(job.status);
  const genBtn = $(kind === 'dub' ? '#btn-generate' : '#tts-generate');
  const cancelBtn = $(kind === 'dub' ? '#btn-cancel' : '#tts-cancel');
  genBtn.disabled = active;
  cancelBtn.classList.toggle('hidden', !active);

  // ---- progress card: while running, or when the job failed
  const showProg = active || job.status === 'error' || job.status === 'cancelled';
  progEl.classList.toggle('hidden', !showProg);
  if (showProg) {
    const elapsed = Math.max(0, Math.round(Date.now() / 1000 - (job.created || Date.now() / 1000)));
    const steps = (job.steps || []).map(stepHtml).join('');
    const err = job.error ? noticeHtml('bad', errText(job.error), job.error.message) : '';
    const VOX_FIX = ['VOX_NOT_INSTALLED', 'VOX_START_FAILED', 'VOX_LOAD_FAILED', 'VOX_LOAD_TIMEOUT', 'VOX_OOM'];
    const errAct = job.error && job.error.code === 'TRANSLATE_FAILED'
      ? `<div style="margin-top:10px"><button class="btn btn-sm" type="button" data-goto="settings">${icon('globe')}<span>${esc(t('err.gotest'))}</span></button></div>`
      : (job.error && VOX_FIX.includes(job.error.code)
        ? `<div style="margin-top:10px"><button class="btn btn-sm" type="button" data-goto="settings">${icon('chip')}<span>${esc(t('err.open_vox'))}</span></button></div>` : '');
    const warns = (job.warnings || []).map((w) => noticeHtml('warn', errText(w), w.message)).join('');
    const logs = (job.logs || []).join('\n');
    const openLogs = progEl.querySelector('details.logs')?.open;
    progEl.innerHTML = `
      <div class="card-head"><span class="step-badge">${icon('wand')}</span><h2>${esc(t('prog.title'))}${job.title ? ` · <span class="muted" style="font-weight:600">${esc(job.title.slice(0, 70))}</span>` : ''}</h2>${statusChip(job.status)}<span class="counter">${fmtTime(elapsed)}</span></div>
      <div class="steps">${steps}</div>
      ${err ? `<div style="margin-top:14px">${err}${errAct}</div>` : ''}
      ${warns ? `<div style="margin-top:12px;display:grid;gap:10px">${warns}</div>` : ''}
      <details class="logs" ${openLogs ? 'open' : ''}><summary>${esc(t('prog.logs'))}</summary><pre>${esc(logs)}</pre></details>`;
    const pre = $('details.logs pre', progEl);
    if (pre) pre.scrollTop = pre.scrollHeight;
  }

  // ---- result card: only (re)built when the job finishes
  if (full) {
    const draft = !!(job.meta && job.meta.draft);        // a copy / paste draft stays reachable even when its first audio attempt failed
    const outs = job.outputs || {};
    // a Regenerate that failed or was cancelled: the edits are saved in the job and the previous audio is still there - the editor stays,
    // so the user presses Regenerate again instead of making the whole video again
    const retry = kind === 'dub' && !draft && (job.status === 'error' || job.status === 'cancelled') && !!outs['dub.mp3'] && (job.segments || []).some((s) => (s.km || '').trim());
    const ok = (job.status === 'done' || ((draft || retry) && (job.status === 'error' || job.status === 'cancelled'))) && Object.keys(outs).length;
    resEl.classList.toggle('hidden', !ok);
    if (ok) (kind === 'dub' ? renderDubResult : renderTtsResult)(job, resEl);
  }
  if (kind === 'dub') updateDock();
}

const isUploadJob = (job) => !!(job && job.video && job.video.upload);                              // made from a file the user uploaded
const hasSrcMedia = (job) => !!(job && job.video && (job.video.id || job.video.upload));      // a video the speaker's voice can be copied from
const fileUrl = (job, name, dl = false) => `/api/jobs/${job.id}/file/${name}?${dl ? 'download=1&' : ''}v=${Math.round(job.updated || 0)}`;
const dlBtn = (href, ico, label, primary = false) => `<a class="btn ${primary ? 'btn-primary' : ''}" href="${href}" download>${icon(ico)}<span>${esc(label)}</span></a>`;

function renderDubResult(job, el) {
  const segs = job.segments || [];
  const meta = job.meta || {};
  const speedups = segs.filter((s) => s.speed && s.speed > 1.04).length;
  const tm = meta.transcript || {};
  const sl = srcLangOf(job), slName = LANG_NAME[sl];
  const srcChip = `${slName} · ${tm.source === 'whisper' ? 'Whisper (AI)' : tm.source === 'embedded' ? t('res.src.embedded') : tm.source === 'manual' ? (tm.timed ? 'SRT/VTT' : 'Plain text') : tm.generated ? 'Auto captions' : 'Manual captions'}`;
  const srtName = (job.outputs || {})['original.srt'] ? 'original.srt' : 'english.srt';   // jobs made before v1.3 have english.srt
  const hasMp4 = !!(job.outputs || {})['dubbed.mp4'];
  const portraitMp4 = !!(meta.video && meta.video.out_width && meta.video.out_height > meta.video.out_width);      // a vertical (TikTok) video is shown tall
  const canSync = job.video && (job.video.id || (job.video.upload && job.video.has_video)) && (job.params?.output?.sync || 'fit') === 'fit' && meta.timed !== false;
  const warns = (job.warnings || []).map((w) => noticeHtml('warn', errText(w), w.message)).join('');
  const vx = meta.vox;
  const voxInfo = vx ? `<div class="stats"><span>VoxCPM2 · <b>${esc(vx.label || vx.voice)}</b></span>${vx.rtf != null ? `<span>${esc(t('res.vox.speed', { n: vx.rtf }))}</span>` : ''}</div>` : '';
  const charRefs = Object.keys(job.outputs || {}).filter((k) => /^voice_ref_c\d+\.wav$/.test(k)).sort((p, q) => parseInt(p.slice(11), 10) - parseInt(q.slice(11), 10));
  const chById = new Map(((meta.characters) || []).map((c) => [c.id, c]));
  const charRefHtml = charRefs.map((k) => { const id = parseInt(k.slice(11), 10), c = chById.get(id) || {}; return `<div class="vox-ref-char"><span class="cb ${c.gender === 'female' ? 'f' : 'm'}">${c.gender === 'female' ? '♀' : '♂'}${id}</span>${c.name ? `<span class="muted small">${esc(c.name)}</span>` : ''}<audio controls preload="none" src="${fileUrl(job, k)}"></audio></div>`; }).join('');
  const voxRef = ((job.outputs || {})['voice_ref.wav'] || charRefs.length)
    ? `<div class="vox-ref"><b>${icon('mic')} ${esc(t('res.vox.ref'))}</b>${(job.outputs || {})['voice_ref.wav'] ? `<audio controls preload="none" src="${fileUrl(job, 'voice_ref.wav')}"></audio>` : ''}${charRefHtml}<p class="hint" style="margin:6px 0 0">${esc(t('res.vox.ref.hint'))}</p></div>` : '';
  const draft = !!meta.draft;                                                   // copy / paste translation: the subtitles are ready, there is no audio yet
  const staleBox = !draft && job.status !== 'done' ? noticeHtml('warn', t('res.regen_failed')) : '';        // the last Regenerate failed / was cancelled: this is the old audio
  const draftBox = `
    <div class="notice info draft-box">${icon('info')}<div class="n-body"><b>${esc(t(job.status === 'done' ? 'cl.draft.title' : 'cl.draft.failed'))}</b><br>${esc(t('cl.draft.body'))}
      <div class="dl-row" style="margin-top:12px">${dlBtn(fileUrl(job, srtName, true), 'doc', t('dl.srt_src', { lang: slName }))}</div></div></div>`;
  el.innerHTML = `
    <div class="card-head"><span class="step-badge">${icon('check')}</span><h2>${esc(t('res.title'))}${job.title ? ` · <span class="muted" style="font-weight:600">${esc(job.title.slice(0, 80))}</span>` : ''}</h2><span class="chip">${esc(srcChip)}</span>${draft && job.status === 'done' ? `<span class="chip warn">${esc(t('hist.draft'))}</span>` : statusChip(job.status)}</div>
    ${staleBox}
    ${draft ? draftBox : `<div class="player-box">
      <b>${icon('mic')} ${esc(t('res.audio'))}</b>
      <audio id="dub-audio" controls preload="metadata" src="${fileUrl(job, 'dub.mp3')}"></audio>
      <div class="stats">
        <span>${esc(t('res.duration'))} <b>${fmtTime(meta.audio_duration || 0)}</b></span>
        <span>${esc(t('res.segments'))} <b>${segs.length}</b></span>
        ${meta.video && meta.video.aspect === '9:16' && meta.video.out_width ? `<span>MP4 <b>${meta.video.out_width}×${meta.video.out_height}</b> · TikTok 9:16${meta.video.size ? ` · ${fmtBytes(meta.video.size)}` : ''}</span>`
          : (meta.video && meta.video.height ? `<span>MP4 <b>${meta.video.height}p</b>${meta.video.size ? ` · ${fmtBytes(meta.video.size)}` : ''}</span>` : '')}
        ${meta.video && meta.video.hide ? `<span>${esc(t('hs.stat'))} <b>${esc(t(`hs.fx.${HS_FX.includes(meta.video.hide.effect) ? meta.video.hide.effect : 'blur'}`))}</b></span>` : ''}
        ${meta.timed !== false ? `<span>${esc(t('res.speedups'))} <b>${speedups}</b></span><span>${esc(t('res.lag'))} <b>${Number(meta.max_drift || 0).toFixed(1)}s</b></span>` : ''}
      </div>
      ${voxInfo}${voxRef}
      <div class="dl-row">
        ${dlBtn(fileUrl(job, 'dub.mp3', true), 'download', t('dl.mp3'), true)}
        ${hasMp4 ? dlBtn(fileUrl(job, 'dubbed.mp4', true), 'video', t('dl.mp4'), true) : ''}
        ${dlBtn(fileUrl(job, 'khmer.srt', true), 'doc', t('dl.srt'))}
        ${dlBtn(fileUrl(job, srtName, true), 'doc', t('dl.srt_src', { lang: slName }))}
        ${dlBtn(fileUrl(job, 'script_km.txt', true), 'doc', t('dl.txt'))}
      </div>
    </div>`}
    ${warns ? `<div style="margin-top:14px;display:grid;gap:10px">${warns}</div>` : ''}
    ${!draft && canRemakeVideo(job) ? remakePanelHtml(job) : ''}
    ${!draft && hasMp4 ? `<div class="mp4-block dockable" id="mp4-panel">${dockHead('mp4')}<div class="dock-body"><div class="sub-toolbar">${subToggle('en')}${subToggle('km')}</div><div class="mp4-frame yt-frame${portraitMp4 ? ' portrait' : ''}"><video controls preload="metadata" ${!portraitMp4 && job.video && job.video.thumbnail ? `poster="${esc(job.video.thumbnail.replace('hqdefault', 'mqdefault'))}"` : ''} src="${fileUrl(job, 'dubbed.mp4')}${portraitMp4 ? '#t=0.1' : ''}"><track kind="subtitles" srclang="${sl}" label="${esc(slName)}" src="/api/jobs/${job.id}/subtitle/en.vtt"><track kind="subtitles" srclang="km" label="ខ្មែរ" src="/api/jobs/${job.id}/subtitle/km.vtt"></video></div></div></div>` : ''}
    ${canSync ? `<div class="sync-preview"><div class="row"><b>${esc(t(draft ? 'res.sync.title.draft' : 'res.sync.title'))}</b><span class="spacer"></span><button class="btn btn-sm" id="btn-sync" type="button">${icon('video')}<span>${esc(t('res.sync.open'))}</span></button></div><p class="hint" style="margin-top:4px">${esc(t(draft ? (isUploadJob(job) ? 'res.sync.hint.upload.draft' : 'res.sync.hint.draft') : (isUploadJob(job) ? 'res.sync.hint.upload' : 'res.sync.hint')))}</p><div id="sync-holder" style="margin-top:12px"></div></div>` : ''}
    <div class="divider"></div>
    <div class="card-head" style="margin-bottom:6px"><h2>${esc(t('res.edit.title'))}</h2><span class="spacer"></span>${!draft || canSync ? subToggle('clickplay') : ''}${draft ? '' : subToggle('follow')}${subToggle('en')}</div>
    ${draft ? (canSync ? `<p class="hint" style="margin-top:0">${esc(t('res.edit.hint.draft'))}</p>` : '') : `<p class="hint" style="margin-top:0">${esc(t('res.edit.hint'))}</p>`}
    ${claudePanelHtml(job, draft)}
    ${charsPanelHtml(job)}
    ${(() => { voiceSig = voiceSigOf(job); return segTools(job, meta.timed !== false); })()}
    <div class="seg-table${draft ? ' no-audio' : ''}${state.s.subs.clickplay ? ' clickplay' : ''}">
      <div class="seg-head"><div>#</div><div>${esc(t('seg.time'))}</div><div>${esc(t('seg.src', { lang: slName }))}</div><div>${esc(t('seg.km'))}</div><div></div></div>
      ${segs.map((sg) => segRowHtml(sg, sl, job, meta.timed !== false)).join('')}
    </div>
    <div class="seg-actions">
      <div class="seg-status"><button class="btn btn-sm now-btn hidden" id="btn-nowline" type="button" title="${esc(t('seg.now.tip'))}"></button><span class="muted small" id="dirty-label">${esc(t('res.clean'))}</span></div>
      <button class="btn btn-primary" id="btn-regen" type="button">${icon('reset')}<span>${esc(t(draft ? 'cl.generate' : 'btn.regen'))}</span></button>
    </div>`;
  applyI18n(el);
  syncBindings(el);
  updateFrameMocks();
  wireDubResult(job, el);
  paintAutoLabels();
  updateDock();
}
/* ============================================================ the editor table: Khmer text, a voice and a Start / End for every line */
const MIN_WIN = 0.3;                                  // the shortest window the server accepts (End - Start)
let editorDraft = null;                               // unsaved edits survive a language switch / re-render of the same job
/* What the server will do with a line (same formulas as app/pipeline.py): speed up by need x 1.03, never above the maximum. */
function predictSpeed(dur, win, max) {
  if (!(dur > 0)) return null;
  const need = dur / Math.max(0.6, win);
  if (need <= 1.05) return { x: 1, fit: true };
  return { x: Math.min(need * 1.03, max), fit: need * 1.03 <= max + 0.001 };
}
const edgeVoices = () => state.voices.khmer || [];
function voiceName(id) {
  if (!id) return '';
  const e = edgeVoices().find((v) => v.id === id);
  if (e) return e.name;
  if (id === 'vox:original') return t('vox.original.name');
  if (id.startsWith('vox:s:')) return t('vox.char.name', { n: id.slice(6) });
  if (id.startsWith('vox:p:')) { const k = `vox.p.${id.slice(6)}`; return I18N[state.lang][k] ? t(k) : id.slice(6); }
  const c = voxAll().find((v) => v.id === id);
  return c ? c.name : id.replace(/^vox:c:/, '');
}
const globalVoiceName = () => { const v = state.s.voice; return v.engine === 'voxcpm' ? voiceName((v.vox || {}).id) : voiceName(v.id); };
/* <option>s of a voice picker for one line: "same as above", Microsoft voices, and (when VoxCPM2 is installed) designed + cloned voices */
function voiceOptionsHtml(job, current, opts = {}) {
  const have = new Set(['']);
  const opt = (v, label) => { have.add(v); return `<option value="${esc(v)}"${v === current ? ' selected' : ''}>${esc(label)}</option>`; };
  let h = `<option value=""${current === '' ? ' selected' : ''}>${esc(t('seg.voice.same', { name: globalVoiceName() }))}</option>`;
  h += `<optgroup label="${esc(t('seg.voice.group.edge'))}">${edgeVoices().map((v) => opt(v.id, `${v.name} (${v.native})`)).join('')}</optgroup>`;
  if (state.vox && state.vox.installed) {
    const pres = (state.voices.vox || {}).presets || [];
    if (pres.length) h += `<optgroup label="${esc(t('vox.group.designed'))}">${pres.map((p) => opt(p.id, voiceName(p.id))).join('')}</optgroup>`;
    const hasVideo = hasSrcMedia(job), cust = voxAll();
    if (hasVideo || cust.length) h += `<optgroup label="${esc(t('seg.voice.group.clone'))}">${hasVideo ? (opts.char ? opt('vox:s', t('chars.voice.clone')) : opt('vox:original', t('vox.original.name'))) : ''}${cust.map((v) => opt(v.id, v.name)).join('')}</optgroup>`;
  } else {
    h += `<optgroup label="VoxCPM2"><option value="__none" disabled>${esc(t('seg.voice.needvox'))}</option></optgroup>`;
  }
  if (current && !have.has(current)) h += `<option value="${esc(current)}" selected>${esc(t('seg.voice.missing', { name: voiceName(current) }))}</option>`;
  return h;
}
/* The voice lists of an open table follow what is installed / saved (e.g. VoxCPM2 finishes loading after the table was drawn). */
const voiceSigOf = (job) => [state.vox && state.vox.installed ? 1 : 0, ((state.voices.vox || {}).presets || []).length,
  voxAll().map((v) => v.id).join(','), hasSrcMedia(job) ? 1 : 0, job && job.id].join('|');
let voiceSig = '';
function refreshVoiceSelects() {
  const job = state.jobs.dub, sels = $$('#dub-result .vsel, #dub-result #bulk-voice, #dub-result .char-voice');
  if (!sels.length) return;
  const sig = voiceSigOf(job);
  if (sig === voiceSig) return;
  voiceSig = sig;
  sels.forEach((sel) => { sel.innerHTML = voiceOptionsHtml(job, sel.value === '__none' ? '' : sel.value, { char: sel.classList.contains('char-voice') }); });
  paintAutoLabels();
}
const genderName = (g) => t(g === 'female' ? 'voice.female' : 'voice.male');
const canDetectChars = (job) => !!(job && job.video && (job.video.id || job.video.upload) && (job.meta || {}).timed !== false && ((job.meta || {}).upload || {}).has_audio !== false);
/* Characters (found from the sound): who speaks which line, man or woman, and the voice each one gets */
function charsPanelHtml(job) {
  const meta = job.meta || {}, chars = meta.characters || [], can = canDetectChars(job), st = (meta.speakers || {}).state || '';
  const m = chars.filter((c) => c.gender === 'male').length;
  const sum = chars.length ? t('chars.sum', { n: chars.length, m, f: chars.length - m }) : '';
  const head = `<div class="chars-head">${icon('users')}<b>${esc(t('chars.title'))}</b><span class="muted small" id="chars-sum">${esc(sum)}</span><span class="spacer"></span>
    <span class="chars-switch"><span>${esc(t('chars.switch'))}</span><label class="switch"><input type="checkbox" data-bind="voice.auto.on" aria-label="${esc(t('chars.switch'))}"><i></i></label></span>
    ${can ? `<button class="btn btn-sm" id="btn-detect" type="button">${icon('wand')}<span>${esc(t(chars.length ? 'chars.detect.again' : 'chars.detect'))}</span></button>` : ''}</div>`;
  let body;
  if (chars.length) {
    body = `<div class="chars-list">${chars.map((c) => {
      const unsure = !c.gender_set && c.p != null && c.p > 0.28 && c.p < 0.72;
      return `<div class="char-row" data-char="${c.id}" data-gender="${esc(c.gender)}" data-f0="${c.f0 || ''}" data-ref="${(c.ref || []).length ? '1' : ''}" data-orig-gender="${esc(c.gender)}">
        <span class="cb" data-cbadge data-unsure="${unsure ? '1' : ''}"></span>
        <input class="input char-name" maxlength="40" value="${esc(c.name || '')}" placeholder="${esc(t('chars.name.ph'))}" aria-label="${esc(t('chars.name.aria', { n: c.id }))}">
        <span class="char-info muted small"${c.f0 ? ` title="≈${Math.round(c.f0)} Hz"` : ''}>${esc(t('chars.lines', { n: c.lines }))}${unsure ? ` · <b class="warn-txt">${esc(t('chars.unsure'))}</b>` : ''}</span>
        <select class="select char-voice" aria-label="${esc(t('chars.voice.aria', { n: c.id }))}">${voiceOptionsHtml(job, c.voice || '', { char: true })}</select>
        <button class="mini char-flip" type="button" data-flip>${icon('swap')}</button>
      </div>`;
    }).join('')}</div><p class="hint chars-hint">${esc(t('chars.hint'))}</p>`;
  } else {
    const key = { unsure: 'chars.state.unsure', failed: 'chars.state.failed', no_audio: 'chars.state.no_audio', untimed: 'chars.state.untimed', off: 'chars.state.off' }[st];
    body = `<p class="hint chars-none">${esc(t(key && (can || st === 'untimed') ? key : (can ? 'chars.none' : 'chars.none.nomedia')))}</p>`;
  }
  return `<div class="chars-panel" id="chars-panel">${head}${body}</div>`;
}
function segTools(job, timed) {
  return `
    <div class="seg-tools">
      <label class="check sm"><input type="checkbox" id="seg-all"><span>${esc(t('seg.sel.all'))}</span></label>
      <span class="muted small" id="seg-selinfo">${esc(t('seg.sel.none'))}</span>
      <span class="spacer"></span>
      <select class="select sm" id="bulk-voice" aria-label="${esc(t('seg.voice'))}">${voiceOptionsHtml(job, '')}</select>
      <button class="btn btn-sm" id="bulk-apply" type="button" disabled>${esc(t('seg.bulk.apply'))}</button>
      <button class="btn btn-sm btn-ghost" id="bulk-clear" type="button" disabled>${esc(t('seg.bulk.clear'))}</button>
    </div>
    ${timed ? `<p class="hint seg-tip">${esc(t('seg.tip'))}</p>` : ''}`;
}
function segRowHtml(s, sl, job, timed) {
  const wr = String(s.warn || '').split(' ');
  const warns = (wr.includes('late') ? `<span class="late">${esc(t('res.late'))}</span>` : '') + (wr.includes('long') ? `<span class="late">${esc(t('res.long'))}</span>` : '');
  const num = s.idx + 1;
  const tin = (which, val, label) => `<label class="tline"><span>${esc(t(which === 'start' ? 'seg.s' : 'seg.e'))}</span><input class="tin" data-t="${which}" inputmode="decimal" autocomplete="off" spellcheck="false" title="${esc(label)}" aria-label="${esc(label)}" value="${fmtClock(val)}"></label>`;
  const tm = timed
    ? `<div class="tm">${tin('start', s.t0 ?? s.start, t('seg.start'))}${tin('end', s.slot ? s.slot[1] : s.end, t('seg.end'))}<div class="tinfo"><span class="spd"></span>${warns}<button class="mini" type="button" data-extend title="${esc(t('seg.extend'))}" aria-label="${esc(t('seg.extend'))}">${icon('extend')}</button><button class="mini" type="button" data-treset hidden title="${esc(t('seg.reset.time'))}" aria-label="${esc(t('seg.reset.time'))}">${icon('reset')}</button></div></div>`
    : `<div class="tm">${fmtTime(s.start)}<small>${s.speed && s.speed > 1.04 ? `×${Number(s.speed).toFixed(2)}` : ''}${warns ? ` ${warns}` : ''}</small></div>`;
  const cid = Number.isInteger(s.char) ? s.char : 0;
  const unsure = cid && s.gp != null && s.gp > 0.28 && s.gp < 0.72;
  const badge = cid ? `<span class="cb" data-unsure="${unsure ? '1' : ''}"></span>` : '';        // class / symbol / title: paintAutoLabels()
  return `
  <div class="seg-row" data-idx="${s.idx}" data-char="${cid || ''}" data-start="${s.out_start ?? s.start}" data-end="${s.out_end ?? s.end}">
    <div class="idx"><label class="pick"><input type="checkbox" data-pick aria-label="${esc(t('seg.row.select', { n: num }))}"><span>${num}</span></label>${badge}</div>
    ${tm}
    <div class="en" lang="${LANG_HTML[sl] || 'en'}">${esc(s.en)}</div>
    <div class="kmcell"><textarea rows="1" data-idx="${s.idx}" spellcheck="false">${esc(s.km)}</textarea></div>
    <div class="vc"><select class="select vsel" aria-label="${esc(t('seg.voice'))}">${voiceOptionsHtml(job, s.voice || '')}</select><button class="mini" type="button" data-vprev data-ico="volume" title="${esc(t('seg.prev'))}" aria-label="${esc(t('seg.prev'))}">${icon('volume')}</button></div>
    <button class="go" type="button" data-go="${s.idx}" aria-label="Play">${icon('play')}</button>
  </div>`;
}
const autoGrow = (ta) => { ta.style.height = 'auto'; ta.style.height = `${ta.scrollHeight + 2}px`; };
const isCloneVoice = (v) => v === 'vox:original' || v === 'vox:s' || String(v).startsWith('vox:c:') || String(v).startsWith('vox:s:');
/* A clone voice may only be used with permission: ask once (the same tick as in the voice settings). */
function acceptVoice(v) {
  if (!isCloneVoice(v) || state.s.voice.vox.consent) return true;
  if (!window.confirm(`${t('vox.consent')}\n\n${t('vox.consent.hint')}`)) return false;
  state.s.voice.vox.consent = true;
  saveSettings(); syncBindings(); updateDerived();
  return true;
}

function wireDubResult(job, el) {
  const audio = $('#dub-audio', el) || document.createElement('audio');      // a draft has no audio yet: a detached element keeps the listeners below harmless
  const mv = $('video', el);                                     // the MP4 preview (only when the MP4 was built)
  const rows = $$('.seg-row', el);
  const segs = job.segments || [];
  const timed = (job.meta || {}).timed !== false;
  const n = rows.length;
  const draft = !!(job.meta || {}).draft;
  let stopAt = null, stopMedia = 'audio', lastPlayer = 'audio';
  if (el._wired) el._wired.abort();                     // the card is drawn again for every job / language: drop the listeners of the previous drawing
  const ac = new AbortController();
  el._wired = ac;
  const on = (type, fn) => el.addEventListener(type, fn, { signal: ac.signal });
  $$('.seg-row textarea', el).forEach(autoGrow);
  requestAnimationFrame(() => $$('.seg-row textarea', el).forEach(autoGrow));

  /* ---- one editor state per row (same order as the table) */
  const st = rows.map((r, i) => ({
    r, i, s: segs[i], idx: segs[i].idx,
    start: segs[i].t0 ?? segs[i].start, ov1: segs[i].t1 != null, end: segs[i].t1 ?? 0,
    ta: $('textarea', r), vs: $('.vsel', r), a: $('[data-t="start"]', r), b: $('[data-t="end"]', r), spd: $('.spd', r),
  }));
  /* the characters panel: gender flip, a voice, a name (the characters of the job, with what is on the screen now) */
  const cs = $$('.char-row', el).map((r) => ({ r, id: Number(r.dataset.char), c: ((job.meta || {}).characters || []).find((x) => x.id === Number(r.dataset.char)) || {}, name: $('.char-name', r), vs: $('.char-voice', r) }));
  const charChanged = (x) => ({ gender: x.r.dataset.gender !== x.c.gender, voice: x.vs.value !== (x.c.voice || ''), name: x.name.value.trim() !== (x.c.name || '') });
  const charDirty = (c) => c.gender || c.voice || c.name;
  const charsNow = () => cs.map((x) => ({ id: x.id, gender: x.r.dataset.gender, f0: Number(x.r.dataset.f0) || 0, ref: x.r.dataset.ref === '1', voice: x.vs.value }));
  const maxSpeed = () => Number(state.s.output.max_speedup) || 1.4;
  const defEnd = (i) => (i + 1 < n ? st[i + 1].start - 0.10 : st[i].s.end + 3.9);   // = the server: next line's start - 0.1 s
  const textOf = (x) => x.ta.value.trim();
  const natDur = (x) => {                              // how long the line is at normal speed (an estimate once the text was edited)
    const s = x.s;
    const d = s.dur ?? ((s.out_start != null && s.out_end != null && s.speed) ? (s.out_end - s.out_start) * s.speed : null);
    const len0 = (s.km || '').trim().length, len1 = textOf(x).length;
    if (!len1) return { d: null, est: false };
    if (d && len0 && len1 !== len0) return { d: (d * len1) / len0, est: true };
    return { d: d || null, est: false };
  };
  const curT0 = (x) => (Math.abs(x.start - x.s.start) > 0.05 ? x.start : null);
  const curT1 = (x) => (x.ov1 ? x.end : null);
  const same = (p, q) => (p == null && q == null) || (p != null && q != null && Math.abs(p - q) < 0.001);
  const changed = (x) => ({
    km: textOf(x) !== (x.s.km || '').trim(),
    voice: x.vs.value !== (x.s.voice || ''),
    t0: timed && !same(curT0(x), x.s.t0 ?? null),
    t1: timed && !same(curT1(x), x.s.t1 ?? null),
  });
  const isDirty = (c) => c.km || c.voice || c.t0 || c.t1;
  /* what the Claude panel needs from the table */
  const hooks = { total: n, draft, filled: () => st.filter((x) => textOf(x)).length, apply: applyKm, commit: commitKm, onChange: null };
  function applyKm(items) {                              // put Khmer lines (from the pasted answer) into the table: they count as edits until the audio is generated
    const byIdx = new Map(st.map((x) => [x.idx, x]));
    let k = 0;
    for (const it of items) {
      const x = byIdx.get(it.idx);
      if (x && textOf(x) !== String(it.km).trim()) { x.ta.value = it.km; k++; }
    }
    $$('.seg-row textarea', el).forEach(autoGrow);
    recompute();
    return k;
  }
  function commitKm(items) {                             // a draft kept these lines in the job: they are the job's text now, no longer edits
    const byIdx = new Map(st.map((x) => [x.idx, x]));
    items.forEach((it) => { const x = byIdx.get(it.idx); if (x) x.s.km = String(it.km).trim(); });
    recompute();
  }

  function saveDraft() {
    const out = {};
    st.forEach((x) => { if (isDirty(changed(x))) out[x.idx] = { km: x.ta.value, voice: x.vs.value, start: x.start, ov1: x.ov1, end: x.end }; });
    const chars = {};
    cs.forEach((x) => { if (charDirty(charChanged(x))) chars[x.id] = { gender: x.r.dataset.gender, voice: x.vs.value, name: x.name.value }; });
    editorDraft = (Object.keys(out).length || Object.keys(chars).length) ? { jobId: job.id, rows: out, chars } : null;
  }
  function restoreDraft() {
    if (!editorDraft || editorDraft.jobId !== job.id) return;
    st.forEach((x) => {
      const d = editorDraft.rows[x.idx];
      if (!d) return;
      x.ta.value = d.km; x.vs.value = d.voice; x.start = d.start; x.ov1 = d.ov1; x.end = d.end;
    });
    cs.forEach((x) => {
      const d = (editorDraft.chars || {})[x.id];
      if (d) { x.r.dataset.gender = d.gender; x.vs.value = d.voice; x.name.value = d.name; }
    });
    $$('.seg-row textarea', el).forEach(autoGrow);
  }
  function recompute() {
    if (timed) {
      st.forEach((x, i) => { if (!x.ov1) x.end = defEnd(i); });
      const M = maxSpeed();
      st.forEach((x) => {
        const o0 = curT0(x) !== null;
        if (document.activeElement !== x.a) x.a.value = fmtClock(x.start);
        if (document.activeElement !== x.b) x.b.value = fmtClock(x.end);
        x.a.classList.toggle('set', o0);
        x.b.classList.toggle('set', x.ov1);
        x.b.classList.toggle('bad', x.ov1 && x.end - x.start < MIN_WIN);
        const rs = $('[data-treset]', x.r);
        if (rs) rs.hidden = !(o0 || x.ov1);
        const nd = natDur(x), p = predictSpeed(nd.d, x.end - x.start, M);
        if (!p || (p.x < 1.045 && p.fit)) { x.spd.textContent = ''; x.spd.className = 'spd'; x.spd.removeAttribute('title'); }
        else {
          x.spd.textContent = `${nd.est ? '≈' : ''}×${p.x.toFixed(2)}${p.fit ? '' : ' ✕'}`;
          x.spd.className = `spd ${!p.fit ? 'bad' : p.x > 1.15 ? 'warn' : 'ok'}`;
          x.spd.title = [!p.fit ? t('seg.speed.bad', { max: M }) : t('seg.speed.fast', { x: p.x.toFixed(2) }), nd.est ? t('seg.speed.est') : ''].filter(Boolean).join(' · ');
        }
      });
    }
    let k = 0;
    st.forEach((x) => {
      const c = changed(x), d = isDirty(c);
      x.r.classList.toggle('dirty', !!d);
      x.vs.classList.toggle('set', x.vs.value !== '');
      if (d) k++;
    });
    if (draft) {
      const empty = st.filter((x) => !textOf(x)).length;
      $('#dirty-label', el).textContent = empty ? t('cl.empty', { n: empty, total: n }) : t('cl.ready', { n });
    } else {
      const kc = cs.filter((x) => charDirty(charChanged(x))).length;
      $('#dirty-label', el).textContent = (k || kc) ? (k && kc ? t('res.dirty.both', { n: k, c: kc }) : kc ? t('res.dirty.chars', { c: kc }) : t('res.dirty', { n: k })) : t('res.clean');
    }
    saveDraft();
    if (hooks.onChange) hooks.onChange();
  }
  st.forEach((x) => { x.vs.dataset.prev = x.vs.value; });
  restoreDraft();
  st.forEach((x) => { x.vs.dataset.prev = x.vs.value; });
  cs.forEach((x) => { x.vs.dataset.prev = x.vs.value; });
  paintAutoLabels();
  recompute();
  /* "Detect characters" on a finished job: the table is drawn again when the new characters are ready */
  async function detectChars() {
    try {
      closeSync();
      await api(`/api/jobs/${job.id}/speakers`, { method: 'POST', body: { youtube: youtubeBody() } });
      toast(t('toast.detect_started'));
      $('#dub-result').classList.add('hidden');
      updateDock();
      trackJob('dub', job.id);
    } catch (e2) { toast(errText(e2), 'bad'); }
  }

  /* ---- Start / End */
  function commitTime(x, which) {
    const inp = which === 'start' ? x.a : x.b;
    const v = parseClock(inp.value);
    if (v === null) {
      toast(t('seg.err.time'), 'bad');
      inp.classList.add('bad'); setTimeout(() => inp.classList.remove('bad'), 1500);
      inp.value = fmtClock(which === 'start' ? x.start : x.end);
      return;
    }
    if (which === 'start') x.start = Math.abs(v - x.s.start) <= 0.05 ? x.s.start : v;
    else if (Math.abs(v - defEnd(x.i)) <= 0.05) x.ov1 = false;
    else { x.ov1 = true; x.end = v; }
    recompute();
    inp.value = fmtClock(which === 'start' ? x.start : x.end);          // show what was understood ("20" -> 0:20.0), also while the box is focused
  }
  /* Use the free time around a line: first the time up to the next line, then the gap after the line before it has finished. */
  function extendRow(x) {
    const M = maxSpeed(), nd = natDur(x), num = x.idx + 1;
    if (!nd.d) { toast(t('seg.prev.empty')); return; }
    const before = predictSpeed(nd.d, x.end - x.start, M);
    let missing = nd.d + 0.10 - (x.end - x.start);                  // seconds still missing to speak it at normal speed
    if (missing <= 0.02) { toast(t('seg.extend.fits', { n: num })); return; }
    const takeAfter = Math.min(missing, Math.max(0, defEnd(x.i) - x.end));
    missing -= takeAfter;
    let takeBefore = 0;
    if (missing > 0.001) {
      let busyUntil = 0;
      if (x.i > 0) {
        const p = st[x.i - 1], pd = natDur(p), ps = predictSpeed(pd.d, p.end - p.start, M);
        busyUntil = pd.d ? p.start + pd.d / (ps ? ps.x : 1) + 0.12 : p.start + 0.12;      // the line before keeps the time it needs
      }
      takeBefore = Math.min(missing, Math.max(0, x.start - busyUntil));
    }
    if (takeAfter < 0.02 && takeBefore < 0.02) { toast(t('seg.extend.none', { n: num })); return; }
    if (takeBefore >= 0.02) x.start = Math.abs(x.start - takeBefore - x.s.start) <= 0.05 ? x.s.start : x.start - takeBefore;
    if (takeAfter >= 0.02) {
      x.end += takeAfter;
      x.ov1 = Math.abs(x.end - defEnd(x.i)) > 0.05;
    }
    recompute();
    const after = predictSpeed(nd.d, x.end - x.start, M);
    toast(t('seg.extend.ok', { n: num, a: (before ? before.x : 1).toFixed(2), b: (after ? after.x : 1).toFixed(2) }), 'ok');
  }

  /* ---- selecting lines, one voice for many lines */
  const picked = () => st.filter((x) => $('[data-pick]', x.r).checked);
  let lastPick = -1;
  function updateSel() {
    const k = picked().length;
    $('#seg-selinfo', el).textContent = k ? t('seg.sel.count', { n: k }) : t('seg.sel.none');
    $('#bulk-apply', el).disabled = !k;
    $('#bulk-clear', el).disabled = !k;
    const all = $('#seg-all', el);
    all.checked = n > 0 && k === n;
    all.indeterminate = k > 0 && k < n;
    st.forEach((x) => x.r.classList.toggle('picked', $('[data-pick]', x.r).checked));
  }

  /* ---- events */
  /* ---- follow the playback: the line that the audio / MP4 video / YouTube preview has reached is marked and scrolled into view */
  const starts = st.map((x) => Math.min(x.s.start, x.s.out_start ?? x.s.start));       // a line is "reached" when its caption or its Khmer voice starts
  let nowIdx = -1, nowSec = -1, followPausedUntil = 0, autoScrollUntil = 0;
  const nowBtn = $('#btn-nowline', el);
  const rowAt = (tt) => { let k = -1; for (let i = 0; i < n; i++) { if (starts[i] <= tt + 0.05) k = i; else break; } return k; };
  const shown = (node) => {                               // how much of an element is on the screen (0 .. 1)
    if (!node) return 0;
    const r = node.getBoundingClientRect();
    return r.height ? Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0)) / r.height : 0;
  };
  /* The user is WATCHING the video (it is on the screen): the table must not scroll the picture away - the line is still marked and the
     button in the bar names it. Once the video is scrolled out of view the user is working in the table and the table follows. */
  const watching = () => {
    const panel = syncState ? $('#sync-panel') : (mv && lastPlayer === 'video' ? $('#mp4-panel') : null);
    if (!panel || panel.classList.contains('is-docked')) return false;      // a docked player never scrolls away: the table can follow freely
    return shown(panel) > 0.4;
  };
  function scrollToNow(force) {
    if (nowIdx < 0) return;
    const ae = document.activeElement;
    if (!force && ae && el.contains(ae) && ae.matches('textarea, input, select')) return;     // the user is typing in the table: leave it alone
    if (!force && watching()) return;
    const r = st[nowIdx].r.getBoundingClientRect();
    if (!force && r.top >= 120 && r.bottom <= window.innerHeight - 96) return;               // already in view (below the title bar, above the button bar)
    autoScrollUntil = Date.now() + 1300;
    st[nowIdx].r.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
  function onPlayback(tt, how) {                          // how: 'tick' (playing) | 'seek' (the user moved the playhead)
    if (!n || !Number.isFinite(tt)) return;
    const k = rowAt(tt), changed = k !== nowIdx;
    if (changed) {
      if (nowIdx >= 0) { st[nowIdx].r.classList.remove('active'); st[nowIdx].r.removeAttribute('aria-current'); }
      nowIdx = k;
      if (k >= 0) { st[k].r.classList.add('active'); st[k].r.setAttribute('aria-current', 'true'); }
    }
    if (nowBtn) {
      const sec = Math.floor(tt);
      if (changed || sec !== nowSec) {
        nowSec = sec;
        nowBtn.classList.toggle('hidden', k < 0);
        if (k >= 0) nowBtn.textContent = t('seg.now', { n: k + 1, total: n, time: fmtTime(tt) });
      }
    }
    // follow: a new line while playing -> scroll to it, unless the user scrolled by hand a moment ago; moving the playhead always
    // follows (and starts following again)
    if (how === 'seek') followPausedUntil = 0;
    if (k >= 0 && state.s.subs.follow && (changed || how === 'seek') && Date.now() >= followPausedUntil) scrollToNow(false);
  }
  window.addEventListener('scroll', () => { if (Date.now() > autoScrollUntil) followPausedUntil = Date.now() + 8000; }, { passive: true, signal: ac.signal });
  if (nowBtn) nowBtn.addEventListener('click', () => { followPausedUntil = 0; scrollToNow(true); });
  audio.addEventListener('timeupdate', () => {
    if (syncState) { stopAt = null; return; }                // inside the YouTube preview the audio is only a helper (the preview reports the time)
    const tt = audio.currentTime;
    if (stopAt !== null && stopMedia === 'audio' && tt >= stopAt) { audio.pause(); stopAt = null; }
    onPlayback(tt, 'tick');
  });
  audio.addEventListener('seeked', () => { if (!syncState) onPlayback(audio.currentTime, 'seek'); });
  audio.addEventListener('play', () => { if (!syncState) { lastPlayer = 'audio'; if (mv) mv.pause(); } });     // (inside the YouTube preview the audio is only the helper)
  if (mv) {
    mv.addEventListener('timeupdate', () => {
      if (stopAt !== null && stopMedia === 'video' && mv.currentTime >= stopAt) { mv.pause(); stopAt = null; }
      onPlayback(mv.currentTime, 'tick');
    });
    mv.addEventListener('seeked', () => onPlayback(mv.currentTime, 'seek'));
    mv.addEventListener('play', () => { lastPlayer = 'video'; audio.pause(); });
  }
  tableTick = onPlayback;                                 // the YouTube preview reports its time through this
  const rowOf = (node) => { const r = node.closest('.seg-row'); return r ? st[rows.indexOf(r)] : null; };
  /* ---- click a line -> the video plays from that line (proof-reading the subtitles without hunting for the place in the video) */
  const hasSync = !!$('#btn-sync', el);
  const clickPlayOn = () => state.s.subs.clickplay !== false;
  function playFromRow(i) {
    if (!(i >= 0 && i < n)) return;
    const tt = Math.max(0, starts[i]);                       // the moment that "follow" counts as the start of the line
    if (syncState) {
      if (mv) mv.pause();                                      // one picture at a time
      try { syncState.player.seekTo(tt, true); syncState.player.playVideo(); } catch { syncStartAt = tt; /* the player is still loading: it starts there when it is ready */ }
      return;
    }
    if (mv) { audio.pause(); lastPlayer = 'video'; stopAt = null; mv.currentTime = tt; mv.play().catch(() => {}); return; }
    if (hasSync) { openSync('dub', tt); return; }             // the preview is closed: open it right at that line
    if (!draft) { lastPlayer = 'audio'; stopAt = null; audio.currentTime = tt; audio.play().catch(() => {}); }       // no video at all: the Khmer audio
  }
  let viaPointer = false;
  on('pointerdown', (e) => { viaPointer = !!(e.target.closest && e.target.closest('.seg-row textarea')); });
  on('pointerup', () => { viaPointer = false; });             // (a press inside a box that already has the cursor ends here)
  on('keydown', () => { viaPointer = false; });               // Tab / arrow keys moving into a box must not start the video
  on('focusin', (e) => {                                      // clicking INTO the Khmer box of another line plays that line (a second click in the same box does not)
    const ta = e.target.closest && e.target.closest('.seg-row textarea');
    if (!ta || !viaPointer) return;
    viaPointer = false;
    if (clickPlayOn()) playFromRow(rows.indexOf(ta.closest('.seg-row')));
  });
  on('click', (e) => {
    const go = e.target.closest('[data-go]');
    if (go) {                                                    // play this line - in the player that is being used
      const row = go.closest('.seg-row'), t0 = parseFloat(row.dataset.start), t1 = parseFloat(row.dataset.end) + 0.15;
      if (syncState) { try { syncState.player.seekTo(t0, true); syncState.player.playVideo(); } catch { /* player not ready */ } return; }
      if (mv && lastPlayer === 'video') { audio.pause(); mv.currentTime = t0; stopAt = t1; stopMedia = 'video'; mv.play().catch(() => {}); return; }
      if (mv) mv.pause();
      audio.currentTime = t0; stopAt = t1; stopMedia = 'audio';
      audio.play().catch(() => {});
      return;
    }
    const rowEl = e.target.closest('.seg-row');
    if (rowEl && clickPlayOn() && !e.target.closest('button, a, select, input, label, textarea, summary') && !String(window.getSelection ? window.getSelection() : '')) {
      playFromRow(rows.indexOf(rowEl));                       // anywhere else on the line (its number / time / original text / empty space)
      return;
    }
    const pk = e.target.closest('[data-pick]');
    if (pk) {
      const i = rows.indexOf(pk.closest('.seg-row'));
      if (e.shiftKey && lastPick >= 0) {
        for (let j = Math.min(lastPick, i); j <= Math.max(lastPick, i); j++) $('[data-pick]', st[j].r).checked = pk.checked;
      }
      lastPick = i;
      updateSel();
      return;
    }
    const fl = e.target.closest('[data-flip]');
    if (fl) { const r = fl.closest('.char-row'); r.dataset.gender = r.dataset.gender === 'female' ? 'male' : 'female'; paintAutoLabels(); recompute(); return; }
    if (e.target.closest('#btn-detect')) { detectChars(); return; }
    const ex = e.target.closest('[data-extend]');
    if (ex) { extendRow(rowOf(ex)); return; }
    const tr = e.target.closest('[data-treset]');
    if (tr) { const x = rowOf(tr); x.start = x.s.start; x.ov1 = false; recompute(); return; }
    const pv = e.target.closest('[data-vprev]');
    if (pv) { const x = rowOf(pv); previewLine(textOf(x), x.vs.value, pv); return; }
    if (e.target.closest('#bulk-clear')) { st.forEach((x) => { $('[data-pick]', x.r).checked = false; }); lastPick = -1; updateSel(); return; }
    if (e.target.closest('#bulk-apply')) {
      const v = $('#bulk-voice', el).value;
      if (v === '__none' || !acceptVoice(v)) return;
      picked().forEach((x) => { x.vs.value = v; x.vs.dataset.prev = v; });
      recompute();
    }
  });
  on('change', (e) => {
    const tin = e.target.closest('.tin');
    if (tin) { commitTime(rowOf(tin), tin.dataset.t); return; }
    const cv = e.target.closest('.char-voice');
    if (cv) {
      if (cv.value === '__none' || !acceptVoice(cv.value)) { cv.value = cv.dataset.prev || ''; return; }
      cv.dataset.prev = cv.value;
      paintAutoLabels(); recompute();
      return;
    }
    const sel = e.target.closest('.vsel');
    if (sel) {
      if (sel.value === '__none' || !acceptVoice(sel.value)) { sel.value = sel.dataset.prev || ''; return; }
      sel.dataset.prev = sel.value;
      recompute();
      return;
    }
    if (e.target.id === 'seg-all') { st.forEach((x) => { $('[data-pick]', x.r).checked = e.target.checked; }); lastPick = -1; updateSel(); }
  });
  on('keydown', (e) => {
    const tin = e.target.closest && e.target.closest('.tin');
    if (!tin || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
    e.preventDefault();
    const x = rowOf(tin), which = tin.dataset.t;
    const cur = parseClock(tin.value) ?? (which === 'start' ? x.start : x.end);
    tin.value = fmtClock(Math.max(0, Math.round((cur + (e.shiftKey ? 1 : 0.1) * (e.key === 'ArrowUp' ? 1 : -1)) * 10) / 10));
    commitTime(x, which);
  });
  on('input', (e) => {
    if (e.target.matches('.seg-row textarea')) { autoGrow(e.target); recompute(); }
    else if (e.target.matches('.char-name')) recompute();
  });

  $('#btn-regen', el).addEventListener('click', async () => {
    if (draft) {                                           // lines still without Khmer text would stay silent
      const empty = st.filter((x) => !textOf(x)).length;
      if (empty === n) { toast(t('cl.err.none'), 'bad'); return; }
      if (empty && !window.confirm(t('cl.confirm_empty', { n: empty }))) return;
    }
    const edits = [];
    for (const x of st) {
      const c = changed(x);
      if (!isDirty(c)) continue;
      if (x.ov1 && x.end - x.start < MIN_WIN) {
        toast(t('seg.err.range', { n: x.idx + 1, s: MIN_WIN }), 'bad');
        x.b.focus(); x.r.scrollIntoView({ block: 'center', behavior: 'smooth' });
        return;
      }
      const e = { idx: x.idx };
      if (c.km) e.km = textOf(x);
      if (c.voice) e.voice = x.vs.value || null;
      if (c.t0) e.t0 = curT0(x);
      if (c.t1) e.t1 = curT1(x);
      edits.push(e);
    }
    const cedits = [];
    for (const x of cs) {
      const c = charChanged(x);
      if (!charDirty(c)) continue;
      const e = { id: x.id };
      if (c.gender) e.gender = x.r.dataset.gender;
      if (c.voice) e.voice = x.vs.value;
      if (c.name) e.name = x.name.value.trim();
      cedits.push(e);
    }
    const planned = state.s.voice.auto.on ? Object.values(autoPlan(charsNow())) : [];       // the voices the characters are going to get
    const used = new Set([...st.map((x) => x.vs.value), ...planned].filter(Boolean));
    if ([...used].some((v) => v.startsWith('vox:'))) {
      if (state.vox && !state.vox.installed) { toast(t('err.VOX_NOT_INSTALLED'), 'bad'); showPage('settings'); return; }
      if ([...used].some((v) => v === 'vox:original' || v.startsWith('vox:s')) && !hasSrcMedia(job)) { toast(t('err.VOX_NO_ORIGINAL'), 'bad'); return; }
      if ([...used].some(isCloneVoice) && !state.s.voice.vox.consent) { toast(t('err.VOX_CONSENT_REQUIRED'), 'bad'); return; }
    }
    if (st.some((x) => curT0(x) !== null || x.ov1) && state.s.output.sync === 'natural') toast(t('seg.natural'));
    const restore = releaseMedia();
    try {
      closeSync();
      await api(`/api/jobs/${job.id}/regenerate`, { method: 'POST', body: { segments: edits, characters: cedits, voice: voiceBody(), output: outputBody(), youtube: youtubeBody() } });
      editorDraft = null;
      toast(t('toast.regen_started'));
      $('#dub-result').classList.add('hidden');
      updateDock();
      trackJob('dub', job.id);
    } catch (e2) { restore(); toast(errText(e2), 'bad'); }
  });
  const sb = $('#btn-sync', el);
  if (sb) sb.addEventListener('click', () => (syncState ? closeSync() : openSync('dub')));
  const rb = $('#btn-reframe', el);
  if (rb) rb.addEventListener('click', () => remakeVideo(job));
  if (mv) mv.addEventListener('loadedmetadata', applySubs);
  wireClaude(job, el, hooks);
  applySubs();
}

function renderTtsResult(job, el) {
  const meta = job.meta || {};
  el.innerHTML = `
    <div class="card-head"><span class="step-badge">${icon('check')}</span><h2>${esc(t('tts.result'))}</h2>${statusChip(job.status)}</div>
    <div class="player-box">
      <b>${icon('mic')} ${esc(voiceLabel(job.params?.voice))}</b>
      <audio controls preload="metadata" src="${fileUrl(job, 'speech.mp3')}"></audio>
      <div class="stats"><span>${esc(t('res.duration'))} <b>${fmtTime(meta.audio_duration || 0)}</b></span></div>
      <div class="dl-row">${dlBtn(fileUrl(job, 'speech.mp3', true), 'download', t('dl.mp3'), true)}</div>
    </div>
    <div class="field" style="margin-top:18px">
      <label>${esc(t('tts.km_used'))}</label>
      <textarea class="input" id="tts-km" rows="5" spellcheck="false">${esc(meta.km_text || '')}</textarea>
    </div>
    <div class="row" style="margin-top:12px">
      <button class="btn btn-primary" id="tts-regen" type="button">${icon('reset')}<span>${esc(t('btn.regen'))}</span></button>
    </div>`;
  const ta = $('#tts-km', el);
  autoGrow(ta);
  ta.addEventListener('input', () => autoGrow(ta));
  $('#tts-regen', el).addEventListener('click', async () => {
    try {
      await api(`/api/jobs/${job.id}/regenerate`, { method: 'POST', body: { km_text: ta.value.trim(), voice: voiceBody() } });
      toast(t('toast.regen_started'));
      el.classList.add('hidden');
      trackJob('tts', job.id);
    } catch (e) { toast(errText(e), 'bad'); }
  });
}

/* ============================================================ translate with Claude: copy the subtitle, paste the answer */
const CLAUDE_URL = 'https://claude.ai/new';
let claudeMemo = null;                                  // the panel keeps its part and what was filled while the card is drawn again (language switch)
const clList = (nums) => (nums.length > 14 ? `${nums.slice(0, 14).join(', ')} … (${nums.length})` : nums.join(', '));
function claudePanelHtml(job, draft) {
  const sizes = [20, 40, 80, 0];
  return `
    <details class="claude-box" id="claude-box"${draft ? ' open' : ''}>
      <summary>${icon('chat')}<span>${esc(t('cl.title'))}</span><small>${esc(t('cl.sub'))}</small></summary>
      <div class="cl-body">
        <p class="hint" style="margin:0">${esc(t('cl.intro'))}</p>
        <div class="cl-step"><span class="cl-n">1</span><div class="cl-main">
          <b>${esc(t('cl.s1'))}</b>
          <div class="cl-opts">
            <span class="cl-opt">${esc(t('cl.size'))} <span class="seg sm" role="group" aria-label="${esc(t('cl.size'))}">${sizes.map((n) => `<button type="button" data-cl-size="${n}">${n || esc(t('cl.size.all'))}</button>`).join('')}</span></span>
            <span class="cl-opt">${esc(t('cl.names'))} <span class="seg sm" role="group" aria-label="${esc(t('cl.names'))}"><button type="button" data-cl-names="latin">${esc(t('cl.names.latin'))}</button><button type="button" data-cl-names="khmer">${esc(t('cl.names.khmer'))}</button></span></span>
          </div>
          <div class="cl-part">
            <button class="mini" type="button" id="cl-prev" title="${esc(t('cl.prev'))}" aria-label="${esc(t('cl.prev'))}">${icon('left')}</button>
            <span class="lbl" id="cl-partlabel"></span>
            <button class="mini" type="button" id="cl-next" title="${esc(t('cl.next'))}" aria-label="${esc(t('cl.next'))}">${icon('right')}</button>
            <span class="spacer"></span>
            <button class="btn btn-primary btn-sm" type="button" id="cl-copy" disabled>${icon('copy')}<span>${esc(t('cl.copy'))}</span></button>
            <a class="btn btn-sm" id="cl-open" href="${CLAUDE_URL}" target="_blank" rel="noopener noreferrer">${icon('external')}<span>${esc(t('cl.open'))}</span></a>
          </div>
          <div class="cl-only"><span>${esc(t('cl.only'))}</span>
            <button class="btn btn-ghost btn-sm" type="button" id="cl-copy-rules" title="${esc(t('cl.only.tip'))}" disabled>${esc(t('cl.only.rules'))}</button>
            <button class="btn btn-ghost btn-sm" type="button" id="cl-copy-lines" title="${esc(t('cl.only.tip'))}" disabled>${esc(t('cl.only.lines'))}</button></div>
          <details class="cl-preview"><summary>${esc(t('cl.preview'))}</summary><textarea id="cl-prompt" readonly spellcheck="false" rows="8"></textarea></details>
        </div></div>
        <div class="cl-step"><span class="cl-n">2</span><div class="cl-main">
          <b>${esc(t('cl.s2'))}</b>
          <textarea class="input" id="cl-reply" rows="5" spellcheck="false" placeholder="${esc(t('cl.reply.ph'))}"></textarea>
          <div class="cl-actions">
            <button class="btn btn-sm" type="button" id="cl-paste">${icon('paste')}<span>${esc(t('cl.paste'))}</span></button>
            <button class="btn btn-primary btn-sm" type="button" id="cl-apply">${icon('check')}<span>${esc(t('cl.apply'))}</span></button>
            <button class="btn btn-ghost btn-sm" type="button" id="cl-clear">${esc(t('cl.clear'))}</button>
            <span class="spacer"></span><span class="cl-progress" id="cl-progress"></span>
          </div>
          <div class="cl-result" id="cl-result" aria-live="polite"></div>
        </div></div>
      </div>
    </details>`;
}
function wireClaude(job, el, hooks) {
  const box = $('#claude-box', el);
  if (!box) return;
  const cfg = state.s.claude;
  const q = (s) => $(s, box);
  const prev = claudeMemo && claudeMemo.jobId === job.id ? claudeMemo : null;
  const ui = { jobId: job.id, part: prev ? prev.part : 1, parts: 1, first: 1, last: 0, total: hooks.total, text: '', instructions: '', lines: '', seq: 0, applied: prev ? prev.applied : new Set() };     // applied = line numbers filled from pasted answers
  claudeMemo = ui;
  const size = () => Number(cfg.size) || 0;
  const paintOpts = () => {
    $$('[data-cl-size]', box).forEach((b) => b.classList.toggle('active', Number(b.dataset.clSize) === size()));
    $$('[data-cl-names]', box).forEach((b) => b.classList.toggle('active', b.dataset.clNames === cfg.names));
  };
  const paintProgress = () => { q('#cl-progress').textContent = t('cl.progress', { n: hooks.filled(), total: ui.total }); };
  const paint = () => {
    q('#cl-partlabel').textContent = ui.last ? t('cl.part', { p: ui.part, parts: ui.parts, a: ui.first, b: ui.last, total: ui.total }) : '…';
    q('#cl-prev').disabled = ui.part <= 1;
    q('#cl-next').disabled = ui.part >= ui.parts;
    q('#cl-copy').disabled = !ui.text;
    q('#cl-copy-rules').disabled = q('#cl-copy-lines').disabled = !ui.text;
    paintProgress();
  };
  const setResult = (rows) => { q('#cl-result').innerHTML = rows.map(([k, m]) => `<div class="${k}">${esc(m)}</div>`).join(''); };
  hooks.onChange = paintProgress;

  /* the instructions + the numbered lines of the current part come from the server (it knows the glossary and the language) */
  async function load() {
    const seq = ++ui.seq;
    ui.text = ui.instructions = ui.lines = ''; paint();
    try {
      const r = await api(`/api/jobs/${job.id}/translation/prompt`, { method: 'POST', body: { part: ui.part, size: size(), names: cfg.names } });
      if (seq !== ui.seq) return;                         // a newer request is on its way
      Object.assign(ui, { text: r.text, instructions: r.instructions, lines: r.lines_text, part: r.part, parts: r.parts, first: r.first, last: r.last, total: r.total });
      q('#cl-prompt').value = r.text;
    } catch (e) { if (seq === ui.seq) toast(errText(e), 'bad'); }
    if (seq === ui.seq) paint();
  }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch { /* not allowed here: select the text instead */ }
    const ta = q('#cl-prompt');
    q('.cl-preview').open = true;
    ta.focus(); ta.select();
    try { return document.execCommand('copy'); } catch { return false; }
  }
  async function applyReply() {
    const text = q('#cl-reply').value;
    if (!text.trim()) { setResult([['warn', t('cl.status.empty')]]); q('#cl-reply').focus(); return; }
    let r;
    try { r = await api(`/api/jobs/${job.id}/translation/parse`, { method: 'POST', body: { text, first: ui.first, last: ui.last } }); }
    catch (e) { setResult([['bad', errText(e)]]); return; }
    if (!r.count) { setResult([['bad', t('cl.status.none')]]); return; }
    hooks.apply(r.items);
    r.items.forEach((it) => ui.applied.add(it.idx + 1));
    let saved = null;                                              // a draft keeps the lines in the job right away (no audio yet, so nothing gets out of date)
    if (hooks.draft) {
      try { await api(`/api/jobs/${job.id}/translation/save`, { method: 'POST', body: { items: r.items } }); hooks.commit(r.items); saved = true; }
      catch (e) { saved = e; }
    }
    const rows = [], got = r.range[1];
    const still = [];                                              // lines of this part that no pasted answer has filled yet (answers may arrive in several pieces)
    for (let n = ui.first; n <= ui.last; n++) if (!ui.applied.has(n)) still.push(n);
    const cut = got < ui.last && still.some((n) => n > got);       // the answer stops before the end of the part
    const gaps = still.filter((n) => n < got);
    rows.push([still.length ? 'warn' : 'ok', t('cl.status.ok', { n: r.count, a: r.range[0], b: r.range[1] })]);
    if (saved === true) rows.push(['ok', t('cl.status.saved')]);
    else if (saved) rows.push(['warn', t('cl.status.savefail', { msg: errText(saved) })]);
    if (r.positional) rows.push(['warn', t('cl.status.positional', { n: r.count })]);
    if (gaps.length) rows.push(['warn', t('cl.status.missing', { n: gaps.length, list: clList(gaps) })]);
    if (cut) rows.push(['warn', t('cl.status.cut', { a: got, b: got + 1 })]);
    if (r.no_khmer.length) rows.push(['warn', t('cl.status.nokhmer', { list: clList(r.no_khmer) })]);
    if (r.unknown.length) rows.push(['warn', t('cl.status.unknown', { list: clList(r.unknown) })]);
    if (r.duplicates.length) rows.push(['warn', t('cl.status.dupe', { list: clList(r.duplicates) })]);
    const advance = !!ui.last && !still.length && ui.part < ui.parts;      // this part is complete: get the next one ready
    if (advance) {
      const done = ui.part;
      ui.part += 1;
      q('#cl-reply').value = '';
      rows.push(['ok', t('cl.status.next', { p: done, q: ui.part })]);
    }
    if (hooks.filled() >= ui.total) rows.push(['ok', t('cl.status.alldone')]);
    setResult(rows);
    if (advance) await load();
  }

  box.addEventListener('click', async (e) => {
    const sz = e.target.closest('[data-cl-size]');
    if (sz) { cfg.size = Number(sz.dataset.clSize); saveSettings(); ui.part = size() ? Math.floor((ui.first - 1) / size()) + 1 : 1; paintOpts(); load(); return; }
    const nm = e.target.closest('[data-cl-names]');
    if (nm) { cfg.names = nm.dataset.clNames; saveSettings(); paintOpts(); load(); return; }
    if (e.target.closest('#cl-prev')) { ui.part = Math.max(1, ui.part - 1); load(); return; }
    if (e.target.closest('#cl-next')) { ui.part = Math.min(ui.parts, ui.part + 1); load(); return; }
    if (e.target.closest('#cl-copy')) {
      if (!ui.text) return;
      const ok = await copyText(ui.text);
      toast(t(ok ? 'cl.copy.ok' : 'cl.copy.fail'), ok ? 'ok' : 'bad');
      if (ok) {
        const sp = $('span', q('#cl-copy'));
        sp.textContent = t('cl.copied');
        setTimeout(() => { if (sp.isConnected) sp.textContent = t('cl.copy'); }, 1800);
      }
      return;
    }
    const only = e.target.closest('#cl-copy-rules, #cl-copy-lines');
    if (only) {
      const rules = only.id === 'cl-copy-rules', txt = rules ? ui.instructions : ui.lines;
      if (!txt) return;
      const ok = await copyText(txt);
      toast(t(ok ? (rules ? 'cl.only.rules.ok' : 'cl.only.lines.ok') : 'cl.copy.fail'), ok ? 'ok' : 'bad');
      return;
    }
    if (e.target.closest('#cl-paste')) {
      let txt = '';
      try { txt = await navigator.clipboard.readText(); } catch { setResult([['warn', t('cl.paste.denied')]]); q('#cl-reply').focus(); return; }
      q('#cl-reply').value = txt;
      await applyReply();
      return;
    }
    if (e.target.closest('#cl-apply')) { await applyReply(); return; }
    if (e.target.closest('#cl-clear')) { q('#cl-reply').value = ''; setResult([]); }
  });
  box.addEventListener('toggle', () => { if (box.open && !ui.text) load(); });
  paintOpts();
  paint();
  if (box.open) load();
}

/* ============================================================ YouTube sync preview */
let ytApi = null, syncState = null, tableTick = null, ytLastT = -1;
function loadYtApi() {
  if (window.YT && window.YT.Player) return Promise.resolve();
  if (!ytApi) {
    ytApi = new Promise((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { if (prev) prev(); resolve(); };
      const s = document.createElement('script');
      s.src = 'https://www.youtube.com/iframe_api';
      s.onerror = () => { ytApi = null; reject(new Error('YouTube player could not be loaded')); };
      document.head.append(s);
      setTimeout(() => { if (!(window.YT && window.YT.Player)) { ytApi = null; reject(new Error('YouTube player timed out')); } }, 15000);
    });
  }
  return ytApi;
}
/* The uploaded video plays in an ordinary <video>; this object answers the few calls the Sync Preview makes to the YouTube player. */
function localPlayer(v, audio, holder, keepSound = false) {
  v.muted = keepSound ? false : !state.s.subs.orig;
  const align = () => { try { audio.currentTime = v.currentTime; } catch { /* not ready */ } };
  v.addEventListener('playing', () => { align(); audio.play().catch(() => {}); });
  v.addEventListener('seeked', () => { align(); if (!v.paused) audio.play().catch(() => {}); });
  ['pause', 'ended', 'waiting'].forEach((ev) => v.addEventListener(ev, () => audio.pause()));
  v.addEventListener('error', () => { if (!holder.querySelector('.notice')) holder.insertAdjacentHTML('beforeend', `<div style="margin-top:10px">${noticeHtml('warn', t('up.sync.cantplay'))}</div>`); });
  return {
    getCurrentTime: () => v.currentTime,
    getPlayerState: () => (v.ended ? 0 : v.paused ? 2 : (v.seeking || v.readyState < 3) ? 3 : 1),        // the YouTube numbers: 1 playing, 2 paused, 3 buffering, 0 ended
    seekTo: (sec) => { v.currentTime = sec; },
    playVideo: () => { v.play().catch(() => {}); },
    mute: () => { v.muted = true; },
    unMute: () => { v.muted = false; },
    destroy: () => { v.pause(); v.removeAttribute('src'); v.load(); },
  };
}
const NO_AUDIO = { currentTime: 0, paused: true, play: () => Promise.resolve(), pause() {}, style: {} };      // a draft has no Khmer voice yet: the preview code still wants an "audio"
let syncOpening = false, syncStartAt = null;                  // syncStartAt: where the preview starts playing (a line was clicked)
async function openSync(kind, startAt) {
  const job = state.jobs[kind];
  const holder = $('#sync-holder');
  const draft = !!(job && job.meta && job.meta.draft);
  const audio = $('#dub-audio') || (draft ? NO_AUDIO : null);
  if (!job || !holder || !audio || !job.video) return;
  if (Number.isFinite(startAt)) syncStartAt = Math.max(0, startAt);
  if (syncOpening) return;                                    // a second click while the player is still loading: the line is remembered
  syncOpening = true;
  try {
    const local = isUploadJob(job);
    holder.innerHTML = `<div class="dockable" id="sync-panel">${dockHead('sync')}<div class="dock-body"><div class="sub-toolbar" id="sync-subs">${draft ? subToggle('en') : subToggle('en') + subToggle('km') + subToggle('orig') + subToggle('duck')}</div>`
      + `<div class="yt-frame">${local ? `<video id="up-player" playsinline controls preload="metadata"${job.video.thumbnail ? ` poster="${esc(job.video.thumbnail)}"` : ''} src="/api/jobs/${job.id}/source"></video>` : '<div id="yt-player"></div>'}`
      + `<aside class="hs-live hidden" data-hs-live aria-hidden="true"><i class="hs-fx" data-fx="blur"></i></aside>`
      + `<aside class="sub-overlay" id="sub-overlay"><div class="sub-line en"></div><div class="sub-line km"></div></aside></div></div></div>`;
    updateHsUi();
    updateDock();
    let player;
    const applyStart = () => {
      if (syncStartAt === null) return;
      try { player.seekTo(syncStartAt, true); player.playVideo(); syncStartAt = null; } catch { /* not ready yet - called again when the player is */ }
    };
    if (local) {
      audio.pause();
      player = localPlayer($('#up-player'), audio, holder, draft);
      applyStart();
    } else {
      try { await loadYtApi(); } catch (e) { holder.innerHTML = noticeHtml('warn', e.message); return; }
      audio.pause();
      player = new YT.Player('yt-player', {
        videoId: job.video.id, width: '100%', height: '100%',
        playerVars: { playsinline: 1, rel: 0, modestbranding: 1 },
        events: {
          onReady: (ev) => { if (draft || state.s.subs.orig) ev.target.unMute(); else ev.target.mute(); if (syncState) syncState.origOn = null; applyStart(); },
          onStateChange: (ev) => {
            if (ev.data === YT.PlayerState.PLAYING) { audio.currentTime = player.getCurrentTime(); audio.play().catch(() => {}); }
            else if (ev.data === YT.PlayerState.PAUSED || ev.data === YT.PlayerState.ENDED || ev.data === YT.PlayerState.BUFFERING) audio.pause();
          },
        },
      });
    }
    const timer = setInterval(() => {
      try {
        if (player.getPlayerState && player.getPlayerState() === 1) {          // 1 = playing (YouTube and the local player use the same numbers)
          const vt = player.getCurrentTime();
          if (Math.abs(audio.currentTime - vt) > 0.45) audio.currentTime = vt;
          if (audio.paused) audio.play().catch(() => {});
        }
      } catch { /* player not ready */ }
    }, 500);
    syncState = { player, timer, subTimer: setInterval(updateSubs, 120) };
    audio.style.opacity = '.55';
    const b = $('#btn-sync');
    if (b) b.querySelector('span').textContent = t('res.sync.close');
  } finally { syncOpening = false; }
}
function closeSync() {
  syncStartAt = null;
  if (!syncState) return;
  clearInterval(syncState.timer);
  clearInterval(syncState.subTimer);
  try { syncState.player.destroy(); } catch { /* ignore */ }
  syncState = null;
  ytLastT = -1;
  const holder = $('#sync-holder'); if (holder) holder.innerHTML = '';
  updateDock();
  const audio = $('#dub-audio'); if (audio) { audio.pause(); audio.style.opacity = ''; }
  const b = $('#btn-sync'); if (b) b.querySelector('span').textContent = t('res.sync.open');
}

/* ============================================================ history */
async function refreshHistoryBadge() {
  try {
    const { jobs } = await api('/api/jobs');
    const b = $('#hist-badge');
    b.textContent = jobs.length; b.classList.toggle('hidden', !jobs.length);
    return jobs;
  } catch { return []; }
}
async function loadHistory() {
  const jobs = await refreshHistoryBadge();
  $('#hist-count').textContent = t('hist.count', { n: jobs.length });
  const list = $('#hist-list');
  if (!jobs.length) {
    list.innerHTML = `<div class="card empty">${icon('history')}<div>${esc(t('hist.empty'))}</div></div>`;
    return;
  }
  list.innerHTML = `<div class="hist-grid">${jobs.map((j) => {
    const thumb = j.video && j.video.thumbnail
      ? `<img src="${esc(j.video.thumbnail)}" alt="" referrerpolicy="no-referrer" loading="lazy" onerror="this.remove()">`
      : icon(j.kind === 'tts' ? 'mic' : 'doc');
    const voice = voiceLabel(j.params?.voice);
    const when = new Date(j.created * 1000).toLocaleString(state.lang === 'km' ? 'km-KH' : undefined, { dateStyle: 'medium', timeStyle: 'short' });
    return `
    <div class="card hist-card">
      <div class="hist-thumb">${thumb}<span class="chip">${esc(t('hist.kind.' + j.kind))}${LANG_NAME[j.meta?.src_lang] ? ` · ${esc(LANG_NAME[j.meta.src_lang])}` : ''}</span></div>
      <div class="hist-body">
        <div class="hist-title">${esc(j.title || '—')}</div>
        <div class="hist-meta">${esc(when)} · ${esc(voice)}${j.meta?.audio_duration ? ` · ${fmtTime(j.meta.audio_duration)}` : ''}</div>
        <div class="row" style="margin-top:auto">${j.meta?.draft && j.status === 'done' ? `<span class="chip warn">${esc(t('hist.draft'))}</span>` : statusChip(j.status)}<span class="spacer"></span>
          <button class="btn btn-sm" data-open="${j.id}" type="button">${esc(t('hist.open'))}</button>
          <button class="btn btn-sm btn-ghost btn-danger" data-del="${j.id}" type="button" aria-label="${esc(t('hist.delete'))}">${icon('trash')}</button></div>
      </div>
    </div>`;
  }).join('')}</div>`;
}
async function openJob(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    const kind = job.kind;
    state.tracking[kind] = null;
    state.jobs[kind] = job;
    showPage(kind === 'dub' ? 'dub' : 'tts');
    if (kind === 'dub' && job.video && job.video.id) {
      $('#yt-url').value = job.video.url || '';
      state.video = { ...job.video, captions: null, notes: [] };
      state.videoUrl = job.video.url || '';
      setSourceTab('youtube');
      renderVideoCard(state.video);
    }
    if (kind === 'tts') {
      $('#tts-text').value = job.meta?.source_text || '';
      state.s.tts.input_lang = job.params?.input_lang || 'km';
      syncBindings(); updateDerived(); updateCounters();
    }
    renderJob(kind, true);
    if (!DONE.includes(job.status)) trackJob(kind, id);
    setTimeout(() => ($(kind === 'dub' ? '#dub-result' : '#tts-result').scrollIntoView({ behavior: 'smooth', block: 'start' })), 150);
  } catch (e) { toast(errText(e), 'bad'); }
}
document.addEventListener('click', async (e) => {
  const open = e.target.closest('[data-open]');
  if (open) { openJob(open.dataset.open); return; }
  const del = e.target.closest('[data-del]');
  if (del && confirm(t('hist.confirm'))) {
    try {
      await api(`/api/jobs/${del.dataset.del}`, { method: 'DELETE' });
      ['dub', 'tts'].forEach((k) => { if (state.jobs[k]?.id === del.dataset.del) { state.jobs[k] = null; $(k === 'dub' ? '#dub-result' : '#tts-result').classList.add('hidden'); $(k === 'dub' ? '#dub-progress' : '#tts-progress').classList.add('hidden'); } });
      toast(t('toast.deleted'), 'ok'); loadHistory();
    } catch (err) { toast(errText(err), 'bad'); }
  }
});

/* ============================================================ terms (glossary) */
const countTerms = (text) => text.split('\n').filter((l) => l.trim() && !l.trim().startsWith('#')).length;
function updateTermsState() {
  const ed = $('#terms-editor');
  $('#terms-count').textContent = t('terms.count', { n: countTerms(ed.value) });
  $('#terms-state').textContent = state.termsDirty ? t('terms.dirty') : '';
}
async function loadTerms() {
  if (state.termsDirty) return;
  try {
    const g = await api('/api/glossary');
    $('#terms-editor').value = g.text;
    state.termsDirty = false; updateTermsState();
  } catch (e) { toast(errText(e), 'bad'); }
}

/* ============================================================ settings / system */
async function loadSystem() {
  try { state.system = await api('/api/system'); } catch { state.system = null; }
  renderSystem();
  if (state.system) checkUiVersion(state.system.version);
}
/* An old page / cached tab talking to a newer server: reload once to pick up the new files (the flag prevents a loop). */
function checkUiVersion(serverVer) {
  if (!serverVer || serverVer === KDS_UI_VERSION) return;
  const key = 'kds-ui-reload-' + serverVer;
  try {
    if (!sessionStorage.getItem(key)) { sessionStorage.setItem(key, '1'); location.reload(); }
  } catch { /* storage blocked: nothing to do */ }
}
function renderSystem() {
  const s = state.system;
  const foot = $('#sys-status');
  if (!s) { foot.innerHTML = `<div class="sys-row"><span class="dot bad"></span>Server offline</div>`; return; }
  // dot: ok = green, bad = red, off = hollow grey (optional component that is simply not installed)
  const row = (ok, label, tip) => `<div class="sys-row"${tip ? ` title="${esc(tip)}"` : ''}><span class="dot ${ok === true ? 'ok' : ok === false ? 'bad' : ok === 'off' ? 'off' : 'warn'}"></span>${esc(label)}</div>`;
  foot.innerHTML = row(!!s.ffmpeg.ok, 'ffmpeg') + row(!!s.edge_tts, `Edge TTS ${s.edge_tts || ''}`) + row(!!s.yt_dlp, `yt-dlp ${s.yt_dlp || ''}`)
    + row(s.whisper ? true : 'off', t(s.whisper ? 'sys.whisper.on' : 'sys.whisper.off'), t('sys.whisper.tip'))
    + (() => { const vx = s.vox || {}; return row(vx.installed ? (vx.state === 'ready' ? true : 'warn') : 'off', t(vx.installed ? `sys.vox.${vx.state || 'stopped'}` : 'sys.vox.none'), t('sys.vox.tip')); })();
}

/* ---- Settings → Test Google Translate (shows which route works and how fast) */
function renderGtResult(r) {
  const sum = $('#gt-test-summary'), box = $('#gt-test-result');
  const modeName = (m) => t(m === 'direct' ? 'set.gt.mode.direct' : 'set.gt.mode.default');
  const rows = (r.results || []).map((x) => `<tr><td class="mono">${esc(x.route)}</td><td>${esc(modeName(x.mode))}</td>`
    + `<td class="${x.ok ? 'gt-ok' : 'gt-bad'}">${esc(x.ok ? '✓ ' + t('set.gt.ok') : '✗ ' + (x.error || 'error'))}</td><td>${x.ms == null ? '' : esc(x.ms + ' ms')}</td></tr>`).join('');
  const proxies = Object.entries(r.proxies || {}).map(([k, v]) => `${k}=${v}`).join(', ');
  box.innerHTML = `<div style="overflow-x:auto"><table class="gt-table"><thead><tr><th>${esc(t('set.gt.col.route'))}</th><th>${esc(t('set.gt.col.conn'))}</th><th>${esc(t('set.gt.col.result'))}</th><th>${esc(t('set.gt.col.time'))}</th></tr></thead><tbody>${rows}</tbody></table></div>`
    + (proxies ? `<p class="hint">${esc(t('set.gt.proxy'))}<span class="mono">${esc(proxies)}</span>${esc(t('set.gt.proxy2'))}</p>` : '');
  sum.className = 'small'; sum.style.color = (r.verdict === 'ok' || r.verdict === 'partial') ? 'var(--ok)' : 'var(--danger)';
  sum.textContent = t('set.gt.v.' + r.verdict);
}
async function runGoogleTest() {
  const btn = $('#gt-test'), sum = $('#gt-test-summary'), box = $('#gt-test-result');
  btn.disabled = true; state.gt = null; sum.className = 'small muted'; sum.style.color = ''; sum.textContent = t('set.gt.running'); box.innerHTML = '';
  try {
    state.gt = await api('/api/translate/diagnose');
    renderGtResult(state.gt);
  } catch (e) { sum.className = 'small'; sum.style.color = 'var(--danger)'; sum.textContent = t('set.test.fail') + e.message; }
  finally { btn.disabled = false; }
}

/* ============================================================ docked players (v1.6): the video stays fixed on the right while the page scrolls */
const dockMq = window.matchMedia('(min-width: 1180px)');             // narrower windows keep the players inside the page (no room for a side panel)
const dockHead = (id) => `<div class="dock-head"><b>${icon(id === 'mp4' ? 'video' : 'dub')}<span>${esc(t(id === 'mp4' ? 'dock.mp4' : isUploadJob(state.jobs.dub) ? 'dock.sync.upload' : 'dock.sync'))}</span></b><span class="spacer"></span>`
  + `<button class="mini" type="button" data-dock="min" title="${esc(t('dock.min'))}" aria-label="${esc(t('dock.min'))}">${icon('minus')}</button>`
  + `<button class="mini" type="button" data-dock="pin" title="${esc(t('dock.pin'))}" aria-label="${esc(t('dock.pin'))}">${icon('pin')}</button>`
  + (id === 'sync' ? `<button class="mini" type="button" data-dock="close" title="${esc(t('res.sync.close'))}" aria-label="${esc(t('res.sync.close'))}">${icon('x')}</button>` : '')
  + '</div>';
function updateDock() {
  const live = (node) => !!node && state.page === 'dub' && !node.closest('.hidden');       // inside a visible result card
  const sync = $('#sync-panel'), mp4 = $('#mp4-panel');
  const want = !!(state.s.ui && state.s.ui.dock) && dockMq.matches;
  const owner = live(sync) ? 'sync' : live(mp4) ? 'mp4' : null;                            // one player at a time owns the dock - the YouTube preview wins
  [['sync', sync], ['mp4', mp4]].forEach(([id, node]) => {
    if (!node) return;
    const docked = want && owner === id, min = docked && !!state.s.ui.dockMin;
    node.classList.toggle('is-docked', docked);
    node.classList.toggle('is-min', min);
    node.classList.toggle('dock-wait', want && owner !== id);                              // the dock is taken by the other player: nothing to pin here
    const pin = $('[data-dock="pin"]', node), mn = $('[data-dock="min"]', node);
    if (pin) { const k = docked ? 'dock.unpin' : 'dock.pin'; pin.setAttribute('aria-pressed', docked ? 'true' : 'false'); pin.title = t(k); pin.setAttribute('aria-label', t(k)); }
    if (mn) mn.setAttribute('aria-pressed', min ? 'true' : 'false');
  });
  document.body.classList.toggle('has-dock', want && !!owner);                            // the page makes room on the right
}
dockMq.addEventListener('change', updateDock);
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-dock]');
  if (!b) return;
  const k = b.dataset.dock;
  if (k === 'close') { closeSync(); return; }
  if (k === 'pin') state.s.ui.dock = !state.s.ui.dock;
  if (k === 'min') state.s.ui.dockMin = !state.s.ui.dockMin;
  saveSettings();
  updateDock();
});

/* ============================================================ the menu (sidebar) slides out and in */
function applySide(collapsed, persist) {
  document.documentElement.classList.toggle('side-collapsed', collapsed);
  const b = $('#side-toggle');
  if (b) { const k = collapsed ? 'nav.show' : 'nav.hide'; b.setAttribute('aria-expanded', collapsed ? 'false' : 'true'); b.title = t(k); b.setAttribute('aria-label', t(k)); }
  if (persist) { try { localStorage.setItem('kds_side', collapsed ? '1' : '0'); } catch { /* no storage */ } }
}

/* ============================================================ voices: labels, subtitles toggles */
const voxAll = () => (state.voices.vox || {}).custom || [];
/* VoxCPM2 voices: the speaker of the video, one of the 8 designed voices, or one of My voices. */
function normalizeVoxId() {
  const x = state.s.voice.vox, id = x.id || '';
  const presets = (state.voices.vox || {}).presets || [];
  const ok = id === 'vox:original'
    || (id.startsWith('vox:c:') && (!state.voicesLoaded || voxAll().some((v) => v.id === id)))
    || (id.startsWith('vox:p:') && (!state.voicesLoaded || presets.some((p) => p.id === id)));
  if (!ok) { x.id = 'vox:original'; saveSettings(); }
}
/* Load the model in the background as soon as VoxCPM2 is picked, so the first line does not wait 20-60 s for it. */
function prewarmVox() {
  const s = state.vox;
  if (!s || !s.installed || (s.setup && s.setup.running)) return;
  if (voxStateKey(s) === 'stopped') voxAction('start');
}
/* Rough time estimate from the speed measured at install time (balanced = 10 steps). Per generated step the model runs
   ~48 fixed layers + 12 per diffusion step, so the quality setting scales the time like this. */
const VOX_STEPS = { fast: 6, balanced: 10, high: 20 };
function voxQualityHint() {
  const sp = state.vox && state.vox.speed;
  if (!sp || !sp.measured || !(sp.rtf > 0)) return '';
  if (((state.vox.worker || {}).turbo || {}).state === 'on') return '';        // the install-time speed no longer applies
  const f = (k) => (sp.rtf * (48 + 12 * VOX_STEPS[k]) / 168).toFixed(1);
  return t('vox.quality.est', { f: f('fast'), b: f('balanced'), h: f('high') });
}
function voiceLabel(v) {
  if (!v) return '';
  if (v.engine === 'voxcpm') {
    const id = (v.vox && v.vox.id) || '';
    return `VoxCPM2 · ${voiceName(id) || id}`;
  }
  return (v.id || '').replace('km-KH-', '').replace('Neural', '');
}
/* "Mute the original voice while Khmer speaks" is ONE setting (output.duck): used by the MP4 export and by this preview. */
const subOn = (k) => (k === 'duck' ? !!state.s.output.duck : !!state.s.subs[k]);
const subToggle = (k) => `<button type="button" class="tog" data-sub="${k}" aria-pressed="${subOn(k) ? 'true' : 'false'}">${icon(k === 'orig' ? 'volume' : k === 'duck' ? 'volmute' : k === 'follow' ? 'follow' : k === 'clickplay' ? 'play' : 'cc')}<span>${esc(t('sub.' + k, k === 'en' ? { lang: LANG_NAME[srcLangOf(state.jobs.dub)] } : undefined))}</span></button>`;
const setText = (el, txt) => { if (el && el.textContent !== txt) el.textContent = txt; };
function updateSubs() {
  const ov = $('#sub-overlay');
  if (!ov || !syncState) return;
  let tc = 0;
  try { tc = syncState.player.getCurrentTime(); } catch { return; }
  if (tableTick && tc !== ytLastT) {                    // the table marks (and follows) the line the preview has reached
    const jumped = ytLastT >= 0 && Math.abs(tc - ytLastT) > 1.2;
    ytLastT = tc;
    tableTick(tc, jumped ? 'seek' : 'tick');
  }
  const segs = (state.jobs.dub && state.jobs.dub.segments) || [];
  const en = state.s.subs.en ? ((segs.find((s) => tc >= s.start && tc < s.end) || {}).en || '') : '';
  const km = state.s.subs.km ? ((segs.find((s) => s.out_start != null && tc >= s.out_start && tc < s.out_end) || {}).km || '') : '';
  const enLine = $('.sub-line.en', ov);
  if (enLine) enLine.lang = LANG_HTML[srcLangOf(state.jobs.dub)] || 'en';
  setText(enLine, en);
  setText($('.sub-line.km', ov), km);
  // Original sound: on only if the user wants it AND (auto-mute is off OR nobody is speaking right now).
  const draftJob = !!(state.jobs.dub && state.jobs.dub.meta && state.jobs.dub.meta.draft);
  let want = draftJob || !!state.s.subs.orig;                   // a draft has no Khmer voice yet: the original sound is the only sound
  if (want && !draftJob && state.s.output.duck) want = !duckAt(segs, tc);
  if (syncState.origOn !== want) {
    syncState.origOn = want;
    try { if (want) syncState.player.unMute(); else syncState.player.mute(); } catch { /* player not ready */ }
  }
}
/* Same rule as the MP4 export (app/audio.py): the original sound is muted while the original speaker or the Khmer voice speaks. */
const DUCK = { pre: 0.10, post: 0.22, gap: 0.50 };
function duckIntervals(segs) {
  const win = [];
  for (const s of segs) {
    if (!(s.km || '').trim()) continue;                       // nothing replaces this caption (e.g. [Music]) -> leave it alone
    win.push([s.start, s.end]);
    if (s.out_start != null) win.push([s.out_start, s.out_end]);
  }
  win.sort((x, y) => x[0] - y[0]);
  const out = [];
  for (const [a0, b0] of win) {
    if (!(b0 > a0)) continue;
    const a = Math.max(0, a0 - DUCK.pre), b = b0 + DUCK.post, last = out[out.length - 1];
    if (last && a - last[1] <= DUCK.gap) last[1] = Math.max(last[1], b); else out.push([a, b]);
  }
  return out;
}
let duckCache = { segs: null, n: -1, iv: [] };
function duckAt(segs, tc) {
  if (duckCache.segs !== segs || duckCache.n !== segs.length) duckCache = { segs, n: segs.length, iv: duckIntervals(segs) };
  for (const [a, b] of duckCache.iv) { if (tc < a) return false; if (tc <= b) return true; }
  return false;
}
function applySubs() {
  if (syncState) {
    syncState.origOn = null;          // force the mute state to be applied again
    updateSubs();
  }
  const tbl = $('#dub-result .seg-table');
  if (tbl) { tbl.classList.toggle('hide-en', !state.s.subs.en); tbl.classList.toggle('clickplay', !!state.s.subs.clickplay); }   // the English column of the editor follows the same switch
  const v = $('#dub-result video');
  if (v && v.textTracks && v.textTracks.length >= 2) {
    v.textTracks[0].mode = state.s.subs.en ? 'showing' : 'hidden';
    v.textTracks[1].mode = state.s.subs.km ? 'showing' : 'hidden';
  }
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-sub]');
  if (!b) return;
  const k = b.dataset.sub;
  if (k === 'duck') state.s.output.duck = !state.s.output.duck; else state.s.subs[k] = !state.s.subs[k];
  saveSettings();
  $$(`[data-sub="${k}"]`).forEach((x) => x.setAttribute('aria-pressed', subOn(k) ? 'true' : 'false'));
  syncBindings();                      // keeps the switch in the Output card in step
  applySubs();
});

/* ============================================================ VoxCPM2 (optional local engine) */
function voxCardHtml(v) {
  const original = v.kind === 'original', designed = v.kind === 'designed';
  const chips = [];
  if (designed) {
    chips.push(`<span class="chip">${esc(t(v.gender === 'Female' ? 'voice.female' : 'voice.male'))}</span>`);
  } else {
    chips.push(`<span class="chip ok">${esc(t('vox.chip.clone'))}</span>`);
    if (!original) {
      chips.push(v.gender ? `<span class="chip" data-voxgender-chip>${esc(t(v.gender === 'Female' ? 'voice.female' : 'voice.male'))}</span>`
        : `<span class="chip warn" data-voxgender-chip title="${esc(t('vox.gender.unknown.tip'))}">${esc(t('vox.gender.unknown'))}</span>`);
      if (v.duration) chips.push(`<span class="chip">${esc(t('vox.chip.sec', { n: Math.round(v.duration) }))}</span>`);
    }
  }
  const dk = designed ? `vox.p.${v.key}.d` : '';
  const name = original ? t('vox.original.name') : designed ? voiceName(v.id) : v.name;
  const sub = original ? `<div class="hint" style="margin:4px 0 0">${esc(t('vox.original.desc'))}</div>`
    : (designed && I18N[state.lang][dk] ? `<div class="hint" style="margin:4px 0 0">${esc(t(dk))}</div>` : '');
  const play = `<button class="play-btn" type="button" data-voxplay="${esc(v.id)}" title="${esc(t('voice.preview'))}" aria-label="${esc(t('voice.preview'))}">${icon('play')}</button>`;
  const act = original ? '<span></span>'
    : designed ? `<div class="vox-actions"><button class="icon-btn" type="button" data-voxreroll="${esc(v.key)}" title="${esc(t('vox.reroll'))}" aria-label="${esc(t('vox.reroll'))}">${icon('dice')}</button>${play}</div>`
      : `<div class="vox-actions"><button class="icon-btn" type="button" data-voxgender="${esc(v.id)}" title="${esc(t('vox.gender.cycle'))}" aria-label="${esc(t('vox.gender.cycle'))}">${icon('swap')}</button><button class="icon-btn" type="button" data-voxrename="${esc(v.id)}" title="${esc(t('vox.rename'))}" aria-label="${esc(t('vox.rename'))}">${icon('edit')}</button><button class="icon-btn" type="button" data-voxdel="${esc(v.id)}" title="${esc(t('vox.delete'))}" aria-label="${esc(t('vox.delete'))}">${icon('trash')}</button>${play}</div>`;
  const label = designed ? `<div class="voice-name">${esc(name)}<span class="voice-sub">${chips.join('')}</span></div>`
    : `<div class="voice-name">${esc(name)}</div><div class="voice-sub">${chips.join('')}</div>`;
  return `
  <div class="voice-card vox${designed ? ' designed' : ''}" role="radio" tabindex="0" data-voxvoice="${esc(v.id)}" aria-checked="false">
    <span class="tick">${icon('check')}</span>
    <div class="avatar ${original ? 'o' : designed ? (v.gender === 'Female' ? 'f' : 'm') : 'c'}">${icon(original ? 'video' : designed ? 'sparkle' : 'mic')}</div>
    <div>${label}${sub}</div>
    ${act}
  </div>`;
}
function renderVoxVoices() {
  const vv = state.voices.vox || { custom: [], presets: [] };
  $$('.voice-block').forEach((block) => {
    const el = $('.vox-groups', block);
    if (!el) return;
    const isTts = !!block.closest('#page-tts');
    const orig = isTts ? '' : `<div class="vox-group-title">${esc(t('vox.group.original'))}</div><div class="vox-picker">${voxCardHtml({ id: 'vox:original', kind: 'original' })}</div>`;
    const designed = (vv.presets || []).length
      ? `<div class="vox-group-title">${esc(t('vox.group.designed'))}</div><p class="hint vox-designed-hint">${esc(t('vox.designed.hint'))}</p><div class="vox-picker vox-picker-grid">${vv.presets.map(voxCardHtml).join('')}</div>` : '';
    const custom = (vv.custom || []).length
      ? `<div class="vox-group-title">${esc(t('vox.group.custom'))}</div><div class="vox-picker">${vv.custom.map(voxCardHtml).join('')}</div>` : '';
    el.innerHTML = orig + designed + custom;
  });
  updateDerived();
}
async function refreshVoices() {
  try { state.voices = await api('/api/voices'); state.voicesLoaded = true; } catch { /* keep the old list */ }
  normalizeVoxId();
  renderVoxVoices();
}

const voxStateKey = (s) => (!s ? 'none' : (s.setup && s.setup.running) ? 'installing' : !s.installed ? 'none' : ((s.worker && s.worker.state) || 'stopped'));
const macKind = (s) => (s && s.hardware && s.hardware.mac) || null;           // null | 'arm64' (Apple Silicon) | 'intel' | 'rosetta' (Intel Python on an Apple chip)
function renderVoxBanners() {
  const s = state.vox;
  let html = '';
  const note = (kind, text, act) => `<div class="notice ${kind}">${icon(kind === 'bad' || kind === 'warn' ? 'alert' : 'info')}<div class="n-body">${esc(text)}${act ? ` <a href="#settings" data-goto="settings">${esc(act)}</a>` : ''}</div></div>`;
  if (s) {
    const k = voxStateKey(s), w = s.worker || {};
    if (k === 'installing') html = note('info', t('set.vox.status.installing'), t('vox.banner.install'));
    else if (!s.installed) html = (macKind(s) === 'intel' || macKind(s) === 'rosetta') ? note('warn', t(`vox.banner.${macKind(s)}`)) : note('warn', t('vox.banner.notinstalled'), t('vox.banner.install'));
    else if (k === 'ready') html = note('info', t('vox.banner.ready'));
    else if (['loading', 'starting', 'idle'].includes(k)) html = note('info', t('vox.banner.loading', { phase: w.phase || '' }));
    else if (k === 'error') html = note('bad', t('vox.banner.error', { msg: (w.error && w.error.message) || '' }));
    else html = note('info', t('vox.banner.off'));
    if (s.installed && macKind(s) !== 'arm64' && !(s.hardware && s.hardware.nvidia) && !(s.install && s.install.cuda) && k !== 'ready') html += note('warn', t('vox.banner.nogpu'));
  }
  $$('.vox-banner').forEach((b) => { b.innerHTML = html; });
}

const voxSetupErr = (code, msg) => { const k = 'set.vox.err.' + code; return I18N[state.lang][k] ? t(k) : msg; };
function renderVoxInstall(s) {
  const box = $('#vox-install-box');
  const su = s.setup || {};
  if (!su.running && !(su.ok === false && su.error && !s.installed)) { box.classList.add('hidden'); box.innerHTML = ''; return; }
  box.classList.remove('hidden');
  const pct = su.pct;
  let html;
  if (su.running) {
    const label = I18N[state.lang]['set.vox.p' + su.phase_idx] ? t('set.vox.p' + su.phase_idx) : (su.phase || '');
    html = `<div class="vox-install"><div class="phase">${esc(t('set.vox.phase', { i: su.phase_idx, n: su.phase_total, text: label }))}${pct != null ? ` · ${pct}% <span class="muted small">${esc(su.pct_text || '')}</span>` : ''}</div>`
      + `<div class="bar ${pct == null ? 'indet' : ''}"><i style="width:${pct == null ? 35 : pct}%"></i></div>`
      + `<pre class="logbox">${esc((su.lines || []).join('\n'))}</pre>`
      + `<div class="row" style="margin-top:10px"><button class="btn btn-sm" type="button" data-vox-cancel>${icon('stop')}<span>${esc(t('set.vox.cancel'))}</span></button></div></div>`;
  } else {
    html = noticeHtml('bad', `${t('set.vox.failed')} ${voxSetupErr(su.error.code, su.error.message)}`, su.error.message)
      + `<pre class="logbox">${esc((su.lines || []).join('\n'))}</pre>`;
  }
  const pre = $('pre', box);
  const keep = pre ? pre.scrollTop : 0;
  box.innerHTML = html;
  const np = $('pre', box);
  if (np) np.scrollTop = su.running ? np.scrollHeight : keep;
}
function renderVox() {
  const card = $('#card-vox');
  if (!card) return;
  const s = state.vox;
  const chip = $('#vox-chip');
  if (!s) { chip.className = 'chip bad'; chip.textContent = 'offline'; return; }
  const k = voxStateKey(s), w = s.worker || {}, su = s.setup || {};
  chip.className = `chip ${{ none: '', installing: 'accent', stopped: 'warn', starting: 'accent', idle: 'accent', loading: 'accent', ready: 'ok', error: 'bad' }[k] || ''}`;
  chip.textContent = t('set.vox.status.' + k);

  // The PC's hardware is not listed any more - only a warning when it will not work well.
  const hw = s.hardware || {}, g = hw.nvidia;
  const mk = macKind(s);
  const gpuOk = !!g || !!(s.install && s.install.cuda) || !!w.gpu || mk === 'arm64';          // the Mac's own GPU (Metal) counts
  let warn = !gpuOk ? t('set.vox.hw.none') : (g && g.vram_gb < 7.5 ? t('set.vox.hw.small') : '');
  if (mk === 'intel') warn = t('set.vox.hw.intel');
  else if (mk === 'rosetta') warn = t('set.vox.hw.rosetta');
  else if (mk === 'arm64' && hw.ram_gb && hw.ram_gb < 15) warn = t('set.vox.hw.macram', { n: hw.ram_gb });
  $('#vox-hw-warn').innerHTML = warn ? `<div class="notice warn" style="margin-bottom:12px">${icon('alert')}<div class="n-body">${esc(warn)}</div></div>` : '';

  const sp = s.speed || {};
  const gpuFail = s.installed && s.install && s.install.selftest && s.install.selftest.gpu_failed;
  $('#vox-speed').textContent = !s.installed ? '' : ((sp.measured ? t('set.vox.speed.measured', { n: sp.rtf }) : t(sp.kind === 'gpu' ? 'set.vox.speed.gpu' : 'set.vox.speed.cpu')) + (gpuFail ? `\n⚠ ${t('set.vox.gpufail')}` : ''));

  const installing = !!su.running;
  const live = ['starting', 'idle', 'loading', 'ready'].includes(w.state);
  const show = (id, on) => { const el = $(id); el.classList.toggle('hidden', !on); el.disabled = installing; };
  show('#vox-install', !s.installed && !installing);
  show('#vox-reinstall', s.installed && !installing);
  show('#vox-start', s.installed && !installing && !live);
  show('#vox-stop', s.installed && !installing && live);
  show('#vox-test', s.installed && !installing);
  if (mk === 'intel' || mk === 'rosetta') { $('#vox-install').disabled = true; $('#vox-reinstall').disabled = true; }       // PyTorch has no build for it
  renderVoxInstall(s);
  const dev = $('#vox-device');
  if (document.activeElement !== dev) dev.value = (s.config && s.config.device) || 'auto';
  // Turbo (experimental): switch + what the engine says about it
  $('#vox-turbo-row').classList.toggle('hidden', !s.installed || mk === 'arm64');           // Turbo = CUDA graphs: an NVIDIA GPU only (not the Mac's Metal GPU)
  const tb = $('#vox-turbo'), want = !!(s.config && s.config.turbo);
  if (document.activeElement !== tb) tb.checked = want;
  const tw = w.turbo || {}, ts = $('#vox-turbo-state');
  ts.style.color = '';
  if (!want) ts.textContent = '';
  else if (tw.state === 'on') { ts.textContent = t('set.vox.turbo.on', { n: tw.graphs || 1 }); ts.style.color = 'var(--ok)'; }
  else if (tw.state === 'failed') { ts.textContent = t('set.vox.turbo.failed', { reason: tw.reason || '?' }); ts.style.color = 'var(--danger)'; }
  else ts.textContent = t(live ? 'set.vox.turbo.pending' : 'set.vox.turbo.next');
}
let voxTimer = null;
function scheduleVoxPoll() {
  clearTimeout(voxTimer);
  const s = state.vox;
  if (s && ((s.setup && s.setup.running) || ['starting', 'idle', 'loading'].includes((s.worker || {}).state))) voxTimer = setTimeout(loadVox, 1500);
}
async function loadVox() {
  try { state.vox = await api('/api/vox/status'); } catch { state.vox = null; }
  if (state.system && state.vox) {
    const w = state.vox.worker || {};
    state.system.vox = { installed: state.vox.installed, state: w.state, device: w.device, gpu: w.gpu };
  }
  renderVox(); renderVoxBanners(); updateDerived();
  if (state.system) renderSystem();
  scheduleVoxPoll();
}
async function voxAction(name, body) {
  try { await api(`/api/vox/${name}`, { method: 'POST', body: body || {} }); } catch (e) { toast(errText(e), 'bad'); }
  await loadVox();
}
async function voxInstall() {
  if (!confirm(t('set.vox.confirm'))) return;
  await voxAction('setup');
}
async function loadVoxLog() {
  const box = $('#vox-log-box');
  if (!box.open) return;
  try {
    const [a, b] = await Promise.all([api('/api/vox/log?which=setup&n=300'), api('/api/vox/log?which=worker&n=120')]);
    $('#vox-log').textContent = `── installer ──\n${a.lines.join('\n')}\n\n── engine ──\n${b.lines.join('\n')}`;
  } catch (e) { $('#vox-log').textContent = e.message; }
}
async function runVoxPreview(voiceId, onDetail, text) {
  const { id } = await api('/api/vox/preview', { method: 'POST', body: { voice: voiceId, quality: state.s.voice.vox.quality, ...(text ? { text } : {}) } });
  for (;;) {
    const st = await api(`/api/vox/preview/${id}`);
    if (st.state === 'done') return st;
    if (st.state === 'error') { const err = new Error(st.message); err.code = st.code; throw err; }
    if (onDetail) onDetail(st.detail || '');
    await sleep(900);
  }
}
async function voxTest() {
  const btn = $('#vox-test'), msg = $('#vox-msg'), au = $('#vox-test-audio');
  btn.disabled = true; au.classList.add('hidden'); au.pause(); au.removeAttribute('src');
  msg.className = 'small muted'; msg.style.color = ''; msg.textContent = t('set.vox.testing');
  try {
    const st = await runVoxPreview('vox:default', (d) => { msg.textContent = `${t('set.vox.testing')} ${d}`; });
    msg.className = 'small'; msg.style.color = 'var(--ok)';
    msg.textContent = t('set.vox.test.ok', { s: st.seconds == null ? '?' : st.seconds, e: st.elapsed == null ? '?' : st.elapsed });
    au.src = st.url; au.classList.remove('hidden'); au.play().catch(() => {});
  } catch (e) { msg.className = 'small'; msg.style.color = 'var(--danger)'; msg.textContent = errText(e); }
  finally { btn.disabled = false; loadVox(); refreshVoices(); }
}
async function previewVox(voiceId, btn) {
  const wasThis = previewBtn === btn;
  stopPreview();
  if (wasThis) return;
  previewBtn = btn;
  btn.innerHTML = icon('spinner', 'spin');
  try {
    const st = await runVoxPreview(voiceId);
    if (previewBtn !== btn) return;
    const a = new Audio(st.url);
    previewAudio = a;
    a.addEventListener('ended', stopPreview);
    await a.play();
    btn.classList.add('playing'); btn.innerHTML = icon('pause');
    refreshVoices(); loadVox();
  } catch (e) {
    if (previewBtn === btn) stopPreview();
    toast(errText(e), 'bad');
    if (e.code === 'VOX_NOT_INSTALLED') showPage('settings');
  }
}
/* The speaker button of a table row: say THIS line (the text as it stands now) with the voice chosen for the row. */
async function previewLine(text, voiceId, btn) {
  const wasThis = previewBtn === btn;
  stopPreview();
  if (wasThis) return;
  if (!text) { toast(t('seg.prev.empty')); return; }
  const v = state.s.voice;
  const id = voiceId || (v.engine === 'voxcpm' ? (v.vox || {}).id : v.id);
  if (id === 'vox:original') { toast(t('seg.prev.original')); return; }
  if (id.startsWith('vox:') && state.vox && !state.vox.installed) { toast(t('err.VOX_NOT_INSTALLED'), 'bad'); return; }
  previewBtn = btn;
  btn.innerHTML = icon('spinner', 'spin');
  try {
    const url = id.startsWith('vox:')
      ? (await runVoxPreview(id, null, text)).url
      : `/api/voices/preview?${new URLSearchParams({ voice: id, rate: v.rate, pitch: v.pitch, volume: v.volume, term_mode: v.term_mode, en_voice: v.en_voice || '', text: text.slice(0, 600) })}`;
    if (previewBtn !== btn) return;
    const a = new Audio(url);
    previewAudio = a;
    a.addEventListener('ended', stopPreview);
    a.addEventListener('error', () => { if (previewAudio === a) { stopPreview(); toast(t('err.TTS_FAILED'), 'bad'); } });
    await a.play();
    if (previewAudio === a) { btn.classList.add('playing'); btn.innerHTML = icon('pause'); }
  } catch (err) {
    if (previewBtn === btn) stopPreview();
    toast(errText(err), 'bad');
  }
}
document.addEventListener('click', async (e) => {
  const vp = e.target.closest('[data-voxplay]');
  if (vp) { e.stopPropagation(); previewVox(vp.dataset.voxplay, vp); return; }
  const rr = e.target.closest('[data-voxreroll]');
  if (rr) {
    e.stopPropagation();
    const key = rr.dataset.voxreroll, block = rr.closest('.voice-block');
    rr.disabled = true;
    try {
      await api(`/api/vox/presets/${key}/reroll`, { method: 'POST' });
      toast(t('vox.rerolled'), 'ok');
      await refreshVoices();
      const pb = $(`[data-voxplay="vox:p:${key}"]`, block || document);
      if (pb) previewVox(`vox:p:${key}`, pb);
    } catch (err) { toast(errText(err), 'bad'); rr.disabled = false; }
    return;
  }
  const dd = e.target.closest('[data-voxdel]');
  if (dd) {
    e.stopPropagation();
    if (!confirm(t('vox.confirm_delete'))) return;
    try {
      await api(`/api/vox/voices/${dd.dataset.voxdel.replace('vox:c:', '')}`, { method: 'DELETE' });
      toast(t('vox.deleted'), 'ok'); await refreshVoices();
    } catch (err) { toast(errText(err), 'bad'); }
    return;
  }
  const gd = e.target.closest('[data-voxgender]');
  if (gd) {                                                       // not set -> woman -> man -> not set: the pitch decided when the clip was added, this corrects it
    e.stopPropagation();
    const id = gd.dataset.voxgender, cur = (voxAll().find((v) => v.id === id) || {}).gender || '';
    const next = cur === '' ? 'Female' : cur === 'Female' ? 'Male' : '';
    try {
      await api(`/api/vox/voices/${id.replace('vox:c:', '')}`, { method: 'PATCH', body: { gender: next } });
      await refreshVoices();
    } catch (err) { toast(errText(err), 'bad'); }
    return;
  }
  const rn = e.target.closest('[data-voxrename]');
  if (rn) {
    e.stopPropagation();
    const id = rn.dataset.voxrename, cur = (voxAll().find((v) => v.id === id) || {}).name || '';
    const name = (window.prompt(t('vox.rename_prompt'), cur) || '').trim();
    if (!name || name === cur) return;
    try {
      await api(`/api/vox/voices/${id.replace('vox:c:', '')}`, { method: 'PATCH', body: { name } });
      toast(t('vox.renamed'), 'ok'); await refreshVoices();
    } catch (err) { toast(errText(err), 'bad'); }
    return;
  }
  if (e.target.closest('[data-vox-cancel]')) { await api('/api/vox/setup/cancel', { method: 'POST' }).catch(() => {}); loadVox(); return; }
  const card = e.target.closest('.voice-card[data-voxvoice]');
  if (card) { state.s.voice.vox.id = card.dataset.voxvoice; saveSettings(); updateDerived(); }
});
/* ---- My voices: add ONE or MANY clips (every clip = one character). The server takes one clip per request, so they go one after the other. */
let voxUploading = false;
const voxStatus = (html) => $$('[data-vox-upload-status]').forEach((el) => { el.innerHTML = html; el.classList.toggle('hidden', !html); });
const readDataUrl = (f) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.onerror = () => rej(new Error('read failed')); r.readAsDataURL(f); });
async function uploadVoiceFiles(list) {
  const files = Array.from(list || []).filter(Boolean);
  if (!files.length) return;
  if (voxUploading) { toast(t('vox.upload.busy'), 'bad'); return; }
  let single = '';
  if (files.length === 1) {                                         // one clip: ask for its name (as before)
    single = (window.prompt(t('vox.name_prompt'), files[0].name.replace(/\.[^.]+$/, '')) || '').trim();
    if (!single) return;
  }
  voxUploading = true;
  const taken = new Set(voxAll().map((v) => String(v.name).toLowerCase()));
  const nameFor = (f) => {                                          // the file name, made different from every other voice
    if (single) return single;
    const base = (f.name.replace(/\.[^.]+$/, '').trim() || 'My voice').slice(0, 54);
    let nm = base, k = 2;
    while (taken.has(nm.toLowerCase())) nm = `${base} ${k++}`;
    taken.add(nm.toLowerCase());
    return nm;
  };
  const failed = [];
  let ok = 0, lastId = null;
  try {
    // the list shows the newest voice first: adding the LAST file first leaves the voices in the order of the file dialog
    for (let k = files.length - 1; k >= 0; k--) {
      const f = files[k];
      voxStatus(`<span>${esc(t('vox.upload.progress', { i: files.length - k, n: files.length, name: f.name }))}</span>`);
      try {
        if (f.size > 30 * 1024 * 1024) throw Object.assign(new Error('too big'), { code: 'VOX_BAD_AUDIO' });
        const data = await readDataUrl(f);
        const v = await api('/api/vox/voices', { method: 'POST', body: { name: nameFor(f), filename: f.name, data } });
        ok++; lastId = v.id;
        await refreshVoices();                                      // every voice shows up in the list as soon as it is saved
      } catch (err) { failed.push({ name: f.name, msg: errText(err) }); }
    }
  } finally { voxUploading = false; }
  if (files.length === 1) {
    voxStatus('');
    if (ok) { state.s.voice.vox.id = lastId; saveSettings(); updateDerived(); toast(t('vox.uploaded'), 'ok'); }
    else toast(failed[0].msg, 'bad');
    return;
  }
  if (ok) toast(ok === 1 ? t('vox.uploaded') : t('vox.uploaded.many', { n: ok }), 'ok');
  else toast(failed[0].msg, 'bad');
  voxStatus(`<b>${esc(t('vox.upload.done', { ok, n: files.length }))}</b>`
    + (failed.length ? `<div>${esc(t('vox.upload.failed'))}</div><ul>${failed.map((x) => `<li><b>${esc(x.name)}</b> — ${esc(x.msg)}</li>`).join('')}</ul>` : ''));
}
document.addEventListener('change', (e) => {
  const inp = e.target.closest('[data-vox-upload]');
  if (!inp) return;
  const files = Array.from(inp.files || []);                          // (copied first: clearing the box empties its list)
  inp.value = '';
  uploadVoiceFiles(files);
});
/* clips can also be dropped on the VoxCPM2 area (a video dropped elsewhere still opens the Upload tab) */
const voxZone = (e) => (e.target && e.target.closest ? e.target.closest('.engine-vox') : null);
document.addEventListener('dragenter', (e) => { const z = voxZone(e); if (z && filesIn(e)) { e.preventDefault(); z.classList.add('drop'); } });
document.addEventListener('dragover', (e) => { const z = voxZone(e); if (z && filesIn(e)) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; z.classList.add('drop'); } });
document.addEventListener('dragleave', (e) => { const z = voxZone(e); if (z && !z.contains(e.relatedTarget)) z.classList.remove('drop'); });
document.addEventListener('drop', (e) => {
  const z = voxZone(e);
  if (!z || !filesIn(e)) return;
  e.preventDefault(); e.stopPropagation();
  $$('.engine-vox.drop').forEach((x) => x.classList.remove('drop'));
  uploadVoiceFiles(e.dataTransfer.files);
});

/* ============================================================ counters */
function updateCounters() {
  $('#tts-count').textContent = t('counter.chars', { n: $('#tts-text').value.length.toLocaleString() });
  const tr = $('#tr-text').value;
  $('#tr-count').textContent = tr.trim() ? t('counter.lines', { n: tr.split('\n').filter((l) => l.trim()).length.toLocaleString() }) : '';
  const ut = $('#up-text').value;
  $('#up-count').textContent = ut.trim() ? t('counter.lines', { n: ut.split('\n').filter((l) => l.trim()).length.toLocaleString() }) : '';
}

/* ============================================================ init */
function mountTemplates() {
  $$('.voice-block').forEach((b) => { b.append($('#tpl-voice').content.cloneNode(true)); });
  $$('.terms-opts').forEach((b) => { b.append($('#tpl-terms-opts').content.cloneNode(true)); });
  $$('.autovoice-block').forEach((b) => { b.append($('#tpl-autovoice').content.cloneNode(true)); });
  mountFrameControls();
  hydrateIcons();
}
function wireStaticEvents() {
  $('#nav').addEventListener('click', (e) => { const b = e.target.closest('button[data-page]'); if (b) showPage(b.dataset.page); });
  $('#lang-switch').addEventListener('click', (e) => { const b = e.target.closest('button[data-lang]'); if (b) setLang(b.dataset.lang); });
  $('#theme-btn').addEventListener('click', () => { state.theme = state.theme === 'dark' ? 'light' : 'dark'; localStorage.setItem('kds_theme', state.theme); applyTheme(); });
  $('#side-toggle').addEventListener('click', () => applySide(!document.documentElement.classList.contains('side-collapsed'), true));
  $('#src-tabs').addEventListener('click', (e) => { const b = e.target.closest('button[data-tab]'); if (b) setSourceTab(b.dataset.tab); });

  $('#yt-url').addEventListener('input', autoCheck);
  $('#yt-url').addEventListener('input', updateFrameMocks);
  $('#yt-url').addEventListener('paste', () => setTimeout(autoCheck, 50));
  $('#yt-url').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); checkVideo(); } });
  $('#btn-paste').addEventListener('click', () => pasteInto($('#yt-url'), checkVideo));
  $('#btn-check').addEventListener('click', checkVideo);
  $('#btn-generate').addEventListener('click', startDub);
  $('#btn-cancel').addEventListener('click', () => cancelJob('dub'));

  $('#tr-text').addEventListener('input', updateCounters);
  $('#tr-file').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    $('#tr-text').value = await f.text();
    if (!$('#tr-title').value) $('#tr-title').value = f.name.replace(/\.[^.]+$/, '');
    updateCounters(); e.target.value = '';
  });

  wireUpload();

  $('#tts-text').addEventListener('input', updateCounters);
  $('#tts-sample').addEventListener('click', () => { $('#tts-text').value = t(`tts.sample.${LANG_NAME[state.s.tts.input_lang] ? state.s.tts.input_lang : 'km'}`); updateCounters(); });
  $('#tts-paste').addEventListener('click', () => pasteInto($('#tts-text'), updateCounters));
  $('#tts-clear').addEventListener('click', () => { $('#tts-text').value = ''; updateCounters(); });
  $('#tts-generate').addEventListener('click', startTts);
  $('#tts-cancel').addEventListener('click', () => cancelJob('tts'));

  // terms
  $('#terms-editor').addEventListener('input', () => { state.termsDirty = true; updateTermsState(); });
  $('#terms-save').addEventListener('click', async () => {
    try { await api('/api/glossary', { method: 'PUT', body: { text: $('#terms-editor').value } }); state.termsDirty = false; updateTermsState(); toast(t('terms.saved'), 'ok'); }
    catch (e) { toast(errText(e), 'bad'); }
  });
  $('#terms-reset').addEventListener('click', async () => {
    if (!confirm(t('terms.confirm_reset'))) return;
    try { const g = await api('/api/glossary/reset', { method: 'POST' }); $('#terms-editor').value = g.text; state.termsDirty = false; updateTermsState(); toast(t('terms.saved'), 'ok'); }
    catch (e) { toast(errText(e), 'bad'); }
  });
  $('#terms-export').addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([$('#terms-editor').value], { type: 'text/plain;charset=utf-8' }));
    a.download = 'technical-terms.txt'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $('#terms-import').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    $('#terms-editor').value = await f.text(); state.termsDirty = true; updateTermsState(); e.target.value = '';
  });

  $('#hist-refresh').addEventListener('click', loadHistory);

  // settings: LLM
  $('#llm-preset').addEventListener('change', (e) => {
    const p = PRESETS[e.target.value];
    state.s.translate.llm.preset = e.target.value;
    if (p) { state.s.translate.llm.base_url = p.base_url; state.s.translate.llm.model = p.model; }
    saveSettings(); syncBindings(); updateDerived();
  });
  $('#llm-test').addEventListener('click', async () => {
    const out = $('#llm-test-result'); const l = state.s.translate.llm;
    out.className = 'small muted'; out.textContent = '…';
    try {
      const r = await api('/api/llm/test', { method: 'POST', body: { base_url: l.base_url, api_key: l.api_key, model: l.model } });
      if (r.ok) { out.className = 'small'; out.style.color = 'var(--ok)'; out.textContent = t('set.test.ok') + r.sample; }
      else { out.className = 'small'; out.style.color = 'var(--danger)'; out.textContent = t('set.test.fail') + r.error; }
    } catch (e) { out.style.color = 'var(--danger)'; out.textContent = t('set.test.fail') + e.message; }
  });

  $('#gt-test').addEventListener('click', runGoogleTest);

  // settings: VoxCPM2
  $('#vox-install').addEventListener('click', voxInstall);
  $('#vox-reinstall').addEventListener('click', voxInstall);
  $('#vox-start').addEventListener('click', () => voxAction('start'));
  $('#vox-stop').addEventListener('click', () => voxAction('stop'));
  $('#vox-test').addEventListener('click', voxTest);
  $('#vox-device').addEventListener('change', async (e) => {
    try { await api('/api/vox/config', { method: 'PUT', body: { device: e.target.value } }); } catch (err) { toast(errText(err), 'bad'); }
    loadVox();
  });
  $('#vox-turbo').addEventListener('change', async (e) => {
    try { await api('/api/vox/config', { method: 'PUT', body: { turbo: e.target.checked } }); toast(t('set.vox.turbo.restart'), 'ok'); }
    catch (err) { toast(errText(err), 'bad'); }
    loadVox();
  });
  $('#vox-log-box').addEventListener('toggle', loadVoxLog);

  $('#btn-install').addEventListener('click', onInstallClick);
  window.addEventListener('hashchange', () => { const p = location.hash.slice(1); if (p && p !== state.page) showPage(p); });
  window.addEventListener('beforeunload', (e) => { if (state.termsDirty) { e.preventDefault(); e.returnValue = ''; } });
}

/* ============================================================ install as an app - PWA (v1.11) */
let installPrompt = null;                      // the browser's own "install" dialog (Chrome / Edge hand it over; Safari and Firefox do not)
let installedNow = false;
const runsAsApp = () => ['standalone', 'window-controls-overlay', 'minimal-ui', 'fullscreen'].some((m) => window.matchMedia(`(display-mode: ${m})`).matches) || window.navigator.standalone === true;
function updateInstallUi() {
  const box = $('#install-box');
  if (!box) return;
  const show = window.isSecureContext && window.self === window.top && !runsAsApp() && !installedNow;     // only where installing can work: not in a frame, not inside the installed app itself
  box.classList.toggle('hidden', !show);
  if (!show) showInstallHelp(false);
}
function showInstallHelp(open) {
  $('#install-help').classList.toggle('hidden', !open);
  $('#btn-install').setAttribute('aria-expanded', String(open));
}
function registerServiceWorker() {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;             // http://localhost and http://127.0.0.1 count as secure
  try { navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => { /* the dashboard works without it */ }); }
  catch { /* a sandboxed frame: reading navigator.serviceWorker throws */ }
}
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); installPrompt = e; updateInstallUi(); });
window.addEventListener('appinstalled', () => { installPrompt = null; installedNow = true; updateInstallUi(); toast(t('pwa.installed'), 'ok'); });
async function onInstallClick() {
  if (!installPrompt) { showInstallHelp($('#install-help').classList.contains('hidden')); return; }       // no dialog to open (Safari, Firefox ...): say how to do it by hand
  const p = installPrompt;
  installPrompt = null;                                                                  // the event can be used once
  try { await p.prompt(); await p.userChoice; } catch { /* closed without choosing */ }
  updateInstallUi();
}

async function init() {
  { const uv = $('#ui-ver'); if (uv) uv.textContent = KDS_UI_VERSION; }
  applyTheme();
  mountTemplates();
  wireStaticEvents();
  applyI18n();
  applySide(localStorage.getItem('kds_side') === '1', false);
  requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.add('anim')));      // no slide animation on page load
  $$('#lang-switch button').forEach((b) => b.classList.toggle('active', b.dataset.lang === state.lang));
  syncBindings();
  try { state.voices = await api('/api/voices'); state.voicesLoaded = true; } catch { /* offline */ }
  if (!state.voices.khmer.some((v) => v.id === state.s.voice.id)) state.s.voice.id = (state.voices.khmer[0] || {}).id || state.s.voice.id;
  populateEnVoices();
  renderVoiceCards();
  renderVoxVoices();
  normalizeVoxId();
  syncBindings();
  updateDerived();
  updateCounters();
  showPage((location.hash || '#dub').slice(1));
  loadSystem();
  loadVox();
  loadWhisper();
  renderUpload();
  refreshHistoryBadge();
  updateInstallUi();
  registerServiceWorker();
}
init();
})();
