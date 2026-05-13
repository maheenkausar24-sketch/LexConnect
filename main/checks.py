import sys

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def production_security_checks(app_configs, **kwargs):
    if "test" in sys.argv:
        return []

    warnings = []
    if not settings.DEBUG:
        if not settings.SECURE_SSL_REDIRECT:
            warnings.append(
                Warning(
                    "SECURE_SSL_REDIRECT is disabled while DEBUG=False.",
                    hint="Set DJANGO_SECURE_SSL_REDIRECT=True behind HTTPS.",
                    id="lexconnect.W001",
                )
            )
        if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
            warnings.append(
                Warning(
                    "Secure session/CSRF cookies are not fully enabled while DEBUG=False.",
                    hint="Set DJANGO_SESSION_COOKIE_SECURE=True and DJANGO_CSRF_COOKIE_SECURE=True.",
                    id="lexconnect.W002",
                )
            )
        if not settings.CSRF_TRUSTED_ORIGINS:
            warnings.append(
                Warning(
                    "CSRF trusted origins are empty while DEBUG=False.",
                    hint="Set DJANGO_CSRF_TRUSTED_ORIGINS to the public HTTPS origin(s).",
                    id="lexconnect.W003",
                )
            )
        if settings.CELERY_TASK_ALWAYS_EAGER:
            warnings.append(
                Warning(
                    "Celery eager mode is enabled while DEBUG=False.",
                    hint="Set CELERY_TASK_ALWAYS_EAGER=False and run a worker process in production.",
                    id="lexconnect.W004",
                )
            )
        if settings.CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer":
            warnings.append(
                Warning(
                    "Channels is using the in-memory layer while DEBUG=False.",
                    hint="Set REDIS_URL so websocket state works across web processes.",
                    id="lexconnect.W005",
                )
            )
        if settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache":
            warnings.append(
                Warning(
                    "Django cache is using local memory while DEBUG=False.",
                    hint="Set REDIS_URL or DJANGO_CACHE_BACKEND to a shared production cache.",
                    id="lexconnect.W006",
                )
            )
        if settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
            warnings.append(
                Warning(
                    "SQLite is configured while DEBUG=False.",
                    hint="Set POSTGRES_* variables for a production database.",
                    id="lexconnect.W007",
                )
            )
        if not getattr(settings, "LEXCONNECT_CONTENT_SECURITY_POLICY", None):
            warnings.append(
                Warning(
                    "Content Security Policy is not configured.",
                    hint="Keep LEXCONNECT_CONTENT_SECURITY_POLICY enabled or set explicit CSP env overrides.",
                    id="lexconnect.W008",
                )
            )

    if settings.SECURE_HSTS_PRELOAD and not settings.SECURE_HSTS_INCLUDE_SUBDOMAINS:
        warnings.append(
            Error(
                "HSTS preload requires includeSubDomains.",
                hint="Enable DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS or disable DJANGO_SECURE_HSTS_PRELOAD.",
                id="lexconnect.E001",
            )
        )

    return warnings
