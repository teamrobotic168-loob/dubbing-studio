"""Test helper: makes Python on Linux / macOS behave like Python on WINDOWS in the ONE way that matters for the dashboard:
a file that some code still has OPEN cannot be deleted, renamed or replaced ("PermissionError: [WinError 32] The process cannot
access the file because it is being used by another process").

On Windows a browser that is still reading `dubbed.mp4` (a <video> in the page: the server keeps the file open for as long as the
browser leaves the request half-read) therefore blocked "Regenerate" with "Internal error".  macOS and Linux never do that, so the
bug could not be seen in the sandbox; with this file (PYTHONPATH + KDS_WINLOCK_SIM=1) the server process behaves like Windows.

Only READ handles of files that are opened with io.open / open() / Path.open() / anyio.open_file are counted - that is what serves a
file to the browser (Starlette's FileResponse).  Two more settings:
  KDS_WINLOCK_LOG=<file>   appends one line for every refused delete / replace ("unlink dubbed.mp4")
  KDS_WINLOCK_FILE=<file>  a program OUTSIDE this process (a video player, an antivirus scan) holds the files whose names are listed in
                           that text file, one per line - the test edits the list while the server runs.
Nothing here is part of the product: tests/ may be deleted.
"""
import errno
import io
import os
import threading

if os.environ.get("KDS_WINLOCK_SIM") == "1":
    _guard = threading.Lock()
    _open: dict = {}                                    # real path -> number of open read handles
    _log = os.environ.get("KDS_WINLOCK_LOG") or ""
    _extern = os.environ.get("KDS_WINLOCK_FILE") or ""
    _io_open = io.open
    _unlink, _remove, _replace, _rename = os.unlink, os.remove, os.replace, os.rename

    def _key(p):
        try:
            return os.path.realpath(os.fsdecode(os.fspath(p)))
        except Exception:
            return None

    def _bump(key, d):
        with _guard:
            n = _open.get(key, 0) + d
            if n > 0:
                _open[key] = n
            else:
                _open.pop(key, None)

    class _Reader(io.BufferedReader):
        def __init__(self, raw, key):
            super().__init__(raw)
            self._winkey, self._counted = key, True
            _bump(key, 1)

        def close(self):
            try:
                if getattr(self, "_counted", False):
                    self._counted = False
                    _bump(self._winkey, -1)
            finally:
                super().close()

    def _open_read(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        if (mode in ("rb", "br") and buffering == -1 and encoding is None and errors is None and newline is None and closefd is True
                and opener is None and isinstance(file, (str, bytes, os.PathLike))):
            key = _key(file)
            if key:
                return _Reader(io.FileIO(file, "r"), key)
        return _io_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    def _refuse(path, what):
        e = PermissionError(errno.EACCES, "[WinError 32] The process cannot access the file because it is being used by another process", os.fspath(path))
        if _log:
            try:
                with _io_open(_log, "a", encoding="utf-8") as f:
                    f.write(f"{what} {os.path.basename(os.fsdecode(os.fspath(path)))}\n")
            except OSError:
                pass
        raise e

    def _held_outside(k):
        if not _extern:
            return False
        try:
            with _io_open(_extern, "r", encoding="utf-8") as f:
                return os.path.basename(k) in {x.strip() for x in f if x.strip()}
        except OSError:
            return False

    def _busy(p):
        k = _key(p)
        return bool(k) and (_open.get(k, 0) > 0 or _held_outside(k))

    def _wrap1(fn, what):
        def f(path, *a, **kw):
            if kw.get("dir_fd") is None and isinstance(path, (str, bytes, os.PathLike)) and _busy(path):
                _refuse(path, what)
            return fn(path, *a, **kw)
        return f

    def _wrap2(fn, what):
        def f(src, dst, *a, **kw):
            for p in (src, dst):
                if kw.get("src_dir_fd") is None and kw.get("dst_dir_fd") is None and isinstance(p, (str, bytes, os.PathLike)) and _busy(p):
                    _refuse(p, what)
            return fn(src, dst, *a, **kw)
        return f

    io.open = _open_read
    import builtins
    builtins.open = _open_read
    os.unlink, os.remove = _wrap1(_unlink, "unlink"), _wrap1(_remove, "unlink")
    os.replace, os.rename = _wrap2(_replace, "replace"), _wrap2(_rename, "rename")

    def open_handles(name=None):
        """For a test in THIS process: how many read handles are open (of the files whose name ends with `name`)."""
        with _guard:
            return sum(n for k, n in _open.items() if name is None or k.endswith(name))
