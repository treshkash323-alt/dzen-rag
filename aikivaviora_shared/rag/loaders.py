from __future__ import annotations

from pathlib import Path

from aikivaviora_shared.rag.config import SUPPORTED_SUFFIXES


def discover_documents(source: Path) -> list[Path]:
    if not source.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
    return files


def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    if suffix == ".pdf":
        return _load_pdf(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError("Install pypdf: pip install pypdf") from exc

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()
