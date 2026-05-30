# Правила Cursor-агента для AIKIVAVIORA v.3

> Филиал: `C:\Users\kash-\Python_kash\Cursor\AIKIVAVIORA_v.3_Cursor`

## Границы

1. **Писать код только в этом каталоге** (`AIKIVAVIORA_v.3_Cursor/`).
2. **Не изменять** соседние зоны без явного запроса:
   - `C:\Users\kash-\Python_kash\AIKIVAVIORA\` (Codex / NEXUS)
   - `C:\Users\kash-\Python_kash\Claude\`
   - `C:\Users\kash-\Python_kash\Cursor\Projects\` (домашки)
   - остальные папки в `Python_kash\`
3. **Контент Дзен** — читать из `Cursor/Dzen/` или с диска `G:`, не копировать массово в git.

## Перед новым модулем

1. Открыть `00docs/ASSETS_REGISTRY.md`.
2. Найти похожий проект (RAG, бот, редактор).
3. Спросить пользователя: **перенести / переиспользовать / написать заново**.
4. Не создавать `Projects/dzen-rag`, `trailcamp-*` и т.п. — legacy-указатели, канон v.3 здесь.

## Стек v.3 (dzen-rag)

| Слой | Выбор |
|------|--------|
| API | FastAPI |
| Векторное хранилище | ChromaDB → `05data/rag_index/` |
| Embeddings | sentence-transformers (локально) |
| LLM облако | DeepSeek API |
| LLM локально | LM Studio `http://127.0.0.1:1234/v1` |
| Источник текстов | `RAG_SOURCE_PATH` (см. `config/paths.example.env`) |

## Безопасность

- `.env` не коммитить; только `.env.example`.
- Ключи не выводить в чат.
- Индекс и большие модели — в `.gitignore`.

## Синхронизация с экосистемой

- Канон правил AIKIVAVIORA: `AIKIVAVIORA/00docs/ecosystem/00_AI_RULES.md`
- Реестр NEXUS: `AIKIVAVIORA/01core/AIKIVAVIORA_NEXUS/02_registry/PROJECTS_INDEX.md`
- Мост зон: `Cursor/PROFILE/CHATGPT_BRIDGE.md`

Обновления между зонами — **только через пользователя**.
