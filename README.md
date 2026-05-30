# AIKIVAVIORA v.3 — Cursor-филиал

Продуктовая ветка экосистемы AIKIVAVIORA для разработки в **Cursor**.

| Ветка | Путь | Инструмент |
|-------|------|------------|
| **v.3 Cursor (активная)** | `Cursor/AIKIVAVIORA_v.3_Cursor/` | Cursor Agent |
| v.2 Claude | `Claude/Projects/AIKIVAVIORA.v.2/` | Claude Code |
| VS Code / Codex | `AIKIVAVIORA/` | Codex, Copilot, NEXUS |
| Домашки курса | `Cursor/Projects/ДЗ-*` | только материалы и сдача |
| Контент Дзен | `Cursor/Dzen/`, `G:\3_Дзен\...` | не код |

## Принцип

- Новый продуктовый код — **только здесь**, не дублировать модули из других веток.
- Перед созданием модуля — сверка с `00docs/ASSETS_REGISTRY.md`.
- Чужие каталоги `Python_kash/*` — **только чтение**, без правок.

## Первый модуль: Dzen RAG

`02modules/dzen-rag/` — RAG по каналу «Канал про ИИ» (FastAPI + Chroma + DeepSeek / LM Studio).

### Запуск RAG (кратко)

```powershell
# 1. Backend venv
cd 02modules\dzen-rag\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\..\..\config\paths.example.env .env

# 2. Ingest модуля 1.3
cd ..\..\..
$env:RAG_SOURCE_PATH = "G:\3_Дзен\1G_канал про ИИ_статьи на Дзене\4_AIKIVAVIORA_база-RAG\модуль 1.3 - 24.05.2026"
python tools\ingest_from_g.py --reset

# 3. API
cd 02modules\dzen-rag\backend
uvicorn app:app --reload --port 8000
```

Подробнее: `02modules/dzen-rag/README.md`

## Документы

- `CURSOR.md` — правила для агента Cursor
- `00docs/ASSETS_REGISTRY.md` — реестр всех наработок
- `00docs/BRANCH_BOUNDARIES.md` — границы филиалов
- `00docs/RAG_ECOSYSTEM.md` — цепочка G: → ingest → API
- `09education/DZ-7_пояснительная_записка_dzen-rag.md` — ПЗ для сдачи ДЗ-7 (промежуточная)
