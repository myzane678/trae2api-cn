' launch.vbs - TRAE CN relay one-click entry (desktop shortcut target).
' No console flash: when the relay is not up, start the hidden watchdog via
' tools\oneclick.py (base pythonw, GUI subsystem) and poll /healthz for up to
' 20s; if it is already running, open the console immediately.
' The console uses a Chrome app window (--app, no address bar) on an isolated
' profile; falls back to the default browser when Chrome is missing.
'
' Paths are derived from this script's own location, so the project can be
' moved without editing this file. Keep this file ASCII only - wscript reads
' no-BOM files as ANSI.
Option Explicit
Const HEALTH = "http://127.0.0.1:8092/healthz"
Const ADMIN  = "http://127.0.0.1:8092/web/login"

Dim sh, fso, base, chrome, i, ok
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)

' Locate Chrome (same probe order as oneclick.py).
chrome = ""
If fso.FileExists(sh.ExpandEnvironmentStrings("%ProgramFiles%\Google\Chrome\Application\chrome.exe")) Then
  chrome = sh.ExpandEnvironmentStrings("%ProgramFiles%\Google\Chrome\Application\chrome.exe")
ElseIf fso.FileExists(sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")) Then
  chrome = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")
ElseIf fso.FileExists(sh.ExpandEnvironmentStrings("%LocalAppData%\Google\Chrome\Application\chrome.exe")) Then
  chrome = sh.ExpandEnvironmentStrings("%LocalAppData%\Google\Chrome\Application\chrome.exe")
End If

' Any HTTP answer counts as alive (curl exit 0), matching the watchdog.
Function Healthy()
  Healthy = (sh.Run("%ComSpec% /c ""C:\Windows\System32\curl.exe"" -s -o NUL -m 3 " & HEALTH, 0, True) = 0)
End Function

If Not Healthy() Then
  sh.CurrentDirectory = base
  ' Start the hidden watchdog (watchdog.vbs itself has no window). It polls
  ' /healthz and launches tools\oneclick.py --no-open as soon as the relay is
  ' missing, then keeps guarding it for the rest of the session. Going through
  ' the watchdog (instead of oneclick directly) means a later crash self-heals.
  sh.Run "wscript.exe """ & base & "\watchdog.vbs""", 0, False
  ok = False
  For i = 1 To 25
    WScript.Sleep 1000
    If Healthy() Then
      ok = True
      Exit For
    End If
  Next
  If Not ok Then WScript.Quit 1
End If

' Chrome app window (frameless, desktop-app like) on an isolated profile so it
' never merges with the user's daily Chrome. --trae2api-admin-window is a
' marker flag stop-trae2api-helper.ps1 matches to close this window at OS
' level; Chrome ignores unknown flags but keeps them on the command line.
If chrome <> "" Then
  sh.Run """" & chrome & """ --user-data-dir=""" & base & "\data\admin-profile"" --trae2api-admin-window --no-first-run --no-default-browser-check --app=" & ADMIN, 1, False
Else
  sh.Run "rundll32.exe url.dll,FileProtocolHandler " & ADMIN, 0, False
End If
