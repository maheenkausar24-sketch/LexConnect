# LexConnect Project Status

Last updated: 2026-05-13

## Current State

LexConnect is a Django legal-tech platform with role-based client, lawyer, and admin workflows. The current codebase includes hardened booking and payment flows, provider webhook/refund foundations, websocket chat, notifications, audit/security logging, and Phase 3 production infrastructure.

## Completed Architecture

- Django 6 application with service-layer business logic under `main/services/`.
- Role-based authentication and dashboard routing for clients, lawyers, and admins.
- Lawyer verification, availability, booking, rescheduling, cancellation, and review workflows.
- Payment status history, provider event idempotency, refund requests, ledger entries, and reconciliation helpers.
- Booking-linked websocket chat using Django Channels.
- Notification model and async-capable notification creation.
- Audit and security event logging.
- Rate limiting using Django cache, with hashed IP identifiers for anonymous users.
- Celery app, task modules, retry policies, beat schedule, and local eager fallback.
- Optional Redis integration for Celery, Django cache, and Channels.
- Production settings module with stricter security/proxy defaults.
- Docker and Docker Compose foundations for web, worker, beat, and Redis.
- GitHub Actions CI foundation for checks, migration consistency, Celery validation, and tests.

## Local Startup

```bash
env\Scripts\python.exe manage.py migrate
env\Scripts\python.exe manage.py runserver
```

Local development remains fully usable without Redis. If `REDIS_URL` is empty, Celery runs tasks eagerly, cache uses LocMem, and Channels uses the in-memory layer.

## Docker Startup

```bash
docker compose up --build
```

This starts:

- Django ASGI web process
- Redis
- Celery worker
- Celery beat scheduler

## Important Operational Commands

```bash
env\Scripts\python.exe manage.py check
env\Scripts\python.exe manage.py makemigrations --check --dry-run
env\Scripts\python.exe manage.py migrate --check
env\Scripts\python.exe manage.py validate_celery
env\Scripts\python.exe manage.py test
env\Scripts\celery.exe -A lexconnect report
env\Scripts\celery.exe -A lexconnect worker -l info
env\Scripts\celery.exe -A lexconnect beat -l info
```

## Required Environment Variables

Required for production:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `REDIS_URL` or `CELERY_BROKER_URL`

Recommended for production:

- `CELERY_RESULT_BACKEND`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `DJANGO_SECURE_SSL_REDIRECT=True`
- `DJANGO_SECURE_PROXY_SSL_HEADER=True`
- `DJANGO_USE_X_FORWARDED_HOST=True`
- `LEXCONNECT_TRUST_PROXY_HEADERS=True`
- `DJANGO_CSRF_COOKIE_SECURE=True`
- `DJANGO_SESSION_COOKIE_SECURE=True`
- `DEMO_PAYMENT_WEBHOOK_SECRET`

Optional:

- `GEMINI_API_KEY`
- `DJANGO_EMAIL_BACKEND`
- `DJANGO_DEFAULT_FROM_EMAIL`
- `LEXCONNECT_ASYNC_EMAIL`
- `LEXCONNECT_ASYNC_NOTIFICATIONS`
- `LEXCONNECT_ASYNC_WEBHOOKS`

## Current Validation Status

- Django system checks pass.
- Migration dry-run reports no model changes.
- Test suite passes.
- Celery app imports and task registration pass.
- Settings load with local fallback behavior.
- URL resolution for core routes passes.
- ASGI import is stabilized after Django app initialization.

## Remaining Roadmap

- Production deployment rehearsal with Docker Compose and Redis running.
- Real production database provisioning and backup/restore workflow.
- Email provider integration and deliverability testing.
- Centralized log aggregation and alerting.
- Health check endpoints for web, worker, Redis, database, and task queues.
- Real payment provider sandbox integration when moving beyond demo payments.
- Load testing for booking contention, chat traffic, and webhook bursts.
- Object storage strategy for private media and legal documents.

## Production Risks

- SQLite is supported locally but is not suitable for production concurrency.
- Redis/Celery configuration is validated locally but still needs an end-to-end worker rehearsal in the target environment.
- Demo payment provider flows are safe for local/demo use but are not a real gateway integration.
- Docker foundations exist, but final hosting-specific reverse proxy, TLS, secrets, and static/media handling still need deployment decisions.
- Structured logs are emitted, but alert rules and log retention are not yet configured.
