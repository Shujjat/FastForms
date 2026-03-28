# Contributing to FastForms

Thank you for your interest in contributing. By submitting a pull request or other material, you agree that your contributions are licensed under the [MIT License](LICENSE) (same as the project), unless you state otherwise.

## Repository workflow

1. **Fork** [Shujjat/FastForms](https://github.com/Shujjat/FastForms) (or get commit access on the main repo if you are a maintainer).
2. **Branch** from `main` with a short, descriptive name (e.g. `fix/export-csv`, `feature/template-loader`).
3. **Open a pull request** against `main`. The PR template summarizes what reviewers need; fill it in.
4. **CI** must pass: backend migrations + pytest and frontend production build (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Development setup

1. **Backend:** `cd backend`, create a virtualenv, `pip install -r requirements.txt`, copy `.env.example` to `.env`, run `python manage.py migrate`.
2. **Frontend:** `cd frontend`, `npm install`.
3. **Tests:** From `backend` with `DB_ENGINE=sqlite` (or your dev DB): `python -m pytest`. Frontend: `npm run build`.
4. **Optional AI (Ollama):** To work on `/api/ai/*` or the designer “AI form draft” flow, install [Ollama](https://ollama.com), pull a model listed by `ollama list`, and set `OLLAMA_MODEL` to match. See `backend/.env.example` and [Docs/Ollama_AI_Integration_Plan.md](Docs/Ollama_AI_Integration_Plan.md). AI calls are server-side only.
5. **Windows auto-start:** [Docs/WINDOWS_TASK_SCHEDULER.md](Docs/WINDOWS_TASK_SCHEDULER.md) (optional; production servers should still follow [DEPLOYMENT.md](Docs/DEPLOYMENT.md)).

## Pull requests

- Prefer focused PRs with a clear description of the change (what / why / how to test).
- Run backend tests and `npm run build` before submitting when you touch those areas.
- Do not commit secrets (`backend/.env`, `frontend/.env` with real keys).

## Questions

Open a [GitHub issue](https://github.com/Shujjat/FastForms/issues) for bugs or feature discussion. Use the issue templates when they fit.

## Maintainer contact

| | |
|--|--|
| 🔗 **GitHub (this project)** | [github.com/Shujjat/FastForms](https://github.com/Shujjat/FastForms) |
| 🔗 **GitHub (author)** | [github.com/Shujjat/NeuroGraph](https://github.com/Shujjat/NeuroGraph) |
| 📧 **Email** | [shujjat.shirafat@gmail.com](mailto:shujjat.shirafat@gmail.com) |
| 📱 **WhatsApp** | [+92 336 4540037](https://wa.me/923364540037) |

For deployment details and a fuller guide, see [Docs/CONTRIBUTING.md](Docs/CONTRIBUTING.md).
