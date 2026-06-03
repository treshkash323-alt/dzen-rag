$c = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $c) {
    Write-Host "Port 8002 is free."
    exit 0
}
$procId = $c.OwningProcess
Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
Write-Host "Stopped PID $procId"
Start-Sleep -Seconds 2
