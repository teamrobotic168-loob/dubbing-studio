#!/bin/sh
# Runs the test-suites one after another (about 15 minutes for all of them).
#
#   sh tests/run_all.sh                       every suite (the same order as the release checklist)
#   sh tests/run_all.sh test_units test_api   only these
#
# Start it in the BACKGROUND and look at the summary now and then (an AI agent: nohup ... & and poll):
#   nohup sh tests/run_all.sh > /dev/null 2>&1 &
#   cat "${KDS_TEST_WORK:-${TMPDIR:-/tmp}/kds-tests}/final_summary.log"
#
# Do NOT edit app/, static/ or tests/ while it runs: every suite reads its file when it starts.
# Logs: $KDS_TEST_WORK/final_<suite>.log   (default KDS_TEST_WORK = <temp dir>/kds-tests)
# Set PYTHON=/path/to/python3 to use another interpreter (for example the one of your .venv).

HERE=$(cd "$(dirname "$0")" && pwd) || exit 1
PROJECT=$(dirname "$HERE")
KDS_TEST_WORK=${KDS_TEST_WORK:-${TMPDIR:-/tmp}/kds-tests}
export KDS_TEST_WORK
mkdir -p "$KDS_TEST_WORK" || exit 1
PY=${PYTHON:-python3}
SUMMARY="$KDS_TEST_WORK/final_summary.log"
: > "$SUMMARY"

SUITES=${*:-"test_units test_core test_api test_ui test_follow test_clickplay test_layout test_claude test_voices test_speakers test_winlock test_upload test_tiktok test_hardsub test_pwa test_platform test_youtube"}
if command -v timeout >/dev/null 2>&1; then LIMIT="timeout 1500"; else LIMIT=""; fi   # macOS has no `timeout` unless coreutils is installed

# 0) static check of the Python code with pyflakes: undefined names, syntax errors, wrong f-strings ... (runs in a second).
#    "imported but unused" is left out on purpose: a few old modules still have harmless leftovers (see DEVELOPMENT.md, backlog).
if "$PY" -m pyflakes --version >/dev/null 2>&1; then
  ( cd "$PROJECT" && "$PY" -m pyflakes app server.py tools tests/lib.py 2>&1 | grep -v "imported but unused" > "$KDS_TEST_WORK/final_lint.log" )
  if [ -s "$KDS_TEST_WORK/final_lint.log" ]; then lrc=1; else lrc=0; fi
  echo "lint exit $lrc  $(wc -l < "$KDS_TEST_WORK/final_lint.log" | tr -d ' ') finding(s)" >> "$SUMMARY"
else
  echo "lint skipped (pip install pyflakes)" >> "$SUMMARY"
fi

cd "$HERE" || exit 1
for t in $SUITES; do
  start=$(date +%s)
  $LIMIT "$PY" "$t.py" > "$KDS_TEST_WORK/final_$t.log" 2>&1
  rc=$?
  echo "$t exit $rc  ($(( $(date +%s) - start )) s)  $(grep -h '^== ' "$KDS_TEST_WORK/final_$t.log" | tail -1)" >> "$SUMMARY"
done
echo ALLDONE >> "$SUMMARY"
