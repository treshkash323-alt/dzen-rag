from __future__ import annotations

from typing import Literal

import httpx

from aikivaviora_shared.rag.config import RagSettings
from aikivaviora_shared.rag.store import RetrievedChunk

Provider = Literal["deepseek", "lm_studio"]


def choose_provider(settings: RagSettings) -> Provider | None:
    default = settings.llm_default
    if default == "lm_studio" and settings.lm_studio_model:
        return "lm_studio"
    if default == "deepseek" and settings.deepseek_api_key:
        return "deepseek"
    if settings.deepseek_api_key:
        return "deepseek"
    if settings.lm_studio_model:
        return "lm_studio"
    return None


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk.metadata
        label = meta.get("filename") or meta.get("relative_path") or f"chunk-{i}"
        parts.append(f"[{i}] {label}\n{chunk.text}")
    return "\n\n---\n\n".join(parts)


def generate_answer(
    settings: RagSettings,
    query: str,
    chunks: list[RetrievedChunk],
    *,
    provider: Provider | None = None,
) -> tuple[str | None, Provider | None, str]:
    selected = provider or choose_provider(settings)
    if selected is None:
        return None, None, "no_llm_configured"

    context = build_context_block(chunks)
    system_prompt = (
        "Ты ассистент по базе знаний канала «Канал про ИИ». "
        "Отвечай ТОЛЬКО на основе предоставленного контекста, по-русски. "
        "Если ответа нет в контексте, скажи: «Информация не найдена в базе знаний». "
        "Не выдумывай факты."
    )
    user_prompt = (
        f"Контекст:\n{context}\n\n"
        f"Вопрос пользователя:\n{query}\n\n"
        "Дай краткий структурированный ответ."
    )

    try:
        if selected == "deepseek":
            answer = _call_openai_compatible(
                base_url=settings.deepseek_base_url,
                api_key=settings.deepseek_api_key or "",
                model="deepseek-chat",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        else:
            model = settings.lm_studio_model or "local-model"
            answer = _call_openai_compatible(
                base_url=settings.lm_studio_base_url,
                api_key="lm-studio",
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
    except Exception as exc:
        return None, selected, f"llm_error: {exc.__class__.__name__}"

    return answer, selected, "ok"


def _call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Empty LLM response")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("LLM returned no content")
    return str(content).strip()
