# stop-trae2api-helper.ps1 - kill the watchdog, the TRAE relay (8092), the
# OAuth login helper (8765) and the admin console Chrome app window.
# Called by stop-trae2api.cmd and by POST /api/stop; safe to run repeatedly.
#
# The watchdog has to go FIRST: it polls /healthz every 5s and would start the
# relay right back up a few seconds after we kill it.

# Close the console window first: Chrome runs with an isolated user-data-dir
# under data\admin-profile and a marker flag on the command line, so only this
# project's console matches - the user's daily Chrome is never touched.
$consoles = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*--trae2api-admin-window*' }
foreach ($proc in $consoles) {
    Write-Output ("[trae2api] console window: closing pid {0}" -f $proc.ProcessId)
    taskkill /PID $proc.ProcessId /T /F | Out-Null
}

# Match on this project's own directory, not a bare '*trae2api*' wildcard, so a
# differently-located copy (or the sibling workbuddy install) is never hit.
$proj = $PSScriptRoot

# Stop the watchdog before the services, otherwise it respawns them.
$watchdogs = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$proj*watchdog.ps1*" }
foreach ($w in $watchdogs) {
    Write-Output ("[trae2api] watchdog: stopping pid {0}" -f $w.ProcessId)
    Stop-Process -Id $w.ProcessId -Force -ErrorAction SilentlyContinue
}
# The watchdog's oneclick child may be mid-restart; stop it by command line.
$launchers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$proj*tools\oneclick.py*" }
foreach ($l in $launchers) {
    Write-Output ("[trae2api] launcher: stopping pid {0}" -f $l.ProcessId)
    Stop-Process -Id $l.ProcessId -Force -ErrorAction SilentlyContinue
}

# Wait out the watchdog's in-flight respawn (it sleeps up to 25s after a
# restart) so a relay it already launched cannot come up behind us.
Start-Sleep -Seconds 2

$targets = @(
    @{ Port = 8092; Name = 'relay' },
    @{ Port = 8765; Name = 'login-helper' }
)

$stoppedAnything = $false
foreach ($t in $targets) {
    $conns = Get-NetTCPConnection -LocalPort $t.Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Output ("[trae2api] {0}: nothing listening on {1}." -f $t.Name, $t.Port)
        continue
    }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        $procName = try { (Get-Process -Id $p -ErrorAction Stop).ProcessName } catch { 'unknown' }
        Write-Output ("[trae2api] {0}: stopping pid {1} ({2})" -f $t.Name, $p, $procName)
        taskkill /PID $p /T /F | Out-Null
        $stoppedAnything = $true
    }
}

Start-Sleep -Seconds 1

# Verify the port really went quiet - a survivor means the stop did not take.
$still = Get-NetTCPConnection -LocalPort 8092 -State Listen -ErrorAction SilentlyContinue
if ($still) {
    Write-Output '[!] Port 8092 still listening - a leftover process may remain.'
    exit 1
}

if ($stoppedAnything) { Write-Output '[trae2api] stopped.' } else { Write-Output '[trae2api] nothing to stop.' }
exit 0
