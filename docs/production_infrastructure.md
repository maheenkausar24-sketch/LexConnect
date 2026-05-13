# LexConnect Phase 3 Production Infrastructure

## Local Modes

LexConnect remains SQLite-friendly by default. If `REDIS_URL` is empty, Celery uses an in-memory broker and `CELERY_TASK_ALWAYS_EAGER=True`, so tasks run synchronously during local development and tests.

For a fuller local production rehearsal, run:

```bash
docker compose up --build
```

This starts the Django ASGI app, Redis, a Celery worker, and Celery beat.

## Production Settings

Use `DJANGO_SETTINGS_MODULE=lexconnect.settings_production` for deployed environments. Required production values:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `REDIS_URL` or `CELERY_BROKER_URL`

PostgreSQL is enabled by setting the existing `POSTGRES_*` variables. SQLite remains the default when they are absent.

## Operational Processes

- Web: `daphne -b 0.0.0.0 -p 8000 lexconnect.asgi:application`
- Worker: `celery -A lexconnect worker -l info`
- Scheduler: `celery -A lexconnect beat -l info`

Beat schedules payment ledger reconciliation every 30 minutes, failed webhook retry queuing every 15 minutes, and stale online presence cleanup every 5 minutes.

## Validation Commands

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py validate_production
python manage.py deployment_diagnostics
python manage.py production_smoke_test
python manage.py cleanup_operational_records --dry-run
python manage.py validate_celery
python manage.py test
celery -A lexconnect report
```

## Logging

Application logs use JSON formatting via `main.logging.JsonFormatter`. Dedicated loggers exist for requests, audit events, security events, payments, webhooks, and Celery tasks.

## Phase 4D Notes

Use `docs/phase4d_production_runbook.md` and `docs/production_rehearsal.md` for the release checklist, rollback procedure, backup/restore guidance, retention cleanup policy, Linux VPS deployment notes, Nginx/websocket assumptions, monitoring, troubleshooting, and final manual QA pass.
