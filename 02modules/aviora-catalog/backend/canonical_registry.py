"""Главные файлы и группы дубликатов по содержимому индекса."""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from catalog_index import CatalogIndex, IndexEntry
from config import Settings
from paths import catalog_root


def _norm_path(p: str) -> str:
    return p.replace("\\", "/").strip("/")


def _path_score(rel: str) -> tuple[int, int]:
    """Выше = предпочтительнее как «главный»; второй ключ — короче путь."""
    low = rel.lower().replace("\\", "/")
    score = 0
    if "02modules/" in low:
        score += 20
    if "cursor/" in low or "aikivaviora" in low:
        score += 10
    if "09education/" in low or "/docs/" in low:
        score += 5
    if "_archive" in low or "/archive/" in low:
        score -= 15
    if "lm studio" in low:
        score -= 8
    if low.count("/") <= 2:
        score -= 3
    return (score, -len(low))


class CanonicalRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "catalog_root": "",
            "marked": {},
            "groups": {},
        }

    def _store_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "05data" / "aviora_canonical.json"

    def load(self, root: str) -> None:
        path = self._store_path()
        with self._lock:
            if not path.is_file():
                self._data = {"catalog_root": root, "marked": {}, "groups": {}}
                return
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            if (payload.get("catalog_root") or "").lower() != str(root).lower():
                self._data = {"catalog_root": root, "marked": {}, "groups": {}}
                return
            self._data = {
                "catalog_root": root,
                "marked": payload.get("marked") or {},
                "groups": payload.get("groups") or {},
            }

    def save(self) -> None:
        path = self._store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def clear(self) -> None:
        with self._lock:
            root = self._data.get("catalog_root") or ""
            self._data = {"catalog_root": root, "marked": {}, "groups": {}}
        try:
            self._store_path().unlink(missing_ok=True)
        except Exception:
            pass

    def _primary_for_path(self, path: str) -> str | None:
        p = _norm_path(path)
        with self._lock:
            if p in self._data.get("marked", {}):
                return p
            for grp in (self._data.get("groups") or {}).values():
                paths = [_norm_path(x) for x in grp.get("paths") or []]
                if p in paths:
                    primary = _norm_path(grp.get("primary") or "")
                    return primary or None
        return None

    def is_primary(self, path: str) -> bool:
        p = _norm_path(path)
        primary = self._primary_for_path(path)
        return primary == p if primary else False

    def mark_primary(self, path: str, *, note: str = "") -> dict[str, Any]:
        p = _norm_path(path)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._data.setdefault("marked", {})[p] = {
                "note": note.strip(),
                "at": now,
                "by": "user",
            }
            for gid, grp in (self._data.get("groups") or {}).items():
                paths = [_norm_path(x) for x in grp.get("paths") or []]
                if p in paths:
                    grp["primary"] = p
                    grp["primary_source"] = "user"
                    break
        self.save()
        return self.info(path)

    def unmark(self, path: str) -> dict[str, Any]:
        p = _norm_path(path)
        with self._lock:
            self._data.get("marked", {}).pop(p, None)
            for grp in (self._data.get("groups") or {}).values():
                if _norm_path(grp.get("primary") or "") == p and grp.get("primary_source") == "user":
                    paths = grp.get("paths") or []
                    if paths:
                        grp["primary"] = self._pick_primary(paths)
                        grp["primary_source"] = "auto"
        self.save()
        return {"ok": True, "path": p}

    def _pick_primary(self, paths: list[str]) -> str:
        normed = [_norm_path(p) for p in paths]
        return max(normed, key=_path_score)

    def rebuild_duplicate_groups(self, index: CatalogIndex) -> dict[str, Any]:
        """После Scan: группы файлов с одинаковым текстом (хеш)."""
        by_hash: dict[str, list[str]] = {}
        for e in index.entries():
            if not e.text or len(e.text.strip()) < 80:
                continue
            digest = hashlib.sha256(e.text[:8000].encode("utf-8", errors="replace")).hexdigest()[:12]
            by_hash.setdefault(digest, []).append(_norm_path(e.path))

        groups: dict[str, Any] = {}
        dup_file_count = 0
        for digest, paths in by_hash.items():
            if len(paths) < 2:
                continue
            primary = self._pick_primary(paths)
            groups[digest] = {
                "paths": sorted(set(paths)),
                "primary": primary,
                "primary_source": "auto",
                "count": len(paths),
            }
            dup_file_count += len(paths)

        with self._lock:
            old_marked = self._data.get("marked") or {}
            for gid, grp in groups.items():
                if grp.get("primary") in old_marked:
                    grp["primary_source"] = "user"
                    grp["primary"] = grp["primary"]
                for p, meta in old_marked.items():
                    if p in grp["paths"]:
                        grp["primary"] = p
                        grp["primary_source"] = "user"
            self._data["groups"] = groups
        self.save()
        return {
            "duplicate_groups": len(groups),
            "files_in_duplicate_groups": dup_file_count,
        }

    def info(self, path: str) -> dict[str, Any]:
        p = _norm_path(path)
        with self._lock:
            marked = self._data.get("marked", {})
            groups = self._data.get("groups") or {}
        is_primary = self.is_primary(p)
        group_id = None
        dup_paths: list[str] = []
        for gid, grp in groups.items():
            paths = [_norm_path(x) for x in grp.get("paths") or []]
            if p in paths:
                group_id = gid
                dup_paths = [x for x in paths if x != p]
                break
        return {
            "path": p,
            "is_primary": is_primary,
            "user_marked": p in marked,
            "note": (marked.get(p) or {}).get("note", ""),
            "duplicate_group": group_id,
            "duplicate_count": len(dup_paths) + (1 if group_id else 0),
            "duplicate_paths": dup_paths[:8],
            "primary_path": self._primary_for_path(p),
        }

    def list_all(self) -> dict[str, Any]:
        with self._lock:
            groups = dict(self._data.get("groups") or {})
            marked = dict(self._data.get("marked") or {})
        primaries = []
        for gid, grp in groups.items():
            primaries.append(
                {
                    "group": gid,
                    "primary": grp.get("primary"),
                    "count": grp.get("count", len(grp.get("paths") or [])),
                    "source": grp.get("primary_source", "auto"),
                }
            )
        return {
            "marked_paths": list(marked.keys()),
            "marked": marked,
            "duplicate_groups": len(groups),
            "primaries": primaries,
        }

    def enrich_search_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for r in results:
            info = self.info(r["path"])
            row = {**r, **info}
            enriched.append(row)

        def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
            primary_rank = 0 if row.get("is_primary") else 1
            has_dup = 0 if (row.get("duplicate_count") or 0) > 1 else 1
            return (primary_rank, has_dup, row["path"])

        enriched.sort(key=sort_key)
        return enriched

    def format_chat_block(self, hits: list[dict[str, Any]], *, limit: int = 15) -> str:
        if not hits:
            return ""
        lines = ["Совпадения в индексе (★ — главный файл в группе дубликатов):"]
        for h in hits[:limit]:
            star = "★ " if h.get("is_primary") else ""
            dup = h.get("duplicate_count") or 0
            dup_note = f" [дубликаты: {dup}]" if dup > 1 else ""
            sn = (h.get("snippet") or "").strip()
            extra = f" — …{sn}…" if sn else ""
            lines.append(f"- {star}{h.get('path')}{dup_note}{extra}")
            if h.get("is_primary") and (h.get("duplicate_paths") or []):
                others = ", ".join(h["duplicate_paths"][:3])
                if others:
                    lines.append(f"  (копии: {others})")
        return "\n".join(lines) + "\n"


CANONICAL = CanonicalRegistry()
