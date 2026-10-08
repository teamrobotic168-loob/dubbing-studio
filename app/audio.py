"""Audio helpers built on ffmpeg + numpy (no pydub → works on Python 3.13)."""
from __future__ import annotations

import collections
import functools
import os
import re
import shutil
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

import numpy as np

from .config import SAMPLE_RATE as SR

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FFmpegError(RuntimeError):
    pass


def ffmpeg_failure(rc, stderr_tail: str) -> FFmpegError:
    """The error for a failed ffmpeg run.  A missing encoder (a stripped-down ffmpeg build) gets a plain-language hint."""
    tail = (stderr_tail or "").strip()
    msg = f"ffmpeg failed ({rc}): {tail}"
    m = re.search(r"Unknown encoder '([^']+)'|Encoder '?([A-Za-z0-9_]+)'? not found|Unrecognized option '(?:c:v|vcodec)'", tail)
    if m:
        enc = m.group(1) or m.group(2) or "an encoder"
        msg += (f"  -> This ffmpeg build has no '{enc}' encoder. Install the full ffmpeg (Mac: brew install ffmpeg - Windows: winget install ffmpeg - "
                "Linux: your package manager) and start V_Heang Studio again; it uses the ffmpeg it finds on your PATH first.")
    return FFmpegError(msg)


