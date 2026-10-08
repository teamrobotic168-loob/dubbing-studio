"""Windows / macOS / Linux: A launcher scripts (syntax in sh, dash, bash, shellcheck; Python search with a fake Mac; a whole run),
B server.py (free port, certificates), C macOS logic of the VoxCPM2 installer (Apple Silicon, Intel, Rosetta, memory), D warnings in the
browser (Playwright, mocked status), E the release tools (tools/bump_version.py, tools/build_zip.py).  Set ONLY=A,B,C,D,E to run some parts.  (There is no real Mac or Windows here: the Mac is simulated.)"""
import contextlib
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import types
from pathlib import Path

from lib import *  # noqa: E402,F401,F403

WORK.mkdir(parents=True, exist_ok=True)
os.environ["KDS_DATA_DIR"] = str(WORK / "data_platform_units")
shutil.rmtree(WORK / "data_platform_units", ignore_errors=True)

ONLY = set((os.environ.get("ONLY") or "A,B,C,D,E").split(","))
c = Checker("Windows / macOS / Linux")
ROOT = PROJECT
SCRIPTS = ["start.sh", "start.command", "install-voxcpm.sh", "install-voxcpm.command"]


def run(cmd, env=None, cwd=None, timeout=120, inp=""):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run(cmd, capture_output=True, text=True, env=e, cwd=cwd, timeout=timeout, input=inp)
    return r.returncode, (r.stdout + r.stderr)


def fake_bin(d: Path, name: str, body: str):
    p = d / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(0o755)
    return p


