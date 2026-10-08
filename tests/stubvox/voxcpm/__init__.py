"""Stand-in for the real `voxcpm` package (the real model needs ~8 GB RAM / a GPU; the sandbox has neither).

It imitates the parts of the API that app/vox_worker.py uses and makes the audio depend on exactly the things
that identify a voice, so tests can tell voices apart by their pitch:

* voice DESIGN  - the text starts with "(style)":   pitch = f(style) + f(random seed)       (like a new random person)
* voice CLONING - reference_wav_path is given:       pitch = f(bytes of the reference clip)  (the same clip -> the same voice)
* neither:                                           pitch = fixed
The length of the audio is proportional to the number of characters (0.07 s each).
"""
import hashlib
import re
import time

import numpy as np


class _TTS:
    sample_rate = 48000
    device = "cpu"


def _h(data: bytes, mod: int) -> int:
    return int(hashlib.sha1(data).hexdigest()[:8], 16) % mod


class VoxCPM:
    def __init__(self):
        self.tts_model = _TTS()
        self.calls = []

    @classmethod
    def from_pretrained(cls, model_id, **kw):
        time.sleep(0.3)
        return cls()

    def _generate(self, text, **kw):  # no `seed` parameter, like voxcpm 2.0.3
        raise NotImplementedError

    def generate(self, text, cfg_value=2.0, inference_timesteps=10, reference_wav_path=None, **kw):
        style = None
        m = re.match(r"^\((.*?)\)(.*)$", text, re.S)
        if m:
            style, text = m.group(1), m.group(2)
        if reference_wav_path:
            with open(reference_wav_path, "rb") as fh:
                data = fh.read()
            freq = 160 + _h(data, 120) * 7
        elif style:
            freq = 160 + _h(style.encode(), 60) * 14 + int(np.random.randint(0, 14)) * 1.0 + 3.0 * int(np.random.randint(0, 4))
        else:
            freq = 300.0
        n = max(1, int(round(len(text) * 0.07 * 48000)))
        t = np.arange(n) / 48000.0
        env = 0.65 + 0.35 * np.sin(2 * np.pi * 2.5 * t)
        wav = (0.35 * np.sin(2 * np.pi * freq * t) * env).astype(np.float32)
        self.calls.append((style, reference_wav_path, len(text)))
        time.sleep(0.02)
        return wav
