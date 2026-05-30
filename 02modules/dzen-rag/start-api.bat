@echo off
chcp 65001 >nul
title Dzen RAG API — порт 8001

cd /d "%~dp0backend"
if errorlevel 1 (
    echo [Ошибка] Не найдена папка backend.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [Ошибка] Нет виртуального окружения .venv
    echo.
    echo Один раз выполните в PowerShell:
    echo   cd "%~dp0backend"
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo   copy ..\..\..\config\paths.example.env .env
    pause
    exit /b 1
)

echo.
echo  Dzen RAG — запуск сервера
echo  Чат:    http://127.0.0.1:8001/ui/
echo  Swagger: http://127.0.0.1:8001/docs
echo.
echo  Остановка: закройте это окно или Ctrl+C
echo.

start "" "http://127.0.0.1:8001/ui/"

".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8001

echo.
echo Сервер остановлен.
pause
