# FastForms MVP

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

FastForms is open source under the [MIT License](LICENSE). It is a production-oriented Google Forms-like baseline with:
- JWT auth and role field
- Form builder APIs
- Collaborator sharing (editor/viewer)
- Public/private submission flow
- Response listing and basic analytics
- Export APIs and Celery-based notification task
- React frontend for core flows
- Admin user management UI (`/admin/users`) for accounts with role **admin** or Django **superuser**

## Project Structure
- `backend/` Django + DRF API
- `frontend/` React (Vite) app
- `Docs/` SRS, roadmap, [ExecutionPlan.md](Docs/ExecutionPlan.md), [DEPLOYMENT.md](Docs/DEPLOYMENT.md), [CONTRIBUTING.md](Docs/CONTRIBUTING.md), [RUN_ON_NEW_SYSTEM.md](Docs/RUN_ON_NEW_SYSTEM.md), [WINDOWS_TASK_SCHEDULER.md](Docs/WINDOWS_TASK_SCHEDULER.md) (optional auto-start on Windows), [SECURITY.md](Docs/SECURITY.md), [CELERY.md](Docs/CELERY.md), [Ollama_AI_Integration_Plan.md](Docs/Ollama_AI_Integration_Plan.md) (optional local AI)

## Open source and collaboration

- **Repository:** [github.com/Shujjat/FastForms](https://github.com/Shujjat/FastForms)
- **License:** [MIT](LICENSE) — use and contribute under those terms.
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md) and the longer guide in [Docs/CONTRIBUTING.md](Docs/CONTRIBUTING.md).
- **Security:** Report vulnerabilities privately — [Docs/SECURITY.md](Docs/SECURITY.md).
- **CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs backend migrations + pytest (SQLite) and `npm run build` on pushes and pull requests.

### Contact (maintainer)

