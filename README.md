# LexConnect

LexConnect is a Django-based lawyer consultation platform for browsing lawyers, scheduling consultations, managing demo payments, and continuing case conversations in booking-linked chats.

## Core Features

- Client and lawyer authentication
- Category-based lawyer discovery
- Availability-based booking with appointment date and time
- Demo-safe payment status workflow
- Booking-linked chat using Django Channels
- Reviews tied to completed consultations
- Notifications for booking, payment, and chat activity

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Create a `.env` file using the variables below.
4. Run migrations with `python manage.py migrate`.
5. Start the server with `python manage.py runserver`.

## Environment Variables

### Django

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `LEXCONNECT_SITE_URL`

### Email and reminders

- `DJANGO_EMAIL_BACKEND`
- `DJANGO_EMAIL_HOST`
- `DJANGO_EMAIL_PORT`
- `DJANGO_EMAIL_USE_TLS`
- `DJANGO_EMAIL_HOST_USER`
- `DJANGO_EMAIL_HOST_PASSWORD`
- `LEXCONNECT_EMAIL_NOTIFICATIONS`
- `LEXCONNECT_REMINDERS_ENABLED`

For Gmail SMTP, use Django's SMTP backend with `smtp.gmail.com`, port `587`, TLS enabled, and a Gmail app password in `DJANGO_EMAIL_HOST_PASSWORD`. Local demos can keep the console email backend.

### Optional PostgreSQL

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

If PostgreSQL variables are not supplied, the project falls back to SQLite for local development.

### Optional Lexora AI

- `GEMINI_API_KEY`
- `LEXORA_GEMINI_MODEL` defaults to `gemini-2.0-flash`
- `LEXORA_GEMINI_TIMEOUT_MS` defaults to `5000`

Lexora works without a Gemini key by using local keyword/category matching, safe fallback guidance, and existing lawyer recommendations.

## Testing

Run the test suite with:

```bash
python manage.py test
```

## Phase 3 Operations

Phase 3 adds Celery task infrastructure, optional Redis-backed cache/channel/task queues, structured JSON logging, production settings, Docker Compose foundations, and CI checks.

Local development stays dependency-light: when `REDIS_URL` is empty, Celery runs in eager mode with an in-memory broker, Django cache uses LocMem, and Channels uses the in-memory layer.

Useful validation commands:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py validate_production
python manage.py deployment_diagnostics
python manage.py production_smoke_test
python manage.py cleanup_operational_records --dry-run
python manage.py validate_celery
celery -A lexconnect report
```

See `docs/production_infrastructure.md`, `docs/phase4d_production_runbook.md`, and `docs/production_rehearsal.md` for production startup, smoke testing, rollback, backup/restore, Nginx/websocket, and retention guidance.

## Notes

- Demo payments are manual and intentionally do not connect to a real gateway.
- Chat becomes available after payment is marked successful and the booking reaches a confirmed state.
- See `docs/security_baseline.md` for the Phase 1 security and deployment checklist.
