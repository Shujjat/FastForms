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

## Password reset

- `POST /api/auth/password-reset` with `{ "email": "..." }` sends an email (if the user exists) with a link built from `FRONTEND_BASE_URL`.
- In development, email is usually printed to the console (`EMAIL_BACKEND`).

## Operational hygiene

- Run `pip-audit` / `npm audit` periodically; consider CI for dependency checks.
- Keep PostgreSQL and Redis patched and network-restricted in production.
