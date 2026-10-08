"""Who is speaking?  Finds out, from the video's own sound, whether every caption line is spoken by a man or by a woman and
which lines belong to the same person ("character"), so the dub can give men a male voice and women a female voice
without anybody entering a voice per character by hand.

How (nothing to install - numpy only; ffmpeg just decodes the file):

  1. the sound is decoded once to 16 kHz mono;
  2. for every caption line the pitch (F0) of the voiced stretches is measured (YIN) - a man's voice sits around 85-180 Hz, a
     woman's around 165-255 Hz - and a voice-colour fingerprint (MFCC) is taken;
  3. the pitch decides man / woman; lines whose pitch is in the grey zone, or that have too little voiced sound (music,
     whisper, noise), take the answer of the voice they sound like, or of their neighbours;
  4. lines of the same gender are grouped into characters by their pitch and colour - cautiously: it is better to keep two
     people together (they just get the same voice) than to split one person in two (a voice that changes in the middle).

The answer is a guess from physics, not from knowledge: children, singers and low-pitched women (or high-pitched men) can be
wrong, which is why the editor lets you flip the gender of a character or choose the voice of a single line.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import audio

SR = 16000                       # analysis sample rate
HOP = 160                        # 10 ms
WIN = 512                        # 32 ms analysis window (YIN)
F0_MIN, F0_MAX = 60.0, 420.0     # search range of the pitch (Hz)
TAU_MIN = int(SR / F0_MAX)       # 38
TAU_MAX = int(SR / F0_MIN) + 1   # 267
NFFT = 1024                      # >= WIN + TAU_MAX
CHUNK = 3000                     # frames per batch (memory: ~3000 x 1024 x 8 bytes)
F0_OK = (72.0, 380.0)            # a median pitch outside this is not a human voice (a rumble, a whistle, a sub-harmonic): the line gets no pitch
MIN_VOICED = 12                  # frames (120 ms) of clear voice a line needs before its pitch is trusted
VOICED_CONF = 0.72               # 1 - YIN's normalised difference: how periodic a frame has to be to count as voiced

F_SPLIT = 165.0                  # Hz: the usual boundary between men and women (log-scale logistic below)
SLOPE = 9.0                      # steepness of that logistic (per octave)
SURE = 0.80                      # P(female) >= SURE or <= 1 - SURE: the line decides on its own

N_MEL = 24
N_MFCC = 13


# --------------------------------------------------------------------------- #
# decoding
# --------------------------------------------------------------------------- #
def load_pcm(path: str | Path, sr: int = SR, start: float = 0.0, dur: Optional[float] = None) -> np.ndarray:
    """Any audio / video file -> mono int16 samples at `sr` (half the memory of float32: 2 hours = 230 MB)."""
    cmd = [audio.ffmpeg_exe(), "-v", "error", "-nostdin"]
    if start and start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-sn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1"]
    p = audio._run(cmd, timeout=3600)
    return np.frombuffer(p.stdout, dtype=np.int16)


def _f32(x: np.ndarray) -> np.ndarray:
    return x.astype(np.float32) / 32768.0 if x.dtype == np.int16 else x.astype(np.float32, copy=False)


# --------------------------------------------------------------------------- #
# pitch (YIN, vectorised): F0 + how periodic every 10 ms frame is
# --------------------------------------------------------------------------- #
def _hann(n: int) -> np.ndarray:
    return (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)


_HANN = _hann(WIN)


def _mel_filters(n_fft: int = WIN, sr: int = SR, n_mel: int = N_MEL, fmin: float = 80.0, fmax: float = 4000.0) -> np.ndarray:
    def hz2mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel2hz(m):
        return 700.0 * (10 ** (m / 2595.0) - 1.0)

    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_mel + 2)
    hz = mel2hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    fb = np.zeros((n_mel, n_fft // 2 + 1), dtype=np.float32)
    for m in range(1, n_mel + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        c = max(c, l + 1)
        r = max(r, c + 1)
        fb[m - 1, l:c] = (np.arange(l, c) - l) / max(1, c - l)
        fb[m - 1, c:r] = (r - np.arange(c, r)) / max(1, r - c)
    return fb


_MEL = _mel_filters()
_DCT = np.cos(np.pi / N_MEL * (np.arange(N_MEL)[None, :] + 0.5) * np.arange(N_MFCC)[:, None]).astype(np.float32)


def pitch_frames(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """x: float32 mono at SR -> (f0 Hz, conf 0..1, rms, mfcc) per 10 ms frame (f0 = 0 where unvoiced).

    conf = 1 - d'(tau) of YIN: 1 means perfectly periodic.  mfcc is only filled for voiced frames (13 numbers)."""
    L = WIN + TAU_MAX
    n = 1 + max(0, len(x) - L) // HOP
    if len(x) < L:
        return (np.zeros(0, np.float32),) * 3 + (np.zeros((0, N_MFCC), np.float32),)
    f0 = np.zeros(n, np.float32)
    conf = np.zeros(n, np.float32)
    rms = np.zeros(n, np.float32)
    mfcc = np.zeros((n, N_MFCC), np.float32)
    taus = np.arange(TAU_MAX + 1, dtype=np.float32)
    for c0 in range(0, n, CHUNK):
        c1 = min(n, c0 + CHUNK)
        idx = (np.arange(L, dtype=np.int64)[None, :] + HOP * np.arange(c0, c1, dtype=np.int64)[:, None])
        fr = x[idx]                                               # (m, L)
        a = fr[:, :WIN]
        e0 = np.einsum("ij,ij->i", a, a)                           # energy of the reference window
        rms[c0:c1] = np.sqrt(e0 / WIN)
        cs = np.concatenate([np.zeros((fr.shape[0], 1), np.float32), np.cumsum(fr * fr, axis=1, dtype=np.float64).astype(np.float32)], axis=1)
        etau = cs[:, WIN: WIN + TAU_MAX + 1] - cs[:, : TAU_MAX + 1]   # energy of the window shifted by tau
        A = np.fft.rfft(a, NFFT, axis=1)
        B = np.fft.rfft(fr, NFFT, axis=1)
        r = np.fft.irfft(np.conj(A) * B, NFFT, axis=1)[:, : TAU_MAX + 1].astype(np.float32)
        d = e0[:, None] + etau - 2.0 * r                           # difference function d(tau)
        d[:, 0] = 0.0
        run = np.cumsum(d[:, 1:], axis=1)
        dn = np.ones_like(d)
        dn[:, 1:] = d[:, 1:] * taus[None, 1:] / np.maximum(run, 1e-9)    # cumulative mean normalised difference
        sub = dn[:, TAU_MIN: TAU_MAX]                              # the tau range that is searched
        # first dip under the threshold (the smallest period = the highest pitch), else the deepest dip
        below = sub < 0.20
        # a "dip" is a local minimum
        lm = np.zeros_like(below)
        lm[:, 1:-1] = (sub[:, 1:-1] <= sub[:, :-2]) & (sub[:, 1:-1] < sub[:, 2:])
        cand = below & lm
        first = np.argmax(cand, axis=1)
        has = cand[np.arange(len(first)), first]
        deep = np.argmin(sub, axis=1)
        pick = np.where(has, first, deep)
        t = pick + TAU_MIN
        # parabolic refinement
        ti = np.clip(t, 1, TAU_MAX - 1)
        rows = np.arange(len(t))
        y0, y1, y2 = dn[rows, ti - 1], dn[rows, ti], dn[rows, ti + 1]
        den = (y0 - 2 * y1 + y2)
        shift = np.where(np.abs(den) > 1e-9, 0.5 * (y0 - y2) / np.where(np.abs(den) > 1e-9, den, 1.0), 0.0)
        tau = ti + np.clip(shift, -1.0, 1.0)
        cf = 1.0 - dn[rows, ti]
        # octave check: a period twice as long as the true one also gives a deep dip; prefer the shorter one when it is nearly as good
        half = np.round(tau / 2).astype(int)
        okh = half >= TAU_MIN
        hh = np.clip(half, 1, TAU_MAX - 1)
        near = np.stack([dn[rows, np.clip(hh + k, 1, TAU_MAX - 1)] for k in (-1, 0, 1)], axis=1)
        kbest = np.argmin(near, axis=1) - 1
        hpos = np.clip(hh + kbest, 1, TAU_MAX - 1)
        better = okh & (dn[rows, hpos] < dn[rows, ti] + 0.08) & (dn[rows, hpos] < 0.3)
        tau = np.where(better, hpos.astype(np.float32), tau)
        cf = np.where(better, 1.0 - dn[rows, hpos], cf)
        f0[c0:c1] = SR / np.maximum(tau, 1.0)
        conf[c0:c1] = cf
        # voice colour of the frames that sound voiced
        vm = (cf >= VOICED_CONF) & (rms[c0:c1] > 1e-4)
        if vm.any():
            w = a[vm] * _HANN[None, :]
            sp = np.abs(np.fft.rfft(w, WIN, axis=1)) ** 2
            mel = np.log(sp @ _MEL.T + 1e-8)
            mfcc[c0:c1][vm] = mel @ _DCT.T
    f0[(conf < VOICED_CONF) | (rms <= 1e-4)] = 0.0              # not periodic enough, or digital silence
    return f0, conf, rms, mfcc


