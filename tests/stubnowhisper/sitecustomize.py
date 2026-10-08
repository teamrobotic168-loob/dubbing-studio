"""Test helper: makes `faster_whisper` look "not installed" in the server process, unless a folder `faster_whisper` exists next to this
file (the fake pip command of the tests copies the fake package there - that is how "Install Whisper" succeeds without the Internet)."""
import os
import sys
from importlib.abc import MetaPathFinder

HERE = os.path.dirname(os.path.abspath(__file__))


class _Block(MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if (name == "faster_whisper" or name.startswith("faster_whisper.")) and not os.path.isdir(os.path.join(HERE, "faster_whisper")):
            raise ModuleNotFoundError("faster-whisper is 'not installed' (test)")
        return None


sys.meta_path.insert(0, _Block())
