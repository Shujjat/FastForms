# FastForms — Windows Task Scheduler (auto-start)

Use this when you run FastForms from a fixed folder on a Windows server (for example `J:\FastForms\`) and want the backend and frontend to start automatically after reboot or on a schedule.

## Scripts

| File | Purpose |
|------|---------|
| `Run-FastForms.bat` | **Interactive** start from repo root: creates/updates `backend\.venv`, runs migrations, then opens backend (with **venv activated**) and frontend, waits for ports, opens the browser. |
| `scripts/start-fastforms-scheduled.bat` | **Task Scheduler** / unattended: starts minimized windows via `scripts/start-backend.bat` and `scripts/start-frontend.bat` (same venv + npm steps), skips if ports are already in use. |

Logs are appended to:

- `logs/scheduler.log` — when the scheduled script runs and whether ports were skipped.

If **port 8000** (backend) or **5173** (frontend) is already listening, that service is **not** started again (avoids “address already in use”).

## Task Scheduler settings (example)

| Setting | Suggested value |
|--------|------------------|
| **Program/script** | `J:\FastForms\scripts\start-fastforms-scheduled.bat` (adjust drive/path), or run `Run-FastForms.bat` interactively when logged in (no minimization). |
| **Start in** | `J:\FastForms` |
| **Trigger** | **At startup** — add a **delay of 1–2 minutes** so PostgreSQL (and Redis, if used) are running first. |
| **User** | An account that can run Python and Node and read the project folder. |

“Run whether user is logged on or not” may require storing the account password; ensure that account has permission to bind to the ports you use.

## Production expectations

- This flow matches the **installer-style** setup (`runserver` + Vite dev server). For a hardened internet-facing deployment, prefer a reverse proxy, **`npm run build`** + static files, and a production WSGI server (see [DEPLOYMENT.md](DEPLOYMENT.md)).
- Set **`DEBUG=False`**, **`ALLOWED_HOSTS`**, **`CORS_ALLOWED_ORIGINS`**, and a strong **`DJANGO_SECRET_KEY`** in `backend/.env` for any production host.

## Related

- [RUN_ON_NEW_SYSTEM.md](RUN_ON_NEW_SYSTEM.md) — first-time Windows setup.
- [DEPLOYMENT.md](DEPLOYMENT.md) — production checklist.
