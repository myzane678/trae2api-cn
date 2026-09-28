' launch.vbs - TRAE CN relay one-click launcher (desktop shortcut target).
' Thin wrapper: runs start-trae2api-core.ps1 fully hidden (no console flash).
' The core script starts the relay/helper if needed, waits for health and
' opens the admin console in a Chrome app window. Keep this file ASCII only -
' wscript reads no-BOM files as ANSI.
Set ws = CreateObject("WScript.Shell")
ws.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""A:\ClaudeWorkspace\trae2api-cn\start-trae2api-core.ps1""", 0, False
