from datetime import timedelta

from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
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


def health_report():
    checks = [check_database(), check_cache(), check_channels(), check_celery()]
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
