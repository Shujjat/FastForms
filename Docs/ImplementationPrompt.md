# FastForms Implementation Prompt

Use this prompt when generating scaffolding or baseline code from an AI assistant. Keep this document separate from the SRS so requirements and generation instructions do not conflict.

## Goal
Generate a production-ready starter codebase for FastForms using the constraints below.

## Tech Stack
- Backend: Django 5+, Django REST Framework, PostgreSQL, SimpleJWT, Celery, Redis
- Frontend: React (Vite), Tailwind CSS, Zustand or Redux Toolkit, React Hook Form, Axios
- Infra: Docker, Docker Compose, Nginx reverse proxy

## Required Modules
- Auth and user management (roles: Admin, Creator, Analyst, Respondent)
- Form builder (form CRUD, question CRUD, ordering, publish/unpublish)
- Response collection and management
- Analytics and exports
- Sharing and permission controls
- Notifications (email)

## Expected Project Layout
```text
backend/
  config/
  apps/
    users/
    forms/
    responses/
    analytics/
    notifications/
frontend/
  src/
    api/
    components/
    pages/
    store/
    hooks/
```

## API Baseline
- Auth:
  - POST `/api/auth/register`
  - POST `/api/auth/login`
  - POST `/api/auth/token/refresh`
- Forms:
  - GET `/api/forms`
  - POST `/api/forms`
  - GET `/api/forms/{formId}`
  - PUT `/api/forms/{formId}`
  - DELETE `/api/forms/{formId}`
- Questions:
  - POST `/api/forms/{formId}/questions`
  - PUT `/api/forms/{formId}/questions/reorder`
- Responses:
  - POST `/api/forms/{formId}/submit`
  - GET `/api/forms/{formId}/responses`
- Analytics:
  - GET `/api/forms/{formId}/analytics`
  - GET `/api/forms/{formId}/export?format=csv|json`

## Security and Quality Requirements
- JWT auth + role-based authorization
- Input validation and rate limiting
- File upload constraints (type and size)
- Pagination for list endpoints
- Basic tests for backend APIs and frontend critical flows

## Output Requirements
- Working backend and frontend code
- Dockerfiles and `docker-compose.yml`
- `.env.example` files
- Seed script for sample data
- README with setup and run instructions

## Prompt Use Note
When using this with an AI code generator, require the model to output files by path and keep implementation aligned with the requirements in `Docs/SRS.txt`.
