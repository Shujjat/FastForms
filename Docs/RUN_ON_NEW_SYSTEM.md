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
git clone <your-repo-url>
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

## 10) Using the Installer (.exe)

If you have the installer build:

`dist-installer/FastForms-Setup.exe`

After install:

1. Run **Run FastForms** shortcut.
2. It starts backend + frontend terminals.
3. Browser opens `http://127.0.0.1:5173`.

Important:
- Installer does not bundle Python/Node/PostgreSQL.
- Those must already be installed on the machine.

## 11) Troubleshooting

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

### E) Port already in use
- Change backend port:
  - `python manage.py runserver 8001`
- Update frontend API base in `frontend/.env`:
  - `VITE_API_BASE_URL=http://127.0.0.1:8001`

## 12) Production Notes

Before production deployment:

- Set `DEBUG=False`
- Use a strong `DJANGO_SECRET_KEY`
- Restrict `ALLOWED_HOSTS`
- Configure HTTPS reverse proxy (Nginx/Caddy)
- Configure real email backend
- Run Redis + Celery worker
- Use managed PostgreSQL backups and monitoring
