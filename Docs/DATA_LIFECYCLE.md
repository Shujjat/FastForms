# FastForms — Data lifecycle and deletion

## Data inventory (summary)

| Entity | Contents | Typical cascade |
|--------|----------|-----------------|
| **User** | Credentials, role, profile | Deleting user should be handled per your user-management policy (may soft-delete). |
| **Form** | Metadata, questions, collaborators | Owned by user. |
| **Question** | Text, type, options, validation | `ForeignKey` to Form — **CASCADE** on form delete. |
| **Response** | Submission timestamp, optional respondent | `ForeignKey` to Form — **CASCADE** on form delete. |
| **Answer** | JSON value per question | `ForeignKey` to Response — **CASCADE** on response delete. |
| **FormCollaborator** | Sharing roles | **CASCADE** on form delete. |

## Owner actions (API)

- **Delete form:** `DELETE /api/forms/{id}` — removes form, questions, collaborators, **all responses and answers** (Django CASCADE).
- **Clear responses only:** `POST /api/forms/{id}/responses/clear` — deletes all `Response` rows (and answers) for that form; **keeps** the form and questions.

## Automated retention

If `RESPONSE_RETENTION_DAYS` is set in the environment (see `backend/.env.example`), operators can run:

```bash
python manage.py purge_old_responses --dry-run
python manage.py purge_old_responses
```

This deletes responses (and answers) with `submitted_at` older than the cutoff. It does **not** delete forms or questions. Schedule via cron or Celery beat.

## Exports

CSV/JSON exports contain **personal data** from responses. Treat files as confidential. The application logs **export events** at INFO (user id, form id, format) without answer bodies — see `export_responses` in `apps/forms/views.py`.

## File uploads

If you store upload binaries on disk or object storage, ensure deletion jobs remove blobs when answers or forms are deleted (extend purge logic when upload storage is added).
