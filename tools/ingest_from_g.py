#!/usr/bin/env python3
"""Ingest published Dzen texts from RAG_SOURCE_PATH into Chroma index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aikivaviora_shared.rag import ingest_directory, load_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest RAG corpus into ChromaDB")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Override RAG_SOURCE_PATH (folder with .md/.txt/.pdf)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing collection before ingest",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary",
    )
    args = parser.parse_args()

    settings = load_settings()
    source = args.source or settings.source_path

    if not source.is_dir():
        print(f"Источник не найден: {source}", file=sys.stderr)
        print("Создайте канон на G: или задайте RAG_SOURCE_PATH.", file=sys.stderr)
        return 1

    print(f"Ingest: {source}")
    print(f"Index:  {settings.index_path}")
    print(f"Model:  {settings.embedding_model}")
    if args.reset:
        print("Mode:   reset collection")

    result = ingest_directory(settings, source=source, reset=args.reset)
    summary = result.to_dict()

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"Файлов найдено:     {result.files_found}")
        print(f"Файлов проиндекс.: {result.files_ingested}")
        print(f"Чанков записано:    {result.chunks_written}")
        print(f"Пустых пропущено:   {result.skipped_empty}")
        if result.errors:
            print(f"Ошибок:             {len(result.errors)}")
            for err in result.errors:
                print(f"  - {err}")

    return 1 if result.errors and result.chunks_written == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
