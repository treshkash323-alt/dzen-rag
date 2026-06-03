from __future__ import annotations

import io
import json
import logging
import os
import platform
import shutil
import subprocess
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from canonical_registry import CANONICAL
from catalog_index import INDEX
from config import VERSION, Settings, load_settings
from jobs import JOBS
from llm_client import (
    chat_completion,
    choose_provider,
    invalidate_llm_health_cache,
    llm_health_info,
    llm_ok,
)
from catalog_map import build_catalog_map
from audio_transcribe import (
    ffmpeg_available,
    max_transcribe_mb,
    probe_audio_meta,
    run_transcription,
    transcript_for_source,
    whisper_available,
)
from report_saves import save_chat_report, save_search_report
from code_snapshots import (
    create_batch_snapshots,
    create_code_snapshot,
    diff_catalog_paths,
    list_recent_snapshots,
    resolve_diff_path,
)
from paths import (
    CODE_EXTS,
    EDITABLE_EXTS,
    AUDIO_EXTS,
    IMAGE_EXTS,
    WHITELIST_EXTS,
    CatalogError,
    assert_writable,
    catalog_root,
    create_backup,
    file_meta,
    read_policy,
    rel_path,
    resolve_path,
    trash_dir,
)

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[misc, assignment]

app = FastAPI(title="Aviora Catalog", version=VERSION)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
LOG_BUFFER: list[str] = []
_session_read_only = False
_session_llm_enabled = True
_token_session: dict[str, int] = {"last": 0, "session": 0}


def _log(level: str, msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} [{level}] {msg}"
    LOG_BUFFER.append(line)
    if len(LOG_BUFFER) > 500:
        del LOG_BUFFER[:100]
    logging.getLogger("aviora").info(line)


def _settings() -> Settings:
    return load_settings()


def _err(exc: CatalogError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"code": exc.code, "message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(CatalogError)
def catalog_error_handler(_request, exc: CatalogError):
    return _err(exc)


@app.exception_handler(RequestValidationError)
def validation_error_handler(_request, exc: RequestValidationError):
    parts = []
    for item in exc.errors():
        loc = ".".join(str(x) for x in item.get("loc", ()))
        parts.append(f"{loc}: {item.get('msg', '')}")
    return JSONResponse(
        status_code=422,
        content={
            "code": "ERR_VALIDATION",
            "message": "Неверный запрос: " + "; ".join(parts[:3]),
            "detail": exc.errors(),
        },
    )


def _read_only_active(settings: Settings, header: str | None) -> bool:
    return settings.read_only_mode or _session_read_only or header == "true"


def _catalog_hits_for_chat(message: str, *, limit: int = 15) -> str:
    if INDEX.count == 0:
        return (
            "Индекс каталога пуст (нужен Scan в UI). "
            "Поиск слева: ввести слово и Enter.\n"
        )
    hits = INDEX.search(message, limit=limit * 4)
    if not hits:
        for word in message.replace(",", " ").split():
            w = word.strip().lower()
            if len(w) < 3:
                continue
            hits = INDEX.search(w, limit=limit * 4)
            if hits:
                break
    if not hits:
        return "По индексу совпадений для этого вопроса нет.\n"
    hits = CANONICAL.enrich_search_results(hits)[:limit]
    return CANONICAL.format_chat_block(hits, limit=limit)


@app.on_event("startup")
def _startup():
    logging.basicConfig(level=logging.INFO)
    s = _settings()
    root = str(s.catalog_root)
    n = INDEX.load_cache(root)
    CANONICAL.load(root)
    JOBS.reset_llm_cancel()
    _log("INFO", f"Aviora Catalog v{VERSION} root={root} index_cache={n}")


def _mount_cors():
    s = _settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(s.cors_origins),
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Read-Only"],
    )


_mount_cors()
if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")


