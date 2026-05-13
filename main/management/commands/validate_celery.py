from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate LexConnect Celery configuration without requiring a running worker."

    def handle(self, *args, **options):
        try:
            from lexconnect.celery import app
        except ModuleNotFoundError as exc:
            raise CommandError("Celery is not installed. Run pip install -r requirements.txt.") from exc

        app.loader.import_default_modules()
        task_names = sorted(name for name in app.tasks if name.startswith("main.tasks."))
        required_tasks = {
            "main.tasks.send_email_task",
            "main.tasks.create_notification_task",
            "main.tasks.process_provider_webhook_task",
            "main.tasks.retry_failed_provider_events",
            "main.tasks.cleanup_stale_operational_records_task",
            "main.tasks.reconcile_payment_ledgers",
        }
        missing = required_tasks.difference(task_names)
        if missing:
            raise CommandError(f"Missing Celery task registrations: {', '.join(sorted(missing))}")

        self.stdout.write(self.style.SUCCESS("Celery app imports and LexConnect tasks are registered."))
        self.stdout.write(f"broker={settings.CELERY_BROKER_URL}")
        self.stdout.write(f"result_backend={settings.CELERY_RESULT_BACKEND}")
        self.stdout.write(f"task_always_eager={settings.CELERY_TASK_ALWAYS_EAGER}")
        self.stdout.write(f"registered_tasks={len(task_names)}")