@functools.lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """System ffmpeg if available, else the static binary shipped by imageio-ffmpeg."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise FFmpegError(
            "ffmpeg was not found. Install it (https://ffmpeg.org) or run: pip install imageio-ffmpeg"
        ) from exc


def ffmpeg_version() -> str:
    try:
        r = subprocess.run([ffmpeg_exe(), "-version"], capture_output=True, text=True, creationflags=_CREATE_NO_WINDOW)
        return (r.stdout.splitlines() or [""])[0]
    except Exception:
        return ""


def _run(cmd: list, input_bytes: Optional[bytes] = None, timeout: Optional[int] = 3600) -> subprocess.CompletedProcess:
    p = subprocess.run(
        cmd,
        input=input_bytes,
        capture_output=True,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
    )
    if p.returncode != 0:
        raise ffmpeg_failure(p.returncode, p.stderr.decode("utf-8", "ignore")[-800:])
    return p


_OUT_TIME = re.compile(r"^out_time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def parse_out_time(line: str) -> Optional[float]:
    """`out_time=00:01:05.120000` (a line of `ffmpeg -progress`) -> seconds; None for anything else (`out_time=N/A` too)."""
    m = _OUT_TIME.match(line.strip())
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


def run_with_progress(cmd: list, total_s: Optional[float] = None, progress: Optional[Callable[[float], None]] = None,
                      cancel: Optional[Callable[[], bool]] = None) -> None:
    """Run ffmpeg and report how far it is (0..1, from `-progress`).  `cancel()` returning True stops ffmpeg (FFmpegError("cancelled")).
    stdout carries the progress lines, stderr (only errors, thanks to `-v error`) is kept for the message of a failure."""
    cmd = [cmd[0], "-progress", "pipe:1", "-nostats"] + list(cmd[1:])
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, creationflags=_CREATE_NO_WINDOW,
                         text=True, encoding="utf-8", errors="replace", bufsize=1)
    err_tail: collections.deque = collections.deque(maxlen=60)

    def drain() -> None:
        try:
            for line in p.stderr:                 # type: ignore[union-attr]
                err_tail.append(line)
        except Exception:                          # noqa: BLE001
            pass

    th = threading.Thread(target=drain, daemon=True)
    th.start()
    stopped = completed = False
    try:
        for line in p.stdout:                      # type: ignore[union-attr]
            if cancel is not None and cancel():
                stopped = True
                break
            t = parse_out_time(line)
            if t is not None and progress is not None and total_s and total_s > 0:
                try:
                    progress(max(0.0, min(0.99, t / total_s)))
                except Exception:                  # noqa: BLE001 - a broken progress callback must not break the video
                    pass
        completed = True
    finally:
        # Only a cancel (or an exception on our side) stops ffmpeg - and then it is killed at once: a polite SIGTERM can take as long
        # as the whole video (ffmpeg 7 finishes its queues first), and the half-made file is thrown away anyway.  A normal end is never
        # interrupted: ffmpeg may still be finishing the MP4 (the +faststart pass), and killing it there would damage the file.
        if stopped or not completed:
            p.kill()
        rc = p.wait()
        th.join(timeout=2)
    if stopped:
        raise FFmpegError("cancelled")
    if rc != 0:
        raise ffmpeg_failure(rc, "".join(err_tail)[-800:])


# --------------------------------------------------------------------------- #
# decode / encode
# --------------------------------------------------------------------------- #
def decode_to_array(path: str | Path, sr: int = SR) -> np.ndarray:
    """Decode any audio/video file to mono float32 PCM at `sr`."""
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-i", str(path), "-vn", "-f", "f32le", "-ac", "1", "-ar", str(sr), "pipe:1"]
    p = _run(cmd)
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def encode_array(x: np.ndarray, path: str | Path, sr: int = SR, bitrate: str = "128k") -> None:
    """Encode mono float32 PCM to mp3 / wav / m4a depending on the file extension."""
    path = Path(path)
    ext = path.suffix.lower()
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-y", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0"]
    if ext == ".mp3":
        cmd += ["-codec:a", "libmp3lame", "-b:a", bitrate]
    elif ext in (".m4a", ".aac"):
        cmd += ["-codec:a", "aac", "-b:a", bitrate]
    elif ext == ".wav":
        cmd += ["-codec:a", "pcm_s16le"]
    cmd.append(str(path))
    _run(cmd, input_bytes=np.ascontiguousarray(x, dtype=np.float32).tobytes())


def time_stretch(x: np.ndarray, factor: float, sr: int = SR) -> np.ndarray:
    """Speed up (factor > 1) or slow down (< 1) without changing pitch (ffmpeg atempo)."""
    if len(x) == 0 or abs(factor - 1.0) < 0.01:
        return x
    filters = []
    f = float(factor)
    while f > 2.0:
        filters.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        filters.append("atempo=0.5")
        f /= 0.5
    filters.append(f"atempo={f:.4f}")
    cmd = [
        ffmpeg_exe(), "-v", "error", "-nostdin", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
        "-filter:a", ",".join(filters), "-f", "f32le", "-ar", str(sr), "-ac", "1", "pipe:1",
    ]
    p = _run(cmd, input_bytes=np.ascontiguousarray(x, dtype=np.float32).tobytes())
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


# --------------------------------------------------------------------------- #
# DSP helpers
# --------------------------------------------------------------------------- #
def trim_silence(x: np.ndarray, sr: int = SR, rel_thresh: float = 0.025, pad_ms: float = 25.0) -> np.ndarray:
    """Trim leading/trailing silence (Edge TTS adds ~0.2 s lead and up to ~1 s tail)."""
    if len(x) == 0:
        return x
    peak = float(np.max(np.abs(x)))
    if peak < 1e-4:
        return x[:0]
    idx = np.flatnonzero(np.abs(x) > peak * rel_thresh)
    if len(idx) == 0:
        return x[:0]
    pad = int(sr * pad_ms / 1000)
    a = max(0, int(idx[0]) - pad)
    b = min(len(x), int(idx[-1]) + pad)
    return x[a:b]


def rms_of_voiced(x: np.ndarray) -> float:
    if len(x) == 0:
        return 0.0
    peak = float(np.max(np.abs(x)))
    if peak < 1e-5:
        return 0.0
    voiced = x[np.abs(x) > peak * 0.03]
    if len(voiced) == 0:
        return 0.0
    return float(np.sqrt(np.mean(voiced.astype(np.float64) ** 2)))


def normalize_rms(x: np.ndarray, target: float = 0.085, max_gain: float = 3.0, min_gain: float = 0.35) -> np.ndarray:
    r = rms_of_voiced(x)
    if r <= 0:
        return x
    g = float(np.clip(target / r, min_gain, max_gain))
    return (x * g).astype(np.float32)


def fade(x: np.ndarray, sr: int = SR, ms: float = 8.0) -> np.ndarray:
    n = min(int(sr * ms / 1000), len(x) // 2)
    if n <= 0:
        return x
    y = x.copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    y[:n] *= ramp
    y[-n:] *= ramp[::-1]
    return y


def silence(seconds: float, sr: int = SR) -> np.ndarray:
    return np.zeros(int(max(0.0, seconds) * sr), dtype=np.float32)


def mix_into(base: np.ndarray, seg: np.ndarray, start_sec: float, sr: int = SR) -> np.ndarray:
    """Add `seg` into `base` at start_sec. Grows base if needed. Returns (possibly new) base."""
    a = int(max(0.0, start_sec) * sr)
    b = a + len(seg)
    if b > len(base):
        base = np.concatenate([base, np.zeros(b - len(base), dtype=np.float32)])
    base[a:b] += seg
    return base


def soft_limit(x: np.ndarray, ceiling: float = 0.97) -> np.ndarray:
    if len(x) == 0:
        return x
    peak = float(np.max(np.abs(x)))
    if peak <= ceiling:
        return x
    # gentle tanh compression for the loud parts, then hard normalise
    y = np.tanh(x / peak * 1.2) / np.tanh(1.2) * ceiling
    return y.astype(np.float32)


def duration_of(x: np.ndarray, sr: int = SR) -> float:
    return len(x) / float(sr)


# --------------------------------------------------------------------------- #
# media probing / muxing
# --------------------------------------------------------------------------- #
def _ffmpeg_info(path: str | Path) -> str:
    """The text `ffmpeg -i FILE` prints about a file (ffmpeg ends with an error because there is no output - that is fine).
    Decoded as UTF-8 with replacement: titles / names in Khmer, Chinese ... must never crash the probe (Windows uses a legacy code page)."""
    p = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, creationflags=_CREATE_NO_WINDOW)
    return p.stderr.decode("utf-8", "replace")


def probe_media(path: str | Path) -> dict:
    """Light-weight probe using `ffmpeg -i` (imageio's ffmpeg has no ffprobe)."""
    err = _ffmpeg_info(path)
    info = {"duration": None, "video_codec": None, "has_audio": False, "has_video": False, "width": None, "height": None}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    mv = next((m for m in re.finditer(r"Stream #\S+.*?Video:\s*([A-Za-z0-9_]+)([^\n]*)", err) if "attached pic" not in m.group(2)), None)   # the cover of an MP3 is no video
    if mv:
        info["has_video"] = True
        info["video_codec"] = mv.group(1).lower()
        md = re.search(r",\s*(\d{2,5})x(\d{2,5})\b", mv.group(2))      # "..., 1920x1080 [SAR 1:1 DAR 16:9], ..."
        if md:
            info["width"], info["height"] = int(md.group(1)), int(md.group(2))
    if re.search(r"Stream #\S+.*?Audio:", err):
        info["has_audio"] = True
    info["sar"], info["rotation"] = 1.0, 0.0
    if mv:
        ms = re.search(r"\[SAR\s+(\d+):(\d+)", mv.group(2))              # "[SAR 32:27 DAR 16:9]" - pixels that are not square
        if ms and int(ms.group(2)) > 0 and int(ms.group(1)) > 0:
            info["sar"] = int(ms.group(1)) / int(ms.group(2))
        vs = next((x for x in parse_streams(err) if x["type"] == "video" and not x["attached"]), None)
        if vs:
            info["rotation"] = vs["rotation"]                              # phone videos are stored sideways with a "rotate by" flag
    return info


_STREAM_RE = re.compile(r"^\s*Stream #(\d+):(\d+)(?:\[[^\]]*\])?(?:\(([^)]*)\))?[^:]*:\s*(Video|Audio|Subtitle|Data|Attachment):\s*([A-Za-z0-9_]+)(.*)$")
_META_RE = re.compile(r"^\s{4,}([A-Za-z_][\w ./-]*?)\s*:\s?(.*)$")


def parse_streams(err: str) -> List[dict]:
    """The streams listed in the text of `ffmpeg -i` -> [{index, type, codec, lang, title, forced, default, attached, width, height, rotation, pos}].
    `pos` is the number of the stream among the streams of its own type (what `-map 0:s:POS` wants)."""
    out: List[dict] = []
    counts: dict = {}
    cur: Optional[dict] = None
    in_meta = False
    for line in err.splitlines():
        m = _STREAM_RE.match(line)
        if m:
            kind = m.group(4).lower()
            rest = m.group(6) or ""
            cur = {"index": int(m.group(2)), "type": kind, "codec": m.group(5).lower(), "lang": (m.group(3) or "").strip().lower(),
                   "title": "", "forced": "(forced)" in rest, "default": "(default)" in rest, "attached": "attached pic" in rest,
                   "width": None, "height": None, "rotation": 0.0, "pos": counts.get(kind, 0)}
            counts[kind] = counts.get(kind, 0) + 1
            if kind == "video":
                md = re.search(r",\s*(\d{2,5})x(\d{2,5})\b", rest)
                if md:
                    cur["width"], cur["height"] = int(md.group(1)), int(md.group(2))
            out.append(cur)
            in_meta = False
            continue
        if cur is None:
            continue
        if re.match(r"^\s+Metadata:\s*$", line):
            in_meta = True
            continue
        mr = re.search(r"rotation of (-?\d+(?:\.\d+)?) degrees", line)
        if mr:
            cur["rotation"] = float(mr.group(1))
            continue
        if in_meta:
            mm = _META_RE.match(line)
            if mm and mm.group(1).strip().lower() == "title" and not cur["title"]:
                cur["title"] = mm.group(2).strip()
            elif not mm:
                in_meta = False
    return out


def probe_streams(path: str | Path) -> dict:
    """Everything the upload page needs to know about a media file: duration, size of the picture, audio, subtitle tracks."""
    err = _ffmpeg_info(path)
    info = {"duration": None, "streams": parse_streams(err)}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return info


def needs_scale(width, height, max_height) -> bool:
    """Is the picture bigger than the chosen limit?  The SHORTER side is compared (1080p = 1920x1080 and 1080x1920 alike)."""
    try:
        return bool(max_height and width and height and min(int(width), int(height)) > int(max_height))
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# "mute the original voice while Khmer speaks"
#
# The original track is multiplied by a gain envelope (1 = normal, 0 = silent) that drops to 0 for every spoken line
# - both where the ORIGINAL speaker talks (English caption times) and where the KHMER voice is placed - and comes back
# in the pauses.  Short fades avoid clicks.  The envelope is a tiny mono WAV that ffmpeg multiplies with the track, so
# there is no limit on the number of lines (no giant filter expression).
# --------------------------------------------------------------------------- #
DUCK_PRE = 0.10         # start muting a little before a line (captions are often a bit late)
DUCK_POST = 0.22        # ... and keep muting a little after it (last syllable, tail of the Khmer line)
DUCK_MERGE_GAP = 0.50   # pauses shorter than this are not worth un-muting (no "pumping" in dense speech)
DUCK_FADE_OUT = 0.05    # how fast the original goes down when a line starts
DUCK_FADE_IN = 0.22     # ... and how smoothly it comes back
DUCK_SR = 8000          # sample rate of the envelope file (a smooth curve needs very little)


def duck_intervals(windows: Iterable[Tuple[float, float]], pre: float = DUCK_PRE, post: float = DUCK_POST,
                   merge_gap: float = DUCK_MERGE_GAP) -> List[Tuple[float, float]]:
    """Spoken (start, end) windows -> padded, sorted, merged mute intervals."""
    iv = sorted((max(0.0, float(a) - pre), float(b) + post) for a, b in windows
                if a is not None and b is not None and float(b) > float(a))
    out: List[List[float]] = []
    for a, b in iv:
        if out and a - out[-1][1] <= merge_gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def duck_envelope(intervals: Iterable[Tuple[float, float]], total_s: float, sr: int = DUCK_SR,
                  fade_out: float = DUCK_FADE_OUT, fade_in: float = DUCK_FADE_IN) -> np.ndarray:
    """Gain curve: 1.0 everywhere, 0.0 inside each interval, raised-cosine fades just before / after it."""
    n = int(max(1.0, total_s) * sr) + 1
    g = np.ones(n, dtype=np.float32)
    fo, fi = max(1, int(fade_out * sr)), max(1, int(fade_in * sr))
    for a, b in intervals:
        i0, i1 = int(a * sr), min(n, int(b * sr))
        if i0 >= n:
            break
        lo = max(0, i0 - fo)
        if i0 > lo:
            down = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, i0 - lo, endpoint=False)))     # 1 -> 0
            g[lo:i0] = np.minimum(g[lo:i0], down.astype(np.float32))
        g[i0:i1] = 0.0
        hi = min(n, i1 + fi)
        if hi > i1:
            up = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, hi - i1, endpoint=False)))       # 0 -> 1
            g[i1:hi] = np.minimum(g[i1:hi], up.astype(np.float32))
    return g


