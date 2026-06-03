from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import Settings
from paths import (
    CODE_EXTS,
    CatalogError,
    catalog_root,
    detect_branch,
    resolve_path,
    should_skip_dir,
    should_skip_file,
)

SNAPSHOT_REL_DIR = "05data/aviora_code_snapshots"
BRANCH_CODES = {
    "Cursor": "CUR",
    "Claude": "CLA",
    "AIKIVAVIORA": "AVI",
    None: "GEN",
}


def snapshots_root(settings: Settings) -> Path:
    root = catalog_root(settings)
    target = (root / SNAPSHOT_REL_DIR).resolve()
    target.mkdir(parents=True, exist_ok=True)
    for code in BRANCH_CODES.values():
        (target / "by_branch" / code).mkdir(parents=True, exist_ok=True)
    return target


def _sanitize_slug(raw: str, max_len: int = 28) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw.strip())
    s = re.sub(r"-{2,}", "-", s).strip("-").lower()
    return (s[:max_len] or "item").strip("-")


def project_slug(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part == "02modules" and i + 1 < len(parts):
            return _sanitize_slug(parts[i + 1])
        if "dzen-rag" in part.lower():
            return "dzen-rag"
        if "aviora-catalog" in part.lower():
            return "aviora-catalog"
    skip = {
        "cursor",
        "claude",
        "aikivaviora",
        "backend",
        "frontend",
        "02modules",
        "00docs",
        "projects",
    }
    for part in reversed(parts[:-1]):
        if part.lower() not in skip and not part.startswith("."):
            return _sanitize_slug(part)
    return "root"


def revision_slug(rel: str, override: str | None = None) -> str:
    if override:
        o = override.strip()
        if re.fullmatch(r"v[\d.]+", o, re.I):
            return "v" + o.lstrip("vV").replace(".", "")
        return _sanitize_slug(o, 12)
    match = re.search(r"v\d+(?:\.\d+)*", rel, re.I)
    if match:
        return "v" + match.group(0).lstrip("vV").replace(".", "")
    return "main"


def branch_code(branch: str | None) -> str:
    return BRANCH_CODES.get(branch, "GEN")


def _registry_path(base: Path) -> Path:
    return base / "registry.json"


def _load_registry(base: Path) -> dict[str, Any]:
    path = _registry_path(base)
    if not path.is_file():
        data = {"schema": 1, "seq": 0, "recent": []}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    return json.loads(path.read_text(encoding="utf-8"))


def _save_registry(base: Path, data: dict[str, Any]) -> None:
    _registry_path(base).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _append_manifest(base: Path, seq: int, filename: str, source: str, note: str) -> None:
    line = f"| {seq:06d} | `{filename}` | `{source}` | {note or '—'} |\n"
    manifest = base / "MANIFEST.md"
    if not manifest.is_file():
        manifest.write_text(
            "# Журнал снимков кода\n\n| SEQ | Файл | Источник | Заметка |\n"
            "|-----|------|----------|---------|\n",
            encoding="utf-8",
        )
    text = manifest.read_text(encoding="utf-8")
    if "*(пусто" in text:
        text = text.replace(
            "| *(пусто — записи появятся после первого снимка в Catalog)* |\n", ""
        )
    if not text.endswith("\n"):
        text += "\n"
    manifest.write_text(text + line, encoding="utf-8")


def _read_text_file(path: Path, max_bytes: int) -> tuple[str, str]:
    raw = path.read_bytes()[:max_bytes]
    if not raw:
        return "", "utf-8"
    for enc in ("utf-8", "cp1251"):
        try:
            return raw.decode(enc), enc
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def snapshot_path_by_seq(settings: Settings, seq: int) -> str | None:
    base = snapshots_root(settings)
    prefix = f"{int(seq):06d}_"
    for found in base.rglob(f"{prefix}*"):
        if found.is_file() and found.suffix.lower() in CODE_EXTS:
            root = catalog_root(settings)
            return str(found.relative_to(root)).replace("\\", "/")
        if found.is_file() and found.name.endswith(".aviora.meta.json"):
            continue
    for found in base.rglob(f"{prefix}*"):
        if found.is_file() and not found.name.endswith(".meta.json"):
            root = catalog_root(settings)
            rel = str(found.relative_to(root)).replace("\\", "/")
            if rel.endswith(".aviora.meta.json"):
                continue
            return rel
    return None


def list_recent_snapshots(settings: Settings, limit: int = 40) -> list[dict[str, Any]]:
    base = snapshots_root(settings)
    reg = _load_registry(base)
    return list(reg.get("recent") or [])[:limit]


def _iter_code_files(folder: Path, settings: Settings) -> Iterator[Path]:
    if not folder.is_dir():
        return
    snap_marker = SNAPSHOT_REL_DIR.replace("\\", "/")
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not should_skip_dir(d, settings) and not d.startswith(".")
        )
        rel_dir = str(Path(dirpath).relative_to(folder)).replace("\\", "/")
        if snap_marker in rel_dir or rel_dir.startswith(snap_marker):
            dirnames.clear()
            continue
        for name in sorted(filenames):
            if should_skip_file(name, settings):
                continue
            path = Path(dirpath) / name
            if path.suffix.lower() not in CODE_EXTS:
                continue
            yield path


