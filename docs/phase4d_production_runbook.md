# LexConnect Phase 4D Production Runbook

## Startup Validation

Run these before promoting a build:

```bash
python manage.py check --deploy
python manage.py validate_production
python manage.py deployment_diagnostics --fail-on-warning
python manage.py production_smoke_test
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py validate_celery
python manage.py collectstatic --noinput
python manage.py cleanup_operational_records --dry-run
python manage.py test
```

Use `DJANGO_SETTINGS_MODULE=lexconnect.settings_production` for production-like checks.

## Required Production Environment

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY` set to a unique non-development value
- `DJANGO_ALLOWED_HOSTS` set to public hostnames
- `DJANGO_CSRF_TRUSTED_ORIGINS` set to HTTPS origins
- `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` set for cache, channels, and tasks
- `POSTGRES_*` set for PostgreSQL
- `LEXCONNECT_SHOW_DEMO_ACCOUNTS=False`
- `DJANGO_SECURE_SSL_REDIRECT=True` behind HTTPS
- `DJANGO_SESSION_COOKIE_SECURE=True` and `DJANGO_CSRF_COOKIE_SECURE=True`

## Static And Media Storage

- Run `collectstatic` during build or release.
- Serve `STATIC_ROOT` through the web server/CDN.
- Keep uploaded media private. LexConnect routes chat files, lawyer certificates, and case documents through authenticated views.
- For object storage, set `DJANGO_DEFAULT_FILE_STORAGE` to the chosen Django storage backend after installing/configuring that backend.
- Back up media with the database because model rows reference uploaded file paths.

## Backup And Restore

Daily backup baseline:

```bash
pg_dump "$DATABASE_URL" > lexconnect-$(date +%F).sql
tar -czf lexconnect-media-$(date +%F).tgz media/
```

Restore rehearsal:

```bash
psql "$DATABASE_URL" < lexconnect-YYYY-MM-DD.sql
tar -xzf lexconnect-media-YYYY-MM-DD.tgz
python manage.py migrate --check
python manage.py check --deploy
python manage.py validate_production
```

Keep at least one tested restore path for database and media together.

## Rollback Checklist

1. Stop traffic or drain the release target.
2. Record the current git SHA, image tag, and migration state.
3. Restore the previous image or git SHA.
4. If migrations were applied, only roll back after confirming the migration is reversible and no newer data would be lost.
5. Restart web, worker, and beat processes.
6. Run `python manage.py check`, `python manage.py migrate --check`, and hit `/health/live/` and `/health/ready/`.
7. Verify login, admin dashboard, payment review, and an existing chat page.

## Operational Retention

The cleanup task runs daily through Celery beat and can be executed manually:

```bash
python manage.py cleanup_operational_records --dry-run
python manage.py cleanup_operational_records
```

Defaults:

- `LEXCONNECT_OPERATIONAL_EVENT_RETENTION_DAYS=90`
- `LEXCONNECT_READ_NOTIFICATION_RETENTION_DAYS=180`

## Logging Guidance

Logs are JSON-formatted and split by logger name: requests, security, audit, payments, webhooks, realtime, tasks, and operations. Production log shipping should alert on:

- `main.security` warnings
- `main.webhooks` errors
- `main.tasks` `task_failed_dead_letter`
- readiness endpoint failures
- repeated rate limit events

Avoid logging request bodies, uploaded file contents, passwords, session cookies, or payment secrets.

## Final Manual QA

- `/health/live/` returns `200`.
- `/health/ready/` returns `200` and reports database, cache, channels, and celery.
- `python manage.py deployment_diagnostics --fail-on-warning` passes in the production environment.
- `python manage.py production_smoke_test` passes after release.
- Demo accounts are hidden when `LEXCONNECT_SHOW_DEMO_ACCOUNTS=False`.
- Admin-only pages redirect non-admin users.
- Payment status changes require the admin confirmation field and CSRF.
- Chat pages and websocket sends still work for confirmed paid bookings.
- Uploads reject SVGs, empty files, path-like filenames, and mismatched content.

See `docs/production_rehearsal.md` for Linux VPS, Nginx, Redis, Celery, websocket, monitoring, recovery, and troubleshooting guidance.
