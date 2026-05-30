from __future__ import annotations


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            split_at = _find_split_point(text, start, end)
            if split_at <= start:
                split_at = end
            end = split_at

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= length:
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks


def _find_split_point(text: str, start: int, end: int) -> int:
    window = text[start:end]
    for separator in ("\n\n", "\n", ". ", " "):
        idx = window.rfind(separator)
        if idx > len(window) * 0.4:
            return start + idx + len(separator)
    return end
