from __future__ import annotations

from pathlib import Path
from typing import Any

from config import Settings
from paths import catalog_root

# Канон модулей v.3 + зеркала филиалов (см. 00docs/ASSETS_REGISTRY.md)
MODULE_ROWS: list[dict[str, Any]] = [
    {
        "id": "aviora-catalog",
        "title": "Aviora Catalog",
        "port": 8002,
        "status": "MVP",
        "paths": {
            "Cursor": "Cursor/AIKIVAVIORA_v.3_Cursor/02modules/aviora-catalog",
        },
    },
    {
        "id": "dzen-rag",
        "title": "Dzen RAG",
        "port": 8001,
        "status": "active",
        "paths": {
            "Cursor": "Cursor/AIKIVAVIORA_v.3_Cursor/02modules/dzen-rag",
            "Claude": "Claude/Projects/rag-telegram-bot",
            "AIKIVAVIORA": "AIKIVAVIORA/02modules/knowledge/Hello-Who/artifacts/rag-app",
        },
    },
    {
        "id": "aikivaviora-v3",
        "title": "AIKIVAVIORA v.3 (филиал Cursor)",
        "port": None,
        "status": "active",
        "paths": {
            "Cursor": "Cursor/AIKIVAVIORA_v.3_Cursor",
        },
    },
    {
        "id": "aikivaviora-v2",
        "title": "AIKIVAVIORA v.2 (Claude)",
        "port": None,
        "status": "mirror",
        "paths": {
            "Claude": "Claude/Projects/AIKIVAVIORA.v.2",
        },
    },
    {
        "id": "aikivaviora-nexus",
        "title": "NEXUS / Codex (VS Code зона)",
        "port": None,
        "status": "active",
        "paths": {
            "AIKIVAVIORA": "AIKIVAVIORA",
        },
    },
    {
        "id": "dzen-neuro",
        "title": "DzenNeuro (ДЗ-5)",
        "port": None,
        "status": "reference",
        "paths": {
            "Cursor": "Cursor/Projects/ДЗ-5/DzenNeuro",
        },
    },
    {
        "id": "code-snapshots",
        "title": "Снимки кода",
        "port": None,
        "status": "storage",
        "paths": {
            "GEN": "05data/aviora_code_snapshots",
        },
    },
]

BRANCH_ZONES: list[dict[str, Any]] = [
    {
        "branch": "Cursor",
        "role": "Активная разработка v.3, ДЗ, Dzen",
        "root_hint": "Cursor/",
    },
    {
        "branch": "Claude",
        "role": "Claude-зона, rag-telegram-bot, v.2",
        "root_hint": "Claude/",
    },
    {
        "branch": "AIKIVAVIORA",
        "role": "NEXUS, MODULE_REGISTRY, Codex",
        "root_hint": "AIKIVAVIORA/",
    },
]


def build_catalog_map(settings: Settings) -> dict[str, Any]:
    root = catalog_root(settings)
    modules: list[dict[str, Any]] = []
    for row in MODULE_ROWS:
        branches: dict[str, Any] = {}
        for branch, rel in (row.get("paths") or {}).items():
            target = (root / rel.replace("\\", "/")).resolve()
            try:
                target.relative_to(root.resolve())
                inside = True
            except ValueError:
                inside = False
            exists = inside and target.exists()
            branches[branch] = {
                "path": rel.replace("\\", "/"),
                "exists": exists,
                "is_dir": exists and target.is_dir(),
            }
        modules.append(
            {
                "id": row["id"],
                "title": row["title"],
                "port": row.get("port"),
                "status": row.get("status"),
                "branches": branches,
            }
        )
    zones = []
    for z in BRANCH_ZONES:
        hint = z["root_hint"]
        p = root / hint.rstrip("/")
        zones.append({**z, "exists": p.is_dir(), "path": hint})
    return {
        "catalog_root": str(root),
        "modules": modules,
        "branch_zones": zones,
    }
