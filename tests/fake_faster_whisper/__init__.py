"""A tiny stand-in for faster-whisper (tests only): every file 'contains' the same three English sentences."""


class _Seg:
    def __init__(self, start, end, text):
        self.start, self.end, self.text = start, end, text


class _Info:
    language = "en"
    language_probability = 0.99


class WhisperModel:
    def __init__(self, size, *a, **k):
        self.size = size

    def transcribe(self, pcm, language=None, **k):
        dur = len(pcm) / 16000.0
        lines = ["Welcome to this tutorial about the API.", "We will build a Dashboard with Python.", "Thank you for watching."]
        step = max(1.0, dur / len(lines))
        segs = [_Seg(i * step, min(dur, i * step + step - 0.2), t) for i, t in enumerate(lines)]
        return iter(segs), _Info()
