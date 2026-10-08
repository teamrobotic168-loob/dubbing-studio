#!/usr/bin/env python3
"""VoxCPM2 worker.

Runs INSIDE the isolated VoxCPM environment (see vox_setup.py) and is started / stopped by the
dashboard.  It is never imported by the dashboard itself.  It keeps the model loaded and answers
small JSON requests on 127.0.0.1 (protected by a random token), so the 5 GB model is loaded only once.

    GET  /health                -> state, device, GPU, versions
    POST /load                  -> start loading the model (returns immediately; poll /health)
    POST /synth {text, out, ref, style, steps, cfg, seed}   -> writes a mono 16-bit WAV to `out`
    POST /shutdown

    python vox_worker.py --selftest --out test.wav   # load + speak one sentence, print "SELFTEST {json}"
"""
from __future__ import annotations

import argparse
import gc
import inspect
import json
import os
import random
import sys
import threading
import time
import traceback
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

START = time.time()
# Fewer out-of-memory errors on 8 GB cards (memory fragmentation). Must be set before PyTorch is imported;
# both options work on Windows too.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "garbage_collection_threshold:0.8,max_split_size_mb:512")
MODEL_ID = os.environ.get("KDS_VOX_MODEL", "openbmb/VoxCPM2")
SELFTEST_TEXT = "សួស្តី! នេះគឺជាការសាកល្បងសំឡេង។ យើងអាចប្រើ API ដើម្បីបកប្រែវីដេអូបាន។"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    if os.name == "nt":
        try:
            import ctypes

            k = ctypes.windll.kernel32  # type: ignore[attr-defined]
            h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_wav(path, wav, sr: int) -> None:
    import numpy as np

    x = np.clip(np.asarray(wav, dtype=np.float32).reshape(-1), -1.0, 1.0)
    pcm = (x * 32767.0).astype("<i2").tobytes()
    tmp = str(path) + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm)
    os.replace(tmp, str(path))


class TurboSampler:
    """EXPERIMENTAL (opt-in): record the whole diffusion sampler of one speech step as a CUDA graph.

    Why: on a fast CPU + mid-range GPU the model is limited by the CPU, which launches ~3000 tiny GPU kernels for every 0.16 s of
    speech (the GPU is only ~50 % busy). A CUDA graph replays all of them with a single launch. Output stays the same; only the
    time per line drops (about 2x faster is expected).

    Safety: the first recording is compared with the normal result (with the random noise switched off); if it differs, or
    anything at all goes wrong, the normal code is put back and generation simply continues the old way. A marker file
    protects against a hard crash while recording (Turbo is then skipped until the user switches it off and on again).
    """

    def __init__(self, torch_mod, cfm, marker: Path, on_change):
        self.t = torch_mod
        self.cfm = cfm
        self.orig = cfm.forward              # bound method of the real sampler
        self.marker = marker
        self.on_change = on_change           # on_change(state, graphs, reason)
        self.graphs: dict = {}
        self.verified = False
        self.failed = None

    def install(self) -> None:
        self.cfm.forward = self              # an instance attribute shadows the method; nn.Module.__call__ finds it

    def uninstall(self) -> None:
        self.cfm.__dict__.pop("forward", None)

    # ---- the replacement for UnifiedCFM.forward
    def __call__(self, mu, n_timesteps, patch_size, cond, temperature=1.0, cfg_value=1.0, sway_sampling_coef=1.0, use_cfg_zero_star=True):
        kw = dict(n_timesteps=int(n_timesteps), patch_size=int(patch_size), temperature=float(temperature), cfg_value=float(cfg_value),
                  sway_sampling_coef=float(sway_sampling_coef), use_cfg_zero_star=bool(use_cfg_zero_star))
        if self.failed or not self._eligible(mu):
            return self.orig(mu=mu, cond=cond, **kw)
        key = (tuple(sorted(kw.items())), tuple(mu.shape), tuple(cond.shape), str(mu.dtype))
        with self.t.inference_mode():
            g = self.graphs.get(key)
            if g is None:
                try:
                    g = self._capture(mu, cond, kw)
                except BaseException as exc:  # noqa: BLE001 - whatever happens, fall back to the normal sampler
                    self.fail(f"{type(exc).__name__}: {exc}"[:300])
                    return self.orig(mu=mu, cond=cond, **kw)
                self.graphs[key] = g
                self.on_change("on", len(self.graphs), "")
            g["mu"].copy_(mu)
            g["cond"].copy_(cond)
            g["graph"].replay()
            return g["out"].clone()

    @staticmethod
    def _eligible(mu) -> bool:
        return bool(getattr(mu, "is_cuda", False))

    def fail(self, reason: str) -> None:
        log("Turbo switched off: " + reason)
        self.failed = reason
        self.uninstall()
        self.graphs.clear()
        self._clear_marker()
        try:
            self.t.cuda.synchronize()
            self.t.cuda.empty_cache()
        except Exception:
            pass
        self.on_change("failed", 0, reason)

    def _mark(self) -> None:
        try:
            self.marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S") + " recording the CUDA graph\n", encoding="utf-8")
        except OSError:
            pass

    def _clear_marker(self) -> None:
        try:
            self.marker.unlink()
        except OSError:
            pass

    def _record(self, mu_s, cond_s, kw):
        t = self.t
        side = t.cuda.Stream()
        side.wait_stream(t.cuda.current_stream())
        with t.cuda.stream(side):                 # warm-up (cuBLAS handles, lazy CUDA modules) must happen before recording
            for _ in range(3):
                self.orig(mu=mu_s, cond=cond_s, **kw)
        t.cuda.current_stream().wait_stream(side)
        t.cuda.synchronize()
        graph = t.cuda.CUDAGraph()
        with t.cuda.graph(graph):
            out = self.orig(mu=mu_s, cond=cond_s, **kw)
        return graph, out

    def _capture(self, mu, cond, kw) -> dict:
        t = self.t
        self._mark()
        t0 = time.time()
        mu_s, cond_s = mu.clone(), cond.clone()
        if not self.verified:
            kw0 = dict(kw, temperature=0.0)       # no random noise -> both ways must give the same numbers
            ref = self.orig(mu=mu_s, cond=cond_s, **kw0).clone()
            g0, out0 = self._record(mu_s, cond_s, kw0)
            g0.replay()
            t.cuda.synchronize()
            err = float((out0.float() - ref.float()).abs().max())
            scale = float(ref.float().abs().max()) + 1e-6
            del g0, out0
            if not (err <= 0.03 * scale + 1e-3):
                raise RuntimeError(f"the recorded sampler gives a different result (error {err:.4f}, scale {scale:.3f})")
            self.verified = True
        graph, out = self._record(mu_s, cond_s, kw)
        self._clear_marker()
        log(f"Turbo: recorded the sampler for {kw['n_timesteps']} steps in {time.time() - t0:.1f}s")
        return {"graph": graph, "mu": mu_s, "cond": cond_s, "out": out}


