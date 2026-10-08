#!/usr/bin/env python3
"""Change the version of V_Heang Studio in the four places that must always agree.

    python tools/bump_version.py 1.9.2        edit the four places
    python tools/bump_version.py --check      only verify that they agree (exit code 1 when they do not)

The four places (the server compares them at start-up: /api/health says "ui_ok": false and the page shows a red banner when they differ):

    app/__init__.py          __version__ = "X"
    static/index.html        <meta name="kds-ui" content="X">
    static/js/app.js         const KDS_UI_VERSION = 'X';
    static/js/i18n.js        window.I18N_VERSION = 'X';

The tests read the version from app/__init__.py, so they need no edit.  Still to do by hand after a bump: a CHANGELOG.md entry (on top) and the
"new in" line of README.md.  Standard library only; keeps the line endings of the files.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = [
    ("app/__init__.py", r'(__version__\s*=\s*")([^"]+)(")'),
    ("static/index.html", r'(name="kds-ui"\s+content=")([^"]+)(")'),
    ("static/js/app.js", r"(KDS_UI_VERSION\s*=\s*')([^']+)(')"),
    ("static/js/i18n.js", r"(I18N_VERSION\s*=\s*')([^']+)(')"),
]


def read(rel: str) -> str:
    return (ROOT / rel).read_bytes().decode("utf-8")        # bytes: a CRLF file stays CRLF


def versions() -> dict:
    out = {}
    for rel, rx in PLACES:
        m = re.search(rx, read(rel)[:8000])
        out[rel] = m.group(2) if m else None
    return out


def main(argv) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    cur = versions()
    if argv[0] == "--check":
        for rel, v in cur.items():
            print(f"  {rel:<22} {v}")
        ok = len(set(cur.values())) == 1 and None not in cur.values()
        print(("OK: all four places say " + next(iter(cur.values()))) if ok else "MISMATCH: the four places do not agree")
        return 0 if ok else 1
    new = argv[0].lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        print(f"not a version number: {argv[0]!r}  (use MAJOR.MINOR.PATCH, e.g. 1.9.2)")
        return 2
    for rel, rx in PLACES:
        s = read(rel)
        s2, n = re.subn(rx, lambda m: m.group(1) + new + m.group(3), s, count=1)
        if n != 1:
            print(f"cannot find the version in {rel}")
            return 1
        (ROOT / rel).write_bytes(s2.encode("utf-8"))
    after = versions()
    ok = set(after.values()) == {new}
    print(f"{set(cur.values())} -> {new}: " + ("OK, all four places changed" if ok else f"FAILED {after}"))
    if ok:
        print("Next: add a CHANGELOG.md entry, update README.md, run the tests (sh tests/run_all.sh), then  python tools/build_zip.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
