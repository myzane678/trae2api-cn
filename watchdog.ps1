# watchdog.ps1 - hidden watchdog for the TRAE CN relay
# Polls http://127.0.0.1:8092/healthz every 5s; when the endpoint stops
# answering it re-runs tools\oneclick.py --no-open, which restarts the relay
# and the OAuth helper. Logs to data\watchdog.log.
#
# "Down" means no HTTP answer at all. A 503 from /healthz (no usable account)
# still counts as alive - killing and respawning would not fix an account
# problem, only add churn.
$ErrorActionPreference = 'Continue'
$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$log    = Join-Path $proj 'data\watchdog.log'
$health = 'http://127.0.0.1:8092/healthz'

function Log($msg) {
    # Append without a BOM. Windows PowerShell 5.1 has no utf8NoBOM, and its
    # 'utf8' writes a BOM into a new file (a stray character when tailing),
    # so write the bytes ourselves.
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg`r`n"
    try {
        [System.IO.File]::AppendAllText($log, $line, (New-Object System.Text.UTF8Encoding($false)))
    } catch { }
}

New-Item -ItemType Directory -Force -Path (Join-Path $proj 'data') | Out-Null
Log 'watchdog started'

# Probe with curl.exe directly: Start-Process does not set $LASTEXITCODE, which
# makes the loop believe the service is down and re-kill it every round.
function Alive() {
    curl.exe -s -o NUL -m 4 $health 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

$respawnedAt = Get-Date

while ($true) {
    if (-not (Alive)) {
        Log 'health check FAILED - restarting relay via oneclick.py'

        # The console twin uses python.exe; the hidden path needs the GUI
        # interpreter so no terminal flashes. oneclick.py itself picks the
        # base pythonw from pyvenv.cfg and spawns the services detached.
        $pyw = Join-Path $proj '.venv\Scripts\pythonw.exe'
        $py  = Join-Path $proj '.venv\Scripts\python.exe'
        $runner = if (Test-Path $pyw) { $pyw } else { $py }
        $oneclick = Join-Path $proj 'tools\oneclick.py'

        Start-Process -FilePath $runner -ArgumentList "`"$oneclick`" --no-open" `
            -WorkingDirectory $proj -WindowStyle Hidden
        Log 'oneclick.py --no-open dispatched, waiting for health...'

        # Give the relay its startup window (oneclick polls up to 20s itself)
        # before the next probe, so one outage is not counted many times.
        Start-Sleep -Seconds 25
        $respawnedAt = Get-Date
    }
    Start-Sleep -Seconds 5
}
