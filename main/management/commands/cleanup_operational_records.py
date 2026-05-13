from django.core.management.base import BaseCommand

from main.services.operations import cleanup_stale_operational_records


class Command(BaseCommand):
    help = "Delete stale operational events and read notifications using configured retention windows."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show counts without deleting records.")
        parser.add_argument("--events-days", type=int, help="Override operational event retention days.")
        parser.add_argument("--notifications-days", type=int, help="Override read notification retention days.")

    def handle(self, *args, **options):
        result = cleanup_stale_operational_records(
            event_retention_days=options.get("events_days"),
            notification_retention_days=options.get("notifications_days"),
            dry_run=options["dry_run"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Operational cleanup complete: "
                f"{result['deleted_operational_events']}/{result['stale_operational_events']} operational events, "
                f"{result['deleted_read_notifications']}/{result['stale_read_notifications']} read notifications "
                f"(dry_run={result['dry_run']})."
            )
        )