# --------------------------------------------------------------------------- #
# one caption line
# --------------------------------------------------------------------------- #
@dataclass
class LineFeat:
    f0: Optional[float] = None          # median pitch (Hz) of the voiced frames; None = not enough voiced sound
    voiced: int = 0                     # voiced frames (10 ms each)
    frames: int = 0                     # all frames of the line
    p_female: Optional[float] = None    # 0 (man) .. 1 (woman); None = unknown
    mfcc: Optional[np.ndarray] = None   # mean voice colour (13) of the voiced frames
    quality: float = 0.0                # how good a voice reference this line would be (0..1)


def p_female_of(f0: Optional[float]) -> Optional[float]:
    """Pitch -> probability that the speaker is a woman (a logistic on the octave scale around F_SPLIT)."""
    if not f0 or f0 <= 0:
        return None
    z = SLOPE * math.log2(f0 / F_SPLIT)
    return float(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))))


def line_feature(f0: np.ndarray, conf: np.ndarray, rms: np.ndarray, mfcc: np.ndarray) -> LineFeat:
    """Summarise the frames of one caption line."""
    n = len(f0)
    ft = LineFeat(frames=n)
    if n == 0:
        return ft
    v = f0 > 0
    # only frames that are not far below the loudest part of the line (breath, room noise)
    if v.any():
        loud = rms > 0.12 * float(np.percentile(rms[v], 90))
        v = v & loud
    k = int(v.sum())
    ft.voiced = k
    if k < MIN_VOICED:
        return ft
    ff = f0[v]
    # trim octave jumps: keep the main cluster of the pitch (within 1.6x of the median)
    med = float(np.median(ff))
    keep = (ff > med / 1.6) & (ff < med * 1.6)
    if keep.sum() >= MIN_VOICED:
        ff = ff[keep]
        med = float(np.median(ff))
        m2 = mfcc[v][keep]
    else:
        m2 = mfcc[v]
    if not (F0_OK[0] <= med <= F0_OK[1]):
        return ft
    ft.f0 = med
    ft.p_female = p_female_of(med)
    ft.mfcc = m2.mean(axis=0)
    cvv = conf[v]
    ft.quality = float(min(1.0, (len(ff) / max(1, n)) * 1.4) * float(np.mean(cvv)))
    return ft


