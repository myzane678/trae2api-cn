@echo off
REM start-trae2api-login.cmd - run OAuth local helper on 127.0.0.1:8765 (needed for web login callback)
setlocal
set PROJ=A:\ClaudeWorkspace\trae2api-cn
set PY=%PROJ%\.venv\Scripts\python.exe

netstat -ano | findstr /c:":8765" | findstr /c:"LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [trae2api] login helper already listening on 8765.
  ping -n 3 127.0.0.1 >nul
  exit /b 0
)

if not exist "%PROJ%\data" mkdir "%PROJ%\data"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PY%' -ArgumentList '%PROJ%\web_login.py','--relay','http://127.0.0.1:8092','--port','8765' -WorkingDirectory '%PROJ%' -WindowStyle Hidden -RedirectStandardOutput '%PROJ%\data\login-helper-stdout.log' -RedirectStandardError '%PROJ%\data\login-helper-stderr.log'"

echo [trae2api] login helper listening on 127.0.0.1:8765
ping -n 3 127.0.0.1 >nul
exit /b 0
