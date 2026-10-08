@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title V_Heang Studio
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem ---- find Python 3.10+ -------------------------------------------------
set "PY="
call :trypy "py -3"
if not defined PY call :trypy "python"
if not defined PY call :trypy "python3"
if not defined PY (
  echo.
  echo   Python 3.10 or newer is required, and it was not found.
  echo   ^(If Windows opened the Microsoft Store, close it - that is only a shortcut, not Python.^)
  echo   Download Python from https://www.python.org/downloads/
  echo   and tick "Add python.exe to PATH" during installation. Then run start.bat again.
  echo.
  pause
  exit /b 1
)
goto :havepy

:trypy
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%~1"
exit /b 0

:havepy
rem ---- virtual environment -----------------------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment.
    pause
    exit /b 1
  )
)

echo [2/3] Checking packages (the first time takes 1-3 minutes) ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo   Package installation failed. Check your Internet connection and run start.bat again.
  pause
  exit /b 1
)

if /i "%~1"=="update" (
  echo Updating yt-dlp / youtube-transcript-api / edge-tts ...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -U yt-dlp youtube-transcript-api edge-tts
)

echo [3/3] Starting V_Heang Studio - your browser will open automatically.
echo       Keep this window open. Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" server.py
echo.
pause