def write_gain_wav(env: np.ndarray, path: str | Path, sr: int = DUCK_SR) -> None:
    pcm = (np.clip(env, 0.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())


def replace_file(src: str | Path, dst: str | Path, tries: int = 8, wait: float = 0.4) -> None:
    """os.replace with a few retries: on Windows the old file may still be held for a moment (the browser that played it, an antivirus scan);
    a macOS / Linux replace never needs that.  After the last try the problem is explained in words (an FFmpegError, so the audio result is kept)."""
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:
            if i == tries - 1:
                raise FFmpegError(f"The new MP4 is ready, but the old file '{Path(dst).name}' is in use by another program (a video player or the preview?). "
                                  f"Close it and make the video again. ({e})") from e
            time.sleep(wait)


def remove_file(path: str | Path, tries: int = 10, wait: float = 0.3) -> bool:
    """Delete a file; True when it is gone.  On Windows a file that a program still has open (the browser that plays it, an antivirus scan)
    cannot be deleted: try again for a few seconds, then give up QUIETLY (False) - an old copy that stays on the disk must never fail a job."""
    p = Path(path)
    for i in range(max(1, tries)):
        try:
            p.unlink(missing_ok=True)
            return True
        except PermissionError:
            if i < tries - 1:
                time.sleep(wait)
        except OSError:
            return False
    return False


def mux_video(video_path: str | Path, audio_path: str | Path, out_path: str | Path, orig_volume: float = 0.0, progress=None,
              duck_mask: Optional[str | Path] = None, max_height: Optional[int] = None, frame=None, cancel=None, hardsub=None) -> None:
    """Replace (or mix under) the video's audio with the dubbed track.

    duck_mask: optional gain-envelope WAV (see write_gain_wav) applied to the ORIGINAL audio before it is mixed under the dub.
    max_height: a picture whose shorter side is bigger than this (an uploaded 4K video, with the limit at 1080p) is scaled down
    (the video is re-encoded); anything else keeps its size (and is copied untouched when it is already H.264 / HEVC).
    frame: a frame.FramePlan - the picture is put into a vertical 9:16 frame (TikTok), which always re-encodes it.
    hardsub: a hardsub.HardsubPlan - the subtitles burned into the ORIGINAL picture are blurred / covered (always re-encodes the picture);
    together with `frame` the band is made first and the 9:16 frame second.
    progress(p): called with 0..1 while ffmpeg works;  cancel(): returns True when the user cancelled (ffmpeg is stopped).
    The MP4 is written to a temporary file first, so a failure never leaves a half-written (or damaged) result behind.
    """
    video_path, audio_path, out_path = Path(video_path), Path(audio_path), Path(out_path)
    vinfo = probe_media(video_path)
    vcodec = vinfo.get("video_codec") or ""
    copy_ok = vcodec in ("h264", "hevc", "mpeg4", "av1") and vcodec != "av1"
    scale = needs_scale(vinfo.get("width"), vinfo.get("height"), max_height)
    vgraph = None                      # a -filter_complex graph that makes [vout]; None = the picture is copied (or scaled by a plain -vf)
    if frame is not None or hardsub is not None:
        parts, last = [], "0:v:0"
        if hardsub is not None:
            parts.append(hardsub.graph_from(last))
            last = hardsub.out
        if frame is not None:
            parts.append(frame.graph_from(last) if hardsub is not None else frame.graph)
        else:                          # only the band: keep the shape, obey the size limit, make the size even (H.264 needs that)
            lim = int(max_height) if scale else 0
            sc = f"scale=w='if(gt(iw,ih),-2,min(iw,{lim}))':h='if(gt(iw,ih),min(ih,{lim}),-2)'," if scale else ""
            parts.append(f"[{last}]{sc}scale=w='trunc(iw/2)*2':h='trunc(ih/2)*2',format=yuv420p[vout]")
        vgraph = ";".join(parts)
    if frame is not None:
        vopts = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-maxrate", "8M", "-bufsize", "16M", "-profile:v", "high", "-pix_fmt", "yuv420p"]
    elif vgraph:
        vopts = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    elif copy_ok and not scale:
        vopts = ["-c:v", "copy"]
    else:
        vopts = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
        if scale:                      # w / h are decided on the real (rotated) frame, and never enlarge
            lim = int(max_height)
            vopts = ["-vf", f"scale=w='if(gt(iw,ih),-2,min(iw,{lim}))':h='if(gt(iw,ih),min(ih,{lim}),-2)'"] + vopts

    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-y", "-i", str(video_path), "-i", str(audio_path)]
    if orig_volume and orig_volume > 0.001 and vinfo.get("has_audio"):
        if duck_mask:
            cmd += ["-i", str(duck_mask)]
            fc = (
                "[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,aresample=48000[o];"
                # the envelope is copied (not up-mixed) to both channels so that its level stays exactly 1.0 / 0.0
                "[2:a]aformat=sample_fmts=fltp:channel_layouts=mono,aresample=48000,pan=stereo|c0=c0|c1=c0[m];"
                "[o][m]amultiply[d];"
                f"[d]volume={orig_volume:.3f}[bg];[1:a]volume=1.0[fg];"
                "[bg][fg]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]"
            )
        else:
            fc = (
                f"[0:a]volume={orig_volume:.3f}[bg];[1:a]volume=1.0[fg];"
                "[bg][fg]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]"
            )
        cmd += ["-filter_complex", (vgraph + ";" if vgraph else "") + fc, "-map", "[vout]" if vgraph else "0:v:0", "-map", "[aout]"]
    else:
        if vgraph:
            cmd += ["-filter_complex", vgraph]
        cmd += ["-map", "[vout]" if vgraph else "0:v:0", "-map", "1:a:0"]
    aopts = ["-c:a", "aac", "-b:a", "160k"] + (["-ar", "48000", "-ac", "2"] if frame is not None else [])   # TikTok: stereo AAC at 48 kHz
    tmp = out_path.with_name(out_path.stem + ".part" + (out_path.suffix or ".mp4"))
    tmp.unlink(missing_ok=True)
    cmd += vopts + aopts + ["-movflags", "+faststart", str(tmp)]
    try:
        if progress is not None or cancel is not None:
            total = max(vinfo.get("duration") or 0.0, (probe_media(audio_path).get("duration") or 0.0))
            run_with_progress(cmd, total, progress, cancel)
        else:
            _run(cmd, timeout=None)
        replace_file(tmp, out_path)
    finally:
        tmp.unlink(missing_ok=True)