# --------------------------------------------------------------------------- #
# grouping the lines into characters
# --------------------------------------------------------------------------- #
# How far the voice colour (MFCC 1..12 of the voiced frames) of ONE speaker moves from line to line (measured on read speech)
MFCC_SIGMA = np.array([4.8, 5.1, 3.5, 2.6, 2.0, 1.9, 1.7, 1.5, 1.6, 1.3, 1.1, 1.15], np.float32)
F0_SIGMA = 0.25                  # the same for the pitch, in octaves
PITCH_W = 0.3                    # how much the pitch counts next to the colour when two lines are compared (to share evidence)
SPLIT_PITCH_W = 0.05             # ... and when deciding whether two groups of ONE gender are two people (a voice moves in pitch with every sentence)
POOL_ITER = 1                    # how many times the lines pass their evidence on (more = one verdict per voice)
POOL_BW = 1.4                    # lines that sound alike share their evidence about the gender (bigger = a wider circle of "alike")
SPLIT_C = 3.4                    # two groups of one gender are two characters only when they are this many times further apart than a line is from its nearest sibling
CORE_VOICED = 40                 # a line needs this many voiced frames (0.4 s) to take part in forming the characters
MIN_CHAR_LINES = 3               # a character with fewer lines AND less speech than MIN_CHAR_SECONDS is folded into the closest other one
MIN_CHAR_SECONDS = 10.0
MIN_COVERAGE = 0.2               # below this share of clearly measurable speech the answer would be a guess: no characters are made
MIN_MEASURED_S = 3.0             # ... and at least this many seconds must have been measured
MINORITY_SHARE = 0.25            # ... and that is less than this share of all the speech
GREY = 1.2                       # a character whose evidence is weaker than this (logit; 1.2 = 77 %) is "not sure" about its gender
GREY_MERGE_C = 2.2               # two not-sure characters of different gender that sound this close are ONE person on the gender boundary
MAX_PER_GENDER = 4               # characters of one gender (4 designed voices exist per gender)
MAX_POOL = 1500                  # the evidence is pooled over at most this many lines (memory: n x n); the rest only reads it
MAX_CLUSTER = 320                # the grouping is O(n^3): at most this many lines form the characters of a gender, the rest is assigned afterwards
LOGIT_CAP = 4.0
NEIGHBOUR_S = 8.0                # a line without usable sound takes the character of a neighbour that is at most this far away


