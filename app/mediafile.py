"""Sending a media file (audio / video) to the browser WITHOUT keeping it open.

Why this exists (v1.13.0):  Starlette's FileResponse keeps the file open for as long as the browser takes to read the response, and a
browser that has a <video> in the page leaves its request half-read for minutes.  On macOS and Linux that does no harm.  On WINDOWS an
open file can neither be deleted nor replaced ("PermissionError: [WinError 32] The process cannot access the file because it is being
used by another process"), so "Regenerate" of a job whose MP4 was open in the page failed with "Internal error".

Here the file is opened for ONE chunk (256 KB) and closed again at once, so between two chunks nothing is open - however slowly the
browser reads.  Range requests (seeking in a video) work like in FileResponse; a file that is replaced while it is being sent ends the
response early instead of sending a mixture of the old and the new file (the browser asks again).
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from email.utils import formatdate
from typing import List, Mapping, Optional, Tuple
from urllib.parse import quote

import anyio
import anyio.to_thread
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import Receive, Scope, Send

CHUNK = 256 * 1024
_SPEC = re.compile(r"\s*(\d*)\s*-\s*(\d*)\s*")


class RangeNotSatisfiable(Exception):
    """The asked range starts behind the end of the file (answer: 416)."""


def parse_range(header: str, size: int) -> Optional[Tuple[int, int]]:
    """The `Range` header -> (first, last) byte, both included.

    None = no usable single range (another unit, several ranges, nonsense): the whole file is sent, which is always allowed.
    RangeNotSatisfiable = the range lies behind the end of the file."""
    unit, _, spec = (header or "").partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None
    m = _SPEC.fullmatch(spec)
    if not m or (m.group(1) == "" and m.group(2) == ""):
        return None
    a, b = m.groups()
    if a == "":                                              # "-500": the last 500 bytes
        n = int(b)
        if n == 0 or size == 0:
            raise RangeNotSatisfiable()
        return max(0, size - n), size - 1
    first = int(a)
    last = int(b) if b != "" else size - 1
    if b != "" and last < first:                             # nonsense ("5-2"): ignored, the whole file is sent
        return None
    if first >= size:
        raise RangeNotSatisfiable()
    return first, min(last, size - 1)


def _read_at(path: str, pos: int, n: int, ident: List[Optional[int]]) -> bytes:
    """n bytes at `pos`; the file is open only inside this call.  b'' = the end, or the file was replaced / deleted meanwhile.
    ident = [size, modified time]: the size is the one that was announced; the time is taken from the FIRST chunk (fstat both times, so
    it is the same kind of number) and every later chunk must still see it."""
    try:
        with open(path, "rb") as f:
            st = os.fstat(f.fileno())
            if st.st_size != ident[0]:
                return b""
            if ident[1] is None:
                ident[1] = st.st_mtime_ns
            elif st.st_mtime_ns != ident[1]:
                return b""
            f.seek(pos)
            return f.read(n)
    except OSError:
        return b""


class MediaFile(Response):
    """A drop-in for FileResponse for audio / video (Range requests, download name, extra headers) that never holds the file open."""

    def __init__(self, path, media_type: Optional[str] = None, headers: Optional[Mapping[str, str]] = None, filename: Optional[str] = None,
                 content_disposition_type: str = "attachment") -> None:
        super().__init__(None, 200, headers, media_type)
        self.path = os.fspath(path)
        self.filename = filename
        del self.headers["content-length"]                     # the length depends on the range: set for every request
        self.headers.setdefault("accept-ranges", "bytes")
        if filename is not None:                               # the same rule as FileResponse (non-ASCII names -> RFC 5987)
            q = quote(filename)
            self.headers.setdefault("content-disposition", f"{content_disposition_type}; filename*=utf-8''{q}" if q != filename
                                    else f'{content_disposition_type}; filename="{filename}"')

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return
        try:
            st = await anyio.to_thread.run_sync(os.stat, self.path)
            if not stat.S_ISREG(st.st_mode):
                raise FileNotFoundError(self.path)
        except OSError:
            await PlainTextResponse("File is missing on disk.", status_code=404)(scope, receive, send)
            return
        size = st.st_size
        last_modified = formatdate(st.st_mtime, usegmt=True)
        etag = '"' + hashlib.md5(f"{st.st_mtime}-{size}".encode(), usedforsecurity=False).hexdigest() + '"'
        asked = Headers(scope=scope)
        rng = None
        if asked.get("range") and asked.get("if-range") in (None, etag, last_modified):          # If-Range: the file is still the one the browser has
            try:
                rng = parse_range(asked["range"], size)
            except RangeNotSatisfiable:
                await PlainTextResponse("", status_code=416, headers={"Content-Range": f"bytes */{size}"})(scope, receive, send)
                return
        h = MutableHeaders(raw=list(self.raw_headers))
        h.setdefault("last-modified", last_modified)
        h.setdefault("etag", etag)
        if rng is None:
            first, last, status = 0, size - 1, 200
        else:
            first, last, status = rng[0], rng[1], 206
            h["content-range"] = f"bytes {first}-{last}/{size}"
        length = max(0, last - first + 1)
        h["content-length"] = str(length)
        await send({"type": "http.response.start", "status": status, "headers": h.raw})
        if scope["method"].upper() == "HEAD" or length == 0:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return

        ident: List[Optional[int]] = [size, None]
        async with anyio.create_task_group() as tg:
            async def watch() -> None:                                   # the browser went away: stop reading the file
                while True:
                    if (await receive())["type"] == "http.disconnect":
                        tg.cancel_scope.cancel()
                        return

            tg.start_soon(watch)
            pos, left = first, length
            while left > 0:
                chunk = await anyio.to_thread.run_sync(_read_at, self.path, pos, min(CHUNK, left), ident)
                if not chunk:
                    break
                pos += len(chunk)
                left -= len(chunk)
                await send({"type": "http.response.body", "body": chunk, "more_body": left > 0})
            if left > 0:                                                  # the file changed under us: end here (shorter than announced)
                await send({"type": "http.response.body", "body": b"", "more_body": False})
            tg.cancel_scope.cancel()
