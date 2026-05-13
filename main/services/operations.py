from datetime import timedelta
from pathlib import Path

from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage, storages
from django.db import connection
from django.utils import timezone

from ..models import Notification, OperationalEvent


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


def check_staticfiles_storage():
    try:
        storage = storages["staticfiles"]
        return {"name": "staticfiles", "status": "ok", "detail": storage.__class__.__name__}
    except Exception as exc:
        return {"name": "staticfiles", "status": "error", "detail": exc.__class__.__name__}


def check_media_storage():
    try:
        storage_name = default_storage.__class__.__name__
        media_root = getattr(settings, "MEDIA_ROOT", "")
        if media_root and not Path(media_root).exists():
            return {"name": "media", "status": "warning", "detail": f"{storage_name}: media root missing"}
        return {"name": "media", "status": "ok", "detail": storage_name}
    except Exception as exc:
        return {"name": "media", "status": "error", "detail": exc.__class__.__name__}


def runtime_configuration_summary():
    channel_backend = settings.CHANNEL_LAYERS["default"]["BACKEND"]
    return {
        "debug": settings.DEBUG,
        "database_engine": settings.DATABASES["default"]["ENGINE"],
        "cache_backend": settings.CACHES["default"]["BACKEND"],
        "channel_layer": channel_backend.rsplit(".", 1)[-1],
        "celery_broker_scheme": (getattr(settings, "CELERY_BROKER_URL", "") or "").split("://", 1)[0],
        "celery_eager": getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False),
        "staticfiles_storage": storages["staticfiles"].__class__.__name__,
        "media_storage": default_storage.__class__.__name__,
        "secure_ssl_redirect": settings.SECURE_SSL_REDIRECT,
        "secure_proxy_ssl_header": bool(settings.SECURE_PROXY_SSL_HEADER),
        "use_x_forwarded_host": settings.USE_X_FORWARDED_HOST,
        "trust_proxy_headers": getattr(settings, "LEXCONNECT_TRUST_PROXY_HEADERS", False),
        "demo_accounts_enabled": getattr(settings, "LEXCONNECT_SHOW_DEMO_ACCOUNTS", False),
        "csp_report_only": getattr(settings, "LEXCONNECT_CSP_REPORT_ONLY", False),
    }


def health_report():
    checks = [
        check_database(),
        check_cache(),
        check_channels(),
        check_celery(),
        check_staticfiles_storage(),
        check_media_storage(),
    ]
    has_error = any(check["status"] == "error" for check in checks)
    return {
        "status": "error" if has_error else "ok",
        "checked_at": timezone.now().isoformat(),
        "checks": checks,
    }


def cleanup_stale_operational_records(*, event_retention_days=None, notification_retention_days=None, dry_run=False):
    event_days = event_retention_days or getattr(settings, "LEXCONNECT_OPERATIONAL_EVENT_RETENTION_DAYS", 90)
    notification_days = notification_retention_days or getattr(settings, "LEXCONNECT_READ_NOTIFICATION_RETENTION_DAYS", 180)
    event_cutoff = timezone.now() - timedelta(days=event_days)
    notification_cutoff = timezone.now() - timedelta(days=notification_days)

    stale_events = OperationalEvent.objects.filter(created_at__lt=event_cutoff)
    stale_notifications = Notification.objects.filter(is_read=True, read_at__lt=notification_cutoff)
    result = {
        "event_retention_days": event_days,
        "notification_retention_days": notification_days,
        "stale_operational_events": stale_events.count(),
        "stale_read_notifications": stale_notifications.count(),
        "deleted_operational_events": 0,
        "deleted_read_notifications": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return result

    result["deleted_operational_events"] = stale_events.delete()[0]
    result["deleted_read_notifications"] = stale_notifications.delete()[0]
    return result
