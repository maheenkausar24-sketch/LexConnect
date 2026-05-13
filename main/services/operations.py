from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone


def check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"name": "database", "status": "ok", "detail": connection.vendor}
    except Exception as exc:
        return {"name": "database", "status": "error", "detail": exc.__class__.__name__}


def check_cache():
    key = "health:cache"
    value = timezone.now().isoformat()
    try:
        cache.set(key, value, timeout=30)
        if cache.get(key) != value:
            return {"name": "cache", "status": "error", "detail": "cache read/write mismatch"}
        return {"name": "cache", "status": "ok", "detail": cache.__class__.__name__}
    except Exception as exc:
        return {"name": "cache", "status": "error", "detail": exc.__class__.__name__}


def check_channels():
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return {"name": "channels", "status": "error", "detail": "no channel layer configured"}
        return {"name": "channels", "status": "ok", "detail": channel_layer.__class__.__name__}
    except Exception as exc:
        return {"name": "channels", "status": "error", "detail": exc.__class__.__name__}


def check_celery():
    broker_url = getattr(settings, "CELERY_BROKER_URL", "")
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return {"name": "celery", "status": "ok", "detail": "eager task mode"}
    if not broker_url:
        return {"name": "celery", "status": "warning", "detail": "broker not configured"}
    return {"name": "celery", "status": "ok", "detail": broker_url.split("://", 1)[0] or "configured"}


def health_report():
    checks = [check_database(), check_cache(), check_channels(), check_celery()]
    has_error = any(check["status"] == "error" for check in checks)
    return {
        "status": "error" if has_error else "ok",
        "checked_at": timezone.now().isoformat(),
        "checks": checks,
    }
