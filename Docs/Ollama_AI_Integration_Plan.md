# Ollama-based AI — integration plan

**Last updated:** 2026-03-28  

This document describes how to add **Ollama** as an AI backend for FastForms-style features (form assistance, classification, extraction, embeddings) alongside existing cloud or gateway LLM integrations. It is a **planning** artifact: implement in phases and adjust filenames to match the repo when coding.

---

## Goals

- Run **local or LAN-hosted** open models without sending prompts to a third-party API when policy or cost requires it.
- Reuse a **single client abstraction** so pipelines (prompt build → HTTP → parse) stay unchanged; only the transport and base URL differ.
- Keep **configuration explicit** (env vars, optional feature flag) so production defaults remain safe.

---

## Why Ollama

[Ollama](https://ollama.com/) serves models via an HTTP API that is **largely OpenAI-compatible** (`POST /v1/chat/completions`, JSON body with `model`, `messages`). That allows minimal branching if the existing stack already speaks OpenAI-style chat payloads.

Alternatives (LM Studio, vLLM, llama.cpp servers) can be treated the same way if they expose a compatible `/v1` surface; Ollama is the reference here because of simple local install and model pulls.

---

## Architecture

### Provider abstraction

Introduce or extend a small **LLM provider** interface used by services and jobs:

| Concern | Approach |
|--------|----------|
| **Selection** | Config or feature flag: `LLM_PROVIDER=ollama` \| `openai_compatible` \| existing gateway id. |
| **Endpoint** | `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`). Append `/v1/chat/completions` for chat. |
| **Auth** | None for default local Ollama; optional `OLLAMA_API_KEY` if fronted by a proxy that requires it. |
| **Model** | `OLLAMA_MODEL` (e.g. `llama3.2`, `mistral`, `qwen2.5`). Keep separate from cloud model names. |
| **Streaming** | Optional phase 2: if the app uses streaming today, enable `stream: true` with SSE parsing; otherwise keep non-streaming. |

Avoid duplicating prompt assembly: one code path builds `messages`; the provider only serializes and calls HTTP.

### Where this plugs in

- **Backend** (Django/FastAPI): any module that currently calls a remote chat API should call the provider abstraction.
- **Shared library** (if present): centralize HTTP client, timeouts, retries, and logging (redact prompts in production logs if required by policy).
- **Frontend**: no direct browser calls to Ollama unless explicitly allowed; **prefer server-side** calls so the API base URL and model policy stay on the server.

---

## Configuration (environment)

| Variable | Purpose | Example |
|----------|---------|---------|
| `LLM_PROVIDER` | Select backend | `ollama` |
| `OLLAMA_BASE_URL` | Base URL without path | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Model tag known to `ollama pull` | `llama3.2` |
| `OLLAMA_TIMEOUT` | Request timeout (seconds) | `120` |
| `OLLAMA_API_KEY` | Optional, for secured proxies | (empty locally) |

Document these in `.env.example` when implementation starts.

---

## Security and operations

- **Local default**: Ollama binds to localhost; acceptable for dev. For shared machines, restrict firewall and bind address.
- **Remote Ollama**: Treat as **untrusted network** unless TLS and authentication are in place; prefer VPN or SSH tunnel rather than exposing port 11434.
- **Data residency**: Local inference reduces third-party exposure; **logging** must still avoid leaking PII in prompts (align with existing audit/logging policy).
- **Availability**: No SLA for local Ollama; callers should surface clear errors and optional fallback only if product requirements allow (not automatic without explicit approval).

---

## Compatibility notes

- **JSON / structured output**: Rely on prompt + parsing; if the product uses response_format or tool calling, verify the chosen Ollama model and version support it.
- **Embeddings**: If the app uses embeddings for RAG, Ollama exposes `/v1/embeddings` for compatible models; plan a separate embedding provider or the same client with a different path.
- **Token limits**: Local models may have smaller context; add truncation or chunking where existing pipelines assume large cloud limits.

---

## Testing strategy

1. **Unit tests**: Mock HTTP responses for chat completions (success, timeout, 4xx/5xx).
2. **Integration (optional CI)**: Skip live Ollama in CI by default; optional job with `services: ollama` or a manual nightly run.
3. **Manual smoke**: `ollama run <model>` then hit the app with `LLM_PROVIDER=ollama` and one end-to-end flow (e.g. classification or extraction).

---

## Phased rollout

| Phase | Scope | Outcome |
|-------|--------|---------|
| **P1** | Provider interface + env-based Ollama chat for **one** low-risk path (e.g. dev-only or admin-only) | Proves HTTP contract and config |
| **P2** | Wire remaining LLM call sites or feature-flagged parity with existing gateway | Feature parity where models allow |
| **P3** | Embeddings, streaming, or model auto-selection | Optional; driven by product need |

---

## Related documents

| Document | Role |
|----------|------|
| [ExecutionPlan.md](ExecutionPlan.md) | Overall engineering plan and priorities |
| [ExecutionRoadmap.md](ExecutionRoadmap.md) | Phases and backlog |
| [RUN_ON_NEW_SYSTEM.md](RUN_ON_NEW_SYSTEM.md) | Optional: install Ollama + pull models on a new machine |

When this work is scheduled, add a short row under the appropriate phase in `ExecutionPlan.md` (or `ExecutionRoadmap.md`) pointing to this file.

---

## Acceptance criteria (for the implementation PR)

- [x] Ollama can be selected via configuration without code edits outside the provider layer (`apps.llm.client`, `config/settings.py`).
- [x] Existing non-Ollama behavior remains default when Ollama is not configured (`LLM_PROVIDER` unset → `llm_enabled: false`, suggest returns 503).
- [x] `.env.example` documents new variables and safe defaults.
- [x] Tests cover provider selection and error handling; no secrets in repo or logs.

## Implementation (2026-03-28)

| Piece | Location |
|-------|----------|
| Settings | `LLM_PROVIDER`, `OLLAMA_*` in [backend/config/settings.py](../backend/config/settings.py) |
| HTTP client | [backend/apps/llm/client.py](../backend/apps/llm/client.py) — `chat_completion()`, `is_llm_configured()` |
| Form JSON parsing | [backend/apps/llm/suggest.py](../backend/apps/llm/suggest.py) |
| API | `GET /api/ai/health`, `POST /api/ai/suggest_form` — [backend/apps/llm/views.py](../backend/apps/llm/views.py), routed in [backend/config/urls.py](../backend/config/urls.py) |
| Designer UI | “AI form draft (Ollama)” on the Questions tab when logged in as creator/admin |
| Tests | [backend/apps/llm/tests.py](../backend/apps/llm/tests.py) |
