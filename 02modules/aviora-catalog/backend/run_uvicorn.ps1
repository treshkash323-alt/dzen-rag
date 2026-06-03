# Same as start-api.bat, for VS Code / Cursor terminal
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
Set-Location $here
$py = Join-Path $here ".venv\Scripts\python.exe"
$want = "0.3.11"

if (-not (Test-Path $py)) {
    Write-Host "Missing .venv - see start-api.bat"
    exit 1
}

$c = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($c) {
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:8002/health" -TimeoutSec 4
        if ($h.version -eq $want) {
            Write-Host "Already running v$($h.version) PID $($c.OwningProcess)"
            Write-Host "Open http://127.0.0.1:8002/ui/"
            exit 0
        }
        Write-Host "Old API v$($h.version) - stopping PID $($c.OwningProcess)"
    } catch {
        Write-Host "Port busy PID $($c.OwningProcess), health failed - restarting"
    }
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Write-Host "Starting uvicorn $want - keep this terminal open"
& $py -m uvicorn app:app --host 127.0.0.1 --port 8002
