# Как открыть проект в VS Code / Cursor (файлы «не пропали»)

## Почему в окне «Open Folder» пусто

В диалоге **Open Folder** Windows часто показывает **только подпапки**, не файлы `app.py`, `.env`.

В `dzen-rag\backend` на диске есть:

- `app.py`
- `requirements.txt`
- `.env`, `.env.example`
- `run.ps1`

Плюс папки `.venv` и `__pycache__` — их вы и видите в диалоге.

**Файлы не удалены.** Их не показывают в этом окне выбора.

## Что делать

1. В диалоге дойдите до нужной папки, например:  
   `...\02modules\aviora-catalog`  
   или `...\02modules\dzen-rag\backend`
2. Нажмите **«Выбор папки» / Select folder** — не ищите `app.py` в списке.
3. Слева в VS Code/Cursor в **Explorer** появятся все файлы.

## Пути для копирования

**Каталог MVP:**

`C:\Users\kash-\Python_kash\Cursor\AIKIVAVIORA_v.3_Cursor\02modules\aviora-catalog`

**Dzen RAG backend:**

`C:\Users\kash-\Python_kash\Cursor\AIKIVAVIORA_v.3_Cursor\02modules\dzen-rag\backend`

## Catalog ≠ VS Code

Сайт http://127.0.0.1:8002 **не блокирует** VS Code и не заменяет проводник.
