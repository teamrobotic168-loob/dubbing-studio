/* V_Heang Studio - service worker (version {{ver}}).

   It does ONE thing: when the local server is not running, the installed app (or a browser tab) shows /offline.html - "start it with start.bat /
   start.command, this page opens the app by itself" - instead of the browser's error page.

   Everything else goes to the network untouched: the API, audio / video (Range requests), uploads, downloads.  Nothing else is cached, so an updated
   file can never stay hidden (the dashboard is local: the server is the only source of truth).  Only the address "/" (the dashboard itself) is
   looked at: a link to a file or to /api/... is never touched. */
const CACHE = 'kds-offline-{{ver}}';
const OFFLINE = '/offline.html';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.add(new Request(OFFLINE, { cache: 'reload' })))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('kds-offline-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.mode !== 'navigate' || req.method !== 'GET') return;          // a page is being opened (not a script, an API call, a video ...)
  if (new URL(req.url).pathname !== '/') return;                         // the dashboard only
  event.respondWith(
    fetch(req).catch(() => caches.match(OFFLINE).then((cached) => cached || Response.error()))
  );
});
