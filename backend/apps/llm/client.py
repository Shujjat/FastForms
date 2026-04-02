"""
OpenAI-compatible chat completions against Ollama (or any compatible server).

See Docs/Ollama_AI_Integration_Plan.md for configuration.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Seconds to wait for TCP connect to Ollama before failing (fast fail if daemon is down).
OLLAMA_CONNECT_TIMEOUT = 10

# Cache resolved OLLAMA_MODEL=auto per base URL for this process.
_auto_model_cache: dict[str, str] = {}

# Prefer these for form/JSON tasks; skip dedicated code models when auto-selecting.
_CODE_MODEL_PREFIXES = ("codellama", "deepseek-coder", "codegemma", "starcoder")
_PREFERRED_HINTS = (
    "qwen",
    "phi",
    "gemma",
    "mistral",
    "llama",
    "mixtral",
    "tinyllama",
    "vicuna",
    "openchat",
)


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
        RuntimeError: if LLM is not configured, HTTP error from Ollama, or read/connect timeout
        KeyError, IndexError: on unexpected response shape
    """
    if not is_llm_configured():
        raise RuntimeError("LLM is not configured (set LLM_PROVIDER=ollama).")

    base = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    url = f"{base}/v1/chat/completions"
    read_sec = int(getattr(settings, "OLLAMA_TIMEOUT", 300))
    req_timeout = (OLLAMA_CONNECT_TIMEOUT, read_sec)
    configured = (model or getattr(settings, "OLLAMA_MODEL", "auto") or "auto").strip()
    mdl = _resolve_effective_model(base, configured)

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

    msg_chars = sum(len(str(m.get("content") or "")) for m in messages)
    host = base.split("://", 1)[-1].split("/")[0] if "://" in base else base
    logger.info(
        "Ollama POST /v1/chat/completions start model=%r host=%s messages=%d prompt_chars=%d read_timeout_s=%d temp=%s",
        mdl,
        host,
        len(messages),
        msg_chars,
        read_sec,
        temperature,
    )
    t0 = time.monotonic()
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=req_timeout)
    except requests.Timeout as e:
        elapsed = time.monotonic() - t0
        logger.warning(
            "Ollama chat_completion TIMEOUT model=%r elapsed_s=%.2f read_timeout_s=%d error=%s",
            mdl,
            elapsed,
            read_sec,
            e,
        )
        raise RuntimeError(
            f"Ollama did not respond in time (read timeout {read_sec}s). "
            "Increase OLLAMA_TIMEOUT in backend .env, use a smaller model (e.g. phi3:latest), "
            "or warm the model with `ollama run <model>` in a terminal."
        ) from e
    elapsed = time.monotonic() - t0
    if resp.status_code >= 400:
        detail = _ollama_http_error_detail(resp, mdl)
        logger.warning(
            "Ollama chat_completion HTTP_ERROR model=%r status=%d elapsed_s=%.2f detail=%s",
            mdl,
            resp.status_code,
            elapsed,
            detail[:500],
        )
        raise RuntimeError(detail)
    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("Ollama chat_completion BAD_RESPONSE elapsed_s=%.2f keys=%s", elapsed, list(data) if isinstance(data, dict) else type(data))
        raise RuntimeError("Ollama returned an unexpected response (missing message content).") from e
    if content is None or (isinstance(content, str) and not str(content).strip()):
        logger.warning("Ollama chat_completion EMPTY_CONTENT model=%r elapsed_s=%.2f", mdl, elapsed)
        raise RuntimeError("Ollama returned empty message content.")
    out = str(content).strip()
    logger.info(
        "Ollama chat_completion OK model=%r elapsed_s=%.2f response_chars=%d http_status=%d",
        mdl,
        elapsed,
        len(out),
        resp.status_code,
    )
    return out


def _is_code_model(name_lower: str) -> bool:
    return any(name_lower.startswith(p) for p in _CODE_MODEL_PREFIXES)


def _pick_chat_model(names: list[str]) -> str | None:
    if not names:
        return None
    pairs = [(n, n.lower()) for n in names]
    for n, low in pairs:
        if _is_code_model(low):
            continue
        for hint in _PREFERRED_HINTS:
            if hint in low:
                return n
    for n, low in pairs:
        if not _is_code_model(low):
            return n
    return names[0]


def _ollama_installed_model_names(base: str) -> list[str]:
    tag_read = min(15, int(getattr(settings, "OLLAMA_TIMEOUT", 300)))
    r = requests.get(f"{base}/api/tags", timeout=(OLLAMA_CONNECT_TIMEOUT, tag_read))
    r.raise_for_status()
    data = r.json() or {}
    models = data.get("models") or []
    out: list[str] = []
    for m in models:
        name = m.get("name") if isinstance(m, dict) else None
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


def _resolve_effective_model(base: str, configured: str) -> str:
    if configured.lower() != "auto":
        return configured
    cached = _auto_model_cache.get(base)
    if cached:
        return cached
    try:
        names = _ollama_installed_model_names(base)
    except requests.RequestException as e:
        logger.warning("Ollama GET /api/tags failed base=%s: %s", base, e)
        raise RuntimeError(
            "Could not list Ollama models (is Ollama running?). "
            f"Expected GET {base}/api/tags. {e}"
        ) from e
    picked = _pick_chat_model(names)
    if not picked:
        raise RuntimeError(
            "OLLAMA_MODEL=auto but no models are installed. Run `ollama pull qwen3` or set OLLAMA_MODEL to a tag from `ollama list`."
        )
    _auto_model_cache[base] = picked
    logger.info("OLLAMA_MODEL=auto selected %r from installed tags.", picked)
    return picked


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


def ollama_health_model_display() -> str:
    """Configured or cached-resolved model tag for health UI (no network)."""
    if not is_llm_configured():
        return ""
    configured = (getattr(settings, "OLLAMA_MODEL", "auto") or "auto").strip()
    if configured.lower() != "auto":
        return configured
    base = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    return _auto_model_cache.get(base) or "auto"
