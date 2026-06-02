# Публикация репозитория (чек-лист)

Перед `git push` в **публичный** GitHub/GitLab пройдите проверку.

## Не должно попасть в remote

| Категория | Примеры |
|-----------|---------|
| Секреты | `backend/.env`, любой файл с `DEEPSEEK_API_KEY=sk-...` |
| Индекс RAG | `05data/rag_index/`, папки `chroma/` |
| Контент канала | PDF/MD с Дзен, полный снимок `dzen-rag-snapshot_*` |
| Локальные venv | `backend/.venv/` |
| Инвентари G: | `00docs/_rag_*.txt` и др. `00docs/_*` |

## Можно публиковать

- Исходники `02modules/dzen-rag/`, `aikivaviora_shared/`, `tools/ingest_from_g.py`
- `*.env.example` **только с пустым ключом**
- Документация без реальных путей к вашему диску (см. `config/paths.example.env`)

## Команды перед push

```powershell
cd <корень репозитория>
.\scripts\check-public-push.ps1
git status
git push -u origin master
```

Скрипт завершится с ошибкой, если в индексе git есть `.env`, индекс Chroma или подозрительные ключи.

## Первый push (если remote ещё нет)

После создания пустого репозитория на GitHub:

```powershell
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin master
```

В ПЗ (`09education/DZ-7_пояснительная_записка_dzen-rag.md`) вставьте URL репозитория в строку **«Репозиторий GitHub»**.

## После клонирования (для других / для себя на новой машине)

```powershell
cd 02modules\dzen-rag\backend
copy ..\..\..\config\paths.example.env .env
# Заполнить DEEPSEEK_API_KEY локально, не коммитить
pip install -r requirements.txt
# Положить PDF/MD в data/rag_source/ или задать RAG_SOURCE_PATH в .env
```

Подробнее по угрозам API: `02modules/dzen-rag/SECURITY.md`
