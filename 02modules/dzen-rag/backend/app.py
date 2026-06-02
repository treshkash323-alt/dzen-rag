from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aikivaviora_shared.rag.config import SUPPORTED_SUFFIXES  # noqa: E402
from aikivaviora_shared.rag.ingest import ingest_directory, ingest_uploaded_file  # noqa: E402
from aikivaviora_shared.rag.llm import choose_provider, generate_answer  # noqa: E402
from aikivaviora_shared.rag.store import RagStore  # noqa: E402
from aikivaviora_shared.rag.config import load_settings  # noqa: E402

app = FastAPI(title="Dzen RAG", version="0.3.1")

MAX_QUERY_CHARS = 8000
MAX_UPLOAD_BYTES = int(os.environ.get("RAG_MAX_UPLOAD_MB", "25")) * 1024 * 1024

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
_cors_raw = os.environ.get(
    "RAG_CORS_ORIGINS",
    "http://127.0.0.1:8001,http://localhost:8001,http://127.0.0.1:8000,http://localhost:8000",
)
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")


def get_settings():
    """Читает .env заново — после правки backend\\.env достаточно перезапустить uvicorn."""
    return load_settings()


def _resolve_ingest_source(settings, raw: str | None) -> Path:
    """Ingest только внутри RAG_SOURCE_PATH (защита от обхода каталогов)."""
    allowed_root = settings.source_path.resolve()
    source = Path(raw).expanduser().resolve() if raw else allowed_root
    if source == allowed_root:
        return source
    try:
        source.relative_to(allowed_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail="source_path must be inside configured RAG_SOURCE_PATH",
        ) from exc
    return source


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

    query: str | None = Field(
        default=None,
        description="Вопрос (основное поле)",
        examples=["Что делегировать ИИ инженеру?"],
    )
    question: str | None = Field(
        default=None,
        description="Алиас для методички TrailCamp (то же, что query)",
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

    @model_validator(mode="after")
    def resolve_query(self) -> "ChatRequest":
        text = (self.query or self.question or "").strip()
        if not text:
            raise ValueError("query or question is required")
        self.query = text
        return self


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    store = RagStore(settings)
    count = store.chunk_count
    return {
        "status": "ok",
        "module": "dzen-rag",
        "phase": "rag",
        "docs_count": count,
        "chunks_in_index": count,
        "source_path": str(settings.source_path),
        "index_path": str(settings.index_path),
        "index_exists": settings.index_path.is_dir(),
        "embedding_model": settings.embedding_model,
        "llm_deepseek_configured": bool(settings.deepseek_api_key),
        "llm_lm_studio_configured": bool(settings.lm_studio_model),
        "llm_lm_studio_url": settings.lm_studio_base_url,
        "llm_lm_studio_model": settings.lm_studio_model,
        "llm_default_provider": settings.llm_default,
        "llm_auto_resolves_to": choose_provider(settings),
    }


@app.get("/", include_in_schema=False)
def root_ui():
    return RedirectResponse(url="/ui/")


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    """Загрузка PDF/TXT через API (требование ДЗ-7 / TrailCamp)."""
    settings = get_settings()
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Only .pdf, .txt and .md files are allowed",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        result = ingest_uploaded_file(settings, filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store = RagStore(settings)
    result["total_chunks_in_index"] = store.chunk_count
    return result


@app.post("/ingest")
def ingest(body: IngestRequest | None = None) -> dict[str, Any]:
    settings = get_settings()
    body = body or IngestRequest()
    source = _resolve_ingest_source(settings, body.source_path)
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
            detail="Index is empty. Run POST /upload, POST /ingest or tools/ingest_from_g.py first.",
        )

    query = body.query or ""
    if len(query) > MAX_QUERY_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long (max {MAX_QUERY_CHARS} characters)",
        )
    chunks = store.query(query, top_k=body.top_k)
    sources = [
        {
            "text": chunk.text,
            "metadata": chunk.metadata,
            "score": chunk.score,
        }
        for chunk in chunks
    ]
    source_names = sorted(
        {
            (s["metadata"] or {}).get("filename")
            or (s["metadata"] or {}).get("relative_path")
            for s in sources
        }
        - {None}
    )

    provider_choice = None if body.provider == "auto" else body.provider
    if body.provider == "none":
        return {
            "query": query,
            "question": query,
            "answer": None,
            "llm_provider": None,
            "llm_status": "retrieval_only",
            "sources": sources,
            "source_files": source_names,
        }

    answer, provider, llm_status = generate_answer(
        settings,
        query,
        chunks,
        provider=provider_choice,  # type: ignore[arg-type]
    )
    return {
        "query": query,
        "question": query,
        "answer": answer,
        "llm_provider": provider,
        "llm_status": llm_status,
        "sources": sources,
        "source_files": source_names,
    }
