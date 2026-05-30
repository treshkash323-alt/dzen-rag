from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aikivaviora_shared.rag.config import load_settings  # noqa: E402
from aikivaviora_shared.rag.ingest import ingest_directory  # noqa: E402
from aikivaviora_shared.rag.llm import generate_answer  # noqa: E402
from aikivaviora_shared.rag.store import RagStore  # noqa: E402

app = FastAPI(title="Dzen RAG", version="0.2.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")


def get_settings():
    """Читает .env заново — после правки backend\\.env достаточно перезапустить uvicorn."""
    return load_settings()


class IngestRequest(BaseModel):
    """Переиндексация файлов с G: → Chroma. Не для вопросов."""

    source_path: str | None = Field(
        default=None,
        description="Папка на G: (если пусто — из .env RAG_SOURCE_PATH)",
        examples=["G:\\3_Дзен\\...\\модуль 1.3 - 24.05.2026"],
    )
    reset: bool = Field(
        default=False,
        description="true = очистить индекс перед загрузкой",
    )


class ChatRequest(BaseModel):
    """Вопрос к RAG: поиск по статьям + опционально ответ LLM."""

    query: str = Field(
        min_length=1,
        description="Ваш вопрос по материалам канала",
        examples=["Что делегировать ИИ инженеру?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Сколько фрагментов статей подтянуть",
    )
    provider: Literal["auto", "deepseek", "lm_studio", "none"] = Field(
        default="auto",
        description="auto=DeepSeek если есть ключ; none=только фрагменты без ответа",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    store = RagStore(settings)
    return {
        "status": "ok",
        "module": "dzen-rag",
        "phase": "rag",
        "source_path": str(settings.source_path),
        "index_path": str(settings.index_path),
        "index_exists": settings.index_path.is_dir(),
        "chunks_in_index": store.chunk_count,
        "embedding_model": settings.embedding_model,
        "llm_deepseek_configured": bool(settings.deepseek_api_key),
        "llm_lm_studio_configured": bool(settings.lm_studio_model),
        "llm_lm_studio_url": settings.lm_studio_base_url,
    }


@app.get("/", include_in_schema=False)
def root_ui():
    return RedirectResponse(url="/ui/")


@app.post("/ingest")
def ingest(body: IngestRequest | None = None) -> dict[str, Any]:
    settings = get_settings()
    body = body or IngestRequest()
    source = Path(body.source_path) if body.source_path else settings.source_path
    if not source.is_dir():
        raise HTTPException(status_code=400, detail=f"Source not found: {source}")

    result = ingest_directory(settings, source=source, reset=body.reset)
    store = RagStore(settings)
    payload = result.to_dict()
    payload["total_chunks_in_index"] = store.chunk_count
    return payload


@app.post("/chat")
def chat(body: ChatRequest) -> dict[str, Any]:
    settings = get_settings()
    store = RagStore(settings)
    if store.chunk_count == 0:
        raise HTTPException(
            status_code=503,
            detail="Index is empty. Run POST /ingest or tools/ingest_from_g.py first.",
        )

    chunks = store.query(body.query, top_k=body.top_k)
    sources = [
        {
            "text": chunk.text,
            "metadata": chunk.metadata,
            "score": chunk.score,
        }
        for chunk in chunks
    ]

    provider_choice = None if body.provider == "auto" else body.provider
    if body.provider == "none":
        return {
            "query": body.query,
            "answer": None,
            "llm_provider": None,
            "llm_status": "retrieval_only",
            "sources": sources,
        }

    answer, provider, llm_status = generate_answer(
        settings,
        body.query,
        chunks,
        provider=provider_choice,  # type: ignore[arg-type]
    )
    return {
        "query": body.query,
        "answer": answer,
        "llm_provider": provider,
        "llm_status": llm_status,
        "sources": sources,
    }
