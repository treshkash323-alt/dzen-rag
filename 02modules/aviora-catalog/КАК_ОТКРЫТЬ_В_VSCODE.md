# VS Code / Cursor — Aviora Catalog

## Открыть папку

`C:\Users\kash-\Python_kash\Cursor\AIKIVAVIORA_v.3_Cursor\02modules\aviora-catalog`

В диалоге **Open Folder** выберите **папку** `aviora-catalog`, не отдельный `app.py`.

## Python и библиотеки (один раз)

В терминале VS Code (**Terminal → New Terminal**):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Или из корня каталога:

```powershell
.\backend\.venv\Scripts\pip install -r backend\requirements.txt
```

## Интерпретатор в VS Code

1. **Ctrl+Shift+P** → `Python: Select Interpreter`
2. Выберите:  
   `.\backend\.venv\Scripts\python.exe`

Проект уже содержит `.vscode/settings.json` — интерпретатор подставится, если открыта папка **aviora-catalog**.

## Запуск сервера из VS Code

**F5** или Run → **Aviora Catalog API :8002** (конфиг в `.vscode/launch.json`).

Либо в терминале:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8002
```

Не дублируйте с `start-api.bat` на том же порту (ошибка 10048).

## Установленные пакеты (`requirements.txt`)

| Пакет | Зачем |
|-------|--------|
| fastapi, uvicorn | API :8002 |
| python-multipart | Upload |
| python-dotenv | `.env` |
| httpx | LM Studio / DeepSeek |
| Pillow | Изображения |
| pypdf | Текст из PDF при Scan |
| python-docx | docx при Scan |
| openpyxl | xlsx при Scan |

## Рекомендуемые расширения

При открытии папки VS Code предложит: **Python**, **Pylance** (файл `.vscode/extensions.json`).
