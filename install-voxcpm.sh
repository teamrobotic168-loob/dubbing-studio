#!/bin/sh
# Install the optional VoxCPM2 engine (more voices + voice cloning) from the command line.
# Same as Settings -> VoxCPM2 -> Install in the dashboard.   Needs ~10 GB of disk space.
# Apple Silicon Macs (M1 and newer) use the Mac's GPU; Intel Macs are not supported by PyTorch any more.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Run start.sh once first (on a Mac: double-click start.command) - it creates the .venv." >&2
  exit 1
fi
exec .venv/bin/python -m app.vox_setup "$@"