class Engine:
    def __init__(self, device_pref: str = "auto"):
        self.device_pref = device_pref
        self.state = "idle"          # idle | loading | ready | error
        self.phase = ""
        self.error = None            # {"kind": ..., "message": ...}
        self.model = None
        self.sr = 48000
        self.device = "?"
        self.gpu_name = None
        self.vram_gb = None
        self.versions: dict = {}
        self.supports_seed = False
        self.small_vram = False      # <= ~10 GB card: free the cache after every line
        self.loaded_at = None
        self.load_seconds = None
        self.last_activity = time.time()
        self.count = 0
        self._load_lock = threading.Lock()
        self.gen_lock = threading.Lock()
        self.turbo_req = False               # the user switched Turbo on (Settings)
        self.turbo: dict = {"state": "off", "graphs": 0, "reason": ""}
        self.sampler = None
        self.optimized = False
        self.selftest_mode = False

    # ------------------------------------------------------------------ info
    def info(self) -> dict:
        d = {
            "ok": True, "state": self.state, "phase": self.phase, "error": self.error, "device": self.device,
            "gpu": self.gpu_name, "vram_gb": self.vram_gb, "sr": self.sr, "versions": self.versions,
            "model": MODEL_ID, "loaded_at": self.loaded_at, "load_seconds": self.load_seconds,
            "requests": self.count, "uptime": round(time.time() - START, 1),
            "idle_s": round(time.time() - self.last_activity, 1),
            "turbo": dict(self.turbo),
        }
        return d

    # ------------------------------------------------------------------ load
    def start_load(self) -> None:
        with self._load_lock:
            if self.state in ("loading", "ready"):
                return
            self.state = "loading"
            self.error = None
            self.phase = "starting"
        threading.Thread(target=self._load, name="vox-load", daemon=True).start()

    def _fail(self, kind: str, exc: BaseException) -> None:
        msg = f"{type(exc).__name__}: {exc}"
        log("LOAD FAILED: " + traceback.format_exc())
        self.error = {"kind": kind, "message": msg[:800]}
        self.state = "error"
        self.phase = ""

    def _load(self) -> None:
        t0 = time.time()
        torch = None
        try:
            self.phase = "importing PyTorch"
            try:
                import torch as _torch  # noqa: WPS433

                torch = _torch
                self.versions["torch"] = torch.__version__
            except Exception as exc:
                if os.environ.get("KDS_VOX_STUB") != "1":
                    raise RuntimeError(f"PyTorch could not be imported: {exc}") from exc
            self.phase = "importing voxcpm"
            from voxcpm import VoxCPM  # noqa: WPS433

            try:
                from importlib import metadata

                self.versions["voxcpm"] = metadata.version("voxcpm")
            except Exception:
                pass

            want_cpu = self.device_pref == "cpu"
            cuda_ok = bool(torch is not None and torch.cuda.is_available())
            device_arg = "cpu" if want_cpu else None            # None -> VoxCPM picks cuda -> mps -> cpu
            optimize = bool(sys.platform.startswith("linux") and cuda_ok and not want_cpu)
            local_only = os.environ.get("HF_HUB_OFFLINE") == "1"
            self.phase = "loading the model (first start: 1-3 minutes)"
            log(f"Loading {MODEL_ID}: device={device_arg or 'auto'} optimize={optimize} local_only={local_only}")
            model = None
            for opt in ([True, False] if optimize else [False]):
                try:
                    model = VoxCPM.from_pretrained(MODEL_ID, load_denoiser=False, optimize=opt, device=device_arg, local_files_only=local_only)
                    break
                except Exception as exc:
                    if opt:
                        log(f"optimize=True failed ({type(exc).__name__}: {exc}); retrying without torch.compile")
                        model = None
                        gc.collect()
                        if cuda_ok:
                            torch.cuda.empty_cache()
                        continue
                    raise
            self.model = model
            self.optimized = bool(optimize and opt)
            tts = getattr(model, "tts_model", None)
            self.sr = int(getattr(tts, "sample_rate", 48000) or 48000)
            self.device = str(getattr(tts, "device", None) or ("cuda" if cuda_ok else "cpu"))
            try:
                self.supports_seed = "seed" in inspect.signature(model._generate).parameters  # type: ignore[attr-defined]
            except Exception:
                self.supports_seed = False
            if torch is not None and self.device.startswith("cuda"):
                try:
                    idx = int(self.device.split(":")[1]) if ":" in self.device else 0
                    props = torch.cuda.get_device_properties(idx)
                    self.gpu_name = props.name
                    self.vram_gb = round(props.total_memory / 1024 ** 3, 1)
                    self.small_vram = self.vram_gb <= 10.5
                except Exception:
                    pass
            self.loaded_at = time.time()
            self.load_seconds = round(time.time() - t0, 1)
            self.phase = ""
            self.state = "ready"
            log(f"Model ready on {self.device} in {self.load_seconds}s (sr={self.sr}, seed_arg={self.supports_seed})")
        except BaseException as exc:  # noqa: BLE001
            self._fail("oom" if _is_oom(exc) else "load", exc)
            return
        if not self.selftest_mode:
            self._warmup()

    # ------------------------------------------------------------ warm-up / turbo
    def _enable_turbo(self) -> None:
        if not self.turbo_req:
            return

        def no(reason: str) -> None:
            self.turbo.update(state="failed", graphs=0, reason=reason)
            log("Turbo is off: " + reason)

        if not str(self.device).startswith("cuda"):
            return no("it needs an NVIDIA GPU")
        try:
            import torch

            if self.optimized:
                return no("torch.compile is already used")
            cfm = getattr(getattr(self.model, "tts_model", None), "feat_decoder", None)
            if cfm is None or not hasattr(cfm, "estimator") or not hasattr(torch.cuda, "CUDAGraph"):
                return no("this VoxCPM version has a different structure")
            marker = TMP_DIR.parent / "turbo.attempt"
            if marker.exists():
                return no("it crashed the engine last time (switch Turbo off and on again to retry)")

            def changed(state: str, graphs: int, reason: str) -> None:
                self.turbo.update(state=state, graphs=graphs, reason=reason)

            self.sampler = TurboSampler(torch, cfm, marker, changed)
            self.sampler.install()
            self.turbo.update(state="pending", graphs=0, reason="")
        except BaseException as exc:  # noqa: BLE001
            no(f"{type(exc).__name__}: {exc}"[:300])

    def _warmup(self) -> None:
        """The first line after loading is slow (CUDA kernels start up lazily): do that now, before the first real line.
        With Turbo this also records the sampler for the usual quality (10 steps)."""
        t0 = time.time()
        try:
            with self.gen_lock:
                self._enable_turbo()                  # decides and reports (also "needs a GPU" on the CPU)
                if not str(self.device).startswith("cuda"):
                    return
                self.generate("សួស្តី", None, None, 10, 2.0, 1)
            log(f"Warm-up finished in {time.time() - t0:.1f}s (turbo: {self.turbo['state']})")
        except BaseException as exc:  # noqa: BLE001
            log(f"Warm-up failed (ignored): {type(exc).__name__}: {exc}")

    # -------------------------------------------------------------- generate
    def free_memory(self) -> None:
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():     # Mac: the memory is shared with everything else
                torch.mps.empty_cache()
        except Exception:
            pass

    def _seed_all(self, seed: int) -> None:
        random.seed(seed)
        try:
            import numpy as np

            np.random.seed(seed % (2 ** 32))
        except Exception:
            pass
        try:
            import torch

            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except Exception:
            pass

    def generate(self, text: str, ref: str | None, style: str | None, steps: int, cfg: float, seed: int):
        import numpy as np

        if self.model is None or self.state != "ready":
            raise RuntimeError("model is not loaded")
        txt = (text or "").strip()
        if style:
            txt = f"({style.strip()}){txt}"
        kwargs = {"text": txt, "cfg_value": float(cfg), "inference_timesteps": int(steps)}
        if ref:
            kwargs["reference_wav_path"] = ref
        if self.supports_seed:
            kwargs["seed"] = int(seed)
        self._seed_all(int(seed))
        try:
            try:
                wav = self.model.generate(**kwargs)
            except BaseException as exc:  # noqa: BLE001
                if self.sampler is None or self.sampler.failed or _is_oom(exc):
                    raise
                # Turbo misbehaved: put the normal sampler back and speak this line again the normal way
                self.sampler.fail(f"{type(exc).__name__}: {exc}"[:300])
                wav = self.model.generate(**kwargs)
            wav = np.asarray(wav, dtype=np.float32).reshape(-1)
        finally:
            if self.small_vram:
                self.free_memory()
        if wav.size == 0:
            raise RuntimeError("the model returned no audio")
        return wav


