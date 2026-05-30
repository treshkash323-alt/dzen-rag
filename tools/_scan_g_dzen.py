"""One-off scan G: Dzen tree — output UTF-8 to stdout/file."""
from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "00docs" / "_scan_g_dzen.txt"


def walk(root: Path, depth: int = 0, max_depth: int = 3, lines: list[str] | None = None) -> list[str]:
    if lines is None:
        lines = []
    if depth > max_depth or not root.is_dir():
        return lines
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError as e:
        lines.append(f"{'  ' * depth}[ERR] {root}: {e}")
        return lines
    for p in entries:
        rel = p.relative_to(root.parents[max(0, len(root.parents) - 10)] if False else p.parent)
        if p.is_dir():
            lines.append(f"{'  ' * depth}[DIR] {p.name}/")
            walk(p, depth + 1, max_depth, lines)
        elif depth <= max_depth:
            lines.append(f"{'  ' * depth}{p.name}")
    return lines


def main() -> int:
    roots = [
        Path(r"G:\3_Дзен"),
        Path(r"G:\3_Дзен\1G_канал про ИИ_статьи на Дзене"),
        Path(r"C:\Users\kash-\Python_kash\Cursor\Dzen\модуль 1.3 - 24.05.2026"),
    ]
    all_lines: list[str] = []
    for root in roots:
        all_lines.append(f"\n=== {root} ===")
        if not root.exists():
            all_lines.append("  (not found)")
            continue
        if root.is_file():
            all_lines.append("  (file)")
            continue
        all_lines.extend(walk(root, 0, 2))
    text = "\n".join(all_lines)
    OUT.write_text(text, encoding="utf-8")
    print(f"Written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
