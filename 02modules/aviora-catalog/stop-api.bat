@echo off
chcp 65001 >nul
title Остановка Aviora Catalog :8002

echo Останавливаю процесс на порту 8002...
powershell -NoProfile -Command ^
  "$c = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; ^
   if (-not $c) { Write-Host 'Порт 8002 свободен — сервер уже выключен.'; exit 0 }; ^
   $pid = $c.OwningProcess; Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; ^
   Write-Host \"Остановлен PID $pid\""

echo.
pause
