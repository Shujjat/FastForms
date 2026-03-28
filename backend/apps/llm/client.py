"""
OpenAI-compatible chat completions against Ollama (or any compatible server).

See Docs/Ollama_AI_Integration_Plan.md for configuration.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def is_llm_configured() -> bool:
    return getattr(settings, "LLM_PROVIDER", "").strip().lower() == "ollama"


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
) -> str:
    """
    Non-streaming chat completion. Returns assistant message content.

    Raises:
        RuntimeError: if LLM is not configured
        requests.RequestException: on HTTP / network errors
        KeyError, IndexError: on unexpected response shape
    """
    if not is_llm_configured():
        raise RuntimeError("LLM is not configured (set LLM_PROVIDER=ollama).")

    base = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    url = f"{base}/v1/chat/completions"
    timeout = int(getattr(settings, "OLLAMA_TIMEOUT", 120))
    mdl = model or getattr(settings, "OLLAMA_MODEL", "llama3.2")

    headers = {"Content-Type": "application/json"}
    api_key = getattr(settings, "OLLAMA_API_KEY", "") or ""
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    body: dict[str, Any] = {
        "model": mdl,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }

    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(_ollama_http_error_detail(resp, mdl))
    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("Unexpected Ollama JSON: %s", data)
        raise RuntimeError("Ollama returned an unexpected response (missing message content).") from e
    if content is None or (isinstance(content, str) and not str(content).strip()):
        raise RuntimeError("Ollama returned empty message content.")
    return str(content).strip()


def _ollama_http_error_detail(resp: requests.Response, model: str) -> str:
    """Human-readable error for failed chat/completions (e.g. unknown model)."""
    msg = ""
    try:
        j = resp.json()
        err = j.get("error")
        if isinstance(err, dict):
            msg = str(err.get("message") or err)
        elif err is not None:
            msg = str(err)
    except Exception:
        msg = (resp.text or "")[:500]
    low = msg.lower()
    if resp.status_code == 404 and "not found" in low and "model" in low:
        return (
            f"Ollama does not have model {model!r}. "
            f"Run `ollama list` and set OLLAMA_MODEL to an installed tag "
            f"(e.g. OLLAMA_MODEL=qwen3:latest), or run `ollama pull {model}`."
        )
    return f"Ollama HTTP {resp.status_code}: {msg or resp.reason or 'request failed'}"
