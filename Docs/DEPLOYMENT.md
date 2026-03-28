# FastForms — Deployment

This guide describes how to run FastForms in production. For a **fresh developer machine** (Windows, local PostgreSQL), see [RUN_ON_NEW_SYSTEM.md](RUN_ON_NEW_SYSTEM.md). For **auto-start on Windows** (Task Scheduler), see [WINDOWS_TASK_SCHEDULER.md](WINDOWS_TASK_SCHEDULER.md). For **security** (HTTPS, CORS, secrets), see [SECURITY.md](SECURITY.md). For **Celery** workers and queues, see [CELERY.md](CELERY.md).

## Architecture (typical production)

- **PostgreSQL** — application data.
- **Django + DRF** — API (`backend/`).
- **React (Vite) SPA** — static files served by a CDN or reverse proxy (`frontend/` build output).
- **Redis** — Celery broker/result backend (if async tasks are not eager).
- **Celery worker** — background tasks when `CELERY_TASK_ALWAYS_EAGER=False`.

## Pre-deployment checklist

1. **Secrets:** Strong `DJANGO_SECRET_KEY` (50+ random characters). Never commit `backend/.env` or real credentials.
2. **Debug:** `DEBUG=False` in production.
3. **Hosts:** `ALLOWED_HOSTS` lists your API hostnames (comma-separated, no spaces needed).
4. **CORS:** With `DEBUG=False`, set `CORS_ALLOWED_ORIGINS` to your **frontend origin(s)** only (e.g. `https://forms.example.com`).
5. **HTTPS:** Terminate TLS at a reverse proxy (nginx, Caddy, cloud load balancer). Django enables secure cookies and HSTS when `DEBUG=False`; see [SECURITY.md](SECURITY.md).
6. **Email:** Real `EMAIL_BACKEND` and `DEFAULT_FROM_EMAIL` for password reset and invites.
7. **Frontend URL:** `FRONTEND_BASE_URL` must match the URL users open in the browser (password-reset links).
8. **Google Sign-In (optional):** Same OAuth Web client ID in `GOOGLE_OAUTH_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend build), with Google Console origins updated for production.
9. **Celery:** Redis reachable; `CELERY_TASK_ALWAYS_EAGER=False`; run at least one Celery worker process.
10. **Database:** Backups, patches, and restricted network access for PostgreSQL.
11. **Optional LLM (Ollama):** If you enable `LLM_PROVIDER=ollama`, ensure the API can reach Ollama (often same host or private network), set timeouts appropriately, and treat `OLLAMA_API_KEY` as a secret. See [Ollama_AI_Integration_Plan.md](Ollama_AI_Integration_Plan.md) and [SECURITY.md](SECURITY.md).
12. **User administration:** Application **admins** and **superusers** can manage accounts via `/api/users/` and the SPA at `/admin/users`. Protect who receives the `admin` role; public registration does not assign it. See [SECURITY.md](SECURITY.md).
13. **Windows services:** For a simple always-on host using `runserver` + Vite, schedule `scripts\start-fastforms-scheduled.bat` (see [WINDOWS_TASK_SCHEDULER.md](WINDOWS_TASK_SCHEDULER.md)); for public production, still prefer static frontend + WSGI behind HTTPS as above.

## Backend environment (production)

Copy from `backend/.env.example` and set at least:

| Variable | Production notes |
|----------|------------------|
| `DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | Long random string; required when `DEBUG=False` |
| `ALLOWED_HOSTS` | e.g. `api.example.com` |
| `CORS_ALLOWED_ORIGINS` | e.g. `https://app.example.com` |
| `DB_*` | Your PostgreSQL connection |
| `FRONTEND_BASE_URL` | e.g. `https://app.example.com` |
| `EMAIL_BACKEND` / `DEFAULT_FROM_EMAIL` | SMTP or provider-backed backend |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | e.g. `redis://...` |
| `CELERY_TASK_ALWAYS_EAGER` | `False` if you use workers |
| `LLM_PROVIDER` / `OLLAMA_*` | Optional; leave unset to disable `/api/ai/*`. See `backend/.env.example` |

Run migrations on each deploy:

```bash
cd backend
python manage.py migrate
```

## Frontend production build

Build static assets with the **production API URL** available at build time (Vite embeds `VITE_*`):

```bash
cd frontend
# Example: API on same host behind proxy or separate subdomain
set VITE_API_BASE_URL=https://api.example.com
npm ci
npm run build
```

Serve the contents of `frontend/dist/` from your web server or object storage + CDN. Ensure the browser can reach the API URL you set in `VITE_API_BASE_URL` and that CORS allows your frontend origin.

## Reverse proxy

- Terminate **HTTPS** at the proxy; forward `X-Forwarded-Proto` so Django treats requests as secure behind TLS.
- Route `/` (or your SPA path) to static files from `frontend/dist`.
- Route `/api/` (or your chosen API prefix) to the Django app (Gunicorn/uWSGI or container port).

Exact nginx/Caddy snippets depend on your hostnames; align `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `FRONTEND_BASE_URL` with those hostnames.

## Application server (Django)

The repo’s `Dockerfile` uses `runserver` for convenience; **production** should use a WSGI server (e.g. Gunicorn) in front of Django:

```bash
pip install gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Run this behind your reverse proxy or orchestrator (systemd, Docker, Kubernetes). Adjust workers and timeouts for your traffic.

## Celery worker

With `CELERY_TASK_ALWAYS_EAGER=False`, run:

```bash
celery -A config worker -l info
```

Optionally add a beat process if you schedule periodic tasks later. See [CELERY.md](CELERY.md).

## Docker Compose

From the repository root, `docker compose up --build` starts Postgres, Redis, backend, worker, and frontend dev servers. It is oriented toward **local development**. For production, use hardened images, secrets management, non-dev commands (Gunicorn, `npm run build` + static serving), and do not expose database ports publicly.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs migrations/tests and a frontend build; use it to validate changes before deploy.

## After deploy

- Smoke-test: register/login, create form, publish, submit, analytics/export.
- Confirm password-reset email links open your production frontend.
- Monitor logs, DB connections, and Celery queue depth.
