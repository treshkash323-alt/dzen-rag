param(
    [string]$WantVersion = "0.3.13"
)

function Test-Health {
    try {
        return Invoke-RestMethod "http://127.0.0.1:8002/health" -TimeoutSec 3
    }
    catch {
        return $null
    }
}

$conn = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $conn) {
    exit 10
}

$procId = $conn.OwningProcess

# Port busy: wait for /health (first window may still be starting uvicorn)
for ($i = 0; $i -lt 25; $i++) {
    $h = Test-Health
    if ($h -and $h.version -eq $WantVersion) {
        Write-Host "[OK] Catalog v$($h.version) already on :8002 (PID $procId)."
        Write-Host "     Do NOT start a second server window."
        exit 0
    }
    if ($h -and $h.version -and $h.version -ne $WantVersion) {
        Write-Host "[!!] Port 8002: API v$($h.version), need $WantVersion - restart PID $procId"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        exit 11
    }
    if ($i -eq 0) {
        Write-Host "[..] Port 8002 busy (PID $procId), waiting for /health..."
    }
    Start-Sleep -Seconds 1
}

$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
$pn = if ($proc) { $proc.ProcessName } else { "?" }

if ($pn -match "python") {
    Write-Host "[OK] Python on :8002 (PID $procId) but /health slow."
    Write-Host "     Another start-api window is probably starting. Do not open a second one."
    exit 0
}

Write-Host "[!!] Port 8002 used by $pn (PID $procId), not Catalog - freeing port"
Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
exit 11
