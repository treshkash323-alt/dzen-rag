#!/usr/bin/env python3
"""Create RAG canon folder tree on G: — mirrors module/slot naming, empty slots only."""

from __future__ import annotations

from pathlib import Path

BASE = Path(r"G:\3_Дзен\1G_канал про ИИ_статьи на Дзене\4_AIKIVAVIORA_база-RAG")

# Slot grids by module era (from 2_Архив + рабочие модули на G:)
MODULES: list[tuple[str, list[str]]] = [
    (
        "модуль 1.1 - 10.05.2026",
        [
            "1F_08-00_видеоновости",
            "2F_09-00_урок 1_Инженер",
            "3F_09-30_урок 2_Учитель",
            "4F_10-00_урок 3_Родитель",
            "5F_10-30_урок 4_Школьник",
            "6F_15-00_практика 1-2_Инженер-Учитель",
            "7F_15-30_практика 3-4_Родитель-Школьник",
        ],
    ),
    (
        "модуль 1.2 - 17.05.2026",
        [
            "1F_08-00_видеоновости",
            "1F_08-30_видеоновости текстом",
            "2F_09-00_урок 1_Инженер",
            "3F_09-30_урок 2_Учитель",
            "4F_10-00_урок 3_Родитель",
            "5F_10-30_урок 4_Помощник Школьника",
            "6F_15-00_практика 1-2_Инженер-Учитель",
            "7F_15-30_практика 3-4_Родитель-Школьник",
        ],
    ),
    (
        "модуль 1.3 - 24.05.2026",
        [
            "1F_08-00_видеоновости",
            "1F_08-30_видеоновости текстом",
            "2F_09-00_урок 1_Инженер",
            "3F_09-30_урок 2_Учитель",
            "4F_10-00_урок 3_Родитель",
            "5F_10-30_урок 4_Помощник Школьника",
            "6F_11-00_практика Родитель",
            "7F_11-30_практика Помощник Школьника",
            "8F_15-00_практика Инженер",
            "9F_15-30_практика Учитель",
        ],
    ),
    (
        "модуль 1.4 - 31.05.2026",
        [
            "1F_08-00_видеоновости",
            "1F_08-30_видеоновости текстом",
            "2F_09-00_урок 1_Инженер",
            "3F_09-30_урок 2_Учитель",
            "4F_10-00_урок 3_Родитель",
            "5F_10-30_урок 4_Помощник Школьника",
            "6F_11-00_практика Родитель",
            "7F_11-30_практика Помощник Школьника",
            "8F_15-00_практика Инженер",
            "9F_15-30_практика Учитель",
        ],
    ),
]

SLOT_README = """# Слот RAG — только чистовик с канала

Сюда кладите **финальный** текст публикации (как на Дзене после правок).

## Формат

- `.md` или `.txt` — предпочтительно
- Один файл = одна публикация (статья, текст новостного выпуска, урок)
- Примеры имён: `статья.md`, `текст_для_озвучки.md`, `урок_теория.md`

## Не класть

- docx, mp4, png (исходники остаются в рабочих папках модуля)
- черновики и проработку
- автоматические выгрузки без проверки

Правила канала: `Cursor/Dzen/DZEN_FORMAT.md` (в промпт, не дублировать сюда).
"""

ROOT_README = """# 4_AIKIVAVIORA_база-RAG

Каноническая база для RAG (AIKIVAVIORA v.3 Cursor).

## Зачем отдельная папка

- `2_Архив-опубликовано` — рабочий архив (docx, медиа, черновики)
- **Здесь** — только тексты **как на канале**, для индекса Chroma

## Структура

Повторяет вашу сетку выпусков:

```
модуль X.Y - ДД.ММ.ГГГГ/
  1F_08-00_видеоновости/
  1F_08-30_видеоновости текстом/
  2F_09-00_урок 1_Инженер/
  ...
```

В каждый слот — один или несколько `.md` / `.txt` после публикации.

## Как наполнять

1. Опубликовали на Дзене → скопировали **финальный** текст в слот (вручную).
2. Новый модуль → скопируйте папку `_шаблон_модуля_9F/` и переименуйте дату.

## Ingest

`RAG_SOURCE_PATH` указывает на эту папку целиком (рекурсивно все .md/.txt).

Код: `Cursor/AIKIVAVIORA_v.3_Cursor/tools/ingest_from_g.py`

## Связанные пути

| Что | Где |
|-----|-----|
| Рабочие модули | `1G_.../модуль 1.4 - 31.05.2026/` и `2_Архив-опубликовано/` |
| Черновики Cursor | `Cursor/Dzen/` |
| Индекс (генерируется) | `AIKIVAVIORA_v.3_Cursor/05data/rag_index/` |
"""


def main() -> int:
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "README.md").write_text(ROOT_README, encoding="utf-8")

    created: list[str] = []
    for module_name, slots in MODULES:
        mod = BASE / module_name
        mod.mkdir(parents=True, exist_ok=True)
        for slot in slots:
            slot_dir = mod / slot
            slot_dir.mkdir(parents=True, exist_ok=True)
            readme = slot_dir / "README.md"
            if not readme.exists():
                readme.write_text(SLOT_README, encoding="utf-8")
            created.append(str(slot_dir.relative_to(BASE)))

    # Template for future modules (9F grid from 1.3+)
    template = BASE / "_шаблон_модуля_9F"
    _, slots_9f = MODULES[-1]
    for slot in slots_9f:
        d = template / slot
        d.mkdir(parents=True, exist_ok=True)
        (d / "README.md").write_text(SLOT_README, encoding="utf-8")

    log = BASE / "_created_by_v3.txt"
    log.write_text(
        "Created by AIKIVAVIORA v.3 Cursor\n" + "\n".join(created),
        encoding="utf-8",
    )
    print(f"OK: {BASE}")
    print(f"Modules: {len(MODULES)}, slots: {len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
