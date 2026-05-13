# LexConnect Production Rehearsal And Deployment Validation

## What Was Audited

- Django production settings and security headers
- ASGI routing for HTTP and websocket traffic
- WSGI compatibility for non-websocket deployments
- Channels layer selection and Redis assumptions
- Celery worker and beat registration
- Static and private media storage configuration
- JSON logging and operational event visibility
- Docker Compose service wiring
- Environment variable validation and secret separation
- Reverse proxy assumptions for HTTPS and websocket upgrades

## Local Production Simulation

Use this when rehearsing on a workstation or staging VM:

```bash
set DJANGO_SETTINGS_MODULE=lexconnect.settings_production
set DJANGO_DEBUG=False
set DJANGO_SECRET_KEY=replace-with-staging-secret
set DEMO_PAYMENT_WEBHOOK_SECRET=replace-with-separate-webhook-secret
set DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
set DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost
set REDIS_URL=redis://127.0.0.1:6379/0
set CELERY_BROKER_URL=redis://127.0.0.1:6379/0
set CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
set LEXCONNECT_SHOW_DEMO_ACCOUNTS=False
set POSTGRES_DB=lexconnect
set POSTGRES_USER=lexconnect
set POSTGRES_PASSWORD=replace-with-staging-password
```

Then run:

```bash
python manage.py check --deploy
python manage.py validate_production
python manage.py deployment_diagnostics
python manage.py production_smoke_test
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py collectstatic --noinput
python manage.py cleanup_operational_records --dry-run
python manage.py test
```

## Linux VPS Deployment Shape

Recommended process layout:

- `daphne` serves `lexconnect.asgi:application` for HTTP and websockets.
- `celery -A lexconnect worker -l info` runs async jobs.
- `celery -A lexconnect beat -l info` runs scheduled jobs.
- Redis backs Channels, cache, Celery broker, and Celery results.
- PostgreSQL backs application data.
- Nginx terminates TLS and proxies HTTP/websocket traffic to Daphne.

Gunicorn can serve WSGI-only HTTP, but it does not handle this app's websocket path by itself. If Gunicorn is introduced, keep Daphne or another ASGI server for `/ws/` traffic.

## Nginx Proxy Requirements

Minimum websocket-safe proxy behavior:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

location /static/ {
    alias /srv/lexconnect/current/staticfiles/;
}
```

Keep uploaded private media behind authenticated Django views unless a private object-storage backend is configured.

## Verification Commands

Run these after every deploy:

```bash
python manage.py validate_production
python manage.py deployment_diagnostics --fail-on-warning
python manage.py production_smoke_test
python manage.py validate_celery
curl -fsS https://your-domain.example/health/live/
curl -fsS https://your-domain.example/health/ready/
```

Manual smoke checks:

- Login as a client, lawyer, and admin.
- Open admin dashboard, payments, operations, and provider events.
- Confirm payment review still requires CSRF and action confirmation.
- Open an existing confirmed paid chat and verify websocket connection upgrades.
- Upload a permitted test document and reject an invalid file type.

## Monitoring Notes

Alert on:

- `/health/ready/` returning non-200
- Redis connection failures
- Postgres connection failures
- `main.webhooks` errors
- `main.tasks` `task_failed_dead_letter`
- repeated `main.security` rate-limit events
- missing Celery beat cleanup/reconciliation activity

Log fields are JSON and safe for centralized log collection. Do not add request bodies, cookies, passwords, payment signatures, or uploaded file contents to logs.

## Recovery Checklist

1. Put the load balancer or Nginx upstream into maintenance if needed.
2. Capture current git SHA, image tag, database migration state, and failing health output.
3. Restart in this order when services are healthy: Redis/Postgres, web, worker, beat.
4. Run `python manage.py deployment_diagnostics`.
5. If a release caused the issue, redeploy the previous SHA/image.
6. Only reverse migrations after confirming reversibility and data impact.
7. Re-run `production_smoke_test` and manual chat/payment checks.

## Troubleshooting

- `AllowedHostsOriginValidator` rejects websocket connections when `DJANGO_ALLOWED_HOSTS` lacks the public host.
- Websockets fail through Nginx when `Upgrade` and `Connection` headers are missing.
- Readiness warnings about in-memory channel/cache mean Redis is not configured or `REDIS_URL` is not visible.
- Celery tasks not running usually means worker env differs from web env or `CELERY_TASK_ALWAYS_EAGER=True`.
- Static asset 404s after deploy usually mean `collectstatic` was skipped or Nginx points to the wrong `STATIC_ROOT`.
- Private media 404s can mean file storage paths were not restored with the database.
