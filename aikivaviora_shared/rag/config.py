from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path(
    r"G:\3_Дзен\1G_канал про ИИ_статьи на Дзене\4_AIKIVAVIORA_база-RAG"
)
DEFAULT_INDEX = PROJECT_ROOT / "05data" / "rag_index"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}
COLLECTION_NAME = "dzen_rag"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    defaults = (
        PROJECT_ROOT / "config" / "paths.example.env",
        PROJECT_ROOT / "02modules" / "dzen-rag" / "backend" / ".env.example",
    )
    for candidate in defaults:
        if candidate.is_file():
            load_dotenv(candidate, override=False)

    overrides = (
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "02modules" / "dzen-rag" / "backend" / ".env",
    )
    for candidate in overrides:
        if candidate.is_file():
            load_dotenv(candidate, override=True)


@dataclass(frozen=True)
class RagSettings:
    source_path: Path
    index_path: Path
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    deepseek_api_key: str | None
    deepseek_base_url: str
    lm_studio_base_url: str
    lm_studio_model: str | None
    collection_name: str = COLLECTION_NAME

    @property
    def has_llm(self) -> bool:
        return bool(self.deepseek_api_key) or bool(self.lm_studio_base_url)


def load_settings() -> RagSettings:
    _load_dotenv()
    index_raw = os.environ.get("RAG_INDEX_PATH", str(DEFAULT_INDEX))
    index_path = Path(index_raw)
    if not index_path.is_absolute():
        index_path = (PROJECT_ROOT / index_path).resolve()
    else:
        index_path = index_path.resolve()

    source_raw = os.environ.get("RAG_SOURCE_PATH", str(DEFAULT_SOURCE))
    source_path = Path(source_raw).expanduser()

    return RagSettings(
        source_path=source_path,
        index_path=index_path,
        embedding_model=os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        chunk_size=int(os.environ.get("RAG_CHUNK_SIZE", "900")),
        chunk_overlap=int(os.environ.get("RAG_CHUNK_OVERLAP", "120")),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
        deepseek_base_url=os.environ.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        ),
        lm_studio_base_url=os.environ.get(
            "LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1"
        ),
        lm_studio_model=os.environ.get("LM_STUDIO_MODEL") or None,
    )
