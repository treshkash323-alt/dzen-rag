# Dzen RAG — модуль v.3

RAG-ассистент по материалам Дзен-канала «Канал про ИИ».

## Стек

- FastAPI, ChromaDB, sentence-transformers, pypdf
- LLM: DeepSeek (облако) | LM Studio (локально, опционально)
- Источник: `RAG_SOURCE_PATH` из `config/paths.example.env`
- Общий код: `aikivaviora_shared/rag/`

## Запуск

> **Шпаргалка:** [`SHPARGALKA.md`](SHPARGALKA.md)

**Ярлык на рабочий стол:** правый клик по `start-api.bat` → «Создать ярлык» → перетащить на рабочий стол.

```powershell
cd backend
.\run.ps1
```

- **Чат:** http://127.0.0.1:8001/ui/
- **Swagger:** http://127.0.0.1:8001/docs

## Индекс

ChromaDB → `05data/rag_index/` (в `.gitignore`, не коммитить).

## ДЗ-7 (сдача курса)

- ПЗ: `09education/DZ-7_пояснительная_записка_dzen-rag.md`
- **Чек-лист вручную:** `09education/DZ-7_ЧТО_СДЕЛАТЬ_ВРУЧНУЮ.md`
- Публичный git: `PUBLIC_RELEASE.md`, `scripts/check-public-push.ps1`

## Связи

- Legacy README: `Cursor/Projects/dzen-rag/README.md` (не дублировать код там)
- DzenNeuro: `Cursor/Projects/ДЗ-5/DzenNeuro/` (редактор, не search)
- Playwright export: `tools/dzen_playwright_export.py`
