@echo off
REM start-trae2api.cmd - launch TRAE CN relay (8092) + OAuth helper (8765),
REM wait for health, then open the admin console.
REM Console-visible twin of launch.vbs: launch.vbs starts the hidden watchdog
REM (fully windowless); this one runs tools\oneclick.py directly so the caller
REM sees progress. Paths are relative to this file.
setlocal
cd /d "%~dp0"
title TRAE2API - Starting
set HEALTH=http://127.0.0.1:8092/healthz
set CURL="C:\Windows\System32\curl.exe"

echo ============================================================
echo   TRAE2API - Start
echo ============================================================
echo.

%CURL% -s -o NUL -m 3 %HEALTH%
if %errorlevel%==0 (
    echo [!] Service already running. Nothing to do.
    echo.
    ping -n 4 127.0.0.1 >nul
    goto open
)

if not exist ".venv\Scripts\python.exe" (
    echo [!] Python venv not found: .venv\Scripts\python.exe
    echo     Recreate it with: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    echo.
    ping -n 9 127.0.0.1 >nul
    exit /b 1
)

echo [*] Starting relay and login helper (hidden)...
".venv\Scripts\python.exe" "tools\oneclick.py"
if errorlevel 1 (
    echo.
    echo ============================================================
    echo   [FAIL] Relay did not come up. Check log:
    echo   %~dp0data\relay-stderr.log
    echo ============================================================
    echo.
    ping -n 11 127.0.0.1 >nul
    exit /b 1
)

:open
echo.
echo ============================================================
echo   [OK] START SUCCESS
echo   API:      http://127.0.0.1:8092/v1
echo   Console:  http://127.0.0.1:8092/web/login
echo   Health:   http://127.0.0.1:8092/healthz
echo ============================================================
echo.
echo   This window can be closed; the relay keeps running hidden.
echo ============================================================
ping -n 6 127.0.0.1 >nul
exit /b 0
