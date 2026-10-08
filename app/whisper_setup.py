"""Install Whisper (the optional faster-whisper package) from the dashboard.

A video that is uploaded from the computer has no YouTube captions, so Whisper (AI speech recognition) is what normally turns its speech
into subtitles.  This runs ``pip install faster-whisper`` in the background with the SAME Python that runs the dashboard (on Windows that is
the .venv made by start.bat), shows the output, and tells when the package can be used.  The model itself (about 150 MB for "base") is
downloaded the first time it is needed.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from typing import List

from . import asr


def disabled() -> bool:
    """A shared / demo server must not install packages (the same switch as the VoxCPM2 installer)."""
    return os.environ.get("KDS_VOX_DISABLE_INSTALL") == "1" or os.environ.get("KDS_DISABLE_INSTALL") == "1"


def command() -> List[str]:
    raw = os.environ.get("KDS_WHISPER_PIP_CMD")          # tests only: a JSON list that replaces the real pip command
    if raw:
        return [str(x) for x in json.loads(raw)]
    return [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--progress-bar", "off", "faster-whisper"]


class WhisperInstaller:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.state = "idle"                  # idle | installing | done | error
        self.error = ""
        self.started = 0.0
        self.finished = 0.0
        self.log: deque = deque(maxlen=300)

    def start(self) -> bool:
        with self._lock:
            if self.state == "installing":
                return False
            self.state, self.error = "installing", ""
            self.started, self.finished = time.time(), 0.0
            self.log.clear()
        threading.Thread(target=self._run, name="kds-whisper-install", daemon=True).start()
        return True

    def _run(self) -> None:
        code, err = 1, ""
        try:
            cmd = command()
            self.log.append("$ " + " ".join(cmd))
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            assert p.stdout is not None
            for line in p.stdout:
                line = line.rstrip()
                if line:
                    self.log.append(line[:300])
            code = p.wait()
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            self.log.append(err)
        importlib.invalidate_caches()
        with self._lock:
            if code == 0 and asr.whisper_installed():
                self.state = "done"
            else:
                self.state = "error"
                tail = [x for x in list(self.log)[-6:] if x]
                self.error = err or ("pip finished but faster-whisper still cannot be found - close and start the dashboard again."
                                     if code == 0 else "pip failed (exit code %s): %s" % (code, " | ".join(tail)[-400:]))
            self.finished = time.time()
            self.log.append("-- done --" if self.state == "done" else "-- failed --")

    def status(self) -> dict:
        with self._lock:
            end = self.finished or time.time()
            return {
                "installed": asr.whisper_installed(), "state": self.state, "error": self.error, "disabled": disabled(),
                "elapsed": round(end - self.started, 1) if self.started else 0.0, "log": list(self.log)[-40:],
            }


installer = WhisperInstaller()
