' watchdog.vbs - launch watchdog.ps1 fully hidden (no console flash)
Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
ws.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & base & "\watchdog.ps1""", 0, False
