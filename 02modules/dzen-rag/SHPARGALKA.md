# Dzen RAG — шпаргалка запуска

> Положение: `02modules/dzen-rag/SHPARGALKA.md`

## Карта папок

```
AIKIVAVIORA_v.3_Cursor\
├── tools\ingest_from_g.py          ← загрузка статей с G: в индекс
├── 05data\rag_index\               ← ChromaDB (не трогать руками)
├── config\paths.example.env        ← образец настроек
└── 02modules\dzen-rag\
    ├── SHPARGALKA.md               ← этот файл
    ├── start-api.ps1               ← запуск API из папки dzen-rag
    ├── backend\
    │   ├── app.py                  ← FastAPI
    │   ├── .env                    ← ваши ключи (не в git!)
    │   └── run.ps1                 ← запуск API (порт 8001)
    └── frontend\
        └── index.html              ← чат в браузере
```

**Контент (статьи):**  
`G:\3_Дзен\1G_канал про ИИ_статьи на Дзене\4_AIKIVAVIORA_база-RAG\`

---

## 1. Первый раз — настройки

```powershell
cd 02modules\dzen-rag\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\..\..\config\paths.example.env .env
```

Откройте `backend\.env` и проверьте:

| Переменная | Что писать |
|------------|------------|
| `RAG_SOURCE_PATH` | Папка на G: (модуль или весь канон) |
| `DEEPSEEK_API_KEY` | Ключ с platform.deepseek.com |
| `LM_STUDIO_MODEL` | См. раздел LM Studio ниже |

---

## 2. Ingest (статьи → индекс)

**Из корня проекта:**

```powershell
cd <корень AIKIVAVIORA_v.3_Cursor>

# один модуль:
$env:RAG_SOURCE_PATH = "G:\3_Дзен\1G_канал про ИИ_статьи на Дзене\4_AIKIVAVIORA_база-RAG\модуль 1.3 - 24.05.2026"
.\02modules\dzen-rag\backend\.venv\Scripts\python.exe tools\ingest_from_g.py --reset

# весь канон на G: (без $env — путь из .env):
.\02modules\dzen-rag\backend\.venv\Scripts\python.exe tools\ingest_from_g.py --reset
```

Ожидаемо для модуля 1.3: **18 файлов → 126 чанков**.

---

## 3. Запуск API

**Важно:** uvicorn запускать из папки **`backend`** (там лежит `app.py`).

Или **двойной клик** / ярлык на рабочем столе:

```
02modules\dzen-rag\start-api.bat
```

(откроет чат в браузере и поднимет API на порту 8001)

```powershell
cd ...\02modules\dzen-rag\backend
.\run.ps1
```

Порт **8001** (8000 на вашем ПК часто занят Windows).

Остановка: **Ctrl+C** в терминале.

---

## 4. Где смотреть результат

| Что | URL |
|-----|-----|
| **Чат (фронт)** | http://127.0.0.1:8001/ui/ |
| Swagger (ручные тесты) | http://127.0.0.1:8001/docs |
| Статус индекса | http://127.0.0.1:8001/health |

---

## 5. DeepSeek

1. Ключ в `backend\.env` → `DEEPSEEK_API_KEY=sk-...`
2. Перезапустить API (Ctrl+C → `.\run.ps1`)
3. В чате провайдер: **auto** или **deepseek**
4. В `/health`: `"llm_deepseek_configured": true`

---

## 6. LM Studio (локально, опционально)

1. Откройте **LM Studio**
2. Загрузите модель (Models → выбрать → Load)
3. Вкладка **Local Server** → **Start Server** (порт **1234**)
4. Посмотрите имя модели в интерфейсе сервера (часто подходит `local-model`)
5. В `backend\.env`:

```
LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
LM_STUDIO_MODEL=local-model
```

6. Перезапустить API
7. В чате провайдер: **lm_studio**

Если `LM_STUDIO_MODEL` пустой — **auto** использует только DeepSeek (если есть ключ).

---

## 7. Типичные ошибки

| Симптом | Причина | Решение |
|---------|---------|---------|
| `Could not import module "app"` | Запуск не из `backend` | `cd backend` → `.\run.ps1` |
| `WinError 10013` на 8000 | Порт занят | Используйте **8001** (`run.ps1`) |
| `no_llm_configured` | Старый процесс / нет ключа | Ctrl+C, перезапуск; проверить `.env` |
| `chunks_in_index: 0` | Не делали ingest | `tools\ingest_from_g.py --reset` |
| `answer: null`, есть `sources` | Провайдер `none` или нет LLM | Поставить `auto` + ключ DeepSeek |

---

## 8. После новых файлов на G:

1. Положить PDF/md в слот модуля на G:
2. `ingest_from_g.py --reset`
3. Перезапуск API (если был остановлен — не обязательно для индекса)
4. Вопрос в http://127.0.0.1:8001/ui/

---

## 9. Endpoint (Swagger /docs)

| Endpoint | Зачем | Тело / форма |
|----------|-------|--------------|
| GET `/health` | статус, `docs_count` | — |
| POST `/upload` | загрузка PDF/TXT (ДЗ-7) | multipart: `file` |
| POST `/ingest` | переиндексация с G: | `{"reset": true}` |
| POST `/chat` | вопрос | `{"query": "..."}` или `{"question": "..."}` |
