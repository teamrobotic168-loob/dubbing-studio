"""VoxCPM2 installer + hardware detection (standard library only).

Why a separate environment?  VoxCPM2 needs Python 3.10-3.12 and PyTorch (2-4 GB), while the
dashboard itself runs on any Python 3.10+ with a handful of tiny packages.  So VoxCPM2 lives in
its own virtual environment and is driven through a small local worker process (vox_worker.py).

Run it from the project folder:

    python -m app.vox_setup                 # install (GPU build of PyTorch when an NVIDIA GPU is found)
    python -m app.vox_setup --cpu           # force the CPU build of PyTorch
    python -m app.vox_setup --no-weights    # skip the 5 GB model download (testing)

The dashboard runs the same command from Settings -> VoxCPM2 -> Install.  Progress markers
("##PHASE i/n text", "##PROGRESS pct text", "##ERROR code text") are parsed by the dashboard.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

MODEL_ID = os.environ.get("KDS_VOX_MODEL", "openbmb/VoxCPM2")
PHASES = 6
TORCH_BASE = "https://download.pytorch.org/whl"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
APP_DIR = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# locations
# --------------------------------------------------------------------------- #
def vox_home() -> Path:
    """Where the VoxCPM2 environment, model and logs live.

    Windows: a SHORT path (%LOCALAPPDATA%\\KhmerDub\\voxcpm) because PyTorch has very deep
    folders and Windows still limits paths to 260 characters in many setups.
    macOS: ~/Library/KhmerDub/voxcpm - not inside the project folder, which may live in iCloud Drive (Desktop / Documents) and
    would then upload 10 GB; no space in the path (a space breaks the launchers inside a virtual environment).
    """
    env = os.environ.get("KDS_VOX_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "KhmerDub" / "voxcpm"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "KhmerDub" / "voxcpm"
    data = os.environ.get("KDS_DATA_DIR")
    return (Path(data) if data else APP_DIR.parent / "data").resolve() / "voxcpm"


def venv_dir(home: Optional[Path] = None) -> Path:
    return (home or vox_home()) / "venv"


def venv_python(home: Optional[Path] = None) -> Path:
    v = venv_dir(home)
    return v / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def hf_home(home: Optional[Path] = None) -> Path:
    return (home or vox_home()) / "hf"


def install_json(home: Optional[Path] = None) -> Path:
    return (home or vox_home()) / "install.json"


# --------------------------------------------------------------------------- #
# heartbeat: "an installer is running"
# --------------------------------------------------------------------------- #
HEARTBEAT_STALE_S = 25.0


def heartbeat_path(home: Optional[Path] = None) -> Path:
    return (home or vox_home()) / "setup.alive"


def heartbeat_age(home: Optional[Path] = None) -> Optional[float]:
    """Seconds since a running installer last touched its heartbeat file (None: there is none)."""
    try:
        return max(0.0, time.time() - heartbeat_path(home).stat().st_mtime)
    except OSError:
        return None


def installer_pid(home: Optional[Path] = None) -> Optional[int]:
    try:
        return int(json.loads(heartbeat_path(home).read_text(encoding="utf-8")).get("pid"))
    except Exception:
        return None


class Heartbeat:
    """While the installer runs it touches a small file every few seconds.

    If the dashboard is closed / restarted in the middle of an installation (the installer keeps going in the background),
    the new dashboard sees the fresh heartbeat: it shows the progress and does not start a second installer on top of the
    first one.  A crashed installer simply stops beating and the file goes stale after HEARTBEAT_STALE_S seconds.
    Plain file times only - no OS-specific process APIs.
    """

    def __init__(self, home: Path):
        self.path = heartbeat_path(home)
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, daemon=True, name="setup-heartbeat")

    def _beat(self) -> None:
        try:
            self.path.write_text(json.dumps({"pid": os.getpid(), "t": time.time()}), encoding="utf-8")
        except OSError:
            pass

    def _run(self) -> None:
        while not self._stop.wait(4.0):
            self._beat()

    def __enter__(self) -> "Heartbeat":
        self._beat()
        self._th.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        try:
            self.path.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# hardware detection
# --------------------------------------------------------------------------- #
def _nvidia_smi() -> Optional[str]:
    cands = [shutil.which("nvidia-smi")]
    if os.name == "nt":
        cands += [r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"]
    for c in cands:
        if c and Path(c).exists():
            return c
    return None


def parse_nvidia_smi(csv_text: str, header_text: str = "") -> Optional[dict]:
    """Parse `nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap` (+ the plain header)."""
    lines = [l.strip() for l in (csv_text or "").splitlines() if l.strip()]
    if not lines:
        return None
    best = None
    for l in lines:
        parts = [p.strip() for p in l.split(",")]
        if len(parts) < 3:
            continue
        try:
            vram = float(parts[1]) / 1024.0
        except ValueError:
            vram = 0.0
        cc = None
        if len(parts) >= 4:
            try:
                cc = float(parts[3])
            except ValueError:
                cc = None
        g = {"name": parts[0], "vram_gb": round(vram, 1), "driver": parts[2], "cc": cc}
        if best is None or g["vram_gb"] > best["vram_gb"]:
            best = g
    if best is None:
        return None
    m = re.search(r"CUDA Version:\s*([0-9]+(?:\.[0-9]+)?)", header_text or "")
    best["cuda_driver"] = float(m.group(1)) if m else None
    best["count"] = len(lines)
    return best


def detect_gpu() -> Optional[dict]:
    exe = _nvidia_smi()
    if not exe:
        return None
    try:
        q = subprocess.run(
            [exe, "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW,
        )
        txt = q.stdout
        if q.returncode != 0 or not txt.strip():  # old drivers do not know "compute_cap"
            q = subprocess.run(
                [exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW,
            )
            txt = q.stdout
        h = subprocess.run([exe], capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW)
        return parse_nvidia_smi(txt, h.stdout)
    except Exception:
        return None


def _sysctl(name: str) -> Optional[str]:
    try:
        r = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def mac_arch() -> Optional[str]:
    """None = not a Mac;  'arm64' = Apple Silicon (M1 or newer);  'intel' = an Intel Mac;
    'rosetta' = an Apple Silicon Mac whose Python is the Intel (x86_64) build, running under Rosetta."""
    if sys.platform != "darwin":
        return None
    if platform.machine().lower() in ("arm64", "aarch64"):
        return "arm64"
    return "rosetta" if _sysctl("hw.optional.arm64") == "1" else "intel"


def ram_gb() -> Optional[float]:
    try:
        if sys.platform == "darwin":                  # macOS has no SC_PHYS_PAGES
            v = _sysctl("hw.memsize")
            if v and v.isdigit():
                return round(int(v) / 1024 ** 3, 1)
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = MS()
            ms.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))  # type: ignore[attr-defined]
            return round(ms.ullTotalPhys / 1024 ** 3, 1)
        if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
            return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 1)
    except Exception:
        pass
    return None


def torch_candidates(gpu: Optional[dict]) -> List[str]:
    """PyTorch CUDA wheel indexes to try, best first. Empty list -> use the CPU build."""
    if not gpu:
        return []
    drv = gpu.get("cuda_driver")
    cc = gpu.get("cc")
    if drv is not None and drv < 12.0:
        return []                      # CUDA-11 era driver cannot run CUDA-12 wheels
    out: List[str] = []
    if cc is not None and cc >= 12.0:  # Blackwell (RTX 50xx) needs CUDA >= 12.8 kernels
        if drv is None or drv >= 13.0:
            out.append("cu130")
        if drv is None or drv >= 12.8:
            out.append("cu128")
        return out
    out.append("cu126")               # works on any driver that reports CUDA 12.x
    if drv is not None and drv >= 13.0:
        out.append("cu130")
    return out


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def log(msg: str = "") -> None:
    print(msg, flush=True)


def phase(i: int, text: str) -> None:
    log(f"##PHASE {i}/{PHASES} {text}")


def fail(code: str, text: str) -> "None":
    log(f"##ERROR {code} {text}")
    raise SystemExit(1)


def run(cmd: List[str], env: Optional[dict] = None, cwd: Optional[str] = None, show: bool = True) -> int:
    """Run a command and stream its output into our log."""
    if show:
        log("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.Popen(
        [str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=cwd,
        creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    assert p.stdout is not None
    for line in p.stdout:
        line = line.rstrip()
        if line:
            log("   " + line[:400])
    return p.wait()


def capture(cmd: List[str], timeout: int = 120, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, env=env,
                          creationflags=NO_WINDOW, encoding="utf-8", errors="replace")


def py_version(exe: str) -> Optional[tuple]:
    try:
        r = capture([exe, "-c", "import sys, venv, ensurepip; print(sys.version_info[0], sys.version_info[1], sys.version_info[2])"], timeout=30)
        if r.returncode == 0:
            a, b, c = r.stdout.split()[:3]
            return int(a), int(b), int(c)
    except Exception:
        pass
    return None


def find_python() -> Optional[str]:
    """A Python 3.10 / 3.11 / 3.12 interpreter (VoxCPM2 does not support 3.13+ yet). 3.11 is the most tested."""
    found: dict = {}

    def consider(exe: Optional[str]) -> None:
        if not exe or exe in [v[1] for v in found.values()]:
            return
        v = py_version(exe)
        if v and (3, 10) <= v[:2] <= (3, 12):
            found.setdefault(v[:2], (v, exe))

    consider(sys.executable)
    for ver in ("3.11", "3.10", "3.12"):
        consider(shutil.which(f"python{ver}"))
    if os.name == "nt":
        for ver in ("3.11", "3.10", "3.12"):
            try:
                r = capture(["py", f"-{ver}", "-c", "import sys; print(sys.executable)"], timeout=20)
                if r.returncode == 0 and r.stdout.strip():
                    consider(r.stdout.strip().splitlines()[-1])
            except Exception:
                pass
    for key in ((3, 11), (3, 10), (3, 12)):
        if key in found:
            return found[key][1]
    return None


def pip_cmd(py: Path, *args: str) -> List[str]:
    return [str(py), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--prefer-binary", *args]


def probe_torch(py: Path) -> dict:
    """What PyTorch (if any) is installed in the VoxCPM environment, and can it really use the GPU?"""
    code = (
        "import json\n"
        "r={'version':None,'cuda':False,'smoke':None,'name':None}\n"
        "try:\n"
        "    import torch\n"
        "    r['version']=torch.__version__\n"
        "    if torch.cuda.is_available():\n"
        "        r['cuda']=True; r['name']=torch.cuda.get_device_name(0)\n"
        "        try:\n"
        "            x=torch.ones(32,32,device='cuda',dtype=torch.bfloat16); (x@x).float().sum().item(); torch.cuda.synchronize(); r['smoke']=True\n"
        "        except Exception as e:\n"
        "            r['smoke']=False; r['smoke_error']=str(e)[:200]\n"
        "    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():\n"
        "        r['mps']=True\n"
        "        try:\n"
        "            x=torch.ones(32,32,device='mps'); (x@x).sum().item(); r['mps_smoke']=True\n"
        "        except Exception as e:\n"
        "            r['mps_smoke']=False; r['smoke_error']=str(e)[:200]\n"
        "except Exception as e:\n"
        "    r['error']=str(e)[:200]\n"
        "print('PROBE '+json.dumps(r))\n"
    )
    try:
        out = capture([py, "-c", code], timeout=180).stdout
        for line in out.splitlines():
            if line.startswith("PROBE "):
                return json.loads(line[6:])
    except Exception:
        pass
    return {"version": None, "cuda": False, "smoke": None}


# --------------------------------------------------------------------------- #
# steps
# --------------------------------------------------------------------------- #
def _rmtree_hard(path: Path) -> None:
    """Delete a folder tree; read-only files and a short-lived lock (antivirus, a process that is still exiting) are retried."""
    def fix(func, p, *_):
        try:
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass

    for _ in range(4):
        if not path.exists():
            return
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=fix)
        else:
            shutil.rmtree(path, onerror=fix)
        if not path.exists():
            return
        time.sleep(1.0)


def _venv_usable(py: Path) -> bool:
    """The environment exists AND pip works in it (a cancelled or crashed first attempt can leave a half-built one)."""
    if not py.exists() or not py_version(str(py)):
        return False
    try:
        return capture([py, "-m", "pip", "--version"], timeout=90).returncode == 0
    except Exception:
        return False


def create_venv(home: Path) -> Path:
    py = venv_python(home)
    vdir = venv_dir(home)
    if _venv_usable(py):
        log(f"Using the existing environment: {vdir}")
        return py
    if vdir.exists():
        log("The previous environment is incomplete (an earlier installation was interrupted) - rebuilding it ...")
        _rmtree_hard(vdir)
    exe = find_python()
    if exe:
        v = py_version(exe)
        log(f"Using Python {v[0]}.{v[1]}.{v[2]}  ({exe})")
        if run([exe, "-m", "venv", str(vdir)]) != 0 or not py.exists():
            fail("VENV_FAILED", "Could not create the virtual environment.")
    else:
        log(f"No Python 3.10-3.12 found (this one is {sys.version.split()[0]}). Downloading a private Python 3.11 with 'uv' ...")
        if run([sys.executable, "-m", "uv", "--version"], show=False) != 0:
            rc = run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "uv"])
            if rc != 0:
                rc = run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--user", "uv"])
            if rc != 0:
                rc = run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--break-system-packages", "uv"])
            if rc != 0:
                fail("UV_FAILED", "Could not install 'uv' (needed to fetch Python 3.11). Install Python 3.11 from python.org and try again.")
        env = dict(os.environ)
        if run([sys.executable, "-m", "uv", "venv", "--seed", "--python", "3.11", str(vdir)], env=env) != 0 or not py.exists():
            fail("PYTHON_DOWNLOAD_FAILED", "Could not download Python 3.11. Check your Internet connection or install Python 3.11 from python.org.")
    return py


def install_torch(py: Path, gpu: Optional[dict], force_cpu: bool) -> dict:
    """Install PyTorch (GPU build when it really works, otherwise CPU). Returns the final probe."""
    sysname = sys.platform
    cands = [] if force_cpu else torch_candidates(gpu)
    cur = probe_torch(py)
    if cur.get("version"):
        good = (cands and cur.get("cuda") and cur.get("smoke")) or ((not cands) and not cur.get("cuda") and "cu" not in cur["version"].split("+")[-1])
        if good:
            log(f"PyTorch {cur['version']} is already installed - keeping it.")
            return cur
    if gpu and not cands and not force_cpu:
        drv = gpu.get("cuda_driver")
        if (gpu.get("cc") or 0) >= 12.0:
            log(f"This GPU (RTX 50 series) needs an NVIDIA driver with CUDA 12.8 or newer; yours reports CUDA {drv}. "
                "Update your NVIDIA driver to use the GPU. Installing the CPU build for now.")
        else:
            log(f"NVIDIA driver reports CUDA {drv}; CUDA 12 or newer is needed for the GPU build. "
                "Update your NVIDIA driver to use the GPU. Installing the CPU build for now.")
    for c in cands:
        log(f"Installing PyTorch ({c} = NVIDIA GPU build, about 3 GB) ...")
        rc = run(pip_cmd(py, "--upgrade", "--force-reinstall", "torch", "torchaudio", "--index-url", f"{TORCH_BASE}/{c}"))
        if rc != 0:
            log(f"   {c} could not be installed.")
            continue
        pr = probe_torch(py)
        if pr.get("cuda") and pr.get("smoke"):
            log(f"GPU check passed: {pr.get('name')} (PyTorch {pr.get('version')})")
            return pr
        log(f"   {c} installed but the GPU test failed ({pr.get('smoke_error') or 'CUDA not available'}).")
    if cands:
        log("The GPU build did not work on this computer -> using the CPU build (much slower).")
    log("Installing PyTorch (CPU build) ...")
    if sysname == "darwin":
        rc = run(pip_cmd(py, "torch", "torchaudio"))
    else:
        rc = run(pip_cmd(py, "--upgrade", "--force-reinstall", "torch", "torchaudio", "--index-url", f"{TORCH_BASE}/cpu"))
    if rc != 0:
        fail("TORCH_FAILED", "PyTorch could not be installed. Check your Internet connection and free disk space (about 6 GB), then try again.")
    return probe_torch(py)


def weights_size_hint() -> int:
    try:
        import urllib.request

        d = json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{MODEL_ID}?blobs=true", timeout=15))
        tot = sum(int(s.get("size") or 0) for s in d.get("siblings", []))
        if tot > 1e8:
            return tot
    except Exception:
        pass
    return int(4.96e9)


def dir_size(p: Path) -> int:
    total = 0
    try:
        for f in p.rglob("*"):
            try:
                if f.is_file() and not f.is_symlink():      # snapshot folders hold symlinks to the blobs: count each file once
                    total += f.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


def download_weights(py: Path, home: Path) -> bool:
    hf = hf_home(home)
    hf.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HF_HOME=str(hf), HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_SYMLINKS_WARNING="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    env.pop("HF_HUB_OFFLINE", None)
    total = weights_size_hint()
    log(f"Downloading {MODEL_ID} (about {total / 1e9:.1f} GB). You can close the browser - it keeps going. If it stops, run Install again: it resumes.")
    stop = threading.Event()

    def watcher():
        last = -1
        while not stop.wait(3.0):
            sz = dir_size(hf)
            pct = int(min(99, sz * 100 / total))
            if pct != last:
                last = pct
                log(f"##PROGRESS {pct} {sz / 1e9:.2f} / {total / 1e9:.2f} GB")

    th = threading.Thread(target=watcher, daemon=True)
    th.start()
    code = (
        "import os,sys\n"
        "from huggingface_hub import snapshot_download\n"
        f"p=snapshot_download(repo_id={MODEL_ID!r})\n"
        "print('MODEL_PATH', p)\n"
    )
    rc = 1
    for attempt in range(3):
        rc = run([py, "-c", code], env=env, show=attempt == 0)
        if rc == 0:
            break
        log(f"Download interrupted (attempt {attempt + 1}/3) - retrying in 5 s ...")
        time.sleep(5)
    stop.set()
    th.join(timeout=2)
    if rc == 0:
        log("##PROGRESS 100 model downloaded")
    return rc == 0


def run_selftest(py: Path, home: Path, device: str = "auto") -> dict:
    worker = APP_DIR / "vox_worker.py"
    out_wav = home / "tmp" / "selftest.wav"
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HF_HOME=str(hf_home(home)), HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1", TOKENIZERS_PARALLELISM="false")
    if sys.platform == "darwin":
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"      # an operation the Mac GPU lacks runs on the CPU instead of stopping
    log("Running a real test: loading the model and speaking one Khmer sentence (the first run can take a few minutes) ...")
    p = subprocess.Popen([str(py), "-u", str(worker), "--selftest", "--device", device, "--out", str(out_wav)], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env, creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace")
    result: dict = {"ok": False, "error": "no result"}
    assert p.stdout is not None
    for line in p.stdout:
        line = line.rstrip()
        if line.startswith("SELFTEST "):
            try:
                result = json.loads(line[9:])
            except Exception:
                pass
        elif line:
            log("   " + line[:300])
    p.wait()
    return result


def selftest_with_fallback(py: Path, home: Path, use_cuda: bool, force_cpu: bool = False) -> dict:
    """Self-test on the GPU (NVIDIA, or the Mac's Metal GPU: `use_cuda` means 'a GPU is used'); when that fails (e.g. an 8 GB card out of
    memory) test the CPU so the user is not stuck."""
    st = run_selftest(py, home, "cpu" if force_cpu else "auto")
    if not st.get("ok") and use_cuda and not force_cpu:
        log("The GPU test failed (" + str(st.get("error"))[:200] + "). Trying the CPU instead ...")
        st2 = run_selftest(py, home, "cpu")
        if st2.get("ok"):
            st2["gpu_failed"] = True
            st2["gpu_error"] = str(st.get("error"))[:300]
            try:
                (home / "config.json").write_text(json.dumps({"device": "cpu"}), encoding="utf-8")
            except OSError:
                pass
            log("The CPU works, so 'CPU only' was selected in Settings. Free GPU memory and switch back to 'Automatic' to retry the GPU.")
            return st2
    return st


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Install VoxCPM2 for V_Heang Studio")
    ap.add_argument("--cpu", action="store_true", help="install the CPU build of PyTorch even if an NVIDIA GPU exists")
    ap.add_argument("--no-weights", action="store_true", help="skip the model download and the self-test")
    ap.add_argument("--no-selftest", action="store_true", help="skip the final self-test")
    args = ap.parse_args(argv)

    home = vox_home()
    home.mkdir(parents=True, exist_ok=True)
    with Heartbeat(home):
        return _install(args, home)


def _install(args: argparse.Namespace, home: Path) -> int:
    (home / "tmp").mkdir(exist_ok=True)
    # pip's download cache lives inside the install folder: the PyTorch wheel alone is ~3 GB. It is deleted again once the
    # packages are installed (the default cache would stay hidden on drive C: for ever) but kept after a failure, so a retry
    # does not download the big wheel a second time.
    pip_cache = home / "pipcache"
    os.environ["PIP_CACHE_DIR"] = str(pip_cache)
    info: dict = {"ok": False, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        install_json(home).unlink()
    except OSError:
        pass

    phase(1, "Checking this computer")
    gpu = detect_gpu()
    mac = mac_arch()
    log(f"Install folder: {home}")
    log(f"System: {sys.platform}{' (' + mac + ')' if mac else ''}, RAM {ram_gb() or '?'} GB, CPU cores {os.cpu_count()}")
    if mac == "intel":
        fail("INTEL_MAC", "This is an Intel Mac. PyTorch (which VoxCPM2 needs) no longer supports Intel Macs - its last version for them is 2.2 - "
                          "so VoxCPM2 cannot be installed here. The Edge voices (Srey Mom, Piseth) work fully.")
    if mac == "rosetta":
        fail("ROSETTA_PYTHON", "This Mac has an Apple chip, but the Python that runs V_Heang Studio is the Intel version (running under Rosetta), and PyTorch has no "
                               "Intel build for macOS any more. Install the macOS installer (universal2) of Python from python.org, delete the .venv folder "
                               "and start V_Heang Studio again.")
    if mac == "arm64":
        log("Apple Silicon Mac: VoxCPM2 will use the Mac's GPU (Metal / MPS). It needs about 10 GB of free memory.")
        mem = ram_gb()
        if mem is not None and mem < 15:
            log(f"WARNING: this Mac has only {mem} GB of memory. VoxCPM2 may be very slow or fail here (then use 'CPU only' in Settings or the Edge voices).")
    elif gpu:
        log(f"NVIDIA GPU: {gpu['name']} - {gpu['vram_gb']} GB VRAM, driver CUDA {gpu.get('cuda_driver')}, compute {gpu.get('cc')}")
        if gpu["vram_gb"] < 7.5:
            log(f"WARNING: only {gpu['vram_gb']} GB VRAM. VoxCPM2 wants about 8 GB; it may run out of memory (then use 'CPU only' in Settings).")
    else:
        log("No NVIDIA GPU detected. VoxCPM2 will run on the CPU - it works, but is MUCH slower than real time.")
        mem = ram_gb()
        if mem is not None and mem < 7.5:
            log(f"WARNING: only {mem} GB of RAM. The model needs about 6-8 GB in memory on the CPU; it may not fit.")
    free = shutil.disk_usage(home).free / 1e9
    log(f"Free disk space here: {free:.1f} GB (about 10 GB needed)")
    if free < 9:
        fail("DISK_FULL", f"Only {free:.1f} GB free on the drive that holds {home}. About 10 GB are needed.")

    phase(2, "Preparing the Python environment")
    py = create_venv(home)
    rc = run(pip_cmd(py, "--upgrade", "pip", "wheel", "setuptools"), show=False)
    if rc != 0:
        log("   (pip could not be upgraded - continuing)")

    phase(3, "Installing PyTorch")
    tp = install_torch(py, gpu, args.cpu)
    use_cuda = bool(tp.get("cuda") and tp.get("smoke"))
    use_mps = bool(mac == "arm64" and tp.get("mps") and tp.get("mps_smoke"))
    info.update({"torch": tp.get("version"), "cuda": use_cuda, "mps": use_mps, "gpu": tp.get("name") or (gpu or {}).get("name")})
    if mac == "arm64":
        log("Metal (MPS) check passed." if use_mps else f"Metal (MPS) is not available here ({tp.get('smoke_error') or 'not supported by this macOS / PyTorch'}) - the CPU will be used (slow).")

    phase(4, "Installing VoxCPM2")
    rc = run(pip_cmd(py, "voxcpm>=2.0"))
    if rc != 0:
        fail("VOXCPM_FAILED", "The voxcpm package could not be installed (see the log above). If it mentions 'Microsoft Visual C++', "
                              "install 'Build Tools for Visual Studio' or use Python 3.11 from python.org.")
    r = capture([py, "-c", "from importlib import metadata as m; import sys; print(sys.version.split()[0], m.version('voxcpm'))"], timeout=60)
    if r.returncode != 0:
        fail("VOXCPM_IMPORT", "voxcpm was installed but cannot be found: " + (r.stderr or "")[-300:])
    pyv, vv = (r.stdout.split() + ["?", "?"])[:2]
    info.update({"python": pyv, "voxcpm": vv})
    log(f"Installed: voxcpm {vv} on Python {pyv}")
    if pip_cache.exists():
        freed = dir_size(pip_cache) / 1e9
        _rmtree_hard(pip_cache)
        log(f"Removed the temporary download cache (freed {freed:.1f} GB).")

    phase(5, "Downloading the model" if not args.no_weights else "Skipping the model download")
    weights = False
    if not args.no_weights:
        weights = download_weights(py, home)
        if not weights:
            fail("DOWNLOAD_FAILED", "The model download did not finish. Check your Internet connection and click Install again - it resumes where it stopped.")
    info["weights"] = weights

    phase(6, "Testing" if (weights and not args.no_selftest) else "Finishing")
    info["selftest"] = None
    if weights and not args.no_selftest:
        st = selftest_with_fallback(py, home, use_cuda or use_mps, args.cpu)
        info["selftest"] = st
        if st.get("ok"):
            log(f"Self-test OK: {st.get('audio_s')} s of speech in {st.get('elapsed_s')} s on {st.get('device')} "
                f"(speed {st.get('rtf')}x of real time; below 1 = faster than real time).")
            info["device"] = st.get("device")
        else:
            log("##ERROR SELFTEST_FAILED The model was installed, but the test did not work: " + str(st.get("error"))[:600])
            info["error"] = str(st.get("error"))[:600]
            install_json(home).write_text(json.dumps(info, indent=1), encoding="utf-8")
            return 1
    info["ok"] = True
    info["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    install_json(home).write_text(json.dumps(info, indent=1), encoding="utf-8")
    log("##DONE VoxCPM2 is ready.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        log("##ERROR CANCELLED Cancelled.")
        sys.exit(2)
    except Exception as exc:  # pragma: no cover
        import traceback

        log(traceback.format_exc())
        log(f"##ERROR INTERNAL {type(exc).__name__}: {exc}")
        sys.exit(1)
