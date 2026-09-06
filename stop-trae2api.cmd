@echo off
REM stop-trae2api.cmd - stop TRAE relay (8092) and login helper (8765), then self-close
powershell -NoProfile -ExecutionPolicy Bypass -File "A:\ClaudeWorkspace\trae2api-cn\stop-trae2api-helper.ps1"
ping -n 8 127.0.0.1 >nul
exit /b 0