def _logit(p: float) -> float:
    p = min(0.995, max(0.005, p))
    return max(-LOGIT_CAP, min(LOGIT_CAP, math.log(p / (1.0 - p))))


def _vec(ft: LineFeat) -> np.ndarray:
    return ft.mfcc[1:13] / MFCC_SIGMA


def _dist(A: np.ndarray, la: np.ndarray, B: np.ndarray, lb: np.ndarray, pw: Optional[float] = None) -> np.ndarray:
    """Distance between every line of A and every line of B: voice colour (rms over the 12 numbers) plus a little pitch."""
    a2 = (A * A).sum(axis=1)[:, None]
    b2 = (B * B).sum(axis=1)[None, :]
    d2 = np.maximum(0.0, a2 + b2 - 2.0 * (A @ B.T)) / A.shape[1]
    dp = (la[:, None] - lb[None, :]) / F0_SIGMA
    return np.sqrt(d2 + (PITCH_W if pw is None else pw) * dp * dp)


SCALE_LINES = 40                 # the "closest sibling" is looked for among this many lines (more lines would always find a closer one)


def _scale(D: np.ndarray) -> float:
    """The typical distance between a line and its closest sibling in this video (how much one voice varies here).

    Measured on at most SCALE_LINES lines, spread over the whole video: with hundreds of lines every line has a near-twin, which
    would make the scale (and with it the patience of the grouping) shrink the longer the video is."""
    n = len(D)
    if n > SCALE_LINES:
        pick = np.linspace(0, n - 1, SCALE_LINES).astype(int)
        D = D[np.ix_(pick, pick)]
    D = D.copy()
    np.fill_diagonal(D, np.inf)
    return max(0.3, float(np.median(D.min(axis=1))))


