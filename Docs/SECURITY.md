# FastForms — Security notes

This document summarizes how security is configured and what operators should verify in production.

## Authentication

- JWT access and refresh tokens are issued by SimpleJWT (`/api/auth/login`, `/api/auth/token/refresh`).
- **Google Sign-In** (`POST /api/auth/google`) accepts a Google ID token (`credential`) and returns the same JWT pair. Configure `GOOGLE_OAUTH_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend) to the same OAuth 2.0 Web client ID. New users get an unusable Django password until they use password reset.
- Access tokens are short-lived; refresh tokens rotate on refresh when blacklist is enabled.
- Tokens are stored in `localStorage` in the default frontend. Any XSS in the app could steal tokens. Keep dependencies updated and avoid injecting untrusted HTML.

## Environment and secrets

- Set `DJANGO_SECRET_KEY` to a long random value in production. Django refuses to start with `DEBUG=False` if the key is missing or weak.
- Never commit `backend/.env` or real credentials.

## CORS

- With `DEBUG=True`, all origins are allowed (local development).
- With `DEBUG=False`, set `CORS_ALLOWED_ORIGINS` to a comma-separated list of frontend origins (e.g. `https://app.example.com`).

## HTTPS and cookies

When `DEBUG=False`, the app enables HTTPS-related settings (`SECURE_SSL_REDIRECT`, secure cookies, HSTS). Terminate TLS at a reverse proxy (nginx, Caddy, etc.) and forward `X-Forwarded-Proto` so Django knows the request was HTTPS.

## Rate limits

- Global API throttles apply to anonymous and authenticated users.
- Auth endpoints (`login`, `register`, `token/refresh`, password reset) use a stricter `auth` scope (see `REST_FRAMEWORK` in `backend/config/settings.py`).
- Optional AI endpoints (`/api/ai/*`) use a dedicated `ai` throttle scope (per authenticated user). Tune rates in `DEFAULT_THROTTLE_RATES` if you self-host heavy traffic.

## Optional LLM (Ollama)

- AI features are **server-side only**: the backend calls your Ollama (OpenAI-compatible) endpoint using `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and related settings in `backend/.env` — see `backend/.env.example` and [Ollama_AI_Integration_Plan.md](Ollama_AI_Integration_Plan.md).
- Do not put API keys or model endpoints in the frontend bundle; the React app only calls FastForms APIs.
- If you expose Ollama beyond localhost, use network controls and optional `OLLAMA_API_KEY` as appropriate for your environment.

## User management (admin API)

- Endpoints under **`/api/users/`** (list, create, retrieve, update, soft-delete) require application **`role=admin`** or a Django **superuser** (`IsAdminUser` in `backend/apps/users/permissions.py`).
- **Staff** (`is_staff`) can only be granted or changed by **superusers** (Django admin access).
- The API prevents removing the **last active admin** (by role) and prevents users from deactivating themselves via the deactivate flow.
- The SPA **`/admin/users`** page calls these APIs; treat admin accounts like production credentials.

## Password reset

- `POST /api/auth/password-reset` with `{ "email": "..." }` sends an email (if the user exists) with a link built from `FRONTEND_BASE_URL`.
- In development, email is usually printed to the console (`EMAIL_BACKEND`).

## Operational hygiene

- Run `pip-audit` / `npm audit` periodically; consider CI for dependency checks.
- Keep PostgreSQL and Redis patched and network-restricted in production.

## Reporting vulnerabilities

Please report security issues **privately** instead of using public issues, so they can be addressed before disclosure.

- Prefer [GitHub Security Advisories](https://github.com/Shujjat/FastForms/security/advisories/new) if enabled on the repository, or
- Contact the maintainers with enough detail to reproduce (affected version, steps, impact). Maintainer email and WhatsApp are listed in [CONTRIBUTING.md](CONTRIBUTING.md) under **Maintainer contact**.

Do not include live credentials or production data in reports.
