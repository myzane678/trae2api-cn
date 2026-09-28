# start-trae2api-core.ps1 - one-click launcher core for the TRAE CN relay.
# Called by launch.vbs (hidden, desktop shortcut) and start-trae2api.cmd
# (console). Ensures the relay (8092) and OAuth helper (8765) are running,
# waits for health, then opens the admin console in a Chrome app window.
# ASCII output only: cmd callers may read this file with a legacy codepage.

$Base = 'A:\ClaudeWorkspace\trae2api-cn'
$Py   = Join-Path $Base '.venv\Scripts\python.exe'
$RelayHealth  = 'http://127.0.0.1:8092/healthz'
$HelperPort   = 8765
$AdminUrl     = 'http://127.0.0.1:8092/web/login'
$AdminProfile = Join-Path $Base 'data\admin-profile'

function Test-Healthy([string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

if (-not (Test-Path $Py)) {
    Write-Output '[trae2api] python venv not found: .venv\Scripts\python.exe'
    exit 1
}

if (-not (Test-Healthy $RelayHealth)) {
    if (-not (Test-Path (Join-Path $Base 'data'))) { New-Item -ItemType Directory -Path (Join-Path $Base 'data') | Out-Null }
    Write-Output '[trae2api] relay starting on http://127.0.0.1:8092 ...'
    Start-Process -FilePath $Py -ArgumentList '-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8092' `
        -WorkingDirectory $Base -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Base 'data\relay-stdout.log') `
        -RedirectStandardError  (Join-Path $Base 'data\relay-stderr.log')
} else {
    Write-Output '[trae2api] relay already running.'
}

# OAuth callback helper keeps the authorize button instant.
$helperUp = $false
try {
    $c = Get-NetTCPConnection -LocalPort $HelperPort -State Listen -ErrorAction SilentlyContinue
    $helperUp = [bool]$c
} catch { $helperUp = $false }
if (-not $helperUp) {
    Write-Output '[trae2api] login helper starting on http://127.0.0.1:8765 ...'
    Start-Process -FilePath $Py -ArgumentList (Join-Path $Base 'web_login.py'),'--relay','http://127.0.0.1:8092','--port',"$HelperPort",'--no-open' `
        -WorkingDirectory $Base -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Base 'data\login-helper-stdout.log') `
        -RedirectStandardError  (Join-Path $Base 'data\login-helper-stderr.log')
} else {
    Write-Output '[trae2api] login helper already running.'
}

# Poll relay health up to 20s.
$up = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Healthy $RelayHealth) { $up = $true; break }
}
if (-not $up) {
    Write-Output '[trae2api] FAILED: relay did not become healthy within 20s. Check data\relay-stderr.log'
    exit 1
}
Write-Output '[trae2api] relay healthy.'

# Console in a Chrome app window (frameless, isolated profile). The marker
# flag survives on the command line so stop-trae2api-helper.ps1 can close the
# window when the service stops. Chrome ignores unknown flags.
$chrome = ''
foreach ($p in @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe")) {
    if (Test-Path $p) { $chrome = $p; break }
}
if ($chrome -ne '') {
    Start-Process -FilePath $chrome -ArgumentList `
        "--user-data-dir=`"$AdminProfile`"",'--trae2api-admin-window','--no-first-run','--no-default-browser-check',"--app=$AdminUrl"
    Write-Output '[trae2api] console opened.'
} else {
    Start-Process -FilePath 'rundll32.exe' -ArgumentList 'url.dll,FileProtocolHandler',$AdminUrl
    Write-Output '[trae2api] console opened in default browser (Chrome not found).'
}
exit 0
