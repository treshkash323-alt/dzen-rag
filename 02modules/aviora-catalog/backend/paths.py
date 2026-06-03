from __future__ import annotations

import fnmatch
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import Settings

WHITELIST_EXTS = {
    ".md",
    ".txt",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".csv",
    ".zip",
    ".docx",
    ".xlsx",
    ".doc",
    ".xls",
    ".pptx",
    ".rar",
}

EDITABLE_EXTS = {".md", ".txt"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

SECRET_READ_PATTERNS = (".env", "*.pem", "id_rsa", "id_rsa.pub")

TEXT_EXTS = {".md", ".txt", ".csv"}

# Индексируются по имени/пути (без полнотекста) — фильтр «code»
CODE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
}


class CatalogError(Exception):
    def __init__(self, code: str, message: str = "", detail: str | None = None):
        self.code = code
        self.message = message or code
        self.detail = detail
        super().__init__(self.message)


def catalog_root(settings: Settings) -> Path:
    root = settings.catalog_root.expanduser().resolve()
    if not root.is_dir():
        raise CatalogError("ERR_ROOT_MISSING", f"Catalog root not found: {root}")
    return root


def rel_path(root: Path, full: Path) -> str:
    rel = full.relative_to(root)
    return "" if str(rel) == "." else rel.as_posix()


def resolve_path(settings: Settings, user_path: str | None) -> Path:
    root = catalog_root(settings)
    raw = (user_path or "").strip().replace("\\", "/")
    if not raw or raw in (".", "/"):
        return root
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise CatalogError(
            "ERR_PATH_OUTSIDE_ROOT",
            "Path must stay inside CATALOG_ROOT",
        ) from exc
    return target


def detect_branch(rel: str) -> str | None:
    low = rel.lower().replace("\\", "/")
    if "cursor" in low:
        return "Cursor"
    if "claude" in low:
        return "Claude"
    if "aikivaviora" in low:
        return "AIKIVAVIORA"
    return None


def _matches_secret(name: str) -> bool:
    for pat in SECRET_READ_PATTERNS:
        if fnmatch.fnmatch(name.lower(), pat.lower()) or name == pat:
            return True
    return False


def read_policy(path: Path) -> dict:
    name = path.name
    if _matches_secret(name):
        if name == ".env" or name.endswith(".env"):
            return {
                "allowed": True,
                "read_only": True,
                "banner": "secrets",
                "warning": "Файл с секретами — только просмотр",
            }
        return {
            "allowed": False,
            "read_only": True,
            "banner": "blocked",
            "warning": "Файл заблокирован для просмотра",
        }
    return {"allowed": True, "read_only": False, "banner": None, "warning": None}


def assert_writable(settings: Settings, path: Path, session_read_only: bool) -> None:
    if settings.read_only_mode or session_read_only:
        raise CatalogError("ERR_READ_ONLY", "Read-only mode is enabled")
    policy = read_policy(path)
    if policy.get("read_only"):
        raise CatalogError("ERR_READ_ONLY", "This file cannot be modified")


_SKIP_ALWAYS = frozenset(
    {
        "site-packages",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        "rag_index",
    }
)


def should_skip_dir(name: str, settings: Settings) -> bool:
    return (
        name in settings.scan_exclude_dirs
        or name in _SKIP_ALWAYS
        or name.startswith(".")
    )


def should_skip_file(name: str, settings: Settings) -> bool:
    return any(fnmatch.fnmatch(name, g) for g in settings.scan_exclude_glob)


def create_backup(path: Path) -> Path | None:
    if path.suffix.lower() not in (".md", ".txt", *IMAGE_EXTS):
        return None
    if not path.is_file():
        return None
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    return bak


def trash_dir(settings: Settings) -> Path:
    root = catalog_root(settings)
    t = root / ".trash"
    t.mkdir(exist_ok=True)
    return t


def file_meta(path: Path, root: Path) -> dict:
    st = path.stat()
    rel = rel_path(root, path)
    ext = path.suffix.lower()
    return {
        "path": rel,
        "name": path.name,
        "is_dir": path.is_dir(),
        "size": st.st_size if path.is_file() else None,
        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "ext": ext or None,
        "branch": detect_branch(rel),
        "whitelisted": ext in WHITELIST_EXTS or path.is_dir(),
    }
