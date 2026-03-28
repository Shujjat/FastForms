# FastForms - Run On New System

This guide explains how to set up and run FastForms on a fresh Windows machine.

## 1) Prerequisites

Install these first:

- Python 3.11+ (3.12 recommended)
- Node.js 20+ (npm included)
- PostgreSQL 14+ (or newer)
- Git (optional, for cloning)

Check versions:

```powershell
python --version
npm --version
psql --version
```

If `python`/`npm` is not recognized, add them to PATH and reopen terminal.

## 2) Get the Project

If using git:

```powershell
git clone https://github.com/Shujjat/FastForms.git
cd FastForms
```

Or copy the project folder to the new machine and open terminal in project root.

## 3) Database Setup (PostgreSQL)

Create database and user (example values used by current project):

- DB name: `fastforms`
- User: `postgres`
- Password: your PostgreSQL password
- Port: `5432`

If `fastforms` does not exist, create it:

```sql
CREATE DATABASE fastforms;
```

## 4) Backend Environment

Create `backend/.env` with your DB values:

```env
DB_ENGINE=postgres
DB_NAME=fastforms
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

DEBUG=True
ALLOWED_HOSTS=*
DJANGO_SECRET_KEY=change-this-in-production

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_ALWAYS_EAGER=True
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@fastforms.local
```

Notes:
- `CELERY_TASK_ALWAYS_EAGER=True` is good for local/dev without Redis worker.
- In production, use `False` and run Redis + Celery worker.

## 5) Run Backend

```powershell
cd backend
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```

Backend URL: `http://127.0.0.1:8000`

## 6) Run Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

## 7) First Login / Use

1. Open `http://127.0.0.1:5173`
2. Register account
3. Login
4. Create form (Creator/Admin role)
5. Design, publish, submit responses, view analytics/export

## 8) Security Model (Current)

- All form actions require login.
- Respondents cannot design forms.
- Analysts/respondents cannot access form designer actions.
- **User management** (`/admin/users` in the SPA, and `/api/users/`) is limited to application **admin** role or Django **superusers**. Grant those in Django admin (`/admin/`) or via `createsuperuser`; see the README “Admin / user management” section.

## 8a) Optional: Auto-start with Task Scheduler

To start backend + frontend automatically after reboot (e.g. install under `J:\FastForms\`), use **[WINDOWS_TASK_SCHEDULER.md](WINDOWS_TASK_SCHEDULER.md)** (`scripts\start-fastforms-scheduled.bat`). For a normal interactive start, double-click **`Run-FastForms.bat`** at the project root (activates `backend\.venv`, then runs both servers).

## 9) Optional: Run Tests

Backend tests:

```powershell
cd backend
python manage.py test
```

Frontend build check:

```powershell
cd frontend
npm run build
```

## 10) Optional: Local AI (Ollama)

Form **AI draft** features call the backend, which can use a local [Ollama](https://ollama.com) server (OpenAI-compatible API).

1. Install Ollama for your OS and start it (default `http://127.0.0.1:11434`).
2. Pull a model, for example: `ollama pull llama3.2`, or pick an installed tag from `ollama list` (e.g. `qwen3:latest`).
3. In `backend/.env`, set (uncomment/adjust as in `backend/.env.example`). **`OLLAMA_MODEL` must match an installed model name exactly.**

   ```env
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   OLLAMA_MODEL=qwen3:latest
   ```

4. Restart the Django server. In the form designer, use **AI form draft** when logged in as a creator/admin.

Details and acceptance notes: **[Ollama_AI_Integration_Plan.md](Ollama_AI_Integration_Plan.md)**.

## 11) Using the Installer (.exe)

If you have the installer build:

`dist-installer/FastForms-Setup.exe`

After install:

1. Run **Run FastForms** shortcut.
2. It starts backend + frontend terminals.
3. Browser opens `http://127.0.0.1:5173`.

Important:
- Installer does not bundle Python/Node/PostgreSQL.
- Those must already be installed on the machine.

## 12) Troubleshooting

### A) `python` not found
- Reinstall Python and check "Add Python to PATH".

### B) `npm` not found
- Reinstall Node.js LTS and reopen terminal.

### C) DB connection error
- Verify PostgreSQL service is running.
- Verify `backend/.env` credentials and port.
- Confirm DB `fastforms` exists.

### D) Frontend loads but API fails
- Ensure backend is running on `127.0.0.1:8000`.
- Check browser DevTools network errors.

### E) `no pq wrapper available` / `libpq library not found` / `Error loading psycopg2 or psycopg` (PostgreSQL on Windows)

The app uses **`psycopg2-binary`** in `requirements.txt` so PostgreSQL works without installing PostgreSQL client DLLs separately. If you still see errors after upgrading:

1. Delete `backend\.venv`, run `Run-FastForms.bat` again, **or** in `backend`: `pip uninstall -y psycopg psycopg-binary` then `pip install -r requirements.txt` (removing **psycopg v3** matters: Django tries it first if installed, and its Windows wheel can fail before it falls back to psycopg2).

2. Ensure PostgreSQL **server** is installed and running, and `backend\.env` has correct `DB_*` values.

### F) `did not find executable at '...\pythoncore-3.xx-64\python.exe'` when running `Run-FastForms.bat`

The folder `backend\.venv` was probably created on **another computer** or with a **Python build that was later removed** (the venv remembers that path). **Fix:** delete `backend\.venv` and run `Run-FastForms.bat` again so it recreates the venv with the Python on this machine. Current scripts also try `python -m venv --upgrade .venv` and remove a broken venv automatically.

**Tip:** Prefer Python 3.12 from [python.org](https://www.python.org/downloads/) with “Add python.exe to PATH” so `Run-FastForms.bat` can find `Python312` under `Program Files` or `%LocalAppData%\Programs\Python\Python312\`.

### G) Port already in use
- Change backend port:
  - `python manage.py runserver 8001`
- Update frontend API base in `frontend/.env`:
  - `VITE_API_BASE_URL=http://127.0.0.1:8001`

## 13) Production Notes

Before production deployment, follow **[DEPLOYMENT.md](DEPLOYMENT.md)** for a full checklist (environment variables, HTTPS, CORS, frontend build, Gunicorn, Celery). In summary:

- Set `DEBUG=False`
- Use a strong `DJANGO_SECRET_KEY`
- Restrict `ALLOWED_HOSTS`
- Configure HTTPS reverse proxy (Nginx/Caddy)
- Configure real email backend
- Run Redis + Celery worker
- Use managed PostgreSQL backups and monitoring
