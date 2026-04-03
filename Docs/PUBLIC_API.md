# FastForms public API (v1) for integrators

This document is for **operators** who expose FastForms to customers or internal systems via HTTP. End-user browsers normally use JWT login; **integrations** should use **API keys** and **`/api/v1/`**.

## Overview

| Area | Base path | Authentication |
|------|-----------|----------------|
| Integration API | `/api/v1/` | `X-Api-Key: <secret>` or `Authorization: Api-Key <secret>` |
| Create / revoke keys | `/api/auth/api-keys` | JWT (`Authorization: Bearer <access>`) after `POST /api/auth/login` |
| Interactive docs | `/api/docs/swagger/` | None by default (set `ENABLE_API_DOCS=False` to disable) |
| Machine-readable schema | `GET /api/schema/` | OpenAPI 3 |

## Scopes

Each key carries a subset of:

| Scope | Allows |
|-------|--------|
| `forms:read` | `GET /api/v1/forms`, `GET /api/v1/forms/{id}` |
| `forms:write` | `POST /api/v1/forms` (creator/admin accounts only) |
| `responses:read` | `GET /api/v1/forms/{id}/responses` (owner-only forms) |
| `responses:submit` | `POST /api/v1/forms/{id}/submit` |

Omit `scopes` when creating a key to receive **all** scopes; prefer least privilege for production.

## Creating a key (example)

```http
POST /api/auth/api-keys
Authorization: Bearer <access_token>
Content-Type: application/json

{"name": "CRM integration", "scopes": ["forms:read", "responses:read", "responses:submit"]}
```

Response `201` includes `"key": "ff_...."` **once**. Store it in a secret manager; the server only keeps a hash.

## Calling the integration API

```http
GET /api/v1/forms
X-Api-Key: ff_your_secret_here
```

Pagination: `?page=2&page_size=50` (max page size 100 on v1 list endpoints).

## Revoking

```http
DELETE /api/auth/api-keys/42
Authorization: Bearer <access_token>
```

The key is soft-deactivated (`is_active=false`).

## Security practices

- Rotate keys periodically; revoke on employee offboarding.
- Never commit keys to git or send them in query strings.
- Use HTTPS only in production (`DEBUG=False` with TLS).
- Restrict scopes: e.g. backend workers that only ingest submissions need `responses:submit` (and optionally `forms:read` to discover form IDs).

## Support

Point integrators at **Swagger** (`/api/docs/swagger/`) for request/response models and to try calls with **Authorize → ApiKeyAuth**.
