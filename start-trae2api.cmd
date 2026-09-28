@echo off
REM start-trae2api.cmd - launch TRAE CN relay (8092) + OAuth helper (8765),
REM wait for health, then open the admin console. Console-visible twin of
REM launch.vbs (which runs the same core script hidden).
setlocal
title TRAE2API - Starting
echo ============================================================
echo   TRAE2API - Start
echo ============================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "A:\ClaudeWorkspace\trae2api-cn\start-trae2api-core.ps1"
echo.
echo   API:      http://127.0.0.1:8092/v1
echo   Console:  http://127.0.0.1:8092/web/login
echo.
echo   This window can be closed; the relay keeps running hidden.
echo ============================================================
ping -n 6 127.0.0.1 >nul
exit /b 0
