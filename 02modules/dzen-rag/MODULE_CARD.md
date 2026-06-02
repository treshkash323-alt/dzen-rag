# Module Card

- MODULE_ID: `module_dzen_rag`
- NAME: `Dzen RAG (v.3 Cursor)`
- ENTITY_TYPE: `MODULE`
- PATH: `C:\Users\kash-\Python_kash\Cursor\AIKIVAVIORA_v.3_Cursor\02modules\dzen-rag`
- STATUS: `working — DZ-7 compliance pass 2026-05-30`
- MATURITY_LEVEL: `MVP`
- STRATEGIC_PRIORITY: `HIGH`
- MIGRATION_STATUS: `NEXUS_NATIVE` (v.3 branch)
- OWNER_SCOPE: `Dzen channel knowledge / Cursor product`
- RELATED_TO: `experiment_rag_school_2026_05`, DzenNeuro, legacy `Projects/dzen-rag`
- PURPOSE: Retrieval over published Dzen articles; chat API with cloud/local LLM switch.
- FUTURE_ROLE: Core knowledge module for Dzen Neuro ecosystem and Telegram bridge.
- DEPENDENCIES: `config/paths.example.env`, `tools/ingest_from_g.py`, `05data/rag_index/`, `aikivaviora_shared/rag/`

## Сделано (2026-05-30)

- Ingest: `.md` / `.txt` / `.pdf` → Chroma (`05data/rag_index/`)
- Модуль 1.3 на G: проиндексирован: **18 файлов, 126 чанков**
- FastAPI: `/health`, `/ingest`, `/chat` + DeepSeek / LM Studio
- Frontend: `/ui/` (чат в браузере)
- Запуск: `start-api.bat` (ярлык на рабочий стол), `SHPARGALKA.md`

## Возобновление

1. Двойной клик `start-api.bat` или `backend\run.ps1`
2. Чат: http://127.0.0.1:8001/ui/
3. Новый контент на G: → `tools/ingest_from_g.py --reset`

## Не делано (следующая фаза — см. `Cursor/Projects/TODO.md`)

- [x] POST `/upload` + upload UI (ДЗ-7)
- Зеркало в `Projects/ДЗ-7/` для сдачи
- Telegram-бот
- Авто-ingest по расписанию
- Модули > 1.3 на G:
- Production deploy (`08deploy/`)

- NOTES: Канон на G: `4_AIKIVAVIORA_база-RAG`. `.env` и индекс не в git.
