# stop-trae2api-helper.ps1 - kill TRAE relay (8092), OAuth login helper (8765)
# and the admin console Chrome app window. Called by stop-trae2api.cmd; safe
# to run repeatedly.

# Close the console window first: Chrome runs with an isolated user-data-dir
# under data\admin-profile and a marker flag on the command line, so only this
# project's console matches - the user's daily Chrome is never touched.
$consoles = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*--trae2api-admin-window*' }
foreach ($proc in $consoles) {
    Write-Output ("[trae2api] console window: closing pid {0}" -f $proc.ProcessId)
    taskkill /PID $proc.ProcessId /T /F | Out-Null
}

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

if ($stoppedAnything) { Write-Output '[trae2api] stopped.' } else { Write-Output '[trae2api] nothing to stop.' }
exit 0
