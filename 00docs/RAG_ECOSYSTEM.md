# RAG-экосystem для канала Дзен (v.3)

## Цепочка

```
G: .../4_AIKIVAVIORA_база-RAG/             ← канон (модули + слоты 1F–9F, .md/.txt)
        ↓ tools/ingest_from_g.py
05data/rag_index/                           ← Chroma (локально, не в git)
        ↓
02modules/dzen-rag/backend                  ← FastAPI /chat
        ↓
DeepSeek API  |  LM Studio :1234
```

## Связанные, но отдельные

| Компонент | Где | Связь |
|-----------|-----|--------|
| DzenNeuro | `Projects/ДЗ-5/DzenNeuro` | генерация/редактура, не retrieval |
| Telegram bot | `Claude/Projects/rag-telegram-bot` | клиент к RAG API (будущее) |
| Школа RAG | FAISS + 88 чанков | первый прототип ingest |

## ДЗ-7 (курс)

Методичка TrailCamp в `Projects/ДЗ-7/` — **архитектура** (FastAPI, Chroma, чанки).  
Имя TrailCamp и Gemini **не** используем в v.3.

## Следующие шаги (когда скажете «делай RAG»)

1. Создать папку на `G:` и перенести 5–10 статей в канон.
2. Реализовать ingest + backend в `02modules/dzen-rag/`.
3. Подключить переключатель DeepSeek / LM Studio.
