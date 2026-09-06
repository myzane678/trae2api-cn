@echo off
REM start-trae2api.cmd - launch TRAE CN relay (8092) + OAuth helper (8765), windowless, self-closing
setlocal
set PROJ=A:\ClaudeWorkspace\trae2api-cn
set PY=%PROJ%\.venv\Scripts\python.exe

if not exist "%PROJ%\data" mkdir "%PROJ%\data"

REM relay on 8092
netstat -ano | findstr /c:":8092" | findstr /c:"LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [trae2api] relay already listening on 8092.
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PY%' -ArgumentList '-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8092' -WorkingDirectory '%PROJ%' -WindowStyle Hidden -RedirectStandardOutput '%PROJ%\data\relay-stdout.log' -RedirectStandardError '%PROJ%\data\relay-stderr.log'"
  echo [trae2api] relay starting on http://127.0.0.1:8092
)

REM OAuth callback helper on 8765 (keeps the authorize button instant)
netstat -ano | findstr /c:":8765" | findstr /c:"LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [trae2api] login helper already listening on 8765.
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PY%' -ArgumentList '%PROJ%\web_login.py','--relay','http://127.0.0.1:8092','--port','8765','--no-open' -WorkingDirectory '%PROJ%' -WindowStyle Hidden -RedirectStandardOutput '%PROJ%\data\login-helper-stdout.log' -RedirectStandardError '%PROJ%\data\login-helper-stderr.log'"
  echo [trae2api] login helper starting on http://127.0.0.1:8765
)

ping -n 8 127.0.0.1 >nul
exit /b 0
