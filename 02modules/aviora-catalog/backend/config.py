from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parent
load_dotenv(_BACKEND / ".env")

VERSION = "0.3.8"


@dataclass(frozen=True)
class Settings:
    catalog_root: Path
    host: str
    port: int
    max_upload_mb: int
    max_file_read_mb: int
    scan_exclude_dirs: tuple[str, ...]
    scan_exclude_glob: tuple[str, ...]
    deepseek_api_key: str | None
    deepseek_base_url: str
    lmstudio_base_url: str
    lmstudio_model: str
    llm_default: str
    read_only_mode: bool
    features_billing_enabled: bool
    features_tokens_display: str
    llm_context_chars: int
    max_image_dim: int
    cors_origins: tuple[str, ...]


def load_settings() -> Settings:
    root = Path(
        os.environ.get("CATALOG_ROOT", r"C:\Users\kash-\Python_kash")
    ).expanduser()
    exclude_dirs = tuple(
        d.strip()
        for d in os.environ.get(
            "SCAN_EXCLUDE_DIRS",
            ".venv,node_modules,__pycache__,.git,05data/rag_index,site-packages,dist,build,.mypy_cache",
        ).split(",")
        if d.strip()
    )
    exclude_glob = tuple(
        g.strip()
        for g in os.environ.get("SCAN_EXCLUDE_GLOB", "*.pyc,*.exe").split(",")
        if g.strip()
    )
    cors_raw = os.environ.get(
        "CATALOG_CORS_ORIGINS",
        "http://127.0.0.1:8002,http://localhost:8002",
    )
    cors = tuple(o.strip() for o in cors_raw.split(",") if o.strip())
    return Settings(
        catalog_root=root,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8002")),
        max_upload_mb=int(os.environ.get("MAX_UPLOAD_MB", "25")),
        max_file_read_mb=int(os.environ.get("MAX_FILE_READ_MB", "50")),
        scan_exclude_dirs=exclude_dirs,
        scan_exclude_glob=exclude_glob,
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
        deepseek_base_url=os.environ.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        ).rstrip("/"),
        lmstudio_base_url=os.environ.get(
            "LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"
        ).rstrip("/"),
        lmstudio_model=os.environ.get("LMSTUDIO_MODEL", "local-model"),
        llm_default=os.environ.get("LLM_DEFAULT", "auto"),
        read_only_mode=os.environ.get("READ_ONLY_MODE", "false").lower()
        in ("1", "true", "yes"),
        features_billing_enabled=os.environ.get(
            "FEATURES_BILLING_ENABLED", "false"
        ).lower()
        in ("1", "true", "yes"),
        features_tokens_display=os.environ.get(
            "FEATURES_TOKENS_DISPLAY", "session_only"
        ),
        llm_context_chars=int(os.environ.get("LLM_CONTEXT_CHARS", "12000")),
        max_image_dim=int(os.environ.get("MAX_IMAGE_DIM", "8000")),
        cors_origins=cors or ("http://127.0.0.1:8002",),
    )
