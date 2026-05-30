# Границы филиалов

## Зоны и кто пишет код

| Зона | Путь | Агент / IDE | Можно менять из v.3? |
|------|------|-------------|----------------------|
| **Cursor v.3** | `Cursor/AIKIVAVIORA_v.3_Cursor/` | Cursor | **да** |
| Cursor workspace | `Cursor/` (PROFILE, Dzen, Projects) | Cursor | только по явному запросу |
| Codex / NEXUS | `AIKIVAVIORA/` | Codex, Copilot | **нет** |
| Claude | `Claude/` | Claude Code | **нет** |
| Прочие проекты | `Python_kash/*` | разное | **нет** |

## Иерархия авторитета (из NEXUS)

1. Пользователь  
2. Governance / правила (`00_AI_RULES`, `CURSOR.md`)  
3. Реестр и карточки модулей  
4. Агент  

## Домашки vs продукт

- `Projects/ДЗ-*` — материалы курса и сдача. Код домашки **не** смешивать с `02modules/` без решения пользователя.
- Продукт Дзен (RAG, Neuro) — **v.3**; домашки дают паттерны, не вторую копию.

## Контент vs код

- Тексты статей — `G:` или `Cursor/Dzen/`, не в git целиком.
- Индекс — `05data/rag_index/` (генерируемый, gitignore).

## Синхронизация

Между Claude ↔ Codex ↔ Cursor — через пользователя и `PROFILE/CHATGPT_BRIDGE.md`, не автоматически.
