# Запуск API — всегда из папки backend (рядом с app.py)
Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1
uvicorn app:app --reload --port 8001
