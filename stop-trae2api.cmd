@echo off
REM stop-trae2api.cmd - stop the watchdog, TRAE relay (8092) and login helper
REM (8765), then self-close. Path is relative to this file.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-trae2api-helper.ps1"
ping -n 8 127.0.0.1 >nul
exit /b 0