def _is_oom(exc: BaseException) -> bool:
    name = type(exc).__name__
    return "OutOfMemory" in name or "out of memory" in str(exc).lower()


ENGINE = Engine()
TOKEN = ""
TMP_DIR = Path(".")


class Handler(BaseHTTPRequestHandler):
    server_version = "KDSVox/1"
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):  # silence the default access log
        pass

    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] == "/health":
            self._send(200, ENGINE.info())
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):  # noqa: N802
        if TOKEN and self.headers.get("X-KDS-Token") != TOKEN:
            self._send(403, {"ok": False, "error": "bad token"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}
        except Exception:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        path = self.path.split("?")[0]
        ENGINE.last_activity = time.time()
        if path == "/load":
            ENGINE.start_load()
            self._send(200, ENGINE.info())
        elif path == "/synth":
            self._synth(data)
        elif path == "/shutdown":
            self._send(200, {"ok": True})
            threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0)), daemon=True).start()
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def _synth(self, d: dict) -> None:
        if ENGINE.state != "ready":
            self._send(409, {"ok": False, "kind": "not_ready", "error": f"engine is {ENGINE.state}", "state": ENGINE.state})
            return
        text = str(d.get("text") or "").strip()
        out = Path(str(d.get("out") or ""))
        ref = d.get("ref") or None
        if not text or not out.name:
            self._send(400, {"ok": False, "kind": "bad_input", "error": "text and out are required"})
            return
        try:
            out_res = out.resolve()
            if TMP_DIR.resolve() not in out_res.parents and out_res.parent != TMP_DIR.resolve():
                self._send(400, {"ok": False, "kind": "bad_input", "error": "output path is outside the work folder"})
                return
        except Exception:
            self._send(400, {"ok": False, "kind": "bad_input", "error": "bad output path"})
            return
        if ref and not Path(str(ref)).exists():
            self._send(400, {"ok": False, "kind": "bad_input", "error": f"reference audio not found: {ref}"})
            return
        with ENGINE.gen_lock:
            t0 = time.time()
            wav = None
            for attempt in (1, 2):
                try:
                    wav = ENGINE.generate(text, str(ref) if ref else None, d.get("style") or None,
                                          int(d.get("steps") or 10), float(d.get("cfg") or 2.0), int(d.get("seed") or 1234))
                    write_wav(out_res, wav, ENGINE.sr)
                    break
                except BaseException as exc:  # noqa: BLE001
                    oom = _is_oom(exc)
                    log(("OOM: " if oom else "SYNTH FAILED: ") + traceback.format_exc()[-1500:])
                    if oom:
                        ENGINE.free_memory()
                        if attempt == 1:     # fragmentation is the usual cause on 8 GB cards: one more try with a clean cache
                            log("Out of memory - freed the cache, trying this line once more ...")
                            continue
                    self._send(200, {"ok": False, "kind": "oom" if oom else "error", "error": f"{type(exc).__name__}: {exc}"[:600]})
                    return
        ENGINE.count += 1
        ENGINE.last_activity = time.time()
        dur = len(wav) / float(ENGINE.sr)
        self._send(200, {"ok": True, "sr": ENGINE.sr, "seconds": round(dur, 3), "elapsed": round(time.time() - t0, 3)})


