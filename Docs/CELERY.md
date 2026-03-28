# Celery and background tasks

FastForms uses Celery for asynchronous work (e.g. email notifications when a form response is submitted).

## Local development

1. Run Redis (default broker URL: `redis://localhost:6379/0`).
2. From the `backend` directory with your virtualenv active:

```bash
celery -A config worker -l info
```

3. Keep `CELERY_TASK_ALWAYS_EAGER=False` in `backend/.env` so tasks run in the worker.

## Without Redis (tests / quick demos)

Set `CELERY_TASK_ALWAYS_EAGER=True` in `backend/.env`. Tasks run in the web process synchronously (no separate worker).

## Production

Run one or more Celery workers with the same `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` as the web app. Use process supervision (systemd, Docker, etc.) and monitor worker health.
