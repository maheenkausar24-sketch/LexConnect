import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lexconnect.settings")

app = Celery("lexconnect")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "lexconnect-reconcile-payments": {
        "task": "main.tasks.reconcile_payment_ledgers",
        "schedule": crontab(minute="*/30"),
    },
    "lexconnect-retry-failed-webhooks": {
        "task": "main.tasks.retry_failed_provider_events",
        "schedule": crontab(minute="*/15"),
    },
    "lexconnect-mark-stale-users-offline": {
        "task": "main.tasks.mark_stale_users_offline_task",
        "schedule": crontab(minute="*/5"),
    },
    "lexconnect-cleanup-stale-operational-records": {
        "task": "main.tasks.cleanup_stale_operational_records_task",
        "schedule": crontab(hour="2", minute="15"),
    },
}
