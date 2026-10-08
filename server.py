"""Start V_Heang Studio:  python server.py   (then open http://127.0.0.1:8000)

Environment variables (all optional):
  PORT        default 8000.  When PORT is not set and 8000 is taken:
                - by V_Heang Studio of THIS version (you started it twice): no second copy is started, the one that runs is opened;
                - by anything else (another program, another version): the next free port is used (8001 ... 8019) and shown.
              A PORT you set yourself is never changed.  (Keep to 8000: an installed app - PWA - belongs to one address.)
  HOST        default 127.0.0.1 (only this computer).  Use 0.0.0.0 to reach it from your phone on the same Wi-Fi.
  NO_BROWSER  1 = do not open the browser.
"""
import json
import os
import socket
import sys
import threading
import urllib.request
import webbrowser

DEFAULT_PORT = 8000
PORT_TRIES = 20


def port_is_free(host: str, port: int) -> bool:
    """Can we listen on host:port?  (No SO_REUSEADDR here: on Windows it would say 'free' for a port that is in use.)"""
    try:
        with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
        return True
    except OSError:
        return False


def running_instance(host: str, port: int, version: str):
    """The address of a V_Heang Studio of exactly this `version` that already answers on host:port - or None (free, another program, another version)."""
    h = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # never through a (company) proxy: this is the own computer
        with opener.open(f"http://{h}:{port}/api/health", timeout=1.5) as r:
            d = json.loads(r.read(4096).decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 - nothing there, not HTTP, not JSON ...
        return None
    if isinstance(d, dict) and d.get("ok") is True and "assets" in d and d.get("version") == version:
        return f"http://{h}:{port}"
    return None


def pick_port(host: str, preferred: int = DEFAULT_PORT, tries: int = PORT_TRIES):
    """The first free port from `preferred` on, or None."""
    for p in range(preferred, preferred + tries):
        if port_is_free(host, p):
            return p
    return None


def use_system_certificates() -> None:
    """Python from python.org on a Mac has no certificate store until 'Install Certificates.command' was run, and then every HTTPS
    request of the standard library fails with CERTIFICATE_VERIFY_FAILED.  When (only) that store is missing, use the `certifi` bundle
    that is always installed here.  Other systems are left alone - Windows uses its own store (company proxies need it)."""
    if sys.platform != "darwin" or os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return
    try:
        import ssl

        import certifi

        vp = ssl.get_default_verify_paths()
        if not (os.path.exists(vp.openssl_cafile or "") or os.path.isdir(vp.openssl_capath or "")):
            os.environ["SSL_CERT_FILE"] = certifi.where()
    except Exception:
        pass


def main() -> None:
    use_system_certificates()
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    explicit = os.environ.get("PORT")
    if explicit:
        port = int(explicit)
        if not port_is_free(host, port):
            print(f"\n  Port {port} is already in use (is V_Heang Studio already running in another window?).\n"
                  f"  Close that program, or choose another port:  PORT={port + 1} python server.py\n")
            sys.exit(1)
    else:
        if not port_is_free(host, DEFAULT_PORT):
            from app import __version__
            url = running_instance(host, DEFAULT_PORT, __version__)
            if url:                                # the same program is already open: do not start a second copy (it would sit on 8001 and confuse an installed app)
                print(f"\n  V_Heang Studio is already running ->  {url}\n  (opening it - no second copy is started)\n")
                if os.environ.get("NO_BROWSER") != "1":
                    webbrowser.open(url)
                return
        port = pick_port(host, DEFAULT_PORT)
        if port is None:
            print(f"\n  No free port between {DEFAULT_PORT} and {DEFAULT_PORT + PORT_TRIES - 1}. Close some programs and try again.\n")
            sys.exit(1)
        if port != DEFAULT_PORT:
            print(f"\n  Port {DEFAULT_PORT} is in use (V_Heang Studio may already be open in another window) - using port {port} instead.")
    if os.environ.get("NO_BROWSER") != "1" and host in ("127.0.0.1", "localhost"):
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"\n  V_Heang Studio is running ->  http://{host}:{port}\n  (press Ctrl+C to stop)\n")
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
