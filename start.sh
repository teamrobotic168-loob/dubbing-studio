#!/bin/sh
# V_Heang Studio launcher for macOS and Linux  (Windows: start.bat)
#
#   sh start.sh            start the dashboard      (also: ./start.sh ;  on a Mac you can double-click start.command)
#   sh start.sh update     first upgrade yt-dlp / youtube-transcript-api / edge-tts
#
# It needs Python 3.10 or newer.  KDS_DRY_RUN=1 only reports the Python it would use, KDS_PY_FALLBACKS (a list of paths)
# replaces the built-in list of places where the Mac installers put Python - both are for the tests.
cd "$(dirname "$0")" || exit 1

OS="$(uname -s 2>/dev/null || echo unknown)"
chmod +x start.sh start.command install-voxcpm.sh install-voxcpm.command >/dev/null 2>&1 || true

# ---- Python 3.10 or newer ------------------------------------------------------------------------------------------
is_ok_python() {                       # $1 = a command or a path
  [ -n "$1" ] || return 1
  # /usr/bin/python3 on a Mac without the developer tools is only a stub that opens an installer pop-up
  if [ "$OS" = "Darwin" ] && [ "$1" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then
    return 1
  fi
  "$1" -c 'import sys, venv; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

find_python() {
  for name in python3 python3.13 python3.12 python3.11 python3.10 python; do
    cand="$(command -v "$name" 2>/dev/null)" || continue
    if is_ok_python "$cand"; then PY="$cand"; return 0; fi
  done
  # where the Mac installers put Python (a double-clicked script does not always see them on its PATH)
  for cand in $FALLBACKS; do
    if [ -x "$cand" ] && is_ok_python "$cand"; then PY="$cand"; return 0; fi
  done
  return 1
}

FALLBACKS="${KDS_PY_FALLBACKS-/opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 /usr/bin/python3}"

PY=""
if ! find_python; then
  echo
  echo "  Python 3.10 or newer is required, and it was not found."
  if [ "$OS" = "Darwin" ]; then
    echo "  On a Mac the easiest way:"
    echo "    - download the macOS installer from https://www.python.org/downloads/macos/ and open it, or"
    echo "    - with Homebrew:   brew install python@3.12"
    echo "  (the 'python3' that comes with macOS is too old or is only a stub)"
  else
    echo "  Install it with your package manager (for example: sudo apt install python3 python3-venv)"
    echo "  or from https://www.python.org/downloads/"
  fi
  echo "  Then run this again."
  echo
  exit 1
fi
if [ -n "$KDS_DRY_RUN" ]; then
  echo "PYTHON=$PY"
  exit 0
fi

# ---- virtual environment -----------------------------------------------------------------------------------------
VPY=".venv/bin/python"
if [ -d .venv ] && ! "$VPY" -c 'import sys' >/dev/null 2>&1; then
  echo "The virtual environment in .venv does not work any more (Python was removed or updated) - making a new one ..."
  rm -rf .venv
fi
if [ ! -x "$VPY" ]; then
  if [ "$OS" = "Darwin" ]; then
    # files from a download carry a 'quarantine' flag; remove it once so that the other .command files open without a warning
    xattr -dr com.apple.quarantine . >/dev/null 2>&1 || true
  fi
  echo "[1/3] Creating the virtual environment (Python $("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')) ..."
  if ! "$PY" -m venv .venv; then
    rm -rf .venv
    echo
    echo "  Could not create the virtual environment."
    if [ "$OS" = "Darwin" ]; then
      echo "  Try the Python installer from https://www.python.org/downloads/macos/ ."
    else
      echo "  On Ubuntu / Debian:  sudo apt install python3-venv"
    fi
    echo
    exit 1
  fi
fi

echo "[2/3] Checking packages (the first time takes 1-3 minutes) ..."
if ! "$VPY" -m pip install --disable-pip-version-check -q -r requirements.txt; then
  echo
  echo "  Package installation failed. Check your Internet connection and run this again."
  echo
  exit 1
fi

if [ "${1:-}" = "update" ]; then
  echo "Updating yt-dlp / youtube-transcript-api / edge-tts ..."
  "$VPY" -m pip install --disable-pip-version-check -q -U yt-dlp youtube-transcript-api edge-tts
fi

echo "[3/3] Starting V_Heang Studio - your browser opens by itself (Ctrl+C stops it)"
exec "$VPY" server.py
