@echo off
REM create-desktop-shortcut.cmd - put a "Trae2API" icon on the desktop pointing
REM at launch.vbs, so future starts are a double-click with no console window.
REM Re-runnable: it overwrites any previous shortcut of the same name.
REM
REM The desktop is resolved through .NET's SpecialFolder.DesktopDirectory, not
REM %USERPROFILE%\Desktop: when OneDrive is enabled it redirects the desktop to
REM something like C:\Users\<name>\OneDrive\桌面, and a shortcut written to the
REM literal path would land in a folder the user never looks at.
setlocal
set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"
set "PS1=%TEMP%\trae2api-mkshortcut.ps1"

REM Write a real helper script: inline one-liners with nested quotes are
REM fragile under cmd, and the paths here contain spaces when relocated.
> "%PS1%" echo $ErrorActionPreference = 'Stop'
>>"%PS1%" echo $desk = [Environment]::GetFolderPath('DesktopDirectory')
>>"%PS1%" echo $target = Join-Path $desk 'Trae2API.lnk'
>>"%PS1%" echo $s = (New-Object -ComObject WScript.Shell).CreateShortcut($target)
>>"%PS1%" echo $s.TargetPath = 'wscript.exe'
>>"%PS1%" echo $s.Arguments = '\"' + $env:TRAE2API_LAUNCH + '\"'
>>"%PS1%" echo $s.WorkingDirectory = $env:TRAE2API_PROJ
>>"%PS1%" echo $s.IconLocation = (Join-Path $env:TRAE2API_PROJ 'src\web\assets\trae2api.ico') + ',0'
>>"%PS1%" echo $s.Description = 'Trae2API relay'
>>"%PS1%" echo $s.Save()
>>"%PS1%" echo Write-Host ('[OK] ' + $target)

set "TRAE2API_PROJ=%PROJ%"
set "TRAE2API_LAUNCH=%PROJ%\launch.vbs"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "RC=%errorlevel%"
del "%PS1%" >nul 2>&1

if not "%RC%"=="0" (
  echo [FAIL] Shortcut creation failed - exit %RC%.
  pause
)
exit /b %RC%
