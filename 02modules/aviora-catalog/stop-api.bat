@echo off
setlocal EnableExtensions
title Stop Aviora Catalog :8002

set "SCRIPTS=%~dp0scripts"

echo Stopping process on port 8002...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\port8002-stop.ps1"

echo.
pause
endlocal