@app.get("/health")
def health(
    provider: str = Query("auto"),
    llm_enabled: str = Query("true"),
) -> dict[str, Any]:
    s = _settings()
    enabled = llm_enabled.lower() not in ("0", "false", "no", "off")
    llm = llm_health_info(
        s,
        ui_provider=provider.replace("lm_studio", "lmstudio"),
        session_enabled=enabled and _session_llm_enabled,
    )
    return {
        "status": "ok",
        "module": "aviora-catalog",
        "version": VERSION,
        "files_indexed": INDEX.count,
        "duplicate_groups": CANONICAL.list_all().get("duplicate_groups", 0),
        "whisper_ok": whisper_available(),
        "ffmpeg_ok": ffmpeg_available(),
        "max_audio_transcribe_mb": max_transcribe_mb(),
        "llm_ok": llm_ok(s) and enabled and _session_llm_enabled,
        "read_only": _read_only_active(s, None),
        "catalog_root": str(s.catalog_root),
        "features_billing_enabled": s.features_billing_enabled,
        "tokens_session": _token_session.get("session", 0),
        **llm,
    }


@app.get("/", include_in_schema=False)
def root_ui():
    return RedirectResponse(url="/ui/")


@app.get("/tree")
def tree(path: str = "") -> dict[str, Any]:
    s = _settings()
    root = catalog_root(s)
    target = resolve_path(s, path)
    if not target.is_dir():
        raise CatalogError("ERR_NOT_DIR", "Not a directory")
    children = []
    try:
        entries = sorted(
            target.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
    except PermissionError as exc:
        raise CatalogError("ERR_ACCESS", "Permission denied") from exc
    for p in entries:
        if p.name.startswith(".") and p.name not in (".trash",):
            continue
        children.append(file_meta(p, root))
    return {
        "path": rel_path(root, target),
        "children": children,
        "root": str(root),
    }


@app.get("/file/meta")
def file_meta_route(path: str = Query(...)) -> dict[str, Any]:
    s = _settings()
    root = catalog_root(s)
    target = resolve_path(s, path)
    if not target.exists():
        raise CatalogError("ERR_NOT_FOUND", "File not found")
    meta = file_meta(target, root)
    meta["policy"] = read_policy(target)
    meta["canonical"] = CANONICAL.info(rel_path(root, target))
    if target.suffix.lower() in AUDIO_EXTS:
        am = probe_audio_meta(target)
        meta["audio_meta"] = am
        meta["duration_sec"] = am.get("duration_sec")
    return meta


def _read_file_payload(s: Settings, path: str) -> dict[str, Any]:
    target = resolve_path(s, path)
    if not target.is_file():
        raise CatalogError("ERR_NOT_FILE", "Not a file")
    policy = read_policy(target)
    if not policy.get("allowed"):
        raise CatalogError("ERR_READ_BLOCKED", policy.get("warning") or "Blocked")
    ext = target.suffix.lower()
    max_b = s.max_file_read_mb * 1024 * 1024
    if ext in EDITABLE_EXTS or ext == ".csv":
        text = ""
        encoding = "utf-8"
        for enc in ("utf-8", "cp1251"):
            try:
                text = target.read_bytes()[:max_b].decode(enc)
                encoding = enc
                break
            except Exception:
                continue
        return {
            "path": path,
            "kind": "text",
            "content": text,
            "encoding": encoding,
            "read_only": policy.get("read_only", False),
            "banner": policy.get("banner"),
        }
    if ext == ".pdf":
        return {"path": path, "kind": "pdf", "url": f"/file/raw?path={path}"}
    if ext in IMAGE_EXTS:
        return {"path": path, "kind": "image", "url": f"/file/raw?path={path}"}
    if ext in AUDIO_EXTS:
        tr = transcript_for_source(s, path)
        ameta = probe_audio_meta(target)
        return {
            "path": path,
            "kind": "audio",
            "url": f"/file/raw?path={path}",
            "size": target.stat().st_size,
            "audio_meta": ameta,
            "transcript": tr.get("text") or "",
            "transcript_path": tr.get("transcript_rel"),
            "has_transcript": tr.get("has_transcript", False),
            "whisper_ok": whisper_available(),
            "max_transcribe_mb": max_transcribe_mb(),
            "read_only": True,
        }
    if ext == ".docx":
        from catalog_index import INDEX as _idx

        entry = next((e for e in _idx.entries() if e.path == path), None)
        preview = entry.text if entry else ""
        if not preview:
            preview = _idx._extract_docx(target)  # noqa: SLF001
        return {
            "path": path,
            "kind": "docx_preview",
            "preview": preview,
            "download": f"/file/raw?path={path}",
        }
    if ext == ".xlsx":
        from catalog_index import INDEX as _idx

        entry = next((e for e in _idx.entries() if e.path == path), None)
        preview = entry.text if entry else ""
        if not preview:
            preview = _idx._extract_xlsx(target)  # noqa: SLF001
        return {
            "path": path,
            "kind": "xlsx_preview",
            "preview": preview,
            "download": f"/file/raw?path={path}",
        }
    if ext == ".zip":
        return {"path": path, "kind": "zip", "message": "Use archive API"}
    if ext == ".rar":
        raise CatalogError("ERR_RAR_V02", "RAR support planned for v0.2")
    if ext in CODE_EXTS:
        text = ""
        encoding = "utf-8"
        for enc in ("utf-8", "cp1251"):
            try:
                text = target.read_bytes()[:max_b].decode(enc)
                encoding = enc
                break
            except Exception:
                continue
        return {
            "path": path,
            "kind": "code",
            "content": text,
            "encoding": encoding,
            "read_only": True,
            "banner": policy.get("banner"),
            "message": "Код только для просмотра. Снимок → 05data/aviora_code_snapshots",
            "download": f"/file/raw?path={path}",
            "size": target.stat().st_size,
        }
    return {
        "path": path,
        "kind": "view_only",
        "message": "Редактирование в Catalog только для .md и .txt",
        "download": f"/file/raw?path={path}",
        "size": target.stat().st_size,
    }


@app.get("/file/content")
def file_content(path: str = Query(...)) -> dict[str, Any]:
    return _read_file_payload(_settings(), path)


class CodeSnapshotBody(BaseModel):
    path: str = Field(..., min_length=1)
    note: str = Field("", max_length=500)
    rev: str | None = Field(None, max_length=32)
    tags: list[str] = Field(default_factory=list)


@app.post("/code/snapshot")
def code_snapshot(body: CodeSnapshotBody) -> dict[str, Any]:
    s = _settings()
    return create_code_snapshot(
        s,
        source_path=body.path.replace("\\", "/"),
        note=body.note,
        rev=body.rev,
        tags=body.tags[:12],
    )


class CodeBatchBody(BaseModel):
    path: str = Field(..., min_length=1)
    note: str = Field("", max_length=500)
    rev: str | None = Field(None, max_length=32)
    max_files: int = Field(120, ge=1, le=300)


@app.post("/code/snapshot/batch")
def code_snapshot_batch(body: CodeBatchBody) -> dict[str, Any]:
    s = _settings()
    return create_batch_snapshots(
        s,
        folder_path=body.path.replace("\\", "/"),
        note=body.note,
        rev=body.rev,
        max_files=body.max_files,
    )


class CodeDiffBody(BaseModel):
    path_a: str = Field(..., min_length=1)
    path_b: str = Field(..., min_length=1)


@app.post("/code/diff")
def code_diff(body: CodeDiffBody) -> dict[str, Any]:
    s = _settings()
    pa = resolve_diff_path(s, body.path_a.strip())
    pb = resolve_diff_path(s, body.path_b.strip())
    return diff_catalog_paths(s, pa, pb)


@app.get("/code/snapshots/recent")
def code_snapshots_recent(limit: int = Query(40, ge=1, le=100)) -> dict[str, Any]:
    return {"items": list_recent_snapshots(_settings(), limit=limit)}


@app.get("/catalog/map")
def catalog_map() -> dict[str, Any]:
    return build_catalog_map(_settings())


@app.get("/file/raw")
def file_raw(path: str = Query(...)):
    s = _settings()
    target = resolve_path(s, path)
    if not target.is_file():
        raise CatalogError("ERR_NOT_FILE", "Not a file")
    return FileResponse(target)


class SaveBody(BaseModel):
    path: str
    content: str
    encoding: str = "utf-8"


class BoardBody(BaseModel):
    path: str
    data: dict[str, Any] | list[Any]


@app.get("/board")
def board_get(path: str = Query(...)) -> dict[str, Any]:
    s = _settings()
    target = resolve_path(s, path)
    if not target.is_file():
        return {"path": path, "elements": [], "exists": False}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise CatalogError("ERR_VALIDATION", "Invalid board JSON") from None
    elements = raw.get("elements", raw) if isinstance(raw, dict) else raw
    if not isinstance(elements, list):
        elements = []
    return {"path": path, "elements": elements, "exists": True, "version": 1}


@app.put("/board")
def board_save(
    body: BoardBody,
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    s = _settings()
    target = resolve_path(s, body.path)
    assert_writable(s, target.parent, _read_only_active(s, x_read_only))
    if target.suffix.lower() != ".json":
        raise CatalogError("ERR_NOT_EDITABLE", "Board must be .json")
    payload = body.data if isinstance(body.data, dict) else {"elements": body.data}
    if "elements" not in payload:
        payload = {"version": 1, "elements": payload if isinstance(payload, list) else []}
    elif "version" not in payload:
        payload = {"version": 1, **payload}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _log("INFO", f"board saved {body.path}")
    return {"ok": True, "path": body.path}


@app.put("/file/content")
def file_save(
    body: SaveBody,
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    s = _settings()
    assert_writable(s, resolve_path(s, body.path), _read_only_active(s, x_read_only))
    target = resolve_path(s, body.path)
    if target.suffix.lower() not in EDITABLE_EXTS:
        raise CatalogError("ERR_NOT_EDITABLE", "Only .md and .txt are editable")
    create_backup(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding=body.encoding or "utf-8")
    _log("INFO", f"saved {body.path}")
    return {"ok": True, "path": body.path}


@app.post("/file/upload")
async def file_upload(
    path: str = "",
    file: UploadFile = File(...),
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    s = _settings()
    dest_dir = resolve_path(s, path)
    assert_writable(s, dest_dir, _read_only_active(s, x_read_only))
    if not dest_dir.is_dir():
        raise CatalogError("ERR_NOT_DIR", "Target must be a directory")
    name = Path(file.filename or "").name
    if not name:
        raise CatalogError("ERR_FILENAME", "Filename required")
    ext = Path(name).suffix.lower()
    if ext and ext not in WHITELIST_EXTS:
        raise CatalogError("ERR_EXT", "Extension not allowed")
    content = await file.read()
    max_b = s.max_upload_mb * 1024 * 1024
    if len(content) > max_b:
        raise CatalogError("ERR_TOO_LARGE", f"Max {s.max_upload_mb} MB")
    out = dest_dir / name
    if out.exists():
        create_backup(out)
    out.write_bytes(content)
    root = catalog_root(s)
    return {"ok": True, "path": rel_path(root, out)}


class MkdirBody(BaseModel):
    path: str


@app.post("/file/mkdir")
def file_mkdir(
    body: MkdirBody,
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    s = _settings()
    target = resolve_path(s, body.path)
    assert_writable(s, target.parent, _read_only_active(s, x_read_only))
    target.mkdir(parents=True, exist_ok=True)
    root = catalog_root(s)
    return {"ok": True, "path": rel_path(root, target)}


class RenameBody(BaseModel):
    path: str
    new_name: str


@app.post("/file/rename")
def file_rename(
    body: RenameBody,
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    s = _settings()
    src = resolve_path(s, body.path)
    assert_writable(s, src, _read_only_active(s, x_read_only))
    new_name = Path(body.new_name).name
    dst = src.parent / new_name
    src.rename(dst)
    root = catalog_root(s)
    return {"ok": True, "path": rel_path(root, dst)}


class DeleteBody(BaseModel):
    path: str
    confirm: bool = False


@app.post("/file/delete")
def file_delete(
    body: DeleteBody,
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    s = _settings()
    src = resolve_path(s, body.path)
    assert_writable(s, src, _read_only_active(s, x_read_only))
    tdir = trash_dir(s)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = tdir / f"{stamp}_{src.name}"
    shutil.move(str(src), str(dest))
    root = catalog_root(s)
    return {"ok": True, "trash_path": rel_path(root, dest)}


class ZipListBody(BaseModel):
    path: str


@app.post("/archive/zip/list")
def zip_list(body: ZipListBody) -> dict[str, Any]:
    s = _settings()
    target = resolve_path(s, body.path)
    if target.suffix.lower() != ".zip":
        raise CatalogError("ERR_NOT_ZIP", "Not a zip file")
    with zipfile.ZipFile(target, "r") as zf:
        names = zf.namelist()
    return {"path": body.path, "entries": names}


class ZipExtractBody(BaseModel):
    path: str
    dest: str = ""
    members: list[str] | None = None


@app.post("/archive/zip/extract")
def zip_extract(
    body: ZipExtractBody,
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    s = _settings()
    zpath = resolve_path(s, body.path)
    dest = resolve_path(s, body.dest) if body.dest else zpath.parent
    assert_writable(s, dest, _read_only_active(s, x_read_only))
    root = catalog_root(s)
    extracted: list[str] = []
    with zipfile.ZipFile(zpath, "r") as zf:
        for name in zf.namelist():
            if body.members and name not in body.members:
                continue
            if name.endswith("/"):
                continue
            out = (dest / name).resolve()
            try:
                out.relative_to(root)
            except ValueError as exc:
                raise CatalogError("ERR_ZIP_SLIP", "Unsafe zip path") from exc
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(out, "wb") as dst_f:
                shutil.copyfileobj(src, dst_f)
            extracted.append(rel_path(root, out))
    return {"ok": True, "extracted": extracted}


class ImageTransformBody(BaseModel):
    path: str
    crop: dict[str, int] | None = None
    rotate: int = 0
    flip_h: bool = False
    flip_v: bool = False
    resize: dict[str, int] | None = None
    format: str = "jpeg"
    quality: int = 85


@app.post("/image/preview")
def image_preview(body: ZipListBody):
    return file_raw(path=body.path)


@app.post("/image/transform")
def image_transform(
    body: ImageTransformBody,
    x_read_only: str | None = Header(default=None, alias="X-Read-Only"),
):
    if Image is None:
        raise CatalogError("ERR_PIL", "Pillow not installed")
    s = _settings()
    target = resolve_path(s, body.path)
    assert_writable(s, target, _read_only_active(s, x_read_only))
    if target.suffix.lower() not in IMAGE_EXTS:
        raise CatalogError("ERR_NOT_IMAGE", "Not an image")
    create_backup(target)
    img = Image.open(target)
    w, h = img.size
    if w > s.max_image_dim or h > s.max_image_dim:
        raise CatalogError("ERR_IMAGE_DIM", f"Max {s.max_image_dim}px")
    if body.crop:
        c = body.crop
        img = img.crop((c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"]))
    if body.rotate:
        img = img.rotate(-body.rotate, expand=True)
    flip = getattr(Image, "Transpose", Image)
    if body.flip_h:
        img = img.transpose(getattr(flip, "FLIP_LEFT_RIGHT", Image.FLIP_LEFT_RIGHT))
    if body.flip_v:
        img = img.transpose(getattr(flip, "FLIP_TOP_BOTTOM", Image.FLIP_TOP_BOTTOM))
    if body.resize:
        img = img.resize((body.resize["w"], body.resize["h"]))
    fmt = body.format.lower()
    ext = ".jpg" if fmt in ("jpeg", "jpg") else f".{fmt}"
    buf = io.BytesIO()
    save_kw: dict[str, Any] = {}
    if ext in (".jpg", ".jpeg"):
        save_kw["quality"] = max(1, min(100, body.quality))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
    img.save(buf, format=fmt.upper() if fmt != "jpg" else "JPEG", **save_kw)
    if ext != target.suffix.lower():
        new_path = target.with_suffix(ext)
        target.unlink(missing_ok=True)
        target = new_path
    target.write_bytes(buf.getvalue())
    root = catalog_root(s)
    return {"ok": True, "path": rel_path(root, target)}


class ConvertBody(BaseModel):
    path: str | None = None
    target: str = "html_snippet"
    content: str | None = None


def _md_to_html_snippet(text: str) -> str:
    import html
    import re

    lines = text.splitlines()
    out: list[str] = []
    in_pre = False
    for line in lines:
        if line.strip().startswith("```"):
            if in_pre:
                out.append("</pre>")
                in_pre = False
            else:
                out.append("<pre>")
                in_pre = True
            continue
        if in_pre:
            out.append(html.escape(line))
            continue
        if line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif not line.strip():
            out.append("<br/>")
        else:
            esc = html.escape(line)
            esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
            out.append(f"<p>{esc}</p>")
    if in_pre:
        out.append("</pre>")
    return "\n".join(out)


@app.post("/convert")
def convert(body: ConvertBody) -> dict[str, Any]:
    if body.target != "html_snippet":
        raise CatalogError("ERR_CONVERT", "Conversion not supported")

    path_lower = (body.path or "").lower()
    if body.content is not None:
        text = body.content
        if path_lower.endswith(".txt"):
            import html

            return {
                "html": "".join(
                    f"<p>{html.escape(line)}</p>" if line.strip() else "<br/>"
                    for line in text.splitlines()
                )
            }
        return {"html": _md_to_html_snippet(text)}

    if not body.path:
        raise CatalogError("ERR_VALIDATION", "Укажите path или content")

    s = _settings()
    target = resolve_path(s, body.path)
    if not target.is_file():
        raise CatalogError("ERR_NOT_FILE", "Not a file")
    if target.suffix.lower() == ".md":
        text = target.read_text(encoding="utf-8", errors="replace")
        return {"html": _md_to_html_snippet(text)}
    if target.suffix.lower() == ".txt":
        import html

        text = target.read_text(encoding="utf-8", errors="replace")
        return {
            "html": "".join(
                f"<p>{html.escape(line)}</p>" if line.strip() else "<br/>"
                for line in text.splitlines()
            )
        }
    raise CatalogError("ERR_CONVERT", "Only .md and .txt")


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=16000)
    path: str | None = None
    provider: Literal["auto", "deepseek", "lmstudio", "lm_studio"] = "auto"


@app.post("/chat")
def chat(body: ChatBody) -> dict[str, Any]:
    if not _session_llm_enabled:
        raise CatalogError("ERR_LLM", "LLM выключен (кнопка в шапке)")
    s = _settings()
    prov = body.provider.replace("lm_studio", "lmstudio")
    selected = choose_provider(s, prov)
    if not selected:
        raise CatalogError("ERR_LLM", "LLM not configured")
    context = ""
    if body.path:
        try:
            data = _read_file_payload(s, body.path)
            if data.get("kind") == "text":
                context = data.get("content") or ""
            elif data.get("preview"):
                context = data["preview"]
        except Exception:
            context = ""
    catalog_hits = _catalog_hits_for_chat(body.message)
    context = context[: s.llm_context_chars]
    job = JOBS.create("llm")
    job.status = "running"
    JOBS.set_llm_job(job.id)

    system = (
        "Ты помощник по каталогу Python_kash (Aviora Catalog). "
        "Отвечай по-русски, кратко. Используй блок «Индекс» для путей к проектам; "
        "строки с ★ — рекомендуемый главный файл среди копий с тем же текстом. "
        "Не выдумывай файлы. Если индекс пуст — скажи выполнить Scan."
    )
    user = (
        f"Файл: {body.path or '(не открыт)'}\n\n"
        f"{context}\n\n"
        f"--- Индекс ---\n{catalog_hits}\n"
        f"Вопрос:\n{body.message}"
    )

    try:
        answer, usage = chat_completion(
            s,
            provider=selected,
            system_prompt=system,
            user_prompt=user,
            cancel_check=lambda: JOBS.llm_cancelled,
        )
    except Exception as exc:
        job.status = "error"
        job.error = exc.__class__.__name__
        JOBS.set_llm_job(None)
        if str(exc) == "cancelled" or JOBS.llm_cancelled:
            return {"cancelled": True, "answer": ""}
        raise CatalogError("ERR_LLM", str(exc)) from exc

    if JOBS.llm_cancelled:
        job.status = "cancelled"
        JOBS.set_llm_job(None)
        return {"cancelled": True, "answer": ""}

    job.status = "done"
    JOBS.set_llm_job(None)
    tokens = 0
    approx = False
    if usage and usage.get("total_tokens"):
        tokens = int(usage["total_tokens"])
    else:
        tokens = len(body.message) + len(answer) + len(context)
        approx = True
    _token_session["last"] = tokens
    _token_session["session"] += tokens
    if not (answer or "").strip():
        answer = (
            "Модель вернула пустой текст. В LM Studio: загрузите модель и нажмите "
            "Start Server (порт 1234). Либо задайте DEEPSEEK_API_KEY в .env."
        )
    return {
        "answer": answer,
        "provider": selected,
        "usage": usage,
        "tokens_last": tokens,
        "tokens_approx": approx,
        "job_id": job.id,
    }


@app.post("/chat/cancel")
def chat_cancel():
    JOBS.cancel_llm()
    return {"ok": True}


@app.post("/chat/reset-cancel")
def chat_reset_cancel():
    """Сброс залипшего флага Stop после обновления backend."""
    JOBS.reset_llm_cancel()
    JOBS.set_llm_job(None)
    return {"ok": True}


class ShareBody(BaseModel):
    path: str
    mode: str = "path"


@app.post("/share")
def share(body: ShareBody) -> dict[str, Any]:
    s = _settings()
    target = resolve_path(s, body.path)
    root = catalog_root(s)
    rel = rel_path(root, target)
    return {
        "relative": rel,
        "absolute": str(target),
        "token": None,
        "stub": True,
    }


@app.get("/scan/estimate")
def scan_estimate() -> dict[str, Any]:
    s = _settings()
    files = INDEX.collect_files(s)
    return {"total": len(files), "catalog_root": str(s.catalog_root)}


@app.post("/scan/start")
def scan_start() -> dict[str, Any]:
    s = _settings()
    job = JOBS.create("scan")
    job.status = "running"

    def run():
        try:
            result = INDEX.build(
                s,
                cancel_check=lambda: job.cancelled,
                on_progress=lambda cur, tot, name: (
                    setattr(job, "progress", cur),
                    setattr(job, "total", tot),
                    setattr(job, "current", name),
                ),
            )
            if not result.get("cancelled"):
                dup = CANONICAL.rebuild_duplicate_groups(INDEX)
                result = {**result, **dup}
            job.result = result
            job.status = "cancelled" if result.get("cancelled") else "done"
            _log("INFO", f"scan done {result}")
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            _log("ERROR", f"scan failed {exc}")

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job.id}


class TranscribeBody(BaseModel):
    path: str = Field(..., min_length=1)


@app.post("/audio/transcribe/start")
def audio_transcribe_start(body: TranscribeBody):
    s = _settings()
    rel = body.path.replace("\\", "/")
    target = resolve_path(s, rel)
    if target.suffix.lower() not in AUDIO_EXTS:
        raise CatalogError("ERR_NOT_AUDIO", "Not an audio file")
    if not whisper_available():
        raise CatalogError(
            "ERR_WHISPER_MISSING",
            "pip install faster-whisper in backend/.venv (see README)",
        )
    job = JOBS.create("transcribe")
    job.status = "running"
    job.current = rel
    job.total = 100
    job.progress = 0
    job.message = "Старт…"

    def run():
        try:
            result = run_transcription(
                s,
                rel,
                cancel_check=lambda: job.cancelled,
                on_message=lambda m: setattr(job, "message", m),
                on_progress=lambda p, t, m: (
                    setattr(job, "progress", p),
                    setattr(job, "total", t),
                    setattr(job, "message", m),
                ),
            )
            if result.get("cancelled"):
                job.status = "cancelled"
            else:
                job.result = result
                job.status = "done"
                INDEX.patch_audio_transcript(s, rel)
                _log("INFO", f"transcribe done {rel} -> {result.get('transcript_path')}")
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            _log("ERROR", f"transcribe failed {rel}: {exc}")

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job.id}


@app.get("/audio/transcribe/status/{job_id}")
def audio_transcribe_status(job_id: str):
    job = JOBS.get(job_id)
    if not job or job.type != "transcribe":
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@app.get("/scan/status/{job_id}")
def scan_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise CatalogError("ERR_JOB", "Job not found")
    return job.to_dict()


@app.post("/scan/cancel/{job_id}")
def scan_cancel(job_id: str):
    ok = JOBS.cancel(job_id)
    return {"ok": ok}


@app.get("/search")
def search(
    q: str = "",
    ext: str | None = None,
    branch: str | None = None,
    primary_first: bool = True,
):
    raw = INDEX.search(q, ext=ext, branch=branch, limit=200)
    results = (
        CANONICAL.enrich_search_results(raw)[:100]
        if primary_first
        else raw[:100]
    )
    return {"results": results}


class CanonicalMarkBody(BaseModel):
    path: str = Field(..., min_length=1)
    note: str = ""


@app.get("/canonical")
def canonical_list():
    return CANONICAL.list_all()


@app.get("/canonical/info")
def canonical_info(path: str = Query(...)):
    return CANONICAL.info(path)


@app.post("/canonical/mark")
def canonical_mark(body: CanonicalMarkBody):
    s = _settings()
    resolve_path(s, body.path)
    return CANONICAL.mark_primary(body.path, note=body.note)


@app.post("/canonical/unmark")
def canonical_unmark(body: CanonicalMarkBody):
    s = _settings()
    resolve_path(s, body.path)
    return CANONICAL.unmark(body.path)


class SearchSaveBody(BaseModel):
    query: str = Field(..., min_length=1)
    branch: str = ""
    results: list[dict[str, Any]] = Field(default_factory=list)


class ChatSaveBody(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    path: str = ""


@app.post("/reports/save-search")
def reports_save_search(body: SearchSaveBody):
    s = _settings()
    if not body.results:
        raise HTTPException(status_code=400, detail="Нет результатов для сохранения")
    out = save_search_report(
        s,
        query=body.query.strip(),
        branch=body.branch.strip(),
        results=body.results,
        catalog_version=VERSION,
    )
    _log("INFO", f"search report saved {out['path']}")
    return out


@app.post("/reports/save-chat")
def reports_save_chat(body: ChatSaveBody):
    s = _settings()
    out = save_chat_report(
        s,
        question=body.question.strip(),
        answer=body.answer.strip(),
        file_path=body.path.strip(),
        catalog_version=VERSION,
    )
    _log("INFO", f"chat report saved {out['path']}")
    return out


@app.get("/logs/tail")
def logs_tail(n: int = 80) -> dict[str, Any]:
    return {"lines": LOG_BUFFER[-n:]}


@app.post("/session/reset")
def session_reset() -> dict[str, Any]:
    global _session_read_only, _session_llm_enabled
    cancelled = JOBS.cancel_all()
    INDEX.clear()
    CANONICAL.clear()
    _session_read_only = False
    _session_llm_enabled = True
    invalidate_llm_health_cache()
    _token_session["last"] = 0
    _log("INFO", "session reset")
    return {"ok": True, "cancelled_jobs": cancelled}


@app.get("/explorer/reveal")
def explorer_reveal(path: str = Query(...)):
    s = _settings()
    target = resolve_path(s, path)
    if platform.system() != "Windows":
        return {"ok": False, "message": "Windows only"}
    subprocess.Popen(["explorer", f"/select,{target}"])
    return {"ok": True}


@app.get("/session/read-only")
def get_read_only():
    s = _settings()
    return {"enabled": _read_only_active(s, None)}


class ReadOnlyBody(BaseModel):
    enabled: bool


@app.post("/session/read-only")
def set_read_only(body: ReadOnlyBody):
    global _session_read_only
    _session_read_only = body.enabled
    return {"enabled": _session_read_only}


@app.get("/session/llm")
def get_session_llm() -> dict[str, Any]:
    return {"enabled": _session_llm_enabled}


@app.post("/session/llm")
def set_session_llm(body: ReadOnlyBody) -> dict[str, Any]:
    global _session_llm_enabled
    _session_llm_enabled = body.enabled
    invalidate_llm_health_cache()
    return {"enabled": _session_llm_enabled}


@app.post("/llm/probe")
def llm_probe(provider: str = Query("auto")) -> dict[str, Any]:
    invalidate_llm_health_cache()
    s = _settings()
    info = llm_health_info(
        s,
        ui_provider=provider.replace("lm_studio", "lmstudio"),
        session_enabled=True,
    )
    info["llm_chat_enabled"] = _session_llm_enabled
    info["llm_session_enabled"] = _session_llm_enabled
    return info
