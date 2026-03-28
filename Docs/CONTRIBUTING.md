# Contributing to FastForms

Thank you for helping improve FastForms. Contributions are licensed under the same terms as the project — see the [MIT License](../LICENSE) in the repository root.

This file expands on the short checklist in the root [CONTRIBUTING.md](../CONTRIBUTING.md). Both describe the same expectations.

## Open source expectations

- **License:** MIT — keep the `LICENSE` file intact; new files you add are understood to be under the same license unless you state otherwise in the PR.
- **GitHub:** Issues and pull requests are the default channel for design discussion and code review.
- **CI:** Pushes and PRs run [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). Fix failures in areas you change before requesting review.
- **Scope:** Prefer small, reviewable PRs over large mixed changes; match existing style in touched files.

## Maintainer contact

Use these for questions that do not fit a public GitHub issue (e.g. coordination, private inquiries). Same details work for **GitHub** and **WhatsApp** outreach.

| Channel | Detail |
|--------|--------|
| 🔗 **GitHub (this project)** | [github.com/Shujjat/FastForms](https://github.com/Shujjat/FastForms) — issues and pull requests |
| 🔗 **GitHub (author)** | [github.com/Shujjat/NeuroGraph](https://github.com/Shujjat/NeuroGraph) |
| 📧 **Email** | [shujjat.shirafat@gmail.com](mailto:shujjat.shirafat@gmail.com) |
| 📱 **WhatsApp** | [03364540037](https://wa.me/923364540037) — international format `+92 336 4540037` |

For **security vulnerabilities**, do not open a public issue; follow [SECURITY.md](SECURITY.md) (private reporting).

## Getting started

1. **Clone** the repository and create a branch for your change.
2. **Backend:** `cd backend`, Python 3.11+, virtualenv, `pip install -r requirements.txt`, copy `.env.example` to `.env`, `python manage.py migrate`.
3. **Frontend:** `cd frontend`, `npm install`.
4. **Run:** Backend `python manage.py runserver`; frontend `npm run dev`. See [RUN_ON_NEW_SYSTEM.md](RUN_ON_NEW_SYSTEM.md) for a full local setup including PostgreSQL.

## Where things live

- **`backend/`** — Django project (`config/`), apps (auth, forms, `llm`, etc.), API serializers/views, tests.
- **`frontend/`** — React + Vite SPA, pages, API client, env via `VITE_*`.
- **`scripts/`** — Windows helpers (`start-backend.bat`, `start-frontend.bat`, `start-fastforms-scheduled.bat` for Task Scheduler). Repo root **`Run-FastForms.bat`** runs the full interactive stack with venv activation.
- **`Docs/`** — Design notes, deployment, security, Celery, [WINDOWS_TASK_SCHEDULER.md](WINDOWS_TASK_SCHEDULER.md).

## Tests and checks

Before opening a PR:

- **Backend:** From `backend`, with SQLite for a quick run: `set DB_ENGINE=sqlite` (Windows) or `export DB_ENGINE=sqlite`, then `python -m pytest` or `python manage.py test`.
- **Frontend:** `npm run build`.

Fix any failures you introduce in the areas you changed.

## Pull requests

- Keep PRs **focused** (one concern per PR when possible).
- Describe **what** changed and **why** in the PR description.
- Do **not** commit secrets: no real `backend/.env`, `frontend/.env`, or API keys.

## Deploying your own instance

See [DEPLOYMENT.md](DEPLOYMENT.md) for production environment variables, HTTPS, CORS, Celery, and build steps.

## Code of conduct

Be respectful and constructive in issues and reviews. Assume good intent; prefer clear, minimal changes that match existing style in the touched files.
