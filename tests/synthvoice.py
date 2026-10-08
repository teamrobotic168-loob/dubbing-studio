"""A tiny deterministic 'speaker' for the tests of voices by character (not part of the product).

A glottal harmonic source (the pitch F0, a little vibrato) shaped by three moving formants (scale > 1 = a shorter vocal tract: women,
children), with syllables and pauses - numpy only, so the tests need no recordings and no network.  The same arguments always give the
same sound; another `seed` is another sentence of the same speaker."""
import numpy as np

SR = 16000


def voice(f0, scale, dur, seed=0, sr=SR, snr_db=35.0, pauses=True):
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    t = np.arange(n) / sr
    ph0 = rng.uniform(0, 6.28, 6)
    contour = f0 * (1 + 0.07 * np.sin(2 * np.pi * 0.55 * t + ph0[0]) + 0.035 * np.sin(2 * np.pi * 2.3 * t + ph0[1]) + 0.01 * np.sin(2 * np.pi * 5.7 * t + ph0[2]))
    phase = 2 * np.pi * np.cumsum(contour) / sr
    f1 = 560 * scale * (1 + 0.32 * np.sin(2 * np.pi * 1.7 * t + ph0[3]))
    f2 = 1500 * scale * (1 + 0.28 * np.sin(2 * np.pi * 1.1 * t + ph0[4]))
    f3 = 2550 * scale * np.ones(n)
    out = np.zeros(n)
    hmax = int(min(48, 5000 / f0))
    for h in range(1, hmax + 1):
        fh = h * contour
        env = np.exp(-((fh - f1) / (110 * scale)) ** 2) * 1.0 + np.exp(-((fh - f2) / (190 * scale)) ** 2) * 0.55 + np.exp(-((fh - f3) / (260 * scale)) ** 2) * 0.3
        out += (env + 0.04) * np.sin(h * phase) / (h ** 0.6)
    am = 0.55 + 0.45 * np.sin(2 * np.pi * 3.6 * t + ph0[5]) ** 2
    if pauses:
        gate = np.ones(n)
        for k in range(1, int(dur / 1.6) + 1):
            a = int((k * 1.6 - 0.15) * sr)
            gate[a: a + int(0.18 * sr)] = 0.0
        am = am * np.convolve(gate, np.ones(200) / 200, mode="same")
    out = out * am
    out /= max(1e-9, np.abs(out).max())
    out *= 0.5
    noise = rng.standard_normal(n)
    out = out + noise * (np.sqrt(np.mean(out ** 2)) / (10 ** (snr_db / 20)))
    return out.astype(np.float32)
