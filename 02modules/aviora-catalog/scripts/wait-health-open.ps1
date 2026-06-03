for ($i = 0; $i -lt 90; $i++) {
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:8002/health" -TimeoutSec 2
        if ($h.version) {
            Start-Process "http://127.0.0.1:8002/ui/"
            exit 0
        }
    }
    catch { }
    Start-Sleep -Seconds 1
}
exit 1
