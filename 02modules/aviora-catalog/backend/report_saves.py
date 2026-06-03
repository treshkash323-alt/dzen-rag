"""Сохранение отчётов поиска и чата в каталог Python_kash."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Settings
from paths import catalog_root

SAVES_REL_DIR = "05data/aviora_search_saves"


def saves_dir(settings: Settings) -> Path:
    target = (catalog_root(settings) / SAVES_REL_DIR).resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def _slug(text: str, *, max_len: int = 48) -> str:
    s = re.sub(r"[^\w\-]+", "_", (text or "").strip(), flags=re.UNICODE)
    s = s.strip("_")[:max_len]
    return s or "report"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _rel_path(settings: Settings, target: Path) -> str:
    root = catalog_root(settings)
    return target.resolve().relative_to(root.resolve()).as_posix()


def format_search_markdown(
    *,
    query: str,
    branch: str,
    results: list[dict[str, Any]],
    catalog_version: str,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Поиск каталога: {query}",
        "",
        f"- **Дата:** {now}",
        f"- **Ветка:** {branch or 'все'}",
        f"- **Найдено:** {len(results)}",
        f"- **Aviora Catalog:** v{catalog_version}",
        "",
        "★ — главный файл в группе дубликатов (см. Scan + canonical).",
        "",
        "## Результаты",
        "",
    ]
    if not results:
        lines.append("_Нет совпадений._")
    else:
        for i, r in enumerate(results, 1):
            star = "★ " if r.get("is_primary") else ""
            dup = r.get("duplicate_count") or 0
            dup_note = f" _(копий в группе: {dup})_" if dup > 1 and not r.get("is_primary") else ""
            path = r.get("path") or ""
            name = r.get("name") or Path(path).name
            lines.append(f"{i}. {star}**{path}**{dup_note}")
            if name and name != Path(path).name:
                lines.append(f"   - имя: {name}")
            sn = (r.get("snippet") or "").strip()
            if sn:
                lines.append(f"   - фрагмент: …{sn}…")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_chat_markdown(
    *,
    question: str,
    answer: str,
    file_path: str,
    catalog_version: str,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Ответ чата каталога",
        "",
        f"- **Дата:** {now}",
        f"- **Aviora Catalog:** v{catalog_version}",
    ]
    if file_path:
        lines.append(f"- **Открытый файл:** {file_path}")
    lines.extend(
        [
            "",
            "## Вопрос",
            "",
            question.strip() or "—",
            "",
            "## Ответ",
            "",
            answer.strip() or "—",
            "",
        ]
    )
    return "\n".join(lines)


def save_search_report(
    settings: Settings,
    *,
    query: str,
    branch: str,
    results: list[dict[str, Any]],
    catalog_version: str,
) -> dict[str, Any]:
    body = format_search_markdown(
        query=query,
        branch=branch,
        results=results,
        catalog_version=catalog_version,
    )
    fname = f"search_{_ts()}_{_slug(query)}.md"
    target = saves_dir(settings) / fname
    target.write_text(body, encoding="utf-8")
    return {"ok": True, "path": _rel_path(settings, target), "bytes": len(body.encode("utf-8"))}


def save_chat_report(
    settings: Settings,
    *,
    question: str,
    answer: str,
    file_path: str,
    catalog_version: str,
) -> dict[str, Any]:
    body = format_chat_markdown(
        question=question,
        answer=answer,
        file_path=file_path,
        catalog_version=catalog_version,
    )
    fname = f"chat_{_ts()}_{_slug(question)}.md"
    target = saves_dir(settings) / fname
    target.write_text(body, encoding="utf-8")
    return {"ok": True, "path": _rel_path(settings, target), "bytes": len(body.encode("utf-8"))}
