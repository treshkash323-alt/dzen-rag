from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from aikivaviora_shared.rag.config import RagSettings


@dataclass
class RetrievedChunk:
    text: str
    metadata: dict[str, Any]
    score: float | None


class RagStore:
    def __init__(self, settings: RagSettings) -> None:
        self.settings = settings
        self.settings.index_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(settings.index_path))
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def chunk_count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        self._client.delete_collection(self.settings.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.settings.collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        batch_size = 64
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            self._collection.upsert(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )

    def query(self, query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
        if self.chunk_count == 0:
            return []

        result = self._collection.query(
            query_texts=[query_text],
            n_results=min(top_k, self.chunk_count),
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        chunks: list[RetrievedChunk] = []
        for doc, meta, distance in zip(documents, metadatas, distances):
            score = None if distance is None else round(1.0 - float(distance), 4)
            chunks.append(
                RetrievedChunk(
                    text=doc or "",
                    metadata=meta or {},
                    score=score,
                )
            )
        return chunks


def make_chunk_id(source_root: Path, file_path: Path, chunk_index: int) -> str:
    rel = file_path.resolve().relative_to(source_root.resolve())
    return f"{rel.as_posix()}::{chunk_index}"
