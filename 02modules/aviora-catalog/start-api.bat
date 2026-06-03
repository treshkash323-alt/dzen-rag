@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Aviora Catalog — сервер :8002

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "WANT_VER=0.3.8"

cd /d "%BACKEND%"
if errorlevel 1 (
    echo [Ошибка] Нет папки backend.
    pause
    exit /b 1
)

if not exist "%PY%" (
    echo [Ошибка] Нет .venv — один раз в PowerShell:
    echo   cd "%BACKEND%"
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo   copy .env.example .env
    pause
    exit /b 1
)

echo.
echo  === Aviora Catalog %WANT_VER% ===
echo.

REM Проверка порта 8002: если занят — health; чужой/старый процесс — убить
powershell -NoProfile -Command ^
  "$want = '%WANT_VER%'; ^
   $c = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; ^
   if (-not $c) { exit 10 }; ^
   $pid = $c.OwningProcess; ^
   try { ^
     $h = Invoke-RestMethod 'http://127.0.0.1:8002/health' -TimeoutSec 4; ^
     if ($h.version -eq $want) { ^
       Write-Host \"[OK] Уже работает v$($h.version) (PID $pid). Открою браузер.\"; ^
       Write-Host 'НЕ закрывайте окно того процесса, который держит :8002.'; ^
       exit 0 ^
     }; ^
     Write-Host \"[!!] На :8002 старый API v$($h.version), нужен $want — перезапуск PID $pid\"; ^
   } catch { ^
     Write-Host \"[!!] Порт занят PID $pid, но /health не отвечает — перезапуск\"; ^
   }; ^
   Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; ^
   Start-Sleep -Seconds 2; ^
   exit 11"

set "PORTCHK=%ERRORLEVEL%"
if "%PORTCHK%"=="0" (
    start "" "http://127.0.0.1:8002/ui/"
    echo.
    echo  Браузер открыт. Это окно можно закрыть — сервер в ДРУГОМ терминале.
    echo  Если Catalog не открывается — запустите stop-api.bat, затем start-api.bat снова.
    pause
    exit /b 0
)

if "%PORTCHK%"=="11" (
    echo  Старый процесс на :8002 остановлен, запускаю заново...
    echo.
)

echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  НЕ ЗАКРЫВАЙТЕ ЭТО ЧЁРНОЕ ОКНО — пока работает Catalog  ║
echo  ║  Остановка: Ctrl+C здесь или stop-api.bat               ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  UI: http://127.0.0.1:8002/ui/
echo.

REM Браузер — только когда /health ответит (фоновое ожидание)
start "aviora-open-ui" /min cmd /c ""powershell -NoProfile -Command ^
  \"for ($i=0; $i -lt 90; $i++) { try { $h = Invoke-RestMethod 'http://127.0.0.1:8002/health' -TimeoutSec 2; if ($h.version) { Start-Process 'http://127.0.0.1:8002/ui/'; exit 0 } } catch {}; Start-Sleep -Seconds 1 }\"\""

"%PY%" -m uvicorn app:app --host 127.0.0.1 --port 8002

echo.
echo  Сервер остановлен (окно можно закрыть).
pause
endlocal
