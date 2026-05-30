# aikivaviora_shared

Общие пакеты филиала v.3 (импорт из backend и `tools/`).

## rag/

Ядро RAG pipeline:

- `config.py` — пути и env
- `loaders.py` — `.md`, `.txt`, `.pdf` (pypdf)
- `chunker.py` — разбиение текста
- `store.py` — ChromaDB
- `ingest.py` — batch ingest
- `llm.py` — DeepSeek / LM Studio (опционально) (v.3)

Не копировать целиком `AIKIVAVIORA/aikivaviora_shared/`.

При необходимости — ссылаться на канон:

`C:\Users\kash-\Python_kash\AIKIVAVIORA\aikivaviora_shared\`

Или импортировать отдельные шаблоны после согласования с пользователем.