| | |
|--|--|
| 🔗 **GitHub (this project)** | [github.com/Shujjat/FastForms](https://github.com/Shujjat/FastForms) |
| 🔗 **GitHub (author)** | [github.com/Shujjat/NeuroGraph](https://github.com/Shujjat/NeuroGraph) |
| 📧 **Email** | [shujjat.shirafat@gmail.com](mailto:shujjat.shirafat@gmail.com) |
| 📱 **WhatsApp** | [+92 336 4540037](https://wa.me/923364540037) *(same as 03364540037)* |

## Run Locally (primary workflow)

### Backend
1. `cd backend`
2. `python -m pip install -r requirements.txt`
3. Copy `backend/.env.example` to `backend/.env` and set at least database credentials (PostgreSQL recommended).
4. `python manage.py migrate`
5. `python manage.py runserver`
6. (Optional async worker) `celery -A config worker -l info` — see [Docs/CELERY.md](Docs/CELERY.md)

Backend runs at `http://localhost:8000`.

### Frontend
1. `cd frontend`
2. `npm install`
3. Copy `frontend/.env.example` to `frontend/.env` if you need overrides.
4. `npm run dev`

Frontend runs at `http://localhost:5173`. Set `VITE_API_BASE_URL` if the API is not on `http://localhost:8000`.

### Google Sign-In (optional)

1. In [Google Cloud Console](https://console.cloud.google.com/), create an OAuth 2.0 **Web application** client ID.
2. Add authorized JavaScript origins (e.g. `http://localhost:5173`) and authorized redirect URIs if required by your flow.
3. Set the same client ID in:
   - `backend/.env`: `GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com`
   - `frontend/.env`: `VITE_GOOGLE_CLIENT_ID=....apps.googleusercontent.com`
4. Restart backend and frontend. Use **Sign in with Google** on Login / Register.

### Run with Docker (optional)

From repository root: `docker compose up --build`

### Windows quick start (optional)

From the repository root, **`Run-FastForms.bat`** prepares `backend\.venv` (pip, migrate), starts the API in a window with that **virtual environment activated**, starts the frontend (`npm install` + `npm run dev`), waits for both ports, then opens the browser.

## Production (summary)

Full checklist and hosting patterns are in [Docs/DEPLOYMENT.md](Docs/DEPLOYMENT.md). To auto-start FastForms on a Windows server folder (for example after reboot), see [Docs/WINDOWS_TASK_SCHEDULER.md](Docs/WINDOWS_TASK_SCHEDULER.md). In short:

- Set `DEBUG=False`, a strong `DJANGO_SECRET_KEY`, and `ALLOWED_HOSTS` to your hostnames.
- Set `CORS_ALLOWED_ORIGINS` to your frontend origin(s) (comma-separated).
- Use HTTPS and terminate TLS at a reverse proxy; see [Docs/SECURITY.md](Docs/SECURITY.md).
- Set `FRONTEND_BASE_URL` so password-reset emails link to your SPA.
- Run Celery workers if you use async tasks with `CELERY_TASK_ALWAYS_EAGER=False`.

## Key API Endpoints
- `GET/POST /api/users/` — **admin or superuser only**: list users (`?search=`, `?role=`, `?is_active=true|false`, pagination); create user with password and role
- `GET/PATCH/DELETE /api/users/{id}/` — **admin or superuser only**: view/update user (role, active, staff, profile, optional new password); `DELETE` soft-deactivates the account
- `POST /api/auth/register` — body: `username`, `email`, `password`, `role` (required); optional: `first_name`, `last_name`, `phone`, `organization`
- `POST /api/auth/login`
- `POST /api/auth/google` — body: `credential` (Google ID token JWT), optional `role` (`creator` \| `respondent`)
- `POST /api/auth/token/refresh`
- `POST /api/auth/password-reset` — request reset email (body: `{ "email": "..." }`)
- `POST /api/auth/password-reset/confirm` — `{ "uid", "token", "new_password" }`
- `GET/POST /api/forms`
- `POST /api/forms/{id}/publish`
- `POST /api/forms/{id}/invite` — body: `{ "emails": ["a@b.com", ...], "message": "optional note" }` (form must be published; uses `EMAIL_BACKEND` / `DEFAULT_FROM_EMAIL`)
- `POST /api/forms/{id}/questions`
- `GET/POST /api/forms/{id}/collaborators`
- `POST /api/forms/{id}/submit`
- `GET /api/forms/{id}/responses` — optional query: `search`, `submitted_after`, `submitted_before`, `respondent_id`
- `GET /api/forms/{id}/analytics`
- `GET /api/forms/{id}/export?export_format=csv|json`
- `GET /api/ai/health` — `{ "llm_enabled": true|false }` (optional; requires server-side Ollama config)
- `POST /api/ai/suggest_form` — `{ "prompt": "..." }` — AI-assisted form draft (creators/admins only when LLM is configured)

### Admin / user management

The SPA route **`/admin/users`** (and `GET/POST /api/users/`, `GET/PATCH/DELETE /api/users/{id}/`) are available only to users with application role **`admin`** or to Django **superusers**. Public registration does not offer the `admin` role. Grant access by running `python manage.py createsuperuser` and/or editing the user in Django admin (`/admin/`) to set **Role** to `admin` or to enable **Superuser status**.

## Testing
- Backend unittest-style: `python manage.py test`
- Backend pytest-style: `cd backend && set DB_ENGINE=sqlite && python -m pytest` (Windows PowerShell: `$env:DB_ENGINE="sqlite"; python -m pytest`)
- Frontend build validation: `cd frontend && npm run build`

## CI

GitHub Actions runs backend migrations + pytest (SQLite) and frontend build. See `/.github/workflows/ci.yml`.

## Troubleshooting

**Login returns 500 / `relation "token_blacklist_outstandingtoken" does not exist`**

After pulling changes that enable JWT refresh blacklist, run migrations against **your** database (PostgreSQL):

`python manage.py migrate`

Use the same `backend/.env` as when you start the server. If migrations report nothing to apply but the error persists, reset and re-apply only the blacklist app:

`python manage.py migrate token_blacklist zero`

`python manage.py migrate`

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE). You may use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, subject to including the copyright notice and permission notice in any substantial portion of the software. The software is provided **as is**, without warranty.

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and [Docs/CONTRIBUTING.md](Docs/CONTRIBUTING.md) (maintainer contact and deeper guide).