def watchdog(parent_pid: int, idle_min: float) -> None:
    while True:
        time.sleep(4.0)
        if parent_pid and not pid_alive(parent_pid):
            log("The dashboard is gone - exiting.")
            os._exit(0)
        if idle_min > 0 and ENGINE.state == "ready" and time.time() - ENGINE.last_activity > idle_min * 60:
            log(f"Idle for {idle_min:g} min - exiting to free memory.")
            os._exit(0)


def selftest(out: Path, device_pref: str) -> int:
    ENGINE.device_pref = device_pref
    ENGINE.selftest_mode = True
    ENGINE._load()  # synchronous
    if ENGINE.state != "ready":
        print("SELFTEST " + json.dumps({"ok": False, "error": (ENGINE.error or {}).get("message", "load failed"), "kind": (ENGINE.error or {}).get("kind")}), flush=True)
        return 1
    res: dict = {"ok": False, "device": ENGINE.device, "gpu": ENGINE.gpu_name, "sr": ENGINE.sr, "load_s": ENGINE.load_seconds}
    try:
        if not ENGINE.device.startswith("cpu"):
            log("Warm-up ...")
            ENGINE.generate("សួស្តី", None, "A calm adult woman, clear voice", 6, 2.0, 1)
        log("Speaking the test sentence (voice design) ...")
        t0 = time.time()
        wav = ENGINE.generate(SELFTEST_TEXT, None, "A calm adult woman, clear voice", 10, 2.0, 1234)
        el = time.time() - t0
        write_wav(out, wav, ENGINE.sr)
        dur = len(wav) / float(ENGINE.sr)
        res.update({"ok": True, "audio_s": round(dur, 2), "elapsed_s": round(el, 2), "rtf": round(el / max(dur, 0.01), 2)})
    except BaseException as exc:  # noqa: BLE001
        log(traceback.format_exc()[-1500:])
        res.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:600], "kind": "oom" if _is_oom(exc) else "error"})
        print("SELFTEST " + json.dumps(res, ensure_ascii=False), flush=True)
        return 1
    try:  # cloning path: the generated clip becomes the reference (checks that reference audio can be read)
        log("Checking voice cloning with the clip we just made ...")
        w2 = ENGINE.generate("សួស្តី នេះគឺជាសំឡេងគំរូ។", str(out), None, 6, 2.0, 7)
        res["clone_ok"] = bool(len(w2))
    except BaseException as exc:  # noqa: BLE001
        log(traceback.format_exc()[-1200:])
        res["clone_ok"] = False
        res["clone_error"] = f"{type(exc).__name__}: {exc}"[:400]
    print("SELFTEST " + json.dumps(res, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    global TOKEN, TMP_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--token", default="")
    ap.add_argument("--parent-pid", type=int, default=0)
    ap.add_argument("--tmp-dir", default="")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu"])
    ap.add_argument("--idle-min", type=float, default=30.0)
    ap.add_argument("--turbo", action="store_true", help="EXPERIMENTAL: record the diffusion sampler as a CUDA graph")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default="selftest.wav")
    args = ap.parse_args()

    if args.selftest:
        return selftest(Path(args.out), args.device)

    TOKEN = args.token
    TMP_DIR = Path(args.tmp_dir or os.getcwd())
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    ENGINE.device_pref = args.device
    ENGINE.turbo_req = bool(args.turbo)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.daemon_threads = True
    log(f"READY port={srv.server_address[1]} pid={os.getpid()}")
    threading.Thread(target=watchdog, args=(args.parent_pid, args.idle_min), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
