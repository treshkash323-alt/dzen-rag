"""Аудио: метаданные, транскрипты (faster-whisper), хранение в 05data."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import Settings
from paths import AUDIO_EXTS, catalog_root

TRANSCRIPT_REL_DIR = "05data/aviora_audio_transcripts"


def transcripts_dir(settings: Settings) -> Path:
    target = (catalog_root(settings) / TRANSCRIPT_REL_DIR).resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def transcript_md_path(settings: Settings, source_rel: str) -> Path:
    norm = source_rel.replace("\\", "/").strip("/")
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^\w\-]+", "_", Path(norm).stem)[:48].strip("_") or "audio"
    return transcripts_dir(settings) / f"{stem}__{digest}.md"


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = parts[2].strip()
    if body.startswith("# "):
        body = "\n".join(body.splitlines()[1:]).strip()
    return meta, body


def read_transcript_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"text": "", "meta": {}, "path": None}
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_front_matter(raw)
    rel = meta.get("source", "")
    return {
        "text": body,
        "meta": meta,
        "path": rel,
        "file": str(path),
    }


def transcript_for_source(settings: Settings, source_rel: str) -> dict[str, Any]:
    md = transcript_md_path(settings, source_rel)
    out = read_transcript_file(md)
    out["transcript_rel"] = (
        md.relative_to(catalog_root(settings)).as_posix() if md.is_file() else None
    )
    out["has_transcript"] = bool(out.get("text"))
    return out


def transcript_text_for_index(settings: Settings, source_rel: str) -> str:
    tr = transcript_for_source(settings, source_rel)
    body = (tr.get("text") or "").strip()
    if not body:
        return ""
    return body[:120_000]


def write_transcript_md(
    settings: Settings,
    *,
    source_rel: str,
    body: str,
    engine: str,
    model: str,
    duration_sec: float | None,
) -> str:
    md = transcript_md_path(settings, source_rel)
    now = datetime.now(timezone.utc).isoformat()
    dur = f"{duration_sec:.1f}" if duration_sec is not None else ""
    header = (
        "---\n"
        f"source: {source_rel}\n"
        f"transcribed_at: {now}\n"
        f"engine: {engine}\n"
        f"model: {model}\n"
        f"duration_sec: {dur}\n"
        "---\n\n"
        f"# Transcript: {Path(source_rel).name}\n\n"
    )
    md.write_text(header + body.strip() + "\n", encoding="utf-8")
    return md.relative_to(catalog_root(settings)).as_posix()


def probe_audio_meta(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "duration_sec": None,
        "title": None,
        "artist": None,
        "bitrate": None,
    }
    try:
        from mutagen import File as MutagenFile  # type: ignore

        audio = MutagenFile(path)
        if audio is None:
            return out
        info = getattr(audio, "info", None)
        if info is not None and getattr(info, "length", None):
            out["duration_sec"] = round(float(info.length), 1)
        tags = getattr(audio, "tags", None)
        if tags:
            out["title"] = _tag(tags, "TIT2", "TITLE", "\xa9nam")
            out["artist"] = _tag(tags, "TPE1", "ARTIST", "\xa9ART")
            if getattr(info, "bitrate", None):
                out["bitrate"] = int(info.bitrate)
    except Exception:
        pass
    return out


def _tag(tags: Any, *keys: str) -> str | None:
    for k in keys:
        if k in tags and tags[k]:
            v = tags[k]
            if isinstance(v, (list, tuple)) and v:
                return str(v[0])
            return str(v)
    return None


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        return False


def ffmpeg_available() -> bool:
    import shutil

    return shutil.which("ffmpeg") is not None


def max_transcribe_mb() -> int:
    return int(os.environ.get("MAX_AUDIO_TRANSCRIBE_MB", "1024"))


def _max_transcribe_bytes(settings: Settings) -> int:
    return max_transcribe_mb() * 1024 * 1024


def _chunk_seconds() -> int:
    return max(120, int(os.environ.get("WHISPER_CHUNK_SEC", "600")))


def _use_chunked_transcription(target: Path, meta: dict[str, Any]) -> bool:
    if not ffmpeg_available():
        return False
    size_mb = target.stat().st_size / (1024 * 1024)
    if size_mb >= float(os.environ.get("WHISPER_CHUNK_SIZE_MB", "80")):
        return True
    dur = meta.get("duration_sec") or 0
    chunk_min = int(os.environ.get("WHISPER_CHUNK_MINUTES", "15"))
    return float(dur) >= chunk_min * 60


def _split_audio_chunks(target: Path, work_dir: Path, chunk_sec: int) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    for old in work_dir.glob("part_*.mp3"):
        old.unlink(missing_ok=True)
    pattern = work_dir / "part_%03d.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(target),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_sec),
        "-acodec",
        "libmp3lame",
        "-q:a",
        "4",
        str(pattern),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-500:]
        raise RuntimeError(f"ffmpeg split failed: {err}")
    parts = sorted(work_dir.glob("part_*.mp3"))
    if not parts:
        raise RuntimeError("ffmpeg produced no chunks")
    return parts


def _transcribe_one(
    model: Any,
    audio_path: Path,
    *,
    language: str | None,
    cancel_check: Callable[[], bool],
) -> tuple[str, Any]:
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
    )
    lines: list[str] = []
    for seg in segments:
        if cancel_check():
            return "", info
        t = seg.text.strip()
        if t:
            lines.append(t)
    return "\n".join(lines).strip(), info


def run_transcription(
    settings: Settings,
    source_rel: str,
    *,
    cancel_check: Callable[[], bool],
    on_message: Callable[[str], None],
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    def prog(progress: int, total: int, msg: str) -> None:
        on_message(msg)
        if on_progress:
            on_progress(progress, total, msg)
    root = catalog_root(settings)
    target = (root / source_rel.replace("\\", "/")).resolve()
    if not target.is_file():
        raise FileNotFoundError(source_rel)
    if target.suffix.lower() not in AUDIO_EXTS:
        raise ValueError("Not an audio file")
    size = target.stat().st_size
    limit_mb = max_transcribe_mb()
    if size > _max_transcribe_bytes(settings):
        raise ValueError(
            f"File too large ({size // (1024 * 1024)} MB). "
            f"Limit MAX_AUDIO_TRANSCRIBE_MB={limit_mb} in backend/.env"
        )

    if not whisper_available():
        raise RuntimeError(
            "faster-whisper not installed. Run: pip install faster-whisper "
            "(and install ffmpeg for some formats)."
        )

    from faster_whisper import WhisperModel

    model_name = os.environ.get("WHISPER_MODEL", "small")
    language = os.environ.get("WHISPER_LANGUAGE", "ru") or None
    device = os.environ.get("WHISPER_DEVICE", "cpu")
    compute = os.environ.get("WHISPER_COMPUTE", "int8")

    prog(2, 100, f"Загрузка модели {model_name}…")
    model = WhisperModel(model_name, device=device, compute_type=compute)

    if cancel_check():
        return {"cancelled": True}

    lang = language if language != "auto" else None
    ameta = probe_audio_meta(target)
    chunk_sec = _chunk_seconds()
    work_dir: Path | None = None
    info: Any = None
    text_parts: list[str] = []

    try:
        if _use_chunked_transcription(target, ameta):
            if not ffmpeg_available():
                raise RuntimeError("Long audio needs ffmpeg in PATH for chunked mode")
            digest = hashlib.sha256(source_rel.encode()).hexdigest()[:10]
            work_dir = transcripts_dir(settings) / "_work" / digest
            prog(8, 100, f"Нарезка на части (~{chunk_sec // 60} мин)…")
            parts = _split_audio_chunks(target, work_dir, chunk_sec)
            total = len(parts)
            prog(12, 100, f"Режим частей: {total} фрагментов")
            for i, part in enumerate(parts, start=1):
                if cancel_check():
                    return {"cancelled": True}
                pct = 12 + int(82 * (i - 1) / max(total, 1))
                prog(
                    pct,
                    100,
                    f"Распознавание части {i} из {total}…",
                )
                part_text, info = _transcribe_one(
                    model, part, language=lang, cancel_check=cancel_check
                )
                if cancel_check():
                    return {"cancelled": True}
                if part_text:
                    text_parts.append(part_text)
                prog(
                    12 + int(82 * i / max(total, 1)),
                    100,
                    f"Готово частей: {i}/{total}",
                )
        else:
            prog(15, 100, "Распознавание (длинная запись — подождите)…")
            part_text, info = _transcribe_one(
                model, target, language=lang, cancel_check=cancel_check
            )
            if cancel_check():
                return {"cancelled": True}
            if part_text:
                text_parts.append(part_text)
            prog(90, 100, "Распознавание завершено")
    finally:
        if work_dir and work_dir.is_dir():
            shutil.rmtree(work_dir, ignore_errors=True)

    text = "\n\n".join(text_parts).strip()
    if not text:
        text = "(empty transcript)"

    prog(95, 100, "Сохранение транскрипта…")
    duration = ameta.get("duration_sec") or getattr(info, "duration", None)
    rel_md = write_transcript_md(
        settings,
        source_rel=source_rel.replace("\\", "/"),
        body=text,
        engine="faster-whisper",
        model=model_name,
        duration_sec=float(duration) if duration else None,
    )
    return {
        "cancelled": False,
        "transcript_path": rel_md,
        "chars": len(text),
        "language": getattr(info, "language", None),
    }
