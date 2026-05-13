import logging

from celery import Task, shared_task
from celery.signals import task_failure, task_retry, task_success
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import DatabaseError, OperationalError
from django.utils import timezone

from .audit import record_operational_event
from .models import Notification, Payment, ProviderEvent
from .services.payments import process_provider_webhook, reconcile_payment_ledger
from .utils import create_notification_record, mark_stale_users_offline


task_logger = logging.getLogger("main.tasks")
webhook_logger = logging.getLogger("main.webhooks")


class LoggedRetryTask(Task):
    autoretry_for = (OperationalError, DatabaseError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5


@shared_task(bind=True, base=LoggedRetryTask)
def send_email_task(self, subject, message, recipient_list, from_email=None):
    sent = send_mail(
        subject,
        message,
        from_email or settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        fail_silently=False,
    )
    task_logger.info({"event": "email_sent", "task_id": self.request.id, "recipient_count": len(recipient_list), "sent": sent})
    return sent


@shared_task(bind=True, base=LoggedRetryTask)
def create_notification_task(
    self,
    user_id,
    title,
    message,
    url="",
    notification_type=Notification.NotificationType.GENERAL,
    priority=Notification.Priority.NORMAL,
):
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        task_logger.warning({"event": "notification_user_missing", "task_id": self.request.id, "user_id": user_id})
        return None
    notification = create_notification_record(
        user,
        title,
        message,
        url,
        notification_type=notification_type,
        priority=priority,
    )
    task_logger.info({"event": "notification_created", "task_id": self.request.id, "notification_id": notification.id, "user_id": user_id})
    return notification.id


@shared_task(bind=True, base=LoggedRetryTask)
def process_provider_webhook_task(self, provider, payload, signature=""):
    provider_event, processed = process_provider_webhook(provider, payload, signature=signature)
    webhook_logger.info(
        {
            "event": "provider_webhook_task_finished",
            "task_id": self.request.id,
            "provider": provider,
            "provider_event_id": provider_event.event_id,
            "status": provider_event.processing_status,
            "processed": processed,
        }
    )
    return {"provider_event_id": provider_event.event_id, "processed": processed}


@shared_task(bind=True, base=LoggedRetryTask)
def retry_failed_provider_events(self, limit=50):
    events = list(
        ProviderEvent.objects.filter(processing_status=ProviderEvent.ProcessingStatus.FAILED)
        .order_by("updated_at")
        .values("provider", "event_id", "payload", "replay_count")[:limit]
    )
    queued = 0
    dead_lettered = 0
    for event in events:
        if event["replay_count"] >= 5:
            dead_lettered += 1
            webhook_logger.error(
                {
                    "event": "provider_webhook_dead_lettered",
                    "task_id": self.request.id,
                    "provider": event["provider"],
                    "provider_event_id": event["event_id"],
                    "replay_count": event["replay_count"],
                }
            )
            record_operational_event(
                "webhook",
                "provider_webhook_dead_lettered",
                level="error",
                summary=f"{event['provider']}:{event['event_id']} exceeded retry budget.",
                metadata={"task_id": self.request.id, **event},
            )
            continue
        process_stored_provider_event_task.delay(event["provider"], event["payload"])
        queued += 1
    webhook_logger.info({"event": "failed_provider_events_requeued", "task_id": self.request.id, "queued": queued, "dead_lettered": dead_lettered})
    return {"queued": queued, "dead_lettered": dead_lettered}


@shared_task(bind=True, base=LoggedRetryTask)
def process_stored_provider_event_task(self, provider, payload):
    provider_event, processed = process_provider_webhook(provider, payload, trusted_stored_event=True)
    webhook_logger.info(
        {
            "event": "stored_provider_webhook_retry_finished",
            "task_id": self.request.id,
            "provider": provider,
            "provider_event_id": provider_event.event_id,
            "status": provider_event.processing_status,
            "processed": processed,
        }
    )
    return {"provider_event_id": provider_event.event_id, "processed": processed}


@shared_task(bind=True, base=LoggedRetryTask)
def reconcile_payment_ledgers(self, limit=500):
    payments = Payment.objects.filter(
        payment_status__in=[Payment.PaymentStatus.SUCCESS, Payment.PaymentStatus.REFUNDED]
    ).order_by("-updated_at")[:limit]
    checked = 0
    imbalanced = []
    for payment in payments:
        result = reconcile_payment_ledger(payment)
        checked += 1
        if not result["is_balanced"]:
            imbalanced.append(result["payment_id"])
            task_logger.warning({"event": "payment_ledger_imbalanced", "task_id": self.request.id, **result})
    task_logger.info({"event": "payment_ledger_reconciliation_finished", "task_id": self.request.id, "checked": checked, "imbalanced": imbalanced})
    return {"checked": checked, "imbalanced": imbalanced}


@shared_task(bind=True, base=LoggedRetryTask)
def mark_stale_users_offline_task(self):
    mark_stale_users_offline()
    task_logger.info({"event": "stale_users_marked_offline", "task_id": self.request.id, "finished_at": timezone.now().isoformat()})


@task_retry.connect
def log_task_retry(sender=None, request=None, reason=None, **kwargs):
    task_logger.warning({"event": "task_retry", "task": getattr(sender, "name", ""), "task_id": getattr(request, "id", ""), "reason": str(reason)})
    record_operational_event(
        "task",
        "task_retry",
        level="warning",
        summary=f"{getattr(sender, 'name', '')} retry scheduled.",
        metadata={"task": getattr(sender, "name", ""), "task_id": getattr(request, "id", ""), "reason": str(reason)},
    )


@task_failure.connect
def log_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, **extra):
    task_logger.error(
        {
            "event": "task_failed_dead_letter",
            "task": getattr(sender, "name", ""),
            "task_id": task_id,
            "exception": exception.__class__.__name__ if exception else "",
        }
    )
    record_operational_event(
        "task",
        "task_failed_dead_letter",
        level="error",
        summary=f"{getattr(sender, 'name', '')} failed.",
        metadata={
            "task": getattr(sender, "name", ""),
            "task_id": task_id,
            "exception": exception.__class__.__name__ if exception else "",
        },
    )


@task_success.connect
def log_task_success(sender=None, result=None, **kwargs):
    if sender and sender.name.startswith("main.tasks."):
        task_logger.debug({"event": "task_success", "task": sender.name, "result": result})
