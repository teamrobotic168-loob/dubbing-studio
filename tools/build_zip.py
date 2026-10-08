#!/usr/bin/env python3
"""Build  khmer-dubbing-studio-v<version>.zip  next to the project folder.  Standard library only (Windows, macOS and Linux).

    python tools/build_zip.py [--out DIR]          DIR defaults to the folder that contains the project

What it guarantees (this is why the zip is built by a script and not by hand):

* one top-level folder, "khmer-dubbing-studio/";
* the launchers (start.sh, start.command, install-voxcpm.sh, install-voxcpm.command, tests/run_all.sh) are stored EXECUTABLE (0755) - a
  double-click on a Mac needs it - everything else 0644 (the zip says "made on Unix", so unzip and the macOS Archive Utility keep the modes);
* it REFUSES to build when a line ending is wrong (.bat must be CRLF; .sh / .command must be LF) or the four version places disagree;
* left out: data/ (the user's jobs and caches), .venv/, __pycache__/, *.pyc, .DS_Store, .git/, other zips, tests/.work.

Then:   python tests/smoke_zip.py        (unpacks the zip, starts it, dubs a sample, checks the modes and line endings)
"""
import argparse
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOP = "khmer-dubbing-studio"
EXECUTABLE = {"start.sh", "start.command", "install-voxcpm.sh", "install-voxcpm.command", "tests/run_all.sh"}
SKIP_DIRS = {".venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".work", ".idea", ".vscode"}      # (plus the top-level data/ folder)
SKIP_SUFFIX = (".pyc", ".zip", ".DS_Store", ".swp")
CRLF_FILES = {"start.bat", "install-voxcpm.bat"}


def files():
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if not p.is_file() or any(part in SKIP_DIRS for part in rel.parts[:-1]) or p.name.endswith(SKIP_SUFFIX) or rel.parts[0] == "data":
            continue
        yield p, rel.as_posix()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT.parent), help="folder for the zip (default: next to the project folder)")
    out_dir = Path(ap.parse_args().out).resolve()

    chk = subprocess.run([sys.executable, str(ROOT / "tools" / "bump_version.py"), "--check"], capture_output=True, text=True)
    if chk.returncode != 0:
        print(chk.stdout + chk.stderr)
        return 1
    version = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")).group(1)

    entries, problems = [], []
    for p, rel in files():
        raw = p.read_bytes()
        if rel in CRLF_FILES and raw.count(b"\r\n") != raw.count(b"\n"):
            problems.append(f"{rel}: must have Windows line endings (CRLF) - a .bat file with LF breaks")
        if rel in EXECUTABLE and b"\r" in raw:
            problems.append(f"{rel}: must have Unix line endings (LF) - a CR makes 'sh' fail")
        if rel.endswith((".sh", ".command")) and rel not in EXECUTABLE:
            problems.append(f"{rel}: a shell script that is not in EXECUTABLE (add it in tools/build_zip.py)")
        entries.append((rel, raw, p.stat().st_mtime))
    names = {e[0] for e in entries}
    for must in EXECUTABLE | CRLF_FILES | {"server.py", "requirements.txt", "app/main.py", "static/index.html"}:
        if must not in names:
            problems.append(f"{must}: missing")
    if problems:
        print("NOT BUILT:\n  " + "\n  ".join(problems))
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"khmer-dubbing-studio-v{version}.zip"
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, raw, mtime in entries:
            zi = zipfile.ZipInfo(f"{TOP}/{rel}", date_time=time.localtime(max(mtime, 315532800))[:6])
            zi.create_system = 3                                                    # Unix: the mode below is honoured
            zi.external_attr = ((0o100755 if rel in EXECUTABLE else 0o100644) << 16)
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, raw)
    print(f"{target}  {target.stat().st_size:,} bytes, {len(entries)} files, version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