def _agglomerate(D: np.ndarray, secs: np.ndarray, t_stop: float, max_clusters: int, min_lines: int, min_secs: float) -> List[List[int]]:
    """Average-linkage clustering.  Groups closer than t_stop become one; more than max_clusters are never left; a group that is
    too small to be a person (< min_lines lines AND < min_secs seconds) is folded into the closest other one."""
    n = len(D)
    D = D.astype(np.float64).copy()
    np.fill_diagonal(D, np.inf)
    size = np.ones(n)
    sec = secs.astype(np.float64).copy()
    act = np.ones(n, bool)
    members: List[List[int]] = [[i] for i in range(n)]

    def merge(a: int, b: int) -> None:                       # b into a (Lance-Williams, average linkage)
        newd = (size[a] * D[a] + size[b] * D[b]) / (size[a] + size[b])
        D[a, :] = newd
        D[:, a] = newd
        D[a, a] = np.inf
        D[b, :] = np.inf
        D[:, b] = np.inf
        size[a] += size[b]
        sec[a] += sec[b]
        members[a] += members[b]
        act[b] = False

    while int(act.sum()) > 1:
        k = int(np.argmin(D))
        a, b = divmod(k, n)
        if not np.isfinite(D[a, b]) or (D[a, b] > t_stop and int(act.sum()) <= max_clusters):
            break
        merge(a, b)
    while int(act.sum()) > 1:
        small = [int(i) for i in np.flatnonzero(act) if size[i] < min_lines and sec[i] < min_secs]
        if not small:
            break
        a = min(small, key=lambda i: sec[i])
        row = D[a].copy()
        row[~act] = np.inf
        b = int(np.argmin(row))
        if not np.isfinite(row[b]):
            break
        merge(b, a)
    return [members[int(i)] for i in np.flatnonzero(act)]


@dataclass
class Detection:
    lines: List[dict] = field(default_factory=list)          # one per caption line: {"char": id | None, "gender": "male" | "female" | None, "p": P(woman) | None, "f0": Hz | None}
    characters: List[dict] = field(default_factory=list)     # {"id", "gender", "lines", "seconds", "f0", "p", "ref": [[start, end], ...]}
    duration: float = 0.0                                    # seconds of audio that was looked at
    coverage: float = 0.0                                    # share of the speech time (of the captions) that had a clear voice to measure


def pool_evidence(feats: Sequence[LineFeat]) -> Tuple[Dict[int, float], float]:
    """Line index -> logit that the speaker is a woman, after lines that sound alike have shared what they know.

    One line says little (a short line, a high-pitched man); all the lines of the same voice say a lot."""
    own = {i: _logit(f.p_female) for i, f in enumerate(feats) if f.f0 and f.p_female is not None}
    core = [i for i in own if feats[i].mfcc is not None and feats[i].voiced >= CORE_VOICED]
    if len(core) < 4:
        return dict(own), 1.0
    if len(core) > MAX_POOL:
        core = sorted(sorted(core, key=lambda i: -feats[i].voiced)[:MAX_POOL])
    V = np.stack([_vec(feats[i]) for i in core])
    lf = np.log2(np.array([feats[i].f0 for i in core]))
    w = np.array([min(300, feats[i].voiced) for i in core], np.float64) / 150.0
    ev = np.array([own[i] for i in core])
    D = _dist(V, lf, V, lf)
    s = _scale(D)
    K = np.exp(-(D / (s * POOL_BW)) ** 2)
    np.fill_diagonal(K, 0.0)
    out = {}
    cur = ev
    for _ in range(max(1, POOL_ITER)):
        cur = (K @ (w * cur) + w * ev) / (K @ w + w)      # every pass: the neighbours' current verdict, plus the line's own evidence
    for k, i in enumerate(core):
        out[i] = float(cur[k])
    rest = [i for i in own if i not in out]
    for c0 in range(0, len(rest), 400):
        part = rest[c0: c0 + 400]
        has = [i for i in part if feats[i].mfcc is not None]
        for i in part:
            out[i] = own[i]
        if not has:
            continue
        A = np.stack([_vec(feats[i]) for i in has])
        la = np.log2(np.array([feats[i].f0 for i in has]))
        Kr = np.exp(-(_dist(A, la, V, lf) / (s * POOL_BW)) ** 2)
        wi = np.array([min(300, feats[i].voiced) for i in has], np.float64) / 150.0
        oe = np.array([own[i] for i in has])
        num = Kr @ (w * ev) + wi * oe
        den = Kr @ w + wi
        for k, i in enumerate(has):
            out[i] = float(num[k] / den[k])
    return out, s


