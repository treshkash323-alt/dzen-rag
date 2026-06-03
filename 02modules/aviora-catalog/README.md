# AIKIVAVIORA Catalog v0.3.8

Локальный веб-каталог `Python_kash`: дерево, **Scan + поиск**, правка md/txt, zip, снимки кода, карта филиалов, чат LM Studio / DeepSeek.

Порт **8002**. Соседний модуль: [Dzen RAG](http://127.0.0.1:8001/ui/) (:8001).

## Запуск (рекомендуется)

1. Один раз — окружение:

```powershell
cd 02modules\aviora-catalog\backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

2. Каждый сеанс:

```text
Двойной клик: 02modules\aviora-catalog\start-api.bat
```

**Не закрывайте** чёрное окно bat — это сервер. Браузер: http://127.0.0.1:8002/ui/

Подробно: **`ЗАПУСК.txt`**.

### VS Code / Cursor

```powershell
cd 02modules\aviora-catalog\backend
..\stop-api.bat
.\run_uvicorn.ps1
```

Не запускайте bat и uvicorn одновременно.

### Остановка

`stop-api.bat` или Ctrl+C в окне сервера.

## После запуска

1. **Ctrl+Shift+R** в браузере — в подвале **v0.3.8**
2. **Scan** — дождаться полосы прогресса (~3500 файлов)
3. **Поиск** — слово слева + **Enter**
4. **Чат** — LM Studio Start Server :1234, Send

## Конфигурация

`backend/.env.example` → `.env` (не в git):

| Переменная | Назначение |
|------------|------------|
| `CATALOG_ROOT` | Корень каталога |
| `PORT` | 8002 |
| `LMSTUDIO_BASE_URL` | http://127.0.0.1:1234/v1 |
| `DEEPSEEK_API_KEY` | Опционально |

## Структура

| Путь | Назначение |
|------|------------|
| `backend/app.py` | FastAPI |
| `backend/catalog_index.py` | Scan, поиск, кэш индекса |
| `backend/llm_client.py` | LM Studio / DeepSeek |
| `frontend/` | UI (лента, Scan, чат) |
| `start-api.bat` / `stop-api.bat` | Запуск / остановка |
| `docs/ROADMAP_WORKSPACE.md` | Roadmap |

## Безопасность

Не коммитить `backend/.env`. См. `SECURITY.md`.