def create_code_snapshot(
    settings: Settings,
    *,
    source_path: str,
    note: str = "",
    rev: str | None = None,
    tags: list[str] | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    root = catalog_root(settings)
    source = resolve_path(settings, source_path)
    if not source.is_file():
        raise CatalogError("ERR_NOT_FILE", "Not a file")
    ext = source.suffix.lower()
    if ext not in CODE_EXTS:
        raise CatalogError(
            "ERR_NOT_CODE",
            f"Snapshot only for code types: {', '.join(sorted(CODE_EXTS))}",
        )

    max_b = settings.max_file_read_mb * 1024 * 1024
    raw = source.read_bytes()[:max_b]
    if not raw:
        raise CatalogError("ERR_EMPTY", "File is empty")

    content_hash = hashlib.sha256(raw).hexdigest()
    hash4 = content_hash[:4]
    rel = str(source.relative_to(root)).replace("\\", "/")
    branch = detect_branch(rel)
    br = branch_code(branch)
    proj = project_slug(rel)
    revision = revision_slug(rel, rev)
    base = snapshots_root(settings)

    reg = _load_registry(base)
    seq = int(reg.get("seq", 0)) + 1
    reg["seq"] = seq

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{seq:06d}_{br}_{proj}_{revision}_{ts}_{hash4}{ext}"
    dest_dir = base / "by_branch" / br
    dest_file = dest_dir / filename
    if dest_file.exists():
        raise CatalogError("ERR_EXISTS", "Snapshot file already exists")

    dest_file.write_bytes(raw)
    rel_dest = str(dest_file.relative_to(root)).replace("\\", "/")

    meta = {
        "schema": 1,
        "seq": seq,
        "filename": filename,
        "path": rel_dest,
        "source_path": rel,
        "branch": branch,
        "branch_code": br,
        "project": proj,
        "revision": revision,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sha256": content_hash,
        "size": len(raw),
        "note": note.strip(),
        "tags": tags or [],
        "batch_id": batch_id,
    }
    meta_path = dest_file.with_suffix(dest_file.suffix + ".aviora.meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    entry = {
        "seq": seq,
        "filename": filename,
        "path": rel_dest,
        "source_path": rel,
        "at": meta["created_at"],
    }
    recent = list(reg.get("recent") or [])
    recent.insert(0, entry)
    reg["recent"] = recent[:200]
    _save_registry(base, reg)
    _append_manifest(base, seq, filename, rel, note.strip())

    return {
        "ok": True,
        "seq": seq,
        "filename": filename,
        "path": rel_dest,
        "meta_path": str(meta_path.relative_to(root)).replace("\\", "/"),
        "branch_code": br,
        "project": proj,
        "revision": revision,
        "hash4": hash4,
        "meta": meta,
        "batch_id": batch_id,
    }


def create_batch_snapshots(
    settings: Settings,
    *,
    folder_path: str,
    note: str = "",
    rev: str | None = None,
    max_files: int = 120,
) -> dict[str, Any]:
    root = catalog_root(settings)
    folder = resolve_path(settings, folder_path)
    if not folder.is_dir():
        raise CatalogError("ERR_NOT_DIR", "Not a directory")
    rel_folder = str(folder.relative_to(root)).replace("\\", "/")
    batch_id = (
        f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}-"
        f"{project_slug(rel_folder)}"
    )
    created: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in _iter_code_files(folder, settings):
        if len(created) >= max_files:
            errors.append(
                {"path": str(path), "error": f"limit {max_files} files per batch"}
            )
            break
        rel = str(path.relative_to(root)).replace("\\", "/")
        try:
            item = create_code_snapshot(
                settings,
                source_path=rel,
                note=note,
                rev=rev,
                tags=["batch"],
                batch_id=batch_id,
            )
            created.append(item)
        except CatalogError as exc:
            errors.append({"path": rel, "error": exc.message})
        except Exception as exc:
            errors.append({"path": rel, "error": str(exc)})

    if not created:
        raise CatalogError("ERR_BATCH_EMPTY", "No code files found in folder")

    base = snapshots_root(settings)
    batches_dir = base / "batches"
    batches_dir.mkdir(exist_ok=True)
    manifest = {
        "batch_id": batch_id,
        "folder": rel_folder,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": note.strip(),
        "count": len(created),
        "seq_list": [c["seq"] for c in created],
        "items": [
            {
                "seq": c["seq"],
                "path": c["path"],
                "source_path": c["meta"]["source_path"],
            }
            for c in created
        ],
    }
    (batches_dir / f"{batch_id}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "batch_id": batch_id,
        "folder": rel_folder,
        "count": len(created),
        "created": created,
        "errors": errors,
        "manifest_path": str(
            (batches_dir / f"{batch_id}.json").relative_to(root)
        ).replace("\\", "/"),
    }