# ==================================================================================================================== A. scripts
if "A" in ONLY:
    for f in SCRIPTS:
        raw = (ROOT / f).read_bytes()
        c.check(raw.startswith(b"#!/bin/sh\n") and b"\r" not in raw, f"{f}: starts with #!/bin/sh and has Unix line endings (a CR would break it on a Mac)")
        c.check(bool((ROOT / f).stat().st_mode & stat.S_IXUSR), f"{f}: is executable")
        for sh in ("sh", "dash", "bash"):
            rc, out = run([sh, "-n", str(ROOT / f)])
            c.check(rc == 0, f"{f}: syntax check with {sh}", out[:200])
    rc, out = run(["shellcheck", "-s", "sh"] + [str(ROOT / f) for f in SCRIPTS])
    c.check(rc == 0, "shellcheck (POSIX sh) finds nothing in the four scripts", out[:600])
    rc, out = run(["bash", "--posix", "-n", str(ROOT / "start.sh")])
    c.check(rc == 0, "start.sh also parses in bash's POSIX mode (what /bin/sh is on a Mac)")
    for f in ("start.bat", "install-voxcpm.bat"):
        raw = (ROOT / f).read_bytes()
        c.check(raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r") == raw.count(b"\r\n"), f"{f}: Windows line endings everywhere")
    bat = (ROOT / "start.bat").read_text(encoding="utf-8")
    c.check('call :trypy "py -3"' in bat and 'call :trypy "python"' in bat and ":trypy" in bat and "goto :havepy" in bat and "PYTHONUTF8" in bat and "Microsoft Store" in bat, "start.bat: finds py / python, knows the Microsoft Store shortcut, forces UTF-8")

    # ---- the Python search, with a fake Mac / Linux
    T = Path(tempfile.mkdtemp(prefix="kds_launch_"))
    proj = T / "proj"
    proj.mkdir()
    for f in ("start.sh", "start.command", "install-voxcpm.sh", "install-voxcpm.command"):
        shutil.copy(ROOT / f, proj / f)
        (proj / f).chmod(0o755)

    # a PATH with the few system tools the script uses - and NO Python (this sandbox has several, a real Mac may have none)
    tools = T / "tools"
    tools.mkdir()
    for tool in ("dirname", "chmod", "rm", "sh", "uname", "cat"):
        os.symlink(shutil.which(tool), tools / tool)

    def env_for(bindir, extra=None):
        e = {"PATH": f"{bindir}:{tools}", "KDS_DRY_RUN": "1", "HOME": str(T), "KDS_PY_FALLBACKS": ""}
        e.update(extra or {})
        return e

    def scenario(name, bins):
        d = T / name
        d.mkdir(exist_ok=True)
        for fname, body in bins.items():
            fake_bin(d, fname, body)
        return d

    OLD = 'case "$1" in -c) exit 1;; *) exit 1;; esac'          # a Python that is too old: the version check says no
    NEW = 'case "$1" in -c) exit 0;; *) exit 0;; esac'          # Python 3.10+: the version check says yes
    # a Mac whose only 'python3' is too old
    d = scenario("mac_old", {"uname": "echo Darwin", "python3": OLD, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=proj)
    c.check(rc == 1 and "Python 3.10 or newer is required" in out and "python.org/downloads/macos" in out and "brew install python@3.12" in out, "Mac, only an old Python -> exit 1 and tells how to install (python.org / Homebrew)", out[:300])
    c.check("apt" not in out, "Mac message does not talk about apt")
    d = scenario("linux_old", {"uname": "echo Linux", "python3": OLD})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=proj)
    c.check(rc == 1 and "apt install python3 python3-venv" in out and "brew" not in out, "Linux, only an old Python -> exit 1 and the apt hint")
    d = scenario("mac_ok", {"uname": "echo Darwin", "python3": NEW, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=proj)
    c.check(rc == 0 and out.strip() == f"PYTHON={d}/python3", "a good python3 is used", out)
    d = scenario("mac_versioned", {"uname": "echo Darwin", "python3": OLD, "python3.12": NEW, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=proj)
    c.check(rc == 0 and out.strip() == f"PYTHON={d}/python3.12", "python3 too old, python3.12 fine -> python3.12 is used", out)
    d = scenario("mac_only311", {"uname": "echo Darwin", "python3.11": NEW, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=proj)
    c.check(rc == 0 and out.strip().endswith("/python3.11"), "no python3 at all, python3.11 exists -> used", out)
    d = scenario("mac_python_only", {"uname": "echo Darwin", "python": NEW, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=proj)
    c.check(rc == 0 and out.strip().endswith("/python"), "only a plain 'python' exists -> used", out)
    # the macOS stub: /usr/bin/python3 without the developer tools is skipped (it would open an installer pop-up)
    if Path("/usr/bin/python3").exists():
        d = scenario("mac_stub", {"uname": "echo Darwin", "xcode-select": "exit 2"})
        rc, out = run(["sh", "start.sh"], env_for(d, {"KDS_PY_FALLBACKS": "/usr/bin/python3"}), cwd=proj)
        c.check(rc == 1 and "Python 3.10 or newer is required" in out, "Mac without developer tools: the /usr/bin/python3 stub is NOT started (no installer pop-up)", out[:200])
        d = scenario("mac_nostub", {"uname": "echo Darwin", "xcode-select": "exit 0"})
        rc, out = run(["sh", "start.sh"], env_for(d, {"KDS_PY_FALLBACKS": "/usr/bin/python3"}), cwd=proj)
        c.check(rc == 0 and out.strip() == "PYTHON=/usr/bin/python3", "Mac WITH developer tools: /usr/bin/python3 is accepted when it is new enough", out[:200])
    # the places where the Mac installers put Python are tried when PATH has no Python (a double-clicked script)
    brew = T / "opt_homebrew_bin"
    brew.mkdir()
    fake_bin(brew, "python3", NEW)
    d = scenario("mac_brew", {"uname": "echo Darwin", "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.sh"], env_for(d, {"KDS_PY_FALLBACKS": f"/nonexistent/python3 {brew}/python3"}), cwd=proj)
    c.check(rc == 0 and out.strip() == f"PYTHON={brew}/python3", "no Python on PATH -> the fall-back places (Homebrew / python.org) are tried in order", out)
    c.check("/opt/homebrew/bin/python3" in (ROOT / "start.sh").read_text() and "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" in (ROOT / "start.sh").read_text(), "the built-in fall-back list names Homebrew and python.org")
    # Linux does not ask xcode-select
    d = scenario("linux_ok", {"uname": "echo Linux", "python3": NEW, "xcode-select": "echo CALLED >&2; exit 2"})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=proj)
    c.check(rc == 0 and "CALLED" not in out, "Linux: xcode-select is never called")
    # a path with spaces and non-ASCII letters
    sp = T / "ទីតាំង ថត with space"
    sp.mkdir()
    for f in SCRIPTS:
        shutil.copy(ROOT / f, sp / f)
    d = scenario("mac_ok2", {"uname": "echo Darwin", "python3": NEW, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.sh"], env_for(d), cwd=sp)
    c.check(rc == 0 and out.strip().startswith("PYTHON="), "a folder name with spaces and Khmer letters works")
    rc, out = run(["sh", str(sp / "start.sh")], env_for(d), cwd=T)
    c.check(rc == 0 and out.strip().startswith("PYTHON="), "start.sh can be started from another folder (it changes into its own folder)")

    # ---- start.command: a thin wrapper that keeps the window open on errors
    d = scenario("cmd_bad", {"uname": "echo Darwin", "python3": OLD, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.command"], env_for(d), cwd=proj, inp="\n")
    c.check(rc == 1 and "V_Heang Studio could not start (code 1)" in out and "Press Enter to close this window" in out and "brew install" in out, "start.command: shows the message and waits for Enter when it cannot start", out[-300:])
    d = scenario("cmd_ok", {"uname": "echo Darwin", "python3": NEW, "xcode-select": "exit 0"})
    rc, out = run(["sh", "start.command"], env_for(d), cwd=proj, inp="")
    c.check(rc == 0 and "could not start" not in out and "Press Enter" not in out, "start.command: no pause when everything is fine", out[-200:])
    rc, out = run(["sh", str(proj / "start.command")], env_for(d), cwd=T, inp="")
    c.check(rc == 0, "start.command works when started from another folder (a double-click starts it in the home folder)")

    # ---- a whole run in a scratch copy: venv, pip, server (a stub), second start, a broken venv
    real = T / "real"
    real.mkdir()
    shutil.copy(ROOT / "start.sh", real / "start.sh")
    (real / "requirements.txt").write_text("# nothing to install\n")
    (real / "server.py").write_text("import sys\nprint('SERVER STARTED with', sys.prefix.split('/')[-1], sys.version.split()[0])\n")
    e = {"PATH": os.environ["PATH"], "HOME": str(T)}
    rc, out = run(["sh", "start.sh"], e, cwd=real, timeout=180)
    c.check(rc == 0 and "[1/3] Creating the virtual environment (Python 3." in out and "[2/3]" in out and "[3/3]" in out and "SERVER STARTED with .venv" in out, "whole run: venv is created, packages checked, the server starts inside the venv", out[-500:])
    c.check((real / ".venv" / "bin" / "python").exists(), "whole run: .venv/bin/python exists")
    rc, out = run(["sh", "start.sh"], e, cwd=real, timeout=120)
    c.check(rc == 0 and "[1/3]" not in out and "SERVER STARTED" in out, "second start: the venv is reused", out[-300:])
    py = real / ".venv" / "bin" / "python"
    py.unlink()
    os.symlink("/nonexistent/python", py)
    rc, out = run(["sh", "start.sh"], e, cwd=real, timeout=180)
    c.check(rc == 0 and "does not work any more" in out and "[1/3]" in out and "SERVER STARTED" in out, "a broken .venv is replaced by a new one", out[-400:])
    (real / "requirements.txt").write_text("this-package-does-not-exist-kds-xyz==1.0\n")
    rc, out = run(["sh", "start.sh"], e, cwd=real, timeout=180)
    c.check(rc == 1 and "Package installation failed" in out and "SERVER STARTED" not in out, "pip failure: a clear message and exit code 1 (the server does not start)", out[-300:])
    shutil.rmtree(T, ignore_errors=True)

# ==================================================================================================================== B. server.py
if "B" in ONLY:
    import importlib

    srvmod = importlib.import_module("server")

    def busy(host="127.0.0.1"):
        s = socket.socket()
        s.bind((host, 0))
        s.listen(1)
        return s, s.getsockname()[1]

    # find a block of four consecutive free ports
    base = None
    for cand in range(41000, 42000, 7):
        socks = []
        try:
            for i in range(4):
                s = socket.socket()
                s.bind(("127.0.0.1", cand + i))
                socks.append(s)
            base = cand
            break
        except OSError:
            pass
        finally:
            for s in socks:
                s.close()
    c.check(base is not None, "found a few free ports for the test")
    holder = []
    for p in (base, base + 1):
        s = socket.socket()
        s.bind(("127.0.0.1", p))
        s.listen(1)
        holder.append(s)
    c.check(srvmod.port_is_free("127.0.0.1", base + 2) and not srvmod.port_is_free("127.0.0.1", base) and not srvmod.port_is_free("127.0.0.1", base + 1), "port_is_free: free / taken")
    c.check(srvmod.pick_port("127.0.0.1", base) == base + 2, "pick_port: 8000 taken, 8001 taken -> the next free one")
    c.check(srvmod.pick_port("127.0.0.1", base, tries=2) is None, "pick_port: nothing free in the range -> None")
    c.check(srvmod.pick_port("127.0.0.1", base + 2) == base + 2, "pick_port: the preferred port when it is free")
    rc, out = run([sys.executable, "server.py"], {"PORT": str(base), "HOST": "127.0.0.1", "NO_BROWSER": "1"}, cwd=str(ROOT), timeout=60)
    c.check(rc == 1 and f"Port {base} is already in use" in out and f"PORT={base + 1}" in out, "an explicit PORT that is taken -> a clear message, exit code 1 (no traceback)", out[:300])
    c.check("Traceback" not in out, "no traceback for a busy port")
    for s in holder:
        s.close()
    # the server picks another port by itself when PORT is not set (the default port may be busy: simulate by a different default)
    code = ("import server, socket, sys\n"
            "s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(1); busy = s.getsockname()[1]\n"
            "p = server.pick_port('127.0.0.1', busy)\n"
            "print('PICKED', p - busy)\n")
    rc, out = run([sys.executable, "-c", code], cwd=str(ROOT))
    c.check(rc == 0 and "PICKED 1" in out, "pick_port next to a port in use gives the following one", out)

    # certificates: only a Mac without a certificate store is changed
    import ssl  # noqa: E402

    real_platform, real_vp = sys.platform, ssl.get_default_verify_paths

    class VP:
        def __init__(self, f, d):
            self.openssl_cafile, self.openssl_capath = f, d

    def with_env(platform, vp, pre=None):
        for k in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
            os.environ.pop(k, None)
        os.environ.update(pre or {})
        sys.platform = platform
        ssl.get_default_verify_paths = lambda: vp
        try:
            srvmod.use_system_certificates()
            return os.environ.get("SSL_CERT_FILE")
        finally:
            sys.platform, ssl.get_default_verify_paths = real_platform, real_vp
            for k in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
                os.environ.pop(k, None)

    import certifi  # noqa: E402

    c.check(with_env("darwin", VP("/nonexistent/cert.pem", "/nonexistent/certs")) == certifi.where(), "Mac without certificates (python.org install): the certifi bundle is used")
    c.check(with_env("darwin", VP(certifi.where(), "/nonexistent")) is None, "Mac with a certificate store: nothing changes")
    c.check(with_env("linux", VP("/nonexistent", "/nonexistent")) is None and with_env("win32", VP("/nonexistent", "/nonexistent")) is None, "Windows / Linux: never changed (company proxies live in their own store)")
    c.check(with_env("darwin", VP("/nonexistent", "/nonexistent"), {"SSL_CERT_FILE": "/my/own.pem"}) == "/my/own.pem", "a SSL_CERT_FILE the user set is respected")

# ==================================================================================================================== C. macOS logic (simulated)
if "C" in ONLY:
    from app import vox, vox_setup  # noqa: E402

    real_platform, real_machine = sys.platform, vox_setup.platform.machine
    TD = Path(tempfile.mkdtemp(prefix="kds_mac_"))

    def sysctl_bin(values: dict):
        d = TD / f"sysctl_{len(list(TD.iterdir()))}"
        d.mkdir()
        body = "case \"$2\" in\n" + "".join(f"  {k}) echo {v};;\n" for k, v in values.items()) + "  *) exit 1;;\nesac"
        fake_bin(d, "sysctl", body)
        return d

    @contextlib.contextmanager
    def as_mac(machine="arm64", sysctl=None, home=None):
        old_path = os.environ.get("PATH", "")
        old_home = os.environ.get("HOME")
        sys.platform = "darwin"
        vox_setup.platform.machine = lambda: machine
        if sysctl is not None:
            os.environ["PATH"] = f"{sysctl}:{old_path}"
        if home:
            os.environ["HOME"] = str(home)
        try:
            yield
        finally:
            sys.platform = real_platform
            vox_setup.platform.machine = real_machine
            os.environ["PATH"] = old_path
            if old_home is not None:
                os.environ["HOME"] = old_home

    os.environ.pop("KDS_VOX_HOME", None)
    with as_mac("arm64"):
        c.check(vox_setup.mac_arch() == "arm64", "mac_arch: arm64 -> Apple Silicon")
    with as_mac("x86_64", sysctl_bin({"hw.optional.arm64": 1})):
        c.check(vox_setup.mac_arch() == "rosetta", "mac_arch: x86_64 Python on an Apple chip (sysctl says arm64) -> rosetta")
    with as_mac("x86_64", sysctl_bin({"hw.optional.arm64": 0})):
        c.check(vox_setup.mac_arch() == "intel", "mac_arch: x86_64 and no Apple chip -> intel")
    with as_mac("x86_64", sysctl_bin({})):
        c.check(vox_setup.mac_arch() == "intel", "mac_arch: sysctl does not know hw.optional.arm64 (an Intel Mac) -> intel")
    c.check(vox_setup.mac_arch() is None, "mac_arch: not a Mac (this Linux) -> None")
    with as_mac("arm64", sysctl_bin({"hw.memsize": 17179869184})):
        c.check(vox_setup.ram_gb() == 16.0, "ram_gb on a Mac: sysctl hw.memsize (16 GB)")
    with as_mac("arm64", sysctl_bin({"hw.memsize": 8589934592})):
        c.check(vox_setup.ram_gb() == 8.0, "ram_gb on a Mac: 8 GB")
    c.check((vox_setup.ram_gb() or 0) > 0, "ram_gb on this Linux still works")
    with as_mac("arm64", home=TD / "home"):
        home = vox_setup.vox_home()
        c.check(home == TD / "home" / "Library" / "KhmerDub" / "voxcpm" and " " not in str(home.name) and "data" not in home.parts, "macOS: the VoxCPM2 folder is ~/Library/KhmerDub/voxcpm (not in the project, no space)", str(home))
        os.environ["KDS_VOX_HOME"] = str(TD / "elsewhere")
        c.check(vox_setup.vox_home() == (TD / "elsewhere").resolve(), "macOS: KDS_VOX_HOME still wins")
        os.environ.pop("KDS_VOX_HOME")
    c.check(vox_setup.vox_home() == (Path(os.environ["KDS_DATA_DIR"]) / "voxcpm").resolve(), "Linux: unchanged (data/voxcpm)")

    # ---- the installer on a Mac that cannot run PyTorch
    class Args:
        cpu = False
        no_weights = True
        no_selftest = False

    def run_install(mac, ram, accel_seen=None, selftest_ok=True, tp=None):
        home = TD / f"vh_{mac}_{ram}"
        shutil.rmtree(home, ignore_errors=True)
        home.mkdir()
        saved = {k: getattr(vox_setup, k) for k in ("mac_arch", "ram_gb", "detect_gpu", "create_venv", "run", "install_torch", "capture", "download_weights", "selftest_with_fallback", "pip_cmd")}
        saved_du = shutil.disk_usage
        vox_setup.mac_arch = lambda: mac
        vox_setup.ram_gb = lambda: ram
        vox_setup.detect_gpu = lambda: None
        vox_setup.create_venv = lambda h: Path("/fake/venv/bin/python")
        vox_setup.run = lambda *a, **k: 0
        vox_setup.pip_cmd = lambda *a, **k: ["x"]
        vox_setup.install_torch = lambda py, gpu, cpu: dict(tp or {"version": "2.14.1", "cuda": False, "smoke": None, "mps": True, "mps_smoke": True})
        vox_setup.capture = lambda cmd, timeout=60: types.SimpleNamespace(returncode=0, stdout="3.11.9 2.0.3", stderr="")
        vox_setup.download_weights = lambda py, h: True

        def fake_selftest(py, h, accel, force_cpu=False):
            (accel_seen if accel_seen is not None else []).append(accel)
            return {"ok": selftest_ok, "device": "mps", "audio_s": 3, "elapsed_s": 2, "rtf": 0.7, "error": "boom"}
        vox_setup.selftest_with_fallback = fake_selftest
        shutil.disk_usage = lambda p: types.SimpleNamespace(total=1e12, used=1e11, free=5e11)
        buf = io.StringIO()
        code = None
        try:
            args = Args()
            args.no_weights = False
            with contextlib.redirect_stdout(buf):
                try:
                    code = vox_setup._install(args, home)
                except SystemExit as e:
                    code = e.code
        finally:
            for k, v in saved.items():
                setattr(vox_setup, k, v)
            shutil.disk_usage = saved_du
        info = {}
        try:
            info = json.loads((home / "install.json").read_text())
        except Exception:
            pass
        return code, buf.getvalue(), info

    code, out, info = run_install("intel", 16.0)
    c.check(code == 1 and "##ERROR INTEL_MAC" in out and "Intel Mac" in out and "Edge voices" in out and "PHASE 2" not in out, "installer on an Intel Mac: stops at once with ##ERROR INTEL_MAC (nothing is downloaded)", out[-300:])
    code, out, info = run_install("rosetta", 16.0)
    c.check(code == 1 and "##ERROR ROSETTA_PYTHON" in out and "universal2" in out and "PHASE 2" not in out, "installer with an Intel Python on an Apple chip: ##ERROR ROSETTA_PYTHON", out[-300:])
    seen = []
    code, out, info = run_install("arm64", 16.0, seen)
    c.check(code == 0 and "Apple Silicon Mac: VoxCPM2 will use the Mac's GPU" in out and "WARNING: this Mac has only" not in out and "No NVIDIA GPU detected" not in out and "Metal (MPS) check passed" in out, "installer on a 16 GB Apple Silicon Mac: uses Metal, no warning, no 'No NVIDIA GPU' text", out[-600:])
    c.check(info.get("ok") is True and info.get("mps") is True and info.get("cuda") is False and seen == [True], "installer: install.json says mps=true, the self-test is allowed to try the CPU as a fall-back", str(info) + str(seen))
    seen = []
    code, out, info = run_install("arm64", 8.0, seen)
    c.check(code == 0 and "WARNING: this Mac has only 8.0 GB of memory" in out, "installer on an 8 GB Apple Silicon Mac: warns about memory", out[-500:])
    seen = []
    code, out, info = run_install("arm64", 16.0, seen, tp={"version": "2.14.1", "cuda": False, "smoke": None, "mps": False})
    c.check(code == 0 and "Metal (MPS) is not available here" in out and info.get("mps") is False and seen == [False], "Apple Silicon without working Metal: the CPU is used and said so", out[-400:])
    seen = []
    code, out, info = run_install("arm64", 16.0, seen, selftest_ok=False)
    c.check(code == 1 and "SELFTEST_FAILED" in out, "a failing self-test on a Mac -> ##ERROR SELFTEST_FAILED")
    seen = []
    code, out, info = run_install(None, 16.0, seen, tp={"version": "2.14.1", "cuda": False, "smoke": None})
    c.check(code == 0 and "No NVIDIA GPU detected" in out and "Apple Silicon" not in out and info.get("mps") is False, "installer on a PC without an NVIDIA GPU: the old text, nothing about Macs", out[-400:])

    # ---- the fall-back to the CPU is used by Macs too
    calls = []
    saved_rs = vox_setup.run_selftest
    vox_setup.run_selftest = lambda py, h, dev="auto": (calls.append(dev), {"ok": dev == "cpu", "error": "mps failed"})[1]
    hm = TD / "vh_fallback"
    hm.mkdir()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        st = vox_setup.selftest_with_fallback(Path("/fake"), hm, True, False)
    vox_setup.run_selftest = saved_rs
    c.check(calls == ["auto", "cpu"] and st.get("ok") and st.get("gpu_failed") and json.loads((hm / "config.json").read_text()) == {"device": "cpu"}, "self-test: GPU (Metal) fails -> the CPU is tried and 'CPU only' is saved", str(calls))

    # ---- the manager: hardware, speed, worker environment
    home = make_stub_home(TD / "mgr_home")
    os.environ["KDS_VOX_HOME"] = str(home)
    m = vox.VoxManager() if hasattr(vox, "VoxManager") else vox.manager()
    m._hw = (0.0, None)
    with as_mac("arm64", sysctl_bin({"hw.memsize": 17179869184})):
        hw = m.hardware()
        c.check(hw["mac"] == "arm64" and hw["ram_gb"] == 16.0 and hw["platform"] == "darwin", "manager.hardware(): mac, ram_gb", str(hw))
        (home / "install.json").write_text(json.dumps({"ok": True, "weights": True, "device": "mps", "cuda": False, "mps": True}))
        sp = m.speed_note()
        c.check(sp["kind"] == "gpu" and sp["device"] == "mps" and sp["measured"] is False, "speed note: Metal counts as a GPU", str(sp))
        (home / "install.json").write_text(json.dumps({"ok": True, "weights": True, "device": "mps", "cuda": False, "selftest": {"rtf": 1.6, "device": "mps"}}))
        sp = m.speed_note()
        c.check(sp["measured"] is True and sp["rtf"] == 1.6 and sp["device"] == "mps", "speed note: a measured speed on mps", str(sp))
        (home / "install.json").write_text(json.dumps({"ok": True, "weights": True, "cuda": False}))
        sp = m.speed_note()
        c.check(sp["kind"] == "gpu", "speed note: Apple Silicon, nothing measured yet -> gpu")
        (home / "config.json").write_text(json.dumps({"device": "cpu"}))
        sp = m.speed_note()
        c.check(sp["kind"] == "cpu", "speed note: 'CPU only' chosen -> cpu")
        (home / "config.json").unlink()
    m._hw = (0.0, None)
    hw = m.hardware()
    c.check(hw["mac"] is None, "manager.hardware(): not a Mac -> mac None")

    # the worker is started with PYTORCH_ENABLE_MPS_FALLBACK on a Mac only
    (home / "install.json").write_text(json.dumps({"ok": True, "weights": True, "device": "cpu", "cuda": False}))
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kw):
            captured["env"] = kw.get("env")
            captured["cmd"] = cmd
            self.pid = 99999

        def poll(self):
            return None

    real_popen = vox.subprocess.Popen
    vox.subprocess.Popen = FakePopen
    try:
        with as_mac("arm64"):
            m2 = vox.VoxManager() if hasattr(vox, "VoxManager") else vox.manager()
            m2.start()
            mac_env = captured.get("env") or {}
        captured.clear()
        m3 = vox.VoxManager() if hasattr(vox, "VoxManager") else vox.manager()
        m3.start()
        lin_env = captured.get("env") or {}
    finally:
        vox.subprocess.Popen = real_popen
    c.check(mac_env.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1" and "PYTORCH_ENABLE_MPS_FALLBACK" not in lin_env, "worker environment: the Metal fall-back is on for a Mac only", str(mac_env.get("PYTORCH_ENABLE_MPS_FALLBACK")))
    os.environ.pop("KDS_VOX_HOME", None)
    shutil.rmtree(TD, ignore_errors=True)

# ==================================================================================================================== D. browser: warnings
if "D" in ONLY:
    from playwright.sync_api import sync_playwright  # noqa: E402

    DATA_P = WORK / "data_platform_ui"
    shutil.rmtree(DATA_P, ignore_errors=True)
    srv = Server(8065, DATA_P, make_stub_home(WORK / "vox_platform_ui"), name="platform_ui").start()
    errors = []
    try:
        base_status = srv.api("GET", "/api/vox/status").json()
        c.check("mac" in base_status["hardware"] and base_status["hardware"]["mac"] is None, "GET /api/vox/status: hardware.mac is null on this Linux", str(base_status["hardware"]))
        with sync_playwright() as pw:
            b = pw.chromium.launch()

            def page_with(status, lang="en", w=1440, h=900):
                ctx = b.new_context(viewport={"width": w, "height": h})
                ctx.add_init_script(f"localStorage.setItem('kds_lang','{lang}'); localStorage.setItem('kds_theme','dark'); localStorage.setItem('kds_settings', JSON.stringify({{ui:{{dock:false}}}}));")
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
                pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
                pg.route("**/api/vox/status", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(status)))
                pg.goto(srv.url + "/#settings", wait_until="networkidle")
                pg.wait_for_timeout(500)
                return ctx, pg

            def mk(mac, ram=16.0, installed=True, nvidia=None):
                st = json.loads(json.dumps(base_status))
                st["hardware"].update({"mac": mac, "ram_gb": ram, "nvidia": nvidia, "platform": "darwin" if mac else "linux"})
                st["installed"] = installed
                if not installed:
                    st["install"] = {}
                    st["worker"] = {"state": "stopped"}
                else:
                    st["install"] = dict(st.get("install") or {}, cuda=False, mps=mac == "arm64", device="mps" if mac == "arm64" else "cpu")
                return st

            def warn_text(pg):
                return pg.inner_text("#vox-hw-warn").strip()

            ctx, pg = page_with(mk(None, 16.0))
            c.check("very slow on this computer" in warn_text(pg) and "NVIDIA" not in warn_text(pg) and "GPU" not in warn_text(pg), "PC without a usable graphics card: the warning is there - and names no hardware", warn_text(pg))
            ctx.close()
            ctx, pg = page_with(mk("arm64", 16.0))
            c.check(warn_text(pg) == "", "Apple Silicon Mac with 16 GB: no warning (the Mac's GPU counts)", warn_text(pg))
            c.check(pg.is_enabled("#vox-reinstall") or pg.is_visible("#vox-reinstall"), "Apple Silicon: install buttons work")
            ctx.close()
            ctx, pg = page_with(mk("arm64", 16.0))
            c.check(not pg.is_visible("#vox-turbo-row"), "Apple Silicon: no Turbo switch (it needs an NVIDIA GPU)")
            ctx.close()
            ctx, pg = page_with(mk(None, 16.0))
            c.check(pg.is_visible("#vox-turbo-row"), "PC: the Turbo switch is still there")
            ctx.close()
            ctx, pg = page_with(mk("arm64", 8.0))
            wt = warn_text(pg)
            c.check("enough memory" in wt and "Edge voices" in wt and "GB" not in wt and "Metal" not in wt, "Apple Silicon Mac with 8 GB: warns about memory (no numbers, no hardware names)", wt)
            ctx.close()
            ctx, pg = page_with(mk("arm64", 8.0), lang="km")
            wt = warn_text(pg)
            c.check("memory" in wt and "Edge" in wt and "GB" not in wt and "Metal" not in wt and not wt.startswith("This Mac"), "the memory warning in Khmer (no numbers, no hardware names)", wt)
            ctx.close()
            ctx, pg = page_with(mk("intel", 16.0, installed=False))
            wt = warn_text(pg)
            c.check("Intel Mac" in wt and "cannot be installed" in wt, "Intel Mac: the warning says VoxCPM2 cannot be installed", wt)
            c.check(pg.is_disabled("#vox-install"), "Intel Mac: the Install button is disabled")
            ctx.close()
            ctx, pg = page_with(mk("rosetta", 16.0, installed=False))
            wt = warn_text(pg)
            c.check("Rosetta" in wt and "universal2" in wt and pg.is_disabled("#vox-install"), "Rosetta Python: warning + disabled Install", wt)
            ctx.close()
            ctx, pg = page_with(mk("intel", 16.0, installed=False))
            pg.goto(srv.url + "/#dub", wait_until="networkidle")
            pg.click('.seg[data-bind="voice.engine"] button[data-value="voxcpm"]')
            pg.wait_for_timeout(500)
            banner = pg.inner_text(".vox-banner >> nth=0")
            c.check("Intel Mac" in banner and "Install in Settings" not in banner, "Intel Mac: the voice picker says VoxCPM2 cannot run (no 'install' link)", banner)
            ctx.close()
            ctx, pg = page_with(mk("arm64", 16.0, installed=True))
            pg.goto(srv.url + "/#dub", wait_until="networkidle")
            pg.click('.seg[data-bind="voice.engine"] button[data-value="voxcpm"]')
            pg.wait_for_timeout(500)
            banner = pg.inner_text(".vox-banner >> nth=0")
            c.check("very slow on this computer" not in banner, "Apple Silicon: no 'very slow on this computer' banner", banner)
            ctx.close()
            ctx, pg = page_with(mk(None, 16.0, installed=True))
            pg.goto(srv.url + "/#dub", wait_until="networkidle")
            pg.click('.seg[data-bind="voice.engine"] button[data-value="voxcpm"]')
            pg.wait_for_timeout(500)
            banner = pg.inner_text(".vox-banner >> nth=0")
            c.check("very slow on this computer" in banner or "Engine" in banner, "PC without GPU: banners as before", banner)
            ctx.close()
            # a Mac types ⌘V, not Ctrl+V
            for plat, want, label in (("MacIntel", "⌘V", "Mac"), ("Win32", "Ctrl+V", "Windows"), ("Linux x86_64", "Ctrl+V", "Linux")):
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                ctx.add_init_script(f"localStorage.setItem('kds_lang','en'); localStorage.setItem('kds_settings', JSON.stringify({{ui:{{dock:false}}}})); Object.defineProperty(navigator, 'platform', {{ get: () => '{plat}' }});")
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
                pg.goto(srv.url + "/#dub", wait_until="networkidle")
                pg.click("#btn-paste")
                pg.wait_for_selector("#toasts .toast", timeout=5000)
                tt = pg.inner_text("#toasts .toast")
                c.check(want in tt and (("Ctrl+V" not in tt) if label == "Mac" else ("⌘" not in tt)), f"{label}: the clipboard hint says {want}", tt)
                ctx.close()
            c.check(not errors, "no JavaScript errors", str(errors[:3]))
            b.close()
    finally:
        srv.stop()

# ==================================================================================================================== E. release tools
if "E" in ONLY:
    import zipfile
    tmp = Path(tempfile.mkdtemp(prefix="kds_tools_", dir=str(WORK)))
    try:
        copy = tmp / "khmer-dubbing-studio"
        shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("data", "__pycache__", ".venv", "fixtures", "*.zip"))
        py = sys.executable

        def txt(rel):
            return (copy / rel).read_text(encoding="utf-8")

        rc, out = run([py, "tools/bump_version.py", "--check"], cwd=copy)
        c.check(rc == 0 and VERSION in out, "bump_version --check: the four places agree", out[-200:])
        rc, out = run([py, "tools/bump_version.py", "9.8.7"], cwd=copy)
        c.check(rc == 0 and '__version__ = "9.8.7"' in txt("app/__init__.py") and 'name="kds-ui" content="9.8.7"' in txt("static/index.html")
                and "KDS_UI_VERSION = '9.8.7'" in txt("static/js/app.js") and "I18N_VERSION = '9.8.7'" in txt("static/js/i18n.js"),
                "bump_version 9.8.7 changes all four places", out[-200:])
        rc, out = run([py, "tools/bump_version.py", "banana"], cwd=copy)
        c.check(rc == 2 and "not a version number" in out, "bump_version refuses what is not MAJOR.MINOR.PATCH")
        (copy / "static/js/i18n.js").write_bytes(txt("static/js/i18n.js").replace("9.8.7", "1.0.0", 1).encode("utf-8"))
        rc, out = run([py, "tools/bump_version.py", "--check"], cwd=copy)
        c.check(rc == 1 and "MISMATCH" in out, "bump_version --check catches a place that was forgotten")
        rc, out = run([py, "tools/build_zip.py", "--out", str(tmp / "refused")], cwd=copy)
        c.check(rc == 1 and not (tmp / "refused").exists(), "build_zip refuses to build while the four version places disagree", out[-200:])
        run([py, "tools/bump_version.py", "9.8.7"], cwd=copy)

        # a good build
        outdir = tmp / "out"
        rc, out = run([py, "tools/build_zip.py", "--out", str(outdir)], cwd=copy)
        z = outdir / "khmer-dubbing-studio-v9.8.7.zip"
        c.check(rc == 0 and z.exists(), "build_zip builds khmer-dubbing-studio-v<version>.zip", out[-300:])
        if z.exists():
            zf = zipfile.ZipFile(z)
            info = {i.filename: i for i in zf.infolist()}
            mode = lambda n: (info["khmer-dubbing-studio/" + n].external_attr >> 16) & 0o777  # noqa: E731
            c.check(all(n.startswith("khmer-dubbing-studio/") for n in info), "zip: one top-level folder")
            c.check(all(mode(n) == 0o755 for n in ("start.sh", "start.command", "install-voxcpm.sh", "install-voxcpm.command", "tests/run_all.sh")),
                    "zip: the launchers and run_all.sh are stored executable (0755)")
            c.check(mode("start.bat") == 0o644 and mode("app/main.py") == 0o644 and mode("tools/build_zip.py") == 0o644, "zip: everything else is 0644")
            raw = zf.read("khmer-dubbing-studio/start.bat")
            c.check(raw.count(b"\r\n") == raw.count(b"\n") > 5, "zip: start.bat keeps its Windows line endings")
            c.check(all(i.create_system == 3 for i in info.values()), "zip: marked as made on Unix (so unzip keeps the modes)")
            c.check(not any("/data/" in n or "__pycache__" in n or n.endswith((".pyc", ".zip")) for n in info), "zip: no data/, caches or zips")
            c.check({"khmer-dubbing-studio/" + n for n in ("DEVELOPMENT.md", "HANDOFF_PROMPT.md", "README.md", "CHANGELOG.md", "tests/lib.py", "tools/bump_version.py")} <= set(info),
                    "zip: documents, tests and tools are inside")

        # refusals: a wrong line ending must stop the build (a .bat with LF or a .sh with CR breaks on the user's machine)
        bat = (copy / "start.bat").read_bytes()
        (copy / "start.bat").write_bytes(bat.replace(b"\r\n", b"\n"))
        rc, out = run([py, "tools/build_zip.py", "--out", str(tmp / "o2")], cwd=copy)
        c.check(rc == 1 and "start.bat" in out and "CRLF" in out and not (tmp / "o2").exists(), "build_zip refuses a start.bat with Unix line endings", out[-200:])
        (copy / "start.bat").write_bytes(bat)
        sh = (copy / "start.sh").read_bytes()
        (copy / "start.sh").write_bytes(sh.replace(b"\n", b"\r\n"))
        rc, out = run([py, "tools/build_zip.py", "--out", str(tmp / "o3")], cwd=copy)
        c.check(rc == 1 and "start.sh" in out and "LF" in out, "build_zip refuses a start.sh with Windows line endings", out[-200:])
        (copy / "start.sh").write_bytes(sh)
        (copy / "tools" / "extra.sh").write_text("#!/bin/sh\necho hi\n")
        rc, out = run([py, "tools/build_zip.py", "--out", str(tmp / "o4")], cwd=copy)
        c.check(rc == 1 and "extra.sh" in out and "EXECUTABLE" in out, "build_zip refuses a new shell script that has no executable mode listed", out[-200:])
        (copy / "tools" / "extra.sh").unlink()
        rc, out = run([py, "tools/build_zip.py", "--out", str(tmp / "o5")], cwd=copy)
        c.check(rc == 0, "…and builds again once everything is right", out[-200:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

sys.exit(c.done())