def group_lines(feats: Sequence[LineFeat], starts: Sequence[float], ends: Sequence[float]) -> Detection:
    """The answer for a whole video: who (character + gender) speaks every line."""
    n = len(feats)
    det = Detection(lines=[{"char": None, "gender": None, "p": None, "f0": f.f0} for f in feats])
    if n == 0:
        return det
    ev, scale = pool_evidence(feats)
    if not ev:
        return det
    dur = [max(0.0, ends[i] - starts[i]) for i in range(n)]
    measured = sum(dur[i] for i in ev)
    det.coverage = round(measured / max(1e-9, sum(dur)), 3)
    if det.coverage < MIN_COVERAGE or measured < MIN_MEASURED_S:
        return det                                    # music, noise or whispers: better no answer than a coin toss
    gender = {i: ("female" if e > 0 else "male") for i, e in ev.items()}
    # A gender that has only a stray line or two (a high-pitched burst, music that sounds like a voice) is not a second person:
    # those lines follow the gender of the rest of the video.  Real speakers have 3+ lines or 10+ seconds.
    secs_g = {g: sum(dur[i] for i in gender if gender[i] == g) for g in ("male", "female")}
    cnt_g = {g: sum(1 for i in gender if gender[i] == g) for g in ("male", "female")}
    total = secs_g["male"] + secs_g["female"]
    small = min(("male", "female"), key=lambda g: secs_g[g])
    if 0 < cnt_g[small] < MIN_CHAR_LINES and secs_g[small] < MIN_CHAR_SECONDS and secs_g[small] < MINORITY_SHARE * total:
        big = "female" if small == "male" else "male"
        for i in [i for i in gender if gender[i] == small]:
            gender[i] = big
            ev[i] = 0.0                                   # the line's own verdict was overruled: its p is shown as "not sure"
    chars: List[dict] = []
    line_char: Dict[int, int] = {}
    for g in ("male", "female"):
        mine = [i for i in ev if gender[i] == g]
        if not mine:
            continue
        core = [i for i in mine if feats[i].mfcc is not None and feats[i].voiced >= CORE_VOICED]
        if len(core) > MAX_CLUSTER:
            core = sorted(sorted(core, key=lambda i: -feats[i].voiced)[:MAX_CLUSTER])
        groups: List[List[int]]
        if len(core) < 4:
            groups = [list(core)] if core else []
        else:
            V = np.stack([_vec(feats[i]) for i in core])
            lf = np.log2(np.array([feats[i].f0 for i in core]))
            D = _dist(V, lf, V, lf, SPLIT_PITCH_W)
            groups = [[core[k] for k in grp] for grp in _agglomerate(D, np.array([dur[i] for i in core]), SPLIT_C * _scale(D), MAX_PER_GENDER,
                                                                       MIN_CHAR_LINES, MIN_CHAR_SECONDS)]
        if not groups:                                  # nothing to compare with: all the lines of this gender are one character
            groups = [list(mine)]
        base = len(chars)
        for grp in groups:
            chars.append({"gender": g, "members": list(grp)})
            for i in grp:
                line_char[i] = len(chars) - 1
        # the other lines of this gender (little voiced sound): the character they sound most like
        reps = [(ci, np.stack([_vec(feats[i]) for i in chars[ci]["members"]]), np.log2([feats[i].f0 for i in chars[ci]["members"]])) for ci in range(base, len(chars))]
        for i in mine:
            if i in line_char:
                continue
            best = base
            if feats[i].mfcc is not None and len(reps) > 1:
                v = _vec(feats[i])[None, :]
                bd = 1e9
                for ci, Vc, lc in reps:
                    d = np.sort(_dist(v, np.array([math.log2(feats[i].f0)]), Vc, np.asarray(lc), SPLIT_PITCH_W)[0])[:5]
                    if float(d.mean()) < bd:
                        best, bd = ci, float(d.mean())
            elif len(reps) > 1:
                best = max(range(base, len(chars)), key=lambda ci: sum(dur[j] for j in chars[ci]["members"]))
            chars[best]["members"].append(i)
            line_char[i] = best
    # A voice right on the boundary (a low woman, a high man) is found as one "man" and one "woman": when both are unsure about their
    # gender and sound alike, they are one person - the gender is then decided by all their lines together.
    def char_e(c: dict) -> float:
        own = [i for i in c["members"] if i in ev]
        ww = np.array([min(300, feats[i].voiced) for i in own], np.float64)
        return float((ww * np.array([ev[i] for i in own])).sum() / max(1e-9, ww.sum())) if own else 0.0

    def char_vec(c: dict):
        ids = [i for i in c["members"] if feats[i].mfcc is not None and feats[i].f0 and feats[i].voiced >= CORE_VOICED][:60]
        if not ids:
            return None
        return np.stack([_vec(feats[i]) for i in ids]), np.log2([feats[i].f0 for i in ids])

    merged = True
    while merged and len(chars) > 1:
        merged = False
        cand = []
        for a, ca in enumerate(chars):
            for b, cb in enumerate(chars):
                if a < b and ca["gender"] != cb["gender"] and abs(char_e(ca)) < GREY and abs(char_e(cb)) < GREY:
                    va, vb = char_vec(ca), char_vec(cb)
                    if va is not None and vb is not None:
                        cand.append((float(_dist(va[0], va[1], vb[0], vb[1], SPLIT_PITCH_W).mean()), a, b))
        if cand:
            d, a, b = min(cand)
            if d < GREY_MERGE_C * scale:
                keep, drop = (a, b) if len(chars[a]["members"]) >= len(chars[b]["members"]) else (b, a)
                chars[keep]["members"] += chars[drop]["members"]
                chars[keep]["gender"] = "female" if char_e(chars[keep]) > 0 else "male"
                for i in chars[keep]["members"]:
                    if i in ev:
                        gender[i] = chars[keep]["gender"]
                chars.pop(drop)
                merged = True
    line_char = {i: ci for ci, c in enumerate(chars) for i in c["members"]}
    # lines with no usable sound at all (music, a cough, one word): the neighbour in time (the line before, else after), else the main character
    main = max(range(len(chars)), key=lambda ci: sum(dur[i] for i in chars[ci]["members"]))
    for i in range(n):
        if i in line_char:
            continue
        pick = None
        for j in range(i - 1, -1, -1):
            if starts[i] - ends[j] > NEIGHBOUR_S:
                break
            if j in line_char:
                pick = line_char[j]
                break
        if pick is None:
            for j in range(i + 1, n):
                if starts[j] - ends[i] > NEIGHBOUR_S:
                    break
                if j in line_char:
                    pick = line_char[j]
                    break
        line_char[i] = main if pick is None else pick
        chars[line_char[i]]["members"].append(i)
        chars[line_char[i]].setdefault("guess", []).append(i)
    # number the characters in order of appearance and fill in the answer
    order = sorted(range(len(chars)), key=lambda ci: min(starts[i] for i in chars[ci]["members"]))
    for newid, ci in enumerate(order, start=1):
        c = chars[ci]
        mem = sorted(c["members"])
        own = [i for i in mem if feats[i].f0]
        ww = np.array([min(300, feats[i].voiced) for i in own], np.float64)
        e = float((ww * np.array([ev[i] for i in own])).sum() / max(1e-9, ww.sum())) if own else 0.0
        f0 = float(np.median([feats[i].f0 for i in own])) if own else None
        p = 1.0 / (1.0 + math.exp(-e))
        # the lines that make the best voice reference: clear, long, loud
        best = sorted([i for i in own if feats[i].voiced >= 60 and dur[i] >= 1.2], key=lambda i: -(feats[i].quality * min(1.0, dur[i] / 6.0)))
        ref: List[List[float]] = []
        tot = 0.0
        for i in best:
            ref.append([round(starts[i], 2), round(ends[i], 2)])
            tot += dur[i]
            if tot >= 14.0 or len(ref) >= 6:
                break
        ref.sort()
        c["out"] = {"id": newid, "gender": c["gender"], "lines": len(mem), "seconds": round(sum(dur[i] for i in mem), 1),
                    "f0": round(f0, 1) if f0 else None, "p": round(p, 3), "ref": ref}
        for i in mem:
            det.lines[i]["char"] = newid
            det.lines[i]["gender"] = c["gender"]
            det.lines[i]["p"] = round(1.0 / (1.0 + math.exp(-ev[i])), 3) if i in ev else round(p, 3)
    det.characters = [chars[ci]["out"] for ci in order]
    return det


