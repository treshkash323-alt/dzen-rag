# Реестр наработок Python_kash

> Только для справки. **Не редактировать** проекты по этим путям без запроса пользователя.  
> Обновлено: 30.05.2026 (инвентаризация Cursor-агентом, read-only).

## Корень

`C:\Users\kash-\Python_kash\` — общий каталог всех AI-проектов и зон.

| Папка | Назначение | Статус | Брать в v.3? |
|-------|------------|--------|--------------|
| `_archive` | Архив | хранение | по запросу |
| `AI_Cases` | Кейсы (rss_digest_case) | справочник | паттерны |
| `ai-consultant-kiv-2026` | AI-консультант KIV | отдельный продукт | нет |
| `AIKIVAVIORA` | **Codex / NEXUS / v.1 workspace** | активная инженерная зона | стандарты, NEXUS, модули |
| `ai-kotelnaya` | HVAC / котельная | доменный MVP | позже |
| `ai-service-desk-assistant` | Service desk | отдельный продукт | нет |
| `Claude` | **Claude-зона** (обучение, sandbox) | активная | docs, rag-telegram-bot |
| `coding` | Учебный код | misc | нет |
| `Cursor` | **Cursor workspace** (PROFILE, ДЗ, Dzen) | активная | домашки + этот филиал |
| `DzenTools` | Инструменты Дзен | утилиты | по запросу |
| `EliteMentorAI*` | Образовательные MVP (3 варианта) | эксперiments | UI-референсы |
| `Google AI Studio` | Эксперименты GAS | sandbox | нет |
| `homework-ai-chat` | Домашний чат | учебное | нет |
| `Kiva_Sales_Agent` | Sales agent | отдельный продукт | sales-паттерны |
| `KIVAVIORASystem` | Системный слой KIV | infra | позже |
| `LM Studio` | Локальные LLM | runtime | **local LLM** `:1234` |
| `RSSDigest` | RSS-дайджест | отдельный | нет |
| `test` | Тесты | sandbox | нет |

---

## Три ветки AIKIVAVIORA

| Ветка | Путь | Роль |
|-------|------|------|
| **v.3 Cursor** | `Cursor/AIKIVAVIORA_v.3_Cursor/` | **активная разработка в Cursor** |
| v.2 Claude | `Claude/Projects/AIKIVAVIORA.v.2/` | зеркало структуры 00–09, Claude |
| VS Code | `AIKIVAVIORA/` | NEXUS, MODULE_REGISTRY, Codex |

Структура каталогов (общая логика): `00docs` … `09education`, `tools`, `aikivaviora_shared`.

Канон правил: `AIKIVAVIORA/00docs/ecosystem/00_AI_RULES.md`  
Индекс NEXUS: `AIKIVAVIORA/01core/AIKIVAVIORA_NEXUS/02_registry/PROJECTS_INDEX.md`

---

## RAG и Дзен (приоритет для v.3)

| Что | Путь | Стек / заметки | Действие v.3 |
|-----|------|----------------|--------------|
| **dzen-rag (канон v.3)** | `Cursor/AIKIVAVIORA_v.3_Cursor/02modules/dzen-rag/` | FastAPI + Chroma + ST + DeepSeek + LM Studio | **строим здесь** |
| dzen-rag (legacy stub) | `Cursor/Projects/dzen-rag/README.md` | указатель | не дублировать код |
| DzenNeuro (ДЗ-5) | `Cursor/Projects/ДЗ-5/DzenNeuro/` | React + FastAPI, редактор контента | промпты, UI-идеи |
| RAG школа (Replit) | `Claude/Projects/rag-telegram-bot/` + Hello-Who | Flask + FAISS, 88 чанков, DeepSeek | ingest, чанкинг |
| Hello-Who backend | `AIKIVAVIORA/02modules/knowledge/Hello-Who/artifacts/rag-app` | Flask :5051 | референс API |
| Telegram bridge | `Claude/Projects/rag-telegram-bot/bot.py` | бот → RAG API | позже в v.3 |
| Контент (черновики) | `Cursor/Dzen/модуль 1.3 - 24.05.2026/` | ~1 GB, не индексировать | только архив |
| Контент (stub) | `Cursor/Dzen/knowledge-base/published/` | .gitkeep | временно |
| **Канон RAG** | `G:\3_Дзен\...\4_AIKIVAVIORA_база-RAG\` | модули + слоты 1F–9F, `.md`/`.txt` | **источник ingest** |
| Архив публикаций | `G:\3_Дзен\...\2_Архив-опубликовано` | опубликованное | курация → канон |
| Правила канала | `Cursor/Dzen/DZEN_FORMAT.md` | формат статей | промпты |

---

## Образование и LM

| Что | Путь | Заметки |
|-----|------|---------|
| PROFILE | `Cursor/PROFILE/` | профиль, школы, мост |
| ДЗ-5 DzenNeuro | `Cursor/Projects/ДЗ-5/` | веб-приложение |
| ДЗ-6 | `Cursor/Projects/ДЗ-6/` | ✅ сдан Lite |
| ДЗ-7 материалы | `Cursor/Projects/ДЗ-7/` | TrailCamp — **не делаем**, только референс |
| EduAI FamilyPilot | `AIKIVAVIORA/09education/EduAI_FamilyPilot/` | LM Studio chat | local LLM UX |
| LM Studio models | `C:\LLM_Local\models` (~84 GB) | 8 моделей | Llama 3.1 8B и др. |
| RAG School track | `AIKIVAVIORA/03experiments/01_rag_school_*` | эксперимент | уроки |

---

## Модули AIKIVAVIORA (Codex-зона)

| MODULE_ID | Путь | Зрелость |
|-----------|------|----------|
| core_nexus | `01core/AIKIVAVIORA_NEXUS` | CRITICAL |
| module_sales_mvp | `02modules/sales/AIKIVAVIORASalesMVP` | MVP |
| experiment_hello_who | `02modules/knowledge/Hello-Who` | MVP / homework |
| core_analytics_mvp | `01core/AIKIVAVIORACoreAnalyticsMVP` | ACTIVE |
| corporate / medical | `02modules/corporate|medical/*` | SKELETON |

---

## Правило выбора

```
Нужна фича → REGISTRY → спросить пользователя → перенос в v.3, не клон
```

Новые строки добавлять с датой и источником («найдено при …»).
