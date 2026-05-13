import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value.")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_int(name, default, *, minimum=None, maximum=None):
    value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc
    if minimum is not None and parsed < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    if maximum is not None and parsed > maximum:
        raise ImproperlyConfigured(f"{name} must be at most {maximum}.")
    return parsed


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "lexconnect-local-development-secret-key"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=False.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver" if DEBUG else "")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG=False.")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


INSTALLED_APPS = [
    "channels",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "main.apps.MainConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "main.middleware.RequestLoggingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "main.middleware.PresenceMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "main.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "lexconnect.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.debug",
                "main.context_processors.notification_summary",
            ],
        },
    },
]

WSGI_APPLICATION = "lexconnect.wsgi.application"
ASGI_APPLICATION = "lexconnect.asgi.application"

if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", ""),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "LexConnect <noreply@lexconnect.local>")
PASSWORD_RESET_TIMEOUT = env_int("DJANGO_PASSWORD_RESET_TIMEOUT", 3600, minimum=300)
DEMO_PAYMENT_WEBHOOK_SECRET = os.getenv("DEMO_PAYMENT_WEBHOOK_SECRET", SECRET_KEY)
REDIS_URL = os.getenv("REDIS_URL", "").strip()
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL or "memory://")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL or "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", not bool(REDIS_URL))
CELERY_TASK_EAGER_PROPAGATES = env_bool("CELERY_TASK_EAGER_PROPAGATES", DEBUG)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = env_int("CELERY_WORKER_PREFETCH_MULTIPLIER", 1, minimum=1)
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "lexconnect")
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
LEXCONNECT_ASYNC_EMAIL = env_bool("LEXCONNECT_ASYNC_EMAIL", bool(REDIS_URL))
LEXCONNECT_ASYNC_NOTIFICATIONS = env_bool("LEXCONNECT_ASYNC_NOTIFICATIONS", bool(REDIS_URL))
LEXCONNECT_ASYNC_WEBHOOKS = env_bool("LEXCONNECT_ASYNC_WEBHOOKS", False)
PRESENCE_STALE_SCAN_INTERVAL = env_int("PRESENCE_STALE_SCAN_INTERVAL", 60)
LEXCONNECT_TRUST_PROXY_HEADERS = env_bool("LEXCONNECT_TRUST_PROXY_HEADERS", False)
LEXCONNECT_SHOW_DEMO_ACCOUNTS = env_bool("LEXCONNECT_SHOW_DEMO_ACCOUNTS", DEBUG)

if REDIS_URL and env_bool("DJANGO_USE_REDIS_CACHE", True):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": env_int("DJANGO_CACHE_TIMEOUT", 300, minimum=1),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": os.getenv("DJANGO_CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"),
            "LOCATION": os.getenv("DJANGO_CACHE_LOCATION", "lexconnect-local-cache"),
            "TIMEOUT": env_int("DJANGO_CACHE_TIMEOUT", 300, minimum=1),
        }
    }

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE", 60 * 60 * 8, minimum=300)
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE", False)
SESSION_SAVE_EVERY_REQUEST = env_bool("DJANGO_SESSION_SAVE_EVERY_REQUEST", False)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0 if DEBUG else 31536000, minimum=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False) else None
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", False)
X_FRAME_OPTIONS = "DENY"

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))

STORAGES = {
    "default": {
        "BACKEND": os.getenv("DJANGO_DEFAULT_FILE_STORAGE", "django.core.files.storage.FileSystemStorage"),
    },
    "staticfiles": {
        "BACKEND": os.getenv("DJANGO_STATICFILES_STORAGE", "django.contrib.staticfiles.storage.ManifestStaticFilesStorage" if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"),
    },
}

LEXCONNECT_CSP_REPORT_ONLY = env_bool("LEXCONNECT_CSP_REPORT_ONLY", False)
LEXCONNECT_CONTENT_SECURITY_POLICY = {
    "default-src": env_list("LEXCONNECT_CSP_DEFAULT_SRC", "'self'"),
    "script-src": env_list("LEXCONNECT_CSP_SCRIPT_SRC", "'self','unsafe-inline'"),
    "style-src": env_list("LEXCONNECT_CSP_STYLE_SRC", "'self','unsafe-inline'"),
    "img-src": env_list("LEXCONNECT_CSP_IMG_SRC", "'self',data:"),
    "font-src": env_list("LEXCONNECT_CSP_FONT_SRC", "'self',data:"),
    "connect-src": env_list("LEXCONNECT_CSP_CONNECT_SRC", "'self',ws:,wss:"),
    "object-src": env_list("LEXCONNECT_CSP_OBJECT_SRC", "'none'"),
    "base-uri": env_list("LEXCONNECT_CSP_BASE_URI", "'self'"),
    "form-action": env_list("LEXCONNECT_CSP_FORM_ACTION", "'self'"),
    "frame-ancestors": env_list("LEXCONNECT_CSP_FRAME_ANCESTORS", "'none'"),
}

RATELIMIT_ENABLED = env_bool("DJANGO_RATELIMIT_ENABLED", True)
RATELIMIT_BYPASS_AUTHENTICATED_ADMINS = env_bool("DJANGO_RATELIMIT_BYPASS_ADMINS", False)
LEXCONNECT_OPERATIONAL_EVENT_RETENTION_DAYS = env_int("LEXCONNECT_OPERATIONAL_EVENT_RETENTION_DAYS", 90, minimum=7)
LEXCONNECT_READ_NOTIFICATION_RETENTION_DAYS = env_int("LEXCONNECT_READ_NOTIFICATION_RETENTION_DAYS", 180, minimum=7)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
LEXORA_GEMINI_MODEL = os.getenv("LEXORA_GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
LEXORA_GEMINI_TIMEOUT_MS = env_int("LEXORA_GEMINI_TIMEOUT_MS", 5000, minimum=1000, maximum=20000)

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                "capacity": env_int("CHANNEL_LAYER_CAPACITY", 1000, minimum=1),
                "expiry": env_int("CHANNEL_LAYER_EXPIRY", 60, minimum=1),
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": "main.logging.JsonFormatter",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        }
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"), "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "main.security": {"handlers": ["console"], "level": os.getenv("DJANGO_SECURITY_LOG_LEVEL", "INFO"), "propagate": False},
        "main.audit": {"handlers": ["console"], "level": os.getenv("DJANGO_AUDIT_LOG_LEVEL", "INFO"), "propagate": False},
        "main.requests": {"handlers": ["console"], "level": os.getenv("DJANGO_REQUEST_LOG_LEVEL", "INFO"), "propagate": False},
        "main.payments": {"handlers": ["console"], "level": os.getenv("DJANGO_PAYMENT_LOG_LEVEL", "INFO"), "propagate": False},
        "main.webhooks": {"handlers": ["console"], "level": os.getenv("DJANGO_WEBHOOK_LOG_LEVEL", "INFO"), "propagate": False},
        "main.tasks": {"handlers": ["console"], "level": os.getenv("DJANGO_TASK_LOG_LEVEL", "INFO"), "propagate": False},
        "main.operations": {"handlers": ["console"], "level": os.getenv("DJANGO_OPERATION_LOG_LEVEL", "INFO"), "propagate": False},
        "main.realtime": {"handlers": ["console"], "level": os.getenv("DJANGO_REALTIME_LOG_LEVEL", "INFO"), "propagate": False},
        "celery": {"handlers": ["console"], "level": os.getenv("CELERY_LOG_LEVEL", "INFO"), "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
