# LexConnect Security And Deployment Baseline

## Local Development

- Keep `DJANGO_DEBUG=True`.
- Leave `DJANGO_SECRET_KEY` empty only for local development.
- SQLite, console email, local memory cache, and in-memory Channels are supported for free localhost work.
- Password reset and email verification links are printed to the development console by default.

## Production Checklist

- Set `DJANGO_DEBUG=False`.
- Set a unique `DJANGO_SECRET_KEY`.
- Set `DJANGO_ALLOWED_HOSTS` to the real hostnames.
- Set `DJANGO_CSRF_TRUSTED_ORIGINS` to the HTTPS origins.
- Enable HTTPS settings:
  - `DJANGO_CSRF_COOKIE_SECURE=True`
  - `DJANGO_SESSION_COOKIE_SECURE=True`
  - `DJANGO_SECURE_SSL_REDIRECT=True`
  - `DJANGO_SECURE_HSTS_SECONDS=31536000`
- Use PostgreSQL through the existing `POSTGRES_*` variables.
- Use Redis for Channels by setting `REDIS_URL` before running multiple web workers.
- Serve uploaded media from private storage or through authenticated protected views.
- Remove or restrict demo credential pages before exposing a production deployment.
- Configure a real email backend for password reset and verification mail.
- Keep `GEMINI_API_KEY` optional; Lexora falls back to safe static guidance when unavailable.

## Implemented Phase 1 Controls

- Environment loading with production validation.
- Secure cookie and HTTPS-ready settings.
- Cache-backed rate limiting for sensitive actions.
- Console-safe audit/security logging.
- Email verification and password reset flows.
- MIME, extension, size, and safer filename checks for uploads.
- Protected routes for chat files, certificates, and case documents.
- WebSocket origin validation and per-chat authorization.
- Lexora request validation, rate limiting, disclaimer, and provider error reporting.