def resolve_diff_path(settings: Settings, path_or_seq: str) -> str:
    raw = (path_or_seq or "").strip().replace("\\", "/")
    if not raw:
        raise CatalogError("ERR_VALIDATION", "Empty path")
    if raw.isdigit():
        resolved = snapshot_path_by_seq(settings, int(raw))
        if not resolved:
            raise CatalogError("ERR_NOT_FOUND", f"Snapshot SEQ {raw} not found")
        return resolved
    resolve_path(settings, raw)
    return raw


def diff_catalog_paths(settings: Settings, path_a: str, path_b: str) -> dict[str, Any]:
    root = catalog_root(settings)
    max_b = settings.max_file_read_mb * 1024 * 1024
    a = resolve_path(settings, path_a)
    b = resolve_path(settings, path_b)
    if not a.is_file() or not b.is_file():
        raise CatalogError("ERR_NOT_FILE", "Both sides must be files")
    text_a, enc_a = _read_text_file(a, max_b)
    text_b, enc_b = _read_text_file(b, max_b)
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    if not lines_a and text_a:
        lines_a = [text_a]
    if not lines_b and text_b:
        lines_b = [text_b]
    unified = list(
        difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile=path_a,
            tofile=path_b,
            lineterm="",
        )
    )
    sm = difflib.SequenceMatcher(None, text_a, text_b)
    return {
        "path_a": path_a,
        "path_b": path_b,
        "encoding_a": enc_a,
        "encoding_b": enc_b,
        "similarity": round(sm.ratio(), 4),
        "lines_a": len(lines_a),
        "lines_b": len(lines_b),
        "diff_lines": unified,
        "diff_text": "\n".join(unified),
        "equal": text_a == text_b,
    }
