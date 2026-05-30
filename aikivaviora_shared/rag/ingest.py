from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aikivaviora_shared.rag.chunker import split_text
from aikivaviora_shared.rag.config import RagSettings
from aikivaviora_shared.rag.loaders import discover_documents, load_text
from aikivaviora_shared.rag.store import RagStore, make_chunk_id


@dataclass
class IngestResult:
    source_path: Path
    index_path: Path
    files_found: int = 0
    files_ingested: int = 0
    chunks_written: int = 0
    skipped_empty: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return ingest_result_to_dict(self)


def ingest_result_to_dict(result: IngestResult) -> dict:
    return {
        "source_path": str(result.source_path),
        "index_path": str(result.index_path),
        "files_found": result.files_found,
        "files_ingested": result.files_ingested,
        "chunks_written": result.chunks_written,
        "skipped_empty": result.skipped_empty,
        "errors": result.errors,
        "total_chunks_in_index": result.chunks_written,
    }


def ingest_directory(
    settings: RagSettings,
    *,
    source: Path | None = None,
    reset: bool = False,
) -> IngestResult:
    source_path = (source or settings.source_path).resolve()
    result = IngestResult(
        source_path=source_path,
        index_path=settings.index_path.resolve(),
    )

    if not source_path.is_dir():
        result.errors.append(f"Source not found: {source_path}")
        return result

    files = discover_documents(source_path)
    result.files_found = len(files)

    store = RagStore(settings)
    if reset:
        store.reset()

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for file_path in files:
        try:
            text = load_text(file_path)
        except Exception as exc:
            result.errors.append(f"{file_path.name}: {exc}")
            continue

        if not text.strip():
            result.skipped_empty += 1
            continue

        chunks = split_text(text, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            result.skipped_empty += 1
            continue

        rel_path = file_path.resolve().relative_to(source_path)
        module_hint = _module_hint(source_path, rel_path)

        for idx, chunk in enumerate(chunks):
            ids.append(make_chunk_id(source_path, file_path, idx))
            documents.append(chunk)
            metadatas.append(
                {
                    "source": str(file_path),
                    "relative_path": rel_path.as_posix(),
                    "filename": file_path.name,
                    "suffix": file_path.suffix.lower(),
                    "module": module_hint,
                    "chunk_index": idx,
                    "chunk_total": len(chunks),
                }
            )

        result.files_ingested += 1
        result.chunks_written += len(chunks)

    store.upsert_chunks(ids=ids, documents=documents, metadatas=metadatas)
    return result


def _module_hint(source_path: Path, rel_path: Path) -> str:
    if source_path.name.lower().startswith("модуль"):
        return source_path.name
    parts = rel_path.parts
    if not parts:
        return ""
    first = parts[0]
    if first.lower().startswith("модуль"):
        return first
    return first
