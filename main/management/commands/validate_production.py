from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run production startup validation for deployment readiness."

    def handle(self, *args, **options):
        self.stdout.write("Running Django deployment checks...")
        call_command("check", "--deploy")

        failures = []
        if settings.DEBUG:
            failures.append("DJANGO_DEBUG must be False.")
        if not settings.SECRET_KEY or settings.SECRET_KEY == "lexconnect-local-development-secret-key":
            failures.append("DJANGO_SECRET_KEY must be set to a production-only value.")
        if not settings.ALLOWED_HOSTS:
            failures.append("DJANGO_ALLOWED_HOSTS must include production hostnames.")
        if not settings.CSRF_TRUSTED_ORIGINS:
            failures.append("DJANGO_CSRF_TRUSTED_ORIGINS should include production HTTPS origins.")
        if settings.CELERY_TASK_ALWAYS_EAGER:
            failures.append("CELERY_TASK_ALWAYS_EAGER must be False for production workers.")
        if settings.CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer":
            failures.append("REDIS_URL is required for multi-process websocket channel layers.")
        if settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache":
            failures.append("A shared production cache is required for rate limits and health checks.")
        if settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
            failures.append("POSTGRES_* must be configured for production database storage.")

        if failures:
            for failure in failures:
                self.stderr.write(f"- {failure}")
            raise CommandError("Production validation failed.")

        self.stdout.write(self.style.SUCCESS("Production validation passed."))
