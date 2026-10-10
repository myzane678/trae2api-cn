' launch.vbs - TRAE CN relay one-click launcher (desktop shortcut target).
' Thin wrapper: runs tools\oneclick.py on the BASE pythonw.exe. The venv's
' pythonw.exe is a launcher stub that re-execs the console python.exe, whose
' Windows Terminal handoff flashes a window - the base pythonw is a real
' GUI-subsystem binary, so the whole launch chain stays windowless. oneclick
' is stdlib-only, so no PYTHONPATH is needed for this hop. Keep this file
' ASCII only - wscript reads no-BOM files as ANSI.
Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = "A:\ClaudeWorkspace\trae2api-cn"
pyw = ""
Set f = fso.OpenTextFile(base & "\.venv\pyvenv.cfg", 1, False, -2)
Do While Not f.AtEndOfStream
  line = f.ReadLine
  If InStr(1, line, "home", 1) = 1 Then
    pyw = Trim(Mid(line, InStr(line, "=") + 1)) & "\pythonw.exe"
    Exit Do
  End If
Loop
f.Close
If pyw <> "" And fso.FileExists(pyw) Then
  ws.Run """" & pyw & """ """ & base & "\tools\oneclick.py""", 0, False
Else
  MsgBox "GUI pythonw not found (pyvenv.cfg unreadable or home missing).", 16, "Trae2API"
End If
