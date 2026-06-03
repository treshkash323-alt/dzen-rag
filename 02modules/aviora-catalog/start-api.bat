@echo off
setlocal EnableExtensions
title Aviora Catalog :8002

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "WANT_VER=0.3.13"
set "SCRIPTS=%ROOT%scripts"
set "LOCK=%ROOT%.catalog-server.lock"

cd /d "%BACKEND%"
if errorlevel 1 (
    echo [ERROR] backend folder not found.
    pause
    exit /b 1
)

if not exist "%PY%" (
    echo [ERROR] .venv not found. Run once in PowerShell:
    echo   cd "%BACKEND%"
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo   copy .env.example .env
    pause
    exit /b 1
)

echo.
echo === Aviora Catalog %WANT_VER% ===
echo.

if exist "%LOCK%" (
    echo [INFO] Lock file exists - another start may be in progress.
    echo        Waiting 5 sec before check...
    timeout /t 5 /nobreak >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\port8002-check.ps1" -WantVersion %WANT_VER%
set "PORTCHK=%ERRORLEVEL%"

if "%PORTCHK%"=="0" (
    echo.
    echo ============================================================
    echo  Server ALREADY running on :8002
    echo  Close THIS window - keep the OTHER black cmd with uvicorn
    echo  Stop server: Ctrl+C in that window OR stop-api.bat
    echo ============================================================
    echo.
    start "" "http://127.0.0.1:8002/ui/"
    pause
    exit /b 0
)

if "%PORTCHK%"=="11" (
    echo Old process on :8002 stopped. Starting again...
    echo.
)

echo %DATE% %TIME%> "%LOCK%"

echo ============================================================
echo  THIS window = Catalog server. Do NOT close while working.
echo  Do NOT run start-api.bat again - use stop-api.bat first.
echo  Stop: Ctrl+C here OR stop-api.bat
echo ============================================================
echo.
echo  UI: http://127.0.0.1:8002/ui/
echo.

start /min "" powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\wait-health-open.ps1"

"%PY%" -m uvicorn app:app --host 127.0.0.1 --port 8002

if exist "%LOCK%" del /f /q "%LOCK%" >nul 2>&1

echo.
echo Server stopped.
pause
endlocal
