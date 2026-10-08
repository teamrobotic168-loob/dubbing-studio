"""Background job store (threads) with JSON persistence – powers progress + History."""
from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .config import CACHE_DIR, JOBS_DIR, TTS_CACHE_DIR

STEPS = {
    "dub": ["transcript", "speakers", "translate", "tts", "mix", "video"],
    "tts": ["translate", "tts", "mix"],
}


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, kind: str, params: dict, title: str = "", job_id: Optional[str] = None):
        self.id = job_id or uuid.uuid4().hex[:10]
        self.kind = kind
        self.created = time.time()
        self.updated = self.created
        self.status = "queued"          # queued | running | done | error | cancelled
        self.title = title
        self.params = params            # sanitized: never contains API keys
        self.steps = [{"key": k, "status": "pending", "progress": 0.0, "detail": ""} for k in STEPS[kind]]
        self.logs: List[str] = []
        self.video: Optional[dict] = None
        self.segments: List[dict] = []
        self.outputs: Dict[str, str] = {}
        self.error: Optional[dict] = None
        self.warnings: List[dict] = []
        self.meta: dict = {}
        self.cancel_flag = threading.Event()
        self.lock = threading.RLock()
        self.dir = JOBS_DIR / self.id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._last_save = 0.0

    # -- mutation helpers (thread-safe) ------------------------------------- #
    def log(self, msg: str) -> None:
        with self.lock:
            stamp = time.strftime("%H:%M:%S")
            self.logs.append(f"[{stamp}] {msg}")
            self.logs = self.logs[-400:]
            self.updated = time.time()

    def step(self, key: str, status: Optional[str] = None, progress: Optional[float] = None, detail: Optional[str] = None) -> None:
        with self.lock:
            for s in self.steps:
                if s["key"] == key:
                    if status is not None:
                        s["status"] = status
                        if status == "done":
                            s["progress"] = 1.0
                    if progress is not None:
                        s["progress"] = float(max(0.0, min(1.0, progress)))
                    if detail is not None:
                        s["detail"] = detail
            self.updated = time.time()

    def warn(self, code: str, message: str) -> None:
        with self.lock:
            self.warnings.append({"code": code, "message": message})
        self.log(f"⚠ {message}")

    def check_cancel(self) -> None:
        if self.cancel_flag.is_set():
            raise Cancelled()

    # -- serialisation ------------------------------------------------------- #
    def to_dict(self, with_segments: bool = True, with_logs: bool = True) -> dict:
        with self.lock:
            d = {
                "id": self.id,
                "kind": self.kind,
                "status": self.status,
                "title": self.title,
                "created": self.created,
                "updated": self.updated,
                "params": self.params,
                "steps": [dict(s) for s in self.steps],
                "video": self.video,
                "outputs": dict(self.outputs),
                "error": self.error,
                "warnings": list(self.warnings),
                "meta": self.meta,
            }
            if with_segments:
                d["segments"] = [dict(s) for s in self.segments]
            else:
                d["segment_count"] = len(self.segments)
            if with_logs:
                d["logs"] = self.logs[-120:]
            return d

    def save(self, force: bool = True) -> None:
        now = time.time()
        if not force and now - self._last_save < 1.0:
            return
        self._last_save = now
        try:
            data = self.to_dict(with_segments=True, with_logs=True)
            data["logs"] = self.logs[-400:]
            tmp = self.dir / "job.json.tmp"
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            for i in range(6):                            # Windows: an antivirus scan may hold the file for a moment
                try:
                    tmp.replace(self.dir / "job.json")
                    break
                except PermissionError:
                    if i == 5:
                        raise
                    time.sleep(0.15)
        except Exception:
            pass

    @classmethod
    def load(cls, path: Path) -> Optional["Job"]:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            j = cls(d["kind"], d.get("params") or {}, d.get("title") or "", job_id=d["id"])
            j.created = d.get("created", j.created)
            j.updated = d.get("updated", j.created)
            j.status = d.get("status", "error")
            j.steps = d.get("steps") or j.steps
            j.video = d.get("video")
            j.segments = d.get("segments") or []
            j.outputs = d.get("outputs") or {}
            j.error = d.get("error")
            j.warnings = d.get("warnings") or []
            j.meta = d.get("meta") or {}
            j.logs = d.get("logs") or []
            if j.status in ("queued", "running"):  # server was restarted mid-job
                j.status = "error"
                j.error = {"code": "INTERRUPTED", "message": "The server was restarted while this job was running."}
            return j
        except Exception:
            return None


class JobManager:
    def __init__(self, workers: int = 2):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="kds-job")
        self._load_existing()
        self.prune_cache()

    def _load_existing(self) -> None:
        for p in JOBS_DIR.glob("*/job.json"):
            j = Job.load(p)
            if j:
                self._jobs[j.id] = j

    def create(self, kind: str, params: dict, title: str = "") -> Job:
        job = Job(kind, params, title)
        with self._lock:
            self._jobs[job.id] = job
        job.save()
        return job

    def submit(self, job: Job, fn: Callable[[Job], None]) -> None:
        def runner():
            job.status = "running"
            job.save()
            try:
                fn(job)
            finally:
                job.save()

        self._pool.submit(runner)

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self) -> List[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if not job:
            return False
        job.cancel_flag.set()
        for _ in range(6):                                # Windows: a file that is still open for a moment cannot be deleted - try again
            shutil.rmtree(job.dir, ignore_errors=True)
            if not job.dir.exists():
                break
            time.sleep(0.3)
        return True

    # -- housekeeping ------------------------------------------------------- #
    @staticmethod
    def prune_cache(max_age_days: int = 21, max_total_mb: int = 1500) -> None:
        try:
            files = [p for p in TTS_CACHE_DIR.glob("*") if p.is_file()]
            now = time.time()
            for p in files:
                if now - p.stat().st_mtime > max_age_days * 86400:
                    p.unlink(missing_ok=True)
            for p in (CACHE_DIR / "translate").glob("*"):
                if p.is_file() and now - p.stat().st_mtime > 90 * 86400:
                    p.unlink(missing_ok=True)
            files = sorted((p for p in TTS_CACHE_DIR.glob("*") if p.is_file()), key=lambda p: p.stat().st_mtime)
            total = sum(p.stat().st_size for p in files)
            while files and total > max_total_mb * 1024 * 1024:
                p = files.pop(0)
                total -= p.stat().st_size
                p.unlink(missing_ok=True)
        except Exception:
            pass
