"""Controls the optional VoxCPM2 engine: install, start/stop the worker process, synthesize.

The model lives in its own virtual environment (see vox_setup.py) and runs in a small worker
process (vox_worker.py) that this module starts on demand and talks to over 127.0.0.1.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

import httpx

from . import vox_setup
from .config import BASE_DIR
from .tts import TTSError

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_PROGRESS_BAR = re.compile(r"\d+%\||it/s\]|s/it\]")   # tqdm bars in the engine log are noise
_NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


class VoxError(TTSError):
    """TTS error with a machine-readable code (shown translated in the UI)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if proc.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, creationflags=_NO_WINDOW, timeout=15)
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    proc.kill()
    except Exception:
        pass


def _kill_pid_tree(pid: int) -> None:
    """Stop an installer that was started by an earlier dashboard process (we only know its PID)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=_NO_WINDOW, timeout=15)
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception:
                os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _tail(path: Path, n: int = 60, max_bytes: int = 120_000) -> List[str]:
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
            data = fh.read().decode("utf-8", "replace")
        lines = [l.rstrip() for l in data.replace("\r", "\n").split("\n") if l.strip() and not _PROGRESS_BAR.search(l)]
        return lines[-n:]
    except OSError:
        return []


def _markers(path: Path, max_bytes: int = 2_000_000) -> List[str]:
    """Installer markers (##PHASE / ##PROGRESS / ##ERROR / ##DONE) from a far larger window than the display tail:
    pip prints hundreds of lines per step and would otherwise push the current ##PHASE line out of sight."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
            data = fh.read().decode("utf-8", "replace")
        return [l.rstrip() for l in data.replace("\r", "\n").split("\n") if l.startswith("##")]
    except OSError:
        return []


class VoxManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._worker: Optional[subprocess.Popen] = None
        self._port = 0
        self._token = ""
        self._started_at = 0.0
        self._setup: Optional[subprocess.Popen] = None
        self._synth_lock = threading.Lock()
        self._hw: tuple = (0.0, None)
        self._last_exit: Optional[dict] = None

    # ------------------------------------------------------------- locations
    @property
    def home(self) -> Path:
        h = vox_setup.vox_home()
        h.mkdir(parents=True, exist_ok=True)
        return h

    @property
    def tmp(self) -> Path:
        t = self.home / "tmp"
        t.mkdir(parents=True, exist_ok=True)
        return t

    def _cfg_path(self) -> Path:
        return self.home / "config.json"

    def config(self) -> dict:
        cfg = {"device": "auto", "turbo": False}
        try:
            cfg.update(json.loads(self._cfg_path().read_text(encoding="utf-8")))
        except Exception:
            pass
        if cfg.get("device") not in ("auto", "cpu"):
            cfg["device"] = "auto"
        cfg["turbo"] = bool(cfg.get("turbo"))
        return cfg

    def set_config(self, data: dict) -> dict:
        cfg = self.config()
        if data.get("device") in ("auto", "cpu"):
            cfg["device"] = data["device"]
        if "turbo" in data:
            cfg["turbo"] = bool(data["turbo"])
            # switching Turbo on/off gives it a fresh start: forget that it crashed the engine once
            try:
                (self.home / "turbo.attempt").unlink(missing_ok=True)
            except OSError:
                pass
        self._cfg_path().write_text(json.dumps(cfg), encoding="utf-8")
        return cfg

    # --------------------------------------------------------------- install
    def install_info(self) -> dict:
        try:
            return json.loads(vox_setup.install_json(self.home).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def installed(self) -> bool:
        info = self.install_info()
        return bool(info.get("ok")) and bool(info.get("weights")) and vox_setup.venv_python(self.home).exists()

    def hardware(self) -> dict:
        now = time.time()
        if self._hw[1] is None or now - self._hw[0] > 20:
            self._hw = (now, {
                "nvidia": vox_setup.detect_gpu(),
                "cpu_cores": os.cpu_count(),
                "ram_gb": vox_setup.ram_gb(),
                "platform": sys.platform,
                "mac": vox_setup.mac_arch(),               # None | 'arm64' (Apple Silicon) | 'intel' | 'rosetta'
            })
        return self._hw[1]

    def speed_note(self) -> dict:
        """Plain-language expectation for this computer (measured by the install self-test when available)."""
        info = self.install_info()
        st = info.get("selftest") or {}
        dev = st.get("device") or info.get("device") or ""
        hw = self.hardware()
        rtf = st.get("rtf")
        if rtf is not None:
            kind = "fast" if rtf < 1.0 else ("ok" if rtf < 3 else "slow")
            return {"kind": kind, "rtf": rtf, "device": dev, "measured": True}
        if info.get("cuda") or (hw.get("nvidia") and not self.config()["device"] == "cpu"):
            return {"kind": "gpu", "rtf": None, "device": dev or "cuda", "measured": False}
        if dev == "mps" or info.get("mps") or (hw.get("mac") == "arm64" and not self.config()["device"] == "cpu"):
            return {"kind": "gpu", "rtf": None, "device": dev or "mps", "measured": False}
        return {"kind": "cpu", "rtf": None, "device": dev or "cpu", "measured": False}

    def setup_log_path(self) -> Path:
        return self.home / "setup.log"

    def setup_running(self) -> bool:
        if self._setup is not None:
            return self._setup.poll() is None          # our own installer (a leftover heartbeat file is then stale)
        # No handle: the dashboard was restarted while an installer kept running in the background -> its heartbeat is fresh.
        age = vox_setup.heartbeat_age(self.home)
        return age is not None and age < vox_setup.HEARTBEAT_STALE_S

    def setup_start(self, cpu: bool = False, no_weights: bool = False) -> dict:
        with self._lock:
            if self.setup_running():
                return {"started": False, "reason": "already_running"}
            self.stop()
            log = self.setup_log_path()
            fh = open(log, "wb")
            cmd = [sys.executable, "-u", "-m", "app.vox_setup"]
            if cpu:
                cmd.append("--cpu")
            if no_weights:
                cmd.append("--no-weights")
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
            kw: dict = {}
            if os.name == "nt":
                kw["creationflags"] = _NO_WINDOW | _NEW_GROUP
            else:
                kw["start_new_session"] = True
            self._setup = subprocess.Popen(cmd, cwd=str(BASE_DIR), stdout=fh, stderr=subprocess.STDOUT, env=env, **kw)
            fh.close()
            return {"started": True}

    def setup_cancel(self) -> bool:
        with self._lock:
            if not self.setup_running():
                return False
            if self._setup is not None:
                _kill_tree(self._setup)
            else:
                pid = vox_setup.installer_pid(self.home)
                if pid:
                    _kill_pid_tree(pid)
            try:
                with open(self.setup_log_path(), "ab") as fh:
                    fh.write(b"\n##ERROR CANCELLED Cancelled by the user.\n")
            except OSError:
                pass
            try:
                vox_setup.heartbeat_path(self.home).unlink()
            except OSError:
                pass
            return True

    def setup_status(self) -> dict:
        lines = _tail(self.setup_log_path(), 400)
        marks = _markers(self.setup_log_path())
        st = {"running": self.setup_running(), "phase_idx": 0, "phase_total": vox_setup.PHASES, "phase": "", "pct": None,
              "pct_text": "", "ok": None, "error": None, "lines": [l[:200] for l in lines if not l.startswith("##")][-14:]}
        for l in marks:
            m = re.match(r"##PHASE (\d+)/(\d+) (.*)", l)
            if m:
                st.update(phase_idx=int(m.group(1)), phase_total=int(m.group(2)), phase=m.group(3), pct=None, pct_text="")
                continue
            m = re.match(r"##PROGRESS (\d+) ?(.*)", l)
            if m:
                st.update(pct=int(m.group(1)), pct_text=m.group(2))
                continue
            m = re.match(r"##ERROR (\S+) ?(.*)", l)
            if m:
                st.update(error={"code": m.group(1), "message": m.group(2)}, ok=False)
                continue
            if l.startswith("##DONE"):
                st.update(ok=True, error=None)
        if st["running"]:
            st["ok"] = None
            st["error"] = None
        elif (lines or marks) and st["ok"] is None and st["error"] is None:
            st["error"] = {"code": "INTERRUPTED", "message": "The installation stopped before it finished."}
            st["ok"] = False
        return st

    # ---------------------------------------------------------------- worker
    def _worker_alive(self) -> bool:
        return self._worker is not None and self._worker.poll() is None

    def start(self) -> None:
        with self._lock:
            if self._worker_alive():
                return
            if not self.installed():
                raise VoxError("VOX_NOT_INSTALLED", "VoxCPM2 is not installed yet. Open Settings -> VoxCPM2 and click Install.")
            py = vox_setup.venv_python(self.home)
            self._port = _free_port()
            self._token = secrets.token_hex(16)
            info = self.install_info()
            env = dict(
                os.environ, HF_HOME=str(vox_setup.hf_home(self.home)), HF_HUB_DISABLE_TELEMETRY="1",
                PYTHONIOENCODING="utf-8", PYTHONUTF8="1", TOKENIZERS_PARALLELISM="false", PYTHONUNBUFFERED="1",
            )
            if sys.platform == "darwin":
                env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"      # an operation the Mac GPU lacks runs on the CPU instead of stopping
            if info.get("weights"):
                env["HF_HUB_OFFLINE"] = "1"      # the model is on disk: never wait for the network
            cmd = [str(py), "-u", str(Path(__file__).with_name("vox_worker.py")), "--port", str(self._port), "--token", self._token,
                   "--parent-pid", str(os.getpid()), "--tmp-dir", str(self.tmp), "--device", self.config()["device"],
                   "--idle-min", os.environ.get("KDS_VOX_IDLE_MIN", "30")]
            if self.config().get("turbo"):
                cmd.append("--turbo")
            fh = open(self.home / "worker.log", "wb")
            kw: dict = {}
            if os.name == "nt":
                kw["creationflags"] = _NO_WINDOW | _NEW_GROUP
            else:
                kw["start_new_session"] = True
            self._worker = subprocess.Popen(cmd, cwd=str(self.home), stdout=fh, stderr=subprocess.STDOUT, env=env, **kw)
            fh.close()
            self._started_at = time.time()
            self._last_exit = None

    def stop(self) -> None:
        with self._lock:
            w = self._worker
            if w is None:
                return
            if w.poll() is None:
                try:
                    httpx.post(f"http://127.0.0.1:{self._port}/shutdown", headers={"X-KDS-Token": self._token}, json={}, timeout=2.0, trust_env=False)
                except Exception:
                    pass
                try:
                    w.wait(timeout=3)
                except Exception:
                    _kill_tree(w)
            self._worker = None

    def log_tail(self, which: str = "worker", n: int = 80) -> List[str]:
        return _tail(self.setup_log_path() if which == "setup" else self.home / "worker.log", n)

    def _http(self, method: str, path: str, **kw):
        # trust_env=False: never send loopback traffic through a system / corporate proxy
        return httpx.request(method, f"http://127.0.0.1:{self._port}{path}", headers={"X-KDS-Token": self._token}, trust_env=False, **kw)

    def worker_state(self) -> dict:
        """{'state': stopped|starting|idle|loading|ready|error, ...}"""
        w = self._worker
        if w is None:
            return {"state": "stopped", **({"last_exit": self._last_exit} if self._last_exit else {})}
        rc = w.poll()
        if rc is not None:
            self._worker = None
            self._last_exit = {"code": rc, "tail": self.log_tail("worker", 12)}
            return {"state": "stopped", "last_exit": self._last_exit}
        try:
            r = self._http("GET", "/health", timeout=2.5)
            if r.status_code != 200:
                return {"state": "error", "error": {"kind": "start", "message": f"The engine's health check failed (HTTP {r.status_code}). See the engine log."}}
            return r.json()
        except Exception:
            if self._synth_lock.locked():       # busy speaking (slow CPU): a late health answer is normal
                return {"state": "ready", "busy": True, "phase": ""}
            if time.time() - self._started_at < 120:
                return {"state": "starting", "phase": "starting the engine"}
            return {"state": "error", "error": {"kind": "start", "message": "The engine is not answering."}}

    def status(self) -> dict:
        info = self.install_info()
        ws = self.worker_state()
        return {
            "installed": self.installed(),
            "home": str(self.home),
            "install": info,
            "hardware": self.hardware(),
            "worker": ws,
            "setup": self.setup_status(),
            "config": self.config(),
            "speed": self.speed_note(),
        }

    @staticmethod
    def _code_for(err: Optional[dict]) -> str:
        kind = (err or {}).get("kind")
        return "VOX_OOM" if kind == "oom" else "VOX_LOAD_FAILED"

    def ensure_ready(self, on_status: Optional[Callable[[str], None]] = None, cancelled: Optional[Callable[[], bool]] = None,
                     timeout: float = 1800.0) -> bool:
        """Start the worker if needed and wait until the model is loaded. Returns False when cancelled."""
        if not self.installed():
            raise VoxError("VOX_NOT_INSTALLED", "VoxCPM2 is not installed yet. Open Settings -> VoxCPM2 and click Install.")
        with self._lock:
            st = self.worker_state()
            if st.get("state") in ("stopped", "error"):
                if st.get("state") == "error":
                    self.stop()
                self.start()
        t0 = time.time()
        posted = False
        last = ""
        while True:
            if cancelled and cancelled():
                return False
            st = self.worker_state()
            s = st.get("state")
            if s == "ready":
                return True
            if s == "stopped":
                tail = " | ".join((st.get("last_exit") or {}).get("tail", [])[-4:])
                raise VoxError("VOX_START_FAILED", "The VoxCPM2 engine stopped unexpectedly (often: not enough memory). " + tail[:500])
            if s == "error":
                err = st.get("error") or {}
                raise VoxError(self._code_for(err), (err.get("message") or "The engine could not load the model.")[:700])
            if s == "idle" and not posted:
                try:
                    self._http("POST", "/load", json={}, timeout=5.0)
                    posted = True
                except Exception:
                    pass
            note = st.get("phase") or "starting the engine"
            if on_status and note != last:
                last = note
                on_status(note)
            if time.time() - t0 > timeout:
                raise VoxError("VOX_LOAD_TIMEOUT", f"The engine did not finish loading within {int(timeout // 60)} minutes.")
            time.sleep(0.8)

    def synth(self, text: str, out: Path, ref: Optional[Path] = None, style: Optional[str] = None, steps: int = 10,
              cfg: float = 2.0, seed: int = 1234, timeout: float = 3600.0,
              cancelled: Optional[Callable[[], bool]] = None, cancel_grace: float = 20.0) -> dict:
        """Speak one piece of text. When `cancelled()` turns true the current line may finish; if it takes longer
        than `cancel_grace` seconds the engine is stopped (a slow CPU can need minutes per line)."""
        from .jobs import Cancelled  # local import (jobs does not import this module)

        body = {"text": text, "out": str(out), "ref": str(ref) if ref else None, "style": style, "steps": steps, "cfg": cfg, "seed": seed}
        with self._synth_lock:
            box: dict = {}

            def call() -> None:
                try:
                    r = self._http("POST", "/synth", json=body, timeout=httpx.Timeout(timeout, connect=10.0))
                    box["d"] = r.json()
                except Exception as exc:  # noqa: BLE001
                    box["exc"] = exc

            th = threading.Thread(target=call, name="vox-synth-call", daemon=True)
            th.start()
            cancel_at: Optional[float] = None
            while th.is_alive():
                th.join(0.25)
                if cancelled and cancelled():
                    cancel_at = cancel_at or time.time()
                    if time.time() - cancel_at > cancel_grace:
                        self.stop()          # frees the memory; the model is reloaded the next time
                        th.join(2.0)
                        raise Cancelled()
            exc = box.get("exc")
            if exc is not None or "d" not in box:
                alive = self._worker_alive()
                tail = " | ".join(self.log_tail("worker", 6))[-400:]
                if not alive:
                    raise VoxError("VOX_START_FAILED", "The VoxCPM2 engine crashed while speaking (often: not enough memory). " + tail) from exc
                raise VoxError("VOX_FAILED", f"Could not talk to the VoxCPM2 engine: {type(exc).__name__}: {exc}") from exc
            d = box["d"]
            if cancel_at is not None:
                raise Cancelled()
        if not d.get("ok"):
            kind = d.get("kind")
            msg = str(d.get("error") or "unknown error")[:600]
            if kind == "oom":
                raise VoxError("VOX_OOM", "The GPU ran out of memory. " + msg)
            if kind == "not_ready":
                raise VoxError("VOX_NOT_READY", msg)
            raise VoxError("VOX_FAILED", msg)
        return d


_MANAGER: Optional[VoxManager] = None


def manager() -> VoxManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = VoxManager()
        atexit.register(_MANAGER.stop)
    return _MANAGER