# --------------------------------------------------------------------------- #
# the entry points
# --------------------------------------------------------------------------- #
PAD_S = 0.05                     # a little sound before / after a caption: captions are rarely cut exactly at the voice
MIN_LOOK_S = 0.5                 # a line shorter than this (after the padding) is not analysed


def analyze(path: str | Path, starts: Sequence[float], ends: Sequence[float], progress: Optional[Callable[[float], None]] = None,
            check: Optional[Callable[[], None]] = None) -> Detection:
    """Listen to `path` (a video or audio file) and say who speaks every line [starts[i], ends[i]].

    `check` is called now and then and may raise to stop (the job's cancel button); `progress` gets 0..1."""
    pcm = load_pcm(path)
    n = len(starts)
    feats: List[LineFeat] = []
    for i in range(n):
        if check and i % 6 == 0:
            check()
        a = max(0, int((float(starts[i]) - PAD_S) * SR))
        b = min(len(pcm), int((float(ends[i]) + PAD_S) * SR))
        if (b - a) / SR < MIN_LOOK_S or b - a < WIN + TAU_MAX + HOP:
            feats.append(LineFeat())
        else:
            f0, conf, rms, mfcc = pitch_frames(_f32(pcm[a:b]))
            feats.append(line_feature(f0, conf, rms, mfcc))
        if progress and (i % 8 == 0 or i == n - 1):
            progress((i + 1) / max(1, n))
    det = group_lines(feats, [float(x) for x in starts], [float(x) for x in ends])
    det.duration = len(pcm) / SR
    return det


def gender_of_clip(path: str | Path) -> Optional[dict]:
    """A short voice sample -> {"gender": "Female" | "Male", "p": P(woman), "f0": Hz, "sure": bool}; None when there is no clear voice in it."""
    x = _f32(load_pcm(path))
    ft = line_feature(*pitch_frames(x))
    if ft.f0 is None or ft.p_female is None:
        return None
    p = float(ft.p_female)
    return {"gender": "Female" if p >= 0.5 else "Male", "p": round(p, 3), "f0": round(float(ft.f0), 1), "sure": p >= SURE or p <= 1.0 - SURE}
