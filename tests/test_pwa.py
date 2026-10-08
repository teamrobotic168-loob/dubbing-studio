"""Installable app (PWA, v1.11): A the files (manifest, icons, service worker, offline page, <head>, texts), B the server (routes, headers,
"already running" check of server.py), C browser (Chromium: installable according to the browser itself, service worker, the offline page when the
server is switched off and the way back, the install button).  Set ONLY=A,B,C to run some of the parts.

The dashboard is a LOCAL web page, so the installed app is only a window: when the server is not running, the service worker shows /offline.html
("start it with start.bat / start.command") instead of the browser's error page, and that page opens the app by itself as soon as the server answers.
"""
import base64
import http.server
import json
import os
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path


from lib import *  # noqa: E402,F401,F403

WORK.mkdir(parents=True, exist_ok=True)
STATIC = PROJECT / "static"
ONLY = set((os.environ.get("ONLY") or "A,B,C").split(","))
c = Checker("Installable app (PWA)")
PORT = 8066


def png_size(path):
    d = Path(path).read_bytes()
    assert d[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", d[16:24])


# ==================================================================================================================== A. the files
if "A" in ONLY:
    man = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    c.check(man.get("id") == "/" and man.get("start_url") == "/" and man.get("scope") == "/" and man.get("display") == "standalone", "manifest: id / start_url / scope = '/', display standalone")
    c.check(man.get("name") == "V_Heang Studio" and man.get("short_name") == "V_Heang" and man.get("lang") == "km" and man.get("prefer_related_applications") is False, "manifest: name, short name, language, no 'native app' preference")
    c.check(all(re.fullmatch(r"#[0-9a-fA-F]{6}", man.get(k, "")) for k in ("background_color", "theme_color")), "manifest: colours are #rrggbb")
    c.check(len(man.get("description", "")) > 20, "manifest: description")
    icons = man.get("icons", [])
    key = {(i["sizes"], i.get("purpose", "any")) for i in icons}
    c.check({("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= key, "manifest: icons 192 (any), 512 (any), 512 (maskable)", str(key))
    ok = True
    for i in icons:
        f = STATIC.parent / i["src"].lstrip("/")
        w, h = png_size(f) if f.exists() else (0, 0)
        if not (i["type"] == "image/png" and f"{w}x{h}" == i["sizes"]):
            ok = False
            print("   icon problem:", i, f, (w, h))
    c.check(ok, "manifest: every icon file exists, is a PNG and has the size the manifest says")
    c.check(png_size(STATIC / "icons" / "apple-touch-icon.png") == (180, 180), "apple-touch-icon.png is 180x180")
    c.check(all((STATIC / "icons" / n).stat().st_size < 200_000 for n in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png")), "icons are small (< 200 KB each)")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    pages = set(re.findall(r'<button data-page="(\w+)"', html))
    sc = man.get("shortcuts", [])
    c.check(len(sc) == 4 and all(re.fullmatch(r"/#(\w+)", s["url"]) and s["url"][2:] in pages and s["name"] and s["icons"] for s in sc) and {s["url"][2:] for s in sc} == {"dub", "tts", "terms", "history"},
            "manifest: four shortcuts (jump list) that open real pages: dub, tts, terms, history", str([s["url"] for s in sc]) + str(pages))
    c.check(all((STATIC.parent / s["icons"][0]["src"].lstrip("/")).exists() for s in sc), "manifest: the shortcut icons exist")

    c.check('<link rel="manifest" href="/manifest.webmanifest">' in html and 'name="theme-color"' in html and 'rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png"' in html, "index.html: manifest, theme-color, apple-touch-icon")
    c.check(all(html.count(f'id="{i}"') == 1 for i in ("install-box", "btn-install", "install-help")) and 'data-i18n="pwa.install"' in html and 'data-i18n="pwa.help"' in html, "index.html: the install button and its how-to (one of each)")
    ids = re.findall(r'\sid="([^"]+)"', html)
    c.check(len(ids) == len(set(ids)), "index.html: ids are still unique")
    c.check(html.find('name="kds-ui"') < 3000, "index.html: the version marker is still near the top (the server reads the first 6000 characters)")

    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    c.check(sw.count("{{ver}}") >= 2 and "const CACHE = 'kds-offline-{{ver}}'" in sw and "const OFFLINE = '/offline.html'" in sw, "sw.js: the cache name carries the version ({{ver}}), the page is /offline.html")
    c.check(sw.count("respondWith") == 1 and "req.mode !== 'navigate'" in sw and "pathname !== '/'" in sw and "req.method !== 'GET'" in sw, "sw.js: only a GET page NAVIGATION to '/' is answered (one respondWith, three guards)")
    code_lines = [ln for ln in sw.splitlines() if not ln.strip().startswith(("/*", "*", "//"))]
    code = "\n".join(code_lines)
    c.check(code.count("respondWith") == 1 and ".put(" not in code and "addAll" not in code and code.count("cache.add(") == 1, "sw.js: nothing is cached except the offline page (no put / addAll)")
    c.check("skipWaiting" in sw and "clients.claim" in sw and "caches.delete" in sw, "sw.js: updates at once and removes the caches of older versions")

    off = (STATIC / "offline.html").read_text(encoding="utf-8")
    c.check(not re.search(r'(src|href)="(https?:)?//', off) and 'rel="stylesheet"' not in off and "<script src" not in off and "@import" not in off and not re.search(r"url\((?!#)", off), "offline.html: everything is inline (no file, font or script from outside)")
    c.check("V_Heang Studio មិនទាន់ដំណើរការទេ" in off and "V_Heang Studio is not running" in off and "start.bat" in off and "start.command" in off and "8000" in off, "offline.html: Khmer and English, names both launchers, mentions port 8000")
    c.check("/*{{khmer-font}}*/" in off and '"KDS Khmer"' in off, "offline.html: has the place where the server puts the Khmer font (the page must look right with the server off)")
    c.check("/api/health" in off and "location.pathname === '/'" in off and "location.replace('/')" in off, "offline.html: polls /api/health and returns to the dashboard (only when it stands in for '/')")

    i18n = (STATIC / "js" / "i18n.js").read_text(encoding="utf-8")
    appjs = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    c.check(all(len(re.findall(rf"^\s*'{re.escape(k)}':", i18n, re.M)) == 2 for k in ("pwa.install", "pwa.installed", "pwa.help")), "i18n: pwa.install / pwa.installed / pwa.help exist in Khmer and English")
    c.check("t('pwa.installed')" in appjs and "serviceWorker.register('/sw.js'" in appjs and "beforeinstallprompt" in appjs and "appinstalled" in appjs and "isSecureContext" in appjs, "app.js: registers /sw.js (secure contexts only), handles beforeinstallprompt / appinstalled")
    c.check("'#090d1a'" in appjs and "'#f3f5fc'" in appjs, "app.js: the theme colour of the title bar follows dark / light")
    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    c.check(".side-install" in css and "max-width: 900px) { .side-install { display: none; }" in css, "app.css: the install button is not shown on a narrow screen")

# ==================================================================================================================== B. the server
HTTPD = []


def fake_khmerdub(payload, ctype="application/json"):
    """A tiny HTTP server on a free port that answers every GET with `payload`."""
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    HTTPD.append(s)
    return s.server_address[1]


srv = None
if "B" in ONLY or "C" in ONLY:
    DATA = WORK / "data_pwa"
    shutil.rmtree(DATA, ignore_errors=True)
    srv = Server(PORT, DATA, make_stub_home(WORK / "vox_pwa"), name="pwa").start()
URL = f"http://127.0.0.1:{PORT}"

if "B" in ONLY:
    man_text = (STATIC / "manifest.webmanifest").read_text(encoding="utf-8")
    r = srv.api("GET", "/manifest.webmanifest")
    c.check(r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json") and "no-cache" in r.headers.get("cache-control", "") and r.json() == json.loads(man_text), "GET /manifest.webmanifest: 200, application/manifest+json, no-cache, the file", r.headers.get("content-type", ""))
    r = srv.api("GET", "/sw.js")
    c.check(r.status_code == 200 and "javascript" in r.headers["content-type"] and r.headers.get("service-worker-allowed") == "/" and "no-cache" in r.headers.get("cache-control", ""), "GET /sw.js: 200, JavaScript, Service-Worker-Allowed '/', no-cache", str(dict(r.headers)))
    c.check(f"kds-offline-{VERSION}" in r.text and "{{ver}}" not in r.text and f"(version {VERSION})" in r.text, "GET /sw.js: the version of the server is put in (a new version = a new file = the browser updates it)")
    r = srv.api("GET", "/offline.html")
    src_off = (STATIC / "offline.html").read_text(encoding="utf-8")
    c.check(r.status_code == 200 and r.headers["content-type"].startswith("text/html") and "no-cache" in r.headers.get("cache-control", "") and "{{" not in r.text, "GET /offline.html: 200, HTML, no-cache, no placeholder left")
    m = re.search(r"src:url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", r.text)
    c.check(m is not None and base64.b64decode(m.group(1)) == (STATIC / "fonts" / "kantumruy-pro-khmer-wght-normal.woff2").read_bytes(), "GET /offline.html: the Khmer font is INSIDE the page (data URI = the font file, byte for byte)")
    c.check(re.sub(r"@font-face\{[^}]*\}", "", r.text, count=1) == src_off.replace("/*{{khmer-font}}*/", "") and not re.search(r"url\((?!#|data:)", r.text), "GET /offline.html: the rest is the file as it is; nothing is loaded from outside")
    for n in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png"):
        r = srv.api("GET", f"/static/icons/{n}")
        c.check(r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == (STATIC / "icons" / n).read_bytes(), f"GET /static/icons/{n}: 200 image/png, the file")
    r = srv.api("GET", "/")
    c.check(r.status_code == 200 and r.headers.get("cache-control") == "no-store" and '<link rel="manifest" href="/manifest.webmanifest">' in r.text and "{{" not in r.text, "GET /: still no-store, has the manifest link, no placeholder left")
    h = srv.api("GET", "/api/health").json()
    c.check(h["ok"] is True and h["version"] == VERSION and h["ui_ok"] is True, "the version markers of the UI files still agree (ui_ok)", str(h))
    r = srv.api("GET", "/api/jobs")
    c.check(r.status_code == 200, "the API next to the new routes still works")

    # ---- server.py: "V_Heang Studio is already running" (a second start of the same version must not start a second copy)
    sys.path.insert(0, str(PROJECT))
    import server as srvmod  # noqa: E402
    c.check(srvmod.running_instance("127.0.0.1", PORT, VERSION) == URL, "running_instance: a V_Heang Studio of this version on the port -> its address")
    c.check(srvmod.running_instance("0.0.0.0", PORT, VERSION) == URL, "running_instance: HOST 0.0.0.0 is asked as 127.0.0.1")
    px = subprocess.run([sys.executable, "-c", f"import server; print(server.running_instance('127.0.0.1', {PORT}, '{VERSION}'))"], cwd=str(PROJECT), capture_output=True, text=True,
                        env=dict(os.environ, PYTHONPATH=str(PROJECT), HTTP_PROXY="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9", NO_PROXY="", no_proxy=""))
    c.check(px.stdout.strip() == URL, "running_instance: not sent through a proxy (HTTP_PROXY points nowhere, the answer still comes)", px.stdout + px.stderr[-200:])
    c.check(srvmod.running_instance("127.0.0.1", PORT, "0.0.1") is None, "running_instance: another version -> None (the new port logic is used, the old one is not shown)")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    free = s.getsockname()[1]
    s.close()
    c.check(srvmod.running_instance("127.0.0.1", free, VERSION) is None, "running_instance: nothing listens -> None")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(5)
    t0 = time.time()
    c.check(srvmod.running_instance("127.0.0.1", s.getsockname()[1], VERSION) is None and time.time() - t0 < 4, "running_instance: a program that never answers -> None after a short wait")
    s.close()
    p_ok = fake_khmerdub({"ok": True, "version": VERSION, "assets": "x", "ui_ok": True})
    c.check(srvmod.running_instance("127.0.0.1", p_ok, VERSION) == f"http://127.0.0.1:{p_ok}", "running_instance: only the answer decides (a fake that says what /api/health says is accepted)")
    c.check(all(srvmod.running_instance("127.0.0.1", fake_khmerdub(pl), VERSION) is None for pl in ({"ok": True}, {"ok": False, "version": VERSION, "assets": "x"}, {"version": VERSION, "assets": "x"}, ["ok"], "just text")),
            "running_instance: other programs' answers (no ok / no assets / not JSON ...) -> None")
    c.check(srvmod.running_instance("127.0.0.1", fake_khmerdub("<html>hello</html>", "text/html"), VERSION) is None, "running_instance: an ordinary web page -> None")

    def run_main(snippet, extra_env=None, timeout=60):
        env = dict(os.environ, HOST="127.0.0.1", NO_BROWSER="1", PYTHONPATH=str(PROJECT))
        env.pop("PORT", None)
        env.update(extra_env or {})
        p = subprocess.run([sys.executable, "-c", snippet], cwd=str(PROJECT), env=env, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    t0 = time.time()
    rc, out = run_main(f"import server; server.DEFAULT_PORT = {PORT}; server.main()")
    c.check(rc == 0 and "already running" in out and URL in out and "Traceback" not in out and time.time() - t0 < 30, "server.py: the default port is taken by this V_Heang Studio -> 'already running', exit 0, no second copy", out[-300:])
    c.check(srvmod.port_is_free("127.0.0.1", PORT + 1), "server.py: no second server appeared on the next port")
    rc, out = run_main(f"import app; app.__version__ = '0.0.1'; import server; server.DEFAULT_PORT = {PORT}; server.pick_port = lambda *a, **k: None; server.main()")
    c.check(rc == 1 and "already running" not in out and "No free port" in out, "server.py: the port is taken by ANOTHER version -> not reused (the next-port logic runs)", out[-300:])
    rc, out = run_main(f"import server; server.DEFAULT_PORT = {PORT}; server.main()", {"PORT": str(PORT)})
    c.check(rc == 1 and f"Port {PORT} is already in use" in out, "server.py: a PORT you set yourself that is taken -> the clear message, exit 1 (as before)", out[-200:])

# ==================================================================================================================== C. browser
if "C" in ONLY:
    from playwright.sync_api import sync_playwright  # noqa: E402
    errors = []

    def new_page(b, lang="en", theme="dark", w=1440, h=900, init=None, path="/"):
        ctx = b.new_context(viewport={"width": w, "height": h})
        ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','{theme}'); if (!localStorage.getItem('kds_settings')) localStorage.setItem('kds_settings', JSON.stringify({{ui:{{dock:false}}}}));")
        if init:
            ctx.add_init_script(init)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
        pg.goto(URL + path, wait_until="networkidle")
        return ctx, pg

    def sw_ready(pg):
        return pg.evaluate("() => navigator.serviceWorker.ready.then((r) => ({ scope: r.scope, state: r.active && r.active.state }))")

    proc = None
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()

            # ================================================================== installable (the browser's own verdict) + service worker
            ctx, pg = new_page(b)
            c.check(pg.get_attribute('link[rel="manifest"]', "href") == "/manifest.webmanifest", "the page links the manifest")
            cdp = ctx.new_cdp_session(pg)
            try:
                am = cdp.send("Page.getAppManifest")
                ie = cdp.send("Page.getInstallabilityErrors")
                c.check(am.get("url", "").endswith("/manifest.webmanifest") and am.get("errors") == [], "Chromium reads the manifest without any error", str(am.get("errors")))
                c.check(ie.get("installabilityErrors") == [], "Chromium says: this page IS installable (no installability error)", str(ie.get("installabilityErrors")))
            except Exception as e:  # noqa: BLE001 - an older browser without these calls
                c.check(False, "Chromium can tell about the manifest / installability (CDP)", str(e)[:200])
            sw = sw_ready(pg)
            c.check(sw["scope"] == URL + "/" and sw["state"] == "activated", "service worker: registered with the scope '/' and activated", str(sw))
            names = pg.evaluate("() => caches.keys()")
            c.check(names == [f"kds-offline-{VERSION}"], "service worker: one cache, named with the version (nothing else is stored)", str(names))
            cached = pg.evaluate("(n) => caches.open(n).then((cc) => cc.keys()).then((ks) => ks.map((k) => new URL(k.url).pathname))", names[0])
            c.check(cached == ["/offline.html"], "service worker: only /offline.html is in it", str(cached))
            pg.reload(wait_until="networkidle")
            c.check(pg.evaluate("() => !!navigator.serviceWorker.controller"), "after a reload the service worker controls the page")
            c.check(pg.is_visible("#nav") and pg.is_visible("#install-box"), "the dashboard works with the service worker in control (menu is there)")
            r = pg.evaluate("() => fetch('/static/js/app.js', { headers: { Range: 'bytes=0-9' } }).then((r) => [r.status, r.headers.get('content-range') || ''])")
            c.check(r[0] in (200, 206), "files are fetched as before (a Range request is answered, the worker does not touch it)", str(r))
            h = pg.evaluate("() => fetch('/api/health').then((r) => r.json())")
            c.check(h["ok"] is True and h["version"] == VERSION, "API calls are not touched either")
            pg.goto(URL + "/offline.html", wait_until="domcontentloaded")
            pg.wait_for_function("() => document.querySelector('#st').dataset.state === 'up'", timeout=10000)
            c.check(pg.url.endswith("/offline.html") and "not running" in pg.inner_text("h1"), "/offline.html opened directly (server up): shows itself, only reports 'OK', does NOT jump away")
            # the icons in the browser: size and transparency
            icons = pg.evaluate("""async () => {
                const m = await (await fetch('/manifest.webmanifest')).json();
                const out = [];
                for (const i of m.icons) {
                    const img = new Image(); img.src = i.src; await img.decode();
                    const cv = document.createElement('canvas'); cv.width = img.naturalWidth; cv.height = img.naturalHeight;
                    const g = cv.getContext('2d'); g.drawImage(img, 0, 0);
                    out.push({ purpose: i.purpose, w: img.naturalWidth, corner: g.getImageData(1, 1, 1, 1).data[3], middle: g.getImageData(img.naturalWidth >> 1, img.naturalHeight >> 1, 1, 1).data[3] });
                }
                return out;
            }""")
            c.check(all(i["w"] in (192, 512) for i in icons) and all(i["corner"] == 0 and i["middle"] == 255 for i in icons if i["purpose"] == "any") and all(i["corner"] == 255 for i in icons if i["purpose"] == "maskable"),
                    "icons decode in the browser: 'any' = rounded (transparent corner), 'maskable' = full square (no transparent corner)", str(icons))

            # ================================================================== the server is switched off ...
            srv.stop()
            time.sleep(0.5)
            pg.goto(URL + "/", wait_until="domcontentloaded")
            c.check(pg.url == URL + "/" and "V_Heang Studio is not running" in pg.inner_text("h1") and "start.bat" in pg.inner_text("main") and "មិនទាន់ដំណើរការទេ" in pg.inner_text("h1"), "server OFF: the address '/' shows the 'not running' page (Khmer + English), not the browser's error page", pg.inner_text("body")[:200])
            c.check("not running" in pg.title() and pg.get_attribute("#st", "data-state") == "down", "server OFF: the title says so, the state is 'waiting'")
            fonts = pg.evaluate("() => document.fonts.ready.then(() => [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family))")
            c.check(any("KDS Khmer" in f for f in fonts), "server OFF: the Khmer letters use the font that is inside the page (no file is needed)", str(fonts))
            other, err = "shown", ""
            pg2 = ctx.new_page()                                   # a second tab, so that the error page of this one does not disturb the next navigation
            try:
                pg2.goto(URL + "/static/js/app.js", wait_until="domcontentloaded", timeout=8000)
            except Exception as e:  # noqa: BLE001
                other, err = "error", str(e)
            pg2.close()
            c.check(other == "error" and "ERR_" in err, "server OFF: any OTHER address is not answered by the worker (the browser's own error)", err[:120])
            pg.click("#retry")
            pg.wait_for_timeout(600)
            c.check("not running" in pg.inner_text("h1"), "server OFF: 'Try again' while it is still off -> the same page")

            # ... and switched on again: the page opens the dashboard by itself
            env = dict(os.environ, KDS_DATA_DIR=str(srv.data), KDS_VOX_HOME=str(srv.vox_home), KDS_VOX_STUB="1", KDS_VOX_DISABLE_INSTALL="1", PYTHONPATH=str(STUB), PYTHONUNBUFFERED="1")
            proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)], cwd=str(PROJECT), env=env,
                                    stdout=open(WORK / "pwa_restart.log", "wb"), stderr=subprocess.STDOUT, start_new_session=True)
            pg.wait_for_selector("#nav", timeout=40000)
            c.check(pg.url.split("#")[0] == URL + "/" and pg.is_visible("#nav") and pg.title().startswith("V_Heang Studio ·") and "not running" not in pg.title(), "server ON again: the 'not running' page opens the dashboard BY ITSELF (no click)", pg.url + " | " + pg.title())
            ctx.close()

            # ================================================================== the install button
            ctx, pg = new_page(b)
            c.check(pg.is_visible("#install-box") and pg.inner_text("#btn-install .lbl") == "Install as an app" and not pg.is_visible("#install-help"), "install button: in the menu, English label, the how-to is closed")
            pg.click("#btn-install")
            pg.wait_for_timeout(150)
            helptxt = pg.inner_text("#install-help")
            c.check(pg.get_attribute("#btn-install", "aria-expanded") == "true", "install button: aria-expanded is true while the how-to is open")
            c.check(pg.is_visible("#install-help") and "Add to Dock" in helptxt and "Install page as app" in helptxt and "start.bat" in helptxt and helptxt.count("\n") >= 2, "install button without a browser dialog (Safari, Firefox ...): the how-to opens (three lines)", helptxt)
            pg.click("#btn-install")
            pg.wait_for_timeout(150)
            c.check(not pg.is_visible("#install-help") and pg.get_attribute("#btn-install", "aria-expanded") == "false", "install button: a second click closes the how-to (aria-expanded false)")
            ev = pg.evaluate("""() => {
                window.__prompted = 0;
                const e = new Event('beforeinstallprompt', { cancelable: true });
                e.prompt = async () => { window.__prompted += 1; };
                e.userChoice = Promise.resolve({ outcome: 'accepted' });
                window.dispatchEvent(e);
                return e.defaultPrevented;
            }""")
            c.check(ev is True, "beforeinstallprompt: the page keeps the event (the browser's own banner is held back)")
            pg.click("#btn-install")
            pg.wait_for_timeout(200)
            c.check(pg.evaluate("() => window.__prompted") == 1 and not pg.is_visible("#install-help"), "install button: with the browser's dialog available, a click opens THAT dialog (and not the how-to)")
            pg.click("#btn-install")
            pg.wait_for_timeout(150)
            c.check(pg.evaluate("() => window.__prompted") == 1 and pg.is_visible("#install-help"), "the event can be used once: the next click shows the how-to again")
            pg.evaluate("() => window.dispatchEvent(new Event('appinstalled'))")
            pg.wait_for_timeout(300)
            c.check(not pg.is_visible("#install-box"), "appinstalled: the button goes away")
            toast = pg.evaluate("() => [...document.querySelectorAll('.toast, #toasts *')].map((e) => e.textContent).join(' | ')")
            c.check("Installed - look for V_Heang Studio in your Start menu or Dock" in toast, "appinstalled: a message says where to find the app", toast[:200])
            ctx.close()

            ctx, pg = new_page(b, lang="km")
            c.check(pg.inner_text("#btn-install .lbl") == "ដំឡើងជា App", "install button: Khmer label")
            pg.click("#btn-install")
            pg.wait_for_timeout(150)
            c.check("Add to Dock" in pg.inner_text("#install-help") and "រត់ជាមុន" in pg.inner_text("#install-help"), "install how-to: Khmer text")
            raw = pg.evaluate("() => [...document.querySelectorAll('[data-i18n]')].map((e) => e.textContent.trim()).filter((t) => /^[a-z0-9]+(\\.[a-z0-9]+)+$/i.test(t))")
            c.check(raw == [], "no raw translation keys on the screen", str(raw))
            pg.click("#lang-switch button[data-lang='en']")
            pg.wait_for_timeout(150)
            c.check(pg.inner_text("#btn-install .lbl") == "Install as an app", "language switch: the label changes at once")
            # the title bar colour follows the theme
            pg.click("#theme-btn")
            pg.wait_for_timeout(100)
            light = pg.get_attribute("meta[name=theme-color]", "content")
            pg.click("#theme-btn")
            pg.wait_for_timeout(100)
            c.check(light == "#f3f5fc" and pg.get_attribute("meta[name=theme-color]", "content") == "#090d1a", "theme colour of the title bar: light #f3f5fc, dark #090d1a", light)
            ctx.close()

            ctx, pg = new_page(b, init="""(() => { const mm = window.matchMedia.bind(window);
                window.matchMedia = (q) => /display-mode:\\s*standalone/.test(q) ? { matches: true, media: q, onchange: null, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent() { return false; } } : mm(q); })();""")
            c.check(not pg.is_visible("#install-box"), "inside the installed app (display-mode standalone): no install button")
            ctx.close()

            ctx, pg = new_page(b, init="Object.defineProperty(window, 'isSecureContext', { value: false });")
            c.check(not pg.is_visible("#install-box") and pg.evaluate("() => navigator.serviceWorker.getRegistrations().then((r) => r.length)") == 0, "not a secure address (isSecureContext false): no install button and no service worker is registered")
            ctx.close()

            ctx, pg = new_page(b, w=390, h=800)
            c.check(not pg.is_visible("#install-box"), "narrow screen (390 px): no install button in the top bar")
            ctx.close()

            ctx = b.new_context(viewport={"width": 1300, "height": 800})                # the dashboard inside a frame of another page: nothing to install there
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
            pg.goto(URL + "/offline.html", wait_until="domcontentloaded")               # a page of the same address that embeds the dashboard (a frame of ANOTHER address to 127.0.0.1 is blocked by Chromium itself: local network access)
            pg.evaluate("() => { document.body.innerHTML = '<iframe id=\"f\" src=\"/\" style=\"width:1200px;height:760px;border:0\"></iframe>'; }")
            fr = pg.frame_locator("#f")
            fr.locator("#nav").wait_for(timeout=20000)
            pg.wait_for_timeout(500)
            c.check(fr.locator("#nav").is_visible() and not fr.locator("#install-box").is_visible(), "the dashboard inside an iframe: works, but no install button")
            ctx.close()

            # an old service worker of another version is replaced and its cache removed
            ctx, pg = new_page(b)
            pg.evaluate("() => caches.open('kds-offline-0.0.1').then((c) => c.put('/x', new Response('old')))")
            pg.evaluate("() => navigator.serviceWorker.getRegistration().then((r) => r.unregister())")
            pg.reload(wait_until="networkidle")
            sw_ready(pg)
            pg.wait_for_timeout(500)
            names = pg.evaluate("() => caches.keys()")
            c.check(names == [f"kds-offline-{VERSION}"], "a new worker removes the caches of older versions (kds-offline-0.0.1 is gone)", str(names))
            ctx.close()

            c.check(not errors, "no JavaScript errors in the whole run", "; ".join(errors[:4]))
            b.close()
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=8)
            except Exception:  # noqa: BLE001
                pass

for s_ in HTTPD:
    s_.shutdown()
if srv is not None:
    srv.stop()
sys.exit(c.done())
