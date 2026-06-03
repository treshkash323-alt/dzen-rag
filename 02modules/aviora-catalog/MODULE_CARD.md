# MODULE_CARD — aviora-catalog

| Поле | Значение |
|------|----------|
| ID | aviora-catalog |
| Порт | 8002 |
| Ветка | Cursor v.3 |
| Статус | v0.3.8 |

## Назначение

Веб-каталог для рутины с файлами и папками `Python_kash`: просмотр, правка, поиск, zip, лёгкая правка изображений, LLM по текущему файлу.

## Уже в UI (v0.3.8)

- **Запуск** — `start-api.bat` (один сервер :8002; порт занят = уже работает)
- **Scan** — полоса прогресса; индекс на диск `05data/aviora_catalog_index.json`
- **Чат LM Studio** — модель из `/v1/models` (не local-model)
- **Поиск** — Enter после Scan

## v0.3.0

- **Diff** — лента Код → Diff; пути или SEQ; unified diff в модалке
- **Пакетный снимок** — Код → Пакет; `BATCH-…` + `batches/*.json`
- **Карта филиалов** — вкладка **Карта**; модули × Cursor/Claude/AIKIVAVIORA
- **Снимки кода** — `05data/aviora_code_snapshots/`, SEQ в имени
- **Просмотр code** — read-only в редакторе

## v0.2.2

- **Лента с вкладками** — Главная · Вид · Студия · Сервис
- **Отмена / Повтор** — Ctrl+Z / Ctrl+Y

## Ранее (v0.1.9)

- **Поделиться** — путь в буфер (кнопка в тулбаре и над редактором, Ctrl+E)
- **Экспорт** — HTML / TXT из .md; DOCX — v0.2
- **Фильтры md/pdf/…** — список файлов в текущей папке (не замена Scan)
- **Фото PS-lite** — открыть .jpg/.png → Crop, поворот, Save image
- **Figma-lite** — вкладка «Макет» / «Студия»: рамки, стикеры, **Сохранить макет** → `имя.aviora.json` рядом с .md

## Roadmap (TODO)

- см. `docs/ROADMAP_WORKSPACE.md` — мультифилиалы, diff, очередь задач
- md→docx (pandoc)
- rar/7z extract
- SMTP отправка
- pause scan между папками
- настраиваемые shortcuts
- brightness/contrast, text on image
- batch resize
- i18n EN
- Docker compose production
- fork transform для «Dzen content desk»

## Не входит в MVP

Каталог всего ПК, md→Word, полный Office в браузере, биллинг, публичный деплой без auth.
