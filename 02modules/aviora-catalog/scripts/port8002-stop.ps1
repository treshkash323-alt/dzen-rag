$conn = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $conn) {
    Write-Host "Port 8002 is free - server already stopped."
    exit 0
}
$procId = $conn.OwningProcess
Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
Write-Host "Stopped PID $procId"
exit 0
