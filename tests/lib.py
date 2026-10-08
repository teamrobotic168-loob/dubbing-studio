"""Shared helpers for the V_Heang Studio test-suites (not part of the product).

Everything is relative to this file, so a suite runs from any folder:   python3 tests/test_units.py

  PROJECT   the project folder (the parent of tests/)                  override: KDS_PROJECT
  WORK      scratch space: fixture videos, data folders, logs, shots   override: KDS_TEST_WORK   (default <temp dir>/kds-tests)
  VERSION   read from app/__init__.py, so a version bump never needs an edit in the tests
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

TESTS = Path(__file__).resolve().parent
PROJECT = Path(os.environ.get("KDS_PROJECT") or TESTS.parent).resolve()
WORK = Path(os.environ.get("KDS_TEST_WORK") or (Path(tempfile.gettempdir()) / "kds-tests")).resolve()
WORK.mkdir(parents=True, exist_ok=True)
STUB = TESTS / "stubvox"                   # a fake `voxcpm` package: the VoxCPM2 engine without PyTorch
NOWHISPER = TESTS / "stubnowhisper"        # sitecustomize.py that makes faster-whisper look 'not installed' (+ a fake one that "pip" can switch on)
FIXTURE_JOBS = TESTS / "fixtures" / "jobs"  # three finished demo jobs (English / Chinese / Korean sample)
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))        # `from app import ...` works in every suite (import lib first, set KDS_DATA_DIR, then import app)
VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', (PROJECT / "app" / "__init__.py").read_text(encoding="utf-8")).group(1)


def make_stub_home(home: Path) -> Path:
    """A fake 'VoxCPM2 installed' folder: install.json + a venv/bin/python that is just python3."""
    shutil.rmtree(home, ignore_errors=True)
    (home / "venv" / "bin").mkdir(parents=True)
    py = home / "venv" / "bin" / "python"
    py.write_text("#!/bin/sh\nexec python3 \"$@\"\n")
    py.chmod(0o755)
    (home / "install.json").write_text(json.dumps({"ok": True, "weights": True, "device": "cpu", "cuda": False,
                                                   "selftest": {"rtf": 0.8, "device": "cpu"}}))
    return home


class Server:
    def __init__(self, port: int, data: Path, vox_home: Path, extra_env: dict | None = None, name: str = "srv"):
        self.port, self.data, self.vox_home, self.name = port, data, vox_home, name
        self.extra_env = extra_env or {}
        self.proc = None
        self.url = f"http://127.0.0.1:{port}"
        self.log = WORK / f"{name}.log"

    def start(self):
        env = dict(os.environ, KDS_DATA_DIR=str(self.data), KDS_VOX_HOME=str(self.vox_home), KDS_VOX_STUB="1",
                   KDS_VOX_DISABLE_INSTALL="1", PYTHONPATH=str(STUB), HOST="127.0.0.1", PORT=str(self.port),
                   NO_BROWSER="1", PYTHONUNBUFFERED="1")
        env.update(self.extra_env)                       # a test may override anything above (e.g. PYTHONPATH, KDS_VOX_DISABLE_INSTALL)
        fh = open(self.log, "wb")
        self.proc = subprocess.Popen([sys.executable, "server.py"], cwd=str(PROJECT), env=env, stdout=fh, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        for _ in range(100):
            try:
                if httpx.get(self.url + "/api/health", timeout=2).status_code == 200:
                    return self
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("server did not start: " + self.log.read_text()[-1500:])

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except Exception:
                self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        # the VoxCPM2 worker runs in its own session; find it by its --tmp-dir argument
        subprocess.run(["sh", "-c", f"pkill -f 'vox_worker.py.*{self.vox_home.name}' || true"], capture_output=True)

    # tiny API client
    def api(self, method, path, **kw):
        return httpx.request(method, self.url + path, timeout=kw.pop("timeout", 60), **kw)

    def wait_job(self, job_id, timeout=300):
        t0 = time.time()
        while time.time() - t0 < timeout:
            j = self.api("GET", f"/api/jobs/{job_id}").json()
            if j["status"] in ("done", "error", "cancelled"):
                return j
            time.sleep(0.7)
        raise TimeoutError(f"job {job_id} still running after {timeout}s")


class Checker:
    def __init__(self, title):
        self.title, self.ok, self.bad = title, 0, []

    def check(self, cond, label, detail=""):
        if cond:
            self.ok += 1
        else:
            self.bad.append(f"{label} {detail}".strip())
            print(f"  ✘ {label} {detail}", flush=True)

    def done(self):
        print(f"\n== {self.title}: {self.ok} passed, {len(self.bad)} failed ==")
        for b in self.bad:
            print("   FAIL:", b)
        return 0 if not self.bad else 1
