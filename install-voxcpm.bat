@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Install VoxCPM2
if not exist ".venv\Scripts\python.exe" (
  echo Run start.bat once first ^(it creates the .venv^).
  pause
  exit /b 1
)
echo Installing VoxCPM2 (about 10 GB, 10-30 minutes). You can also do this in the dashboard: Settings - VoxCPM2.
echo.
".venv\Scripts\python.exe" -m app.vox_setup %*
echo.
pause
