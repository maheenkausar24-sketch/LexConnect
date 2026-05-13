from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403
from .settings import env_bool


DEBUG = False

if SECRET_KEY == "lexconnect-local-development-secret-key":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a non-development value in production.")

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list the public hostnames in production.")

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = max(SECURE_HSTS_SECONDS, 31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", True)
LEXCONNECT_TRUST_PROXY_HEADERS = env_bool("LEXCONNECT_TRUST_PROXY_HEADERS", True)
LEXCONNECT_SHOW_DEMO_ACCOUNTS = env_bool("LEXCONNECT_SHOW_DEMO_ACCOUNTS", False)

STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"  # noqa: F405

CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
LEXCONNECT_ASYNC_EMAIL = env_bool("LEXCONNECT_ASYNC_EMAIL", True)
LEXCONNECT_ASYNC_NOTIFICATIONS = env_bool("LEXCONNECT_ASYNC_NOTIFICATIONS", True)

if CELERY_BROKER_URL == "memory://":  # noqa: F405
    raise ImproperlyConfigured("CELERY_BROKER_URL or REDIS_URL must be set in production.")
