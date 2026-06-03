from __future__ import annotations

import time
from typing import Any, Literal

import httpx

from config import Settings

_LLM_HEALTH_CACHE: dict[str, dict[str, Any]] = {}
_LLM_HEALTH_TTL_SEC = 8.0


def invalidate_llm_health_cache() -> None:
    _LLM_HEALTH_CACHE.clear()

Provider = Literal["deepseek", "lmstudio"]


def choose_provider(settings: Settings, requested: str) -> Provider | None:
    req = (requested or settings.llm_default or "auto").lower()
    if req == "none":
        return None
    if req == "deepseek" and settings.deepseek_api_key:
        return "deepseek"
    if req in ("lmstudio", "lm_studio") and settings.lmstudio_base_url:
        return "lmstudio"
    if req == "auto":
        if settings.deepseek_api_key:
            return "deepseek"
        return "lmstudio"
    return None


def llm_ok(settings: Settings) -> bool:
    return choose_provider(settings, settings.llm_default) is not None


def _lmstudio_base_candidates(settings: Settings) -> list[str]:
    raw = (settings.lmstudio_base_url or "http://127.0.0.1:1234/v1").rstrip("/")
    if not raw.endswith("/v1"):
        raw_v1 = raw + "/v1"
    else:
        raw_v1 = raw
    bases = [raw_v1, "http://127.0.0.1:1234/v1", "http://localhost:1234/v1"]
    seen: set[str] = set()
    out: list[str] = []
    for b in bases:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def _model_from_lmstudio_native(payload: dict[str, Any], fallback: str) -> str:
    loaded: list[str] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        instances = item.get("loaded_instances") or []
        if instances:
            loaded.append(str(item.get("key") or item.get("display_name") or fallback))
    if loaded:
        return loaded[0]
    for item in payload.get("models") or []:
        if isinstance(item, dict) and item.get("key"):
            return str(item["key"])
    return fallback


def _probe_lmstudio_http(settings: Settings, info: dict[str, Any], fallback: str) -> None:
    errors: list[str] = []
    roots = ["http://127.0.0.1:1234", "http://localhost:1234"]
    env_base = (settings.lmstudio_base_url or "").rstrip("/")
    if env_base:
        root = env_base.replace("/v1", "").replace("/api/v1", "").rstrip("/")
        if root not in roots:
            roots.insert(0, root)

    urls: list[tuple[str, str]] = []
    for root in roots:
        urls.append((f"{root}/v1/models", "openai"))
        urls.append((f"{root}/api/v1/models", "native"))

    for url, kind in urls:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
            if not response.is_success:
                errors.append(f"{url} → HTTP {response.status_code}")
                continue
            payload = response.json()
            if kind == "openai":
                models = payload.get("data") or []
                if isinstance(models, list) and models:
                    info["llm_active_model"] = _pick_lmstudio_model(models, fallback)
            else:
                info["llm_active_model"] = _model_from_lmstudio_native(payload, fallback)
            info["llm_reachable"] = True
            info["llm_status"] = "lm_studio_online"
            info["llm_probe_url"] = url
            info["llm_probe_error"] = None
            info["llm_probe_hint"] = None
            return
        except Exception as exc:
            errors.append(f"{url} → {exc.__class__.__name__}: {exc}")

    info["llm_reachable"] = False
    info["llm_status"] = "lm_studio_unreachable"
    info["llm_probe_error"] = "; ".join(errors[:4]) or "no response"
    info["llm_probe_hint"] = (
        "LM Studio: Status Running на :1234, затем ↻ в Catalog. "
        "Если сервер уже Running — перезапустите backend Catalog (порт 8002)."
    )


def _pick_lmstudio_model(models: list[dict[str, Any]], fallback: str) -> str:
    for item in models:
        if item.get("loaded") or item.get("state") == "loaded":
            mid = item.get("id")
            if mid:
                return str(mid)
    for item in models:
        mid = item.get("id")
        if mid:
            return str(mid)
    return fallback


def resolve_lmstudio_model(settings: Settings) -> str:
    """Имя модели для /chat/completions (не local-model — иначе HTTP 400)."""
    fallback = settings.lmstudio_model or "local-model"
    info: dict[str, Any] = {"llm_active_model": fallback}
    _probe_lmstudio_http(settings, info, fallback)
    return str(info.get("llm_active_model") or fallback)


def llm_health_info(
    settings: Settings,
    *,
    ui_provider: str | None = None,
    session_enabled: bool = True,
) -> dict[str, Any]:
    requested = (ui_provider or settings.llm_default or "auto").lower().strip()
    now = time.monotonic()
    cached = _LLM_HEALTH_CACHE.get(requested)
    if cached and now - float(cached.get("_t") or 0) < _LLM_HEALTH_TTL_SEC:
        out = {k: v for k, v in cached.items() if k != "_t"}
        out["llm_session_enabled"] = session_enabled
        out["llm_chat_enabled"] = session_enabled
        return out

    provider = choose_provider(settings, requested)
    info: dict[str, Any] = {
        "llm_default": settings.llm_default,
        "llm_ui_provider": requested,
        "llm_auto_resolves_to": provider,
        "llm_session_enabled": session_enabled,
        "llm_chat_enabled": session_enabled,
        "llm_deepseek_configured": bool(settings.deepseek_api_key),
        "llm_lm_studio_configured": bool(settings.lmstudio_base_url),
        "llm_lm_studio_url": settings.lmstudio_base_url,
        "llm_active_model": None,
        "llm_reachable": False,
        "llm_status": "no_llm_configured",
    }
    if not provider:
        if requested == "deepseek" and not settings.deepseek_api_key:
            info["llm_status"] = "deepseek_not_configured"
        elif requested in ("lmstudio", "lm_studio"):
            info["llm_status"] = "lm_studio_not_configured"
        else:
            info["llm_status"] = "no_llm_configured"
        _LLM_HEALTH_CACHE[requested] = {**info, "_t": now}
        return info

    if provider == "deepseek":
        info.update(
            llm_active_model="deepseek-chat",
            llm_reachable=True,
            llm_status="deepseek_ready",
        )
        _LLM_HEALTH_CACHE[requested] = {**info, "_t": now}
        return info

    fallback = settings.lmstudio_model or "local-model"
    info["llm_active_model"] = fallback
    _probe_lmstudio_http(settings, info, fallback)

    info["llm_session_enabled"] = session_enabled
    info["llm_chat_enabled"] = session_enabled
    _LLM_HEALTH_CACHE[requested] = {**info, "_t": now}
    return info


def chat_completion(
    settings: Settings,
    *,
    provider: Provider,
    system_prompt: str,
    user_prompt: str,
    cancel_check,
) -> tuple[str, dict[str, Any] | None]:
    if provider == "deepseek":
        base = settings.deepseek_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = base + "/v1"
        api_key = settings.deepseek_api_key or ""
        model = "deepseek-chat"
    else:
        base = settings.lmstudio_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = base.rstrip("/") + "/v1"
        api_key = "lm-studio"
        model = resolve_lmstudio_model(settings)

    url = base + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=120.0) as client:
        if cancel_check():
            raise RuntimeError("cancelled")
        response = client.post(url, json=payload, headers=headers)
        if cancel_check():
            raise RuntimeError("cancelled")
        response.raise_for_status()
        data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Empty LLM response")
    content = (choices[0].get("message") or {}).get("content") or ""
    usage = data.get("usage")
    return str(content).strip(), usage
