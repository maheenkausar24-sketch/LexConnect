from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from main.models import Lawyer
from main.services.lawyer_import import import_lawyers_from_csv


class Command(BaseCommand):
    help = "Import or update lawyer accounts and profiles from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            dest="path",
            default="",
            help="Optional CSV path. Defaults to lawyers.csv or lawyers_data.csv found under the project root.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            summary = import_lawyers_from_csv(settings.BASE_DIR, csv_path=options.get("path") or None)

        self.stdout.write(self.style.SUCCESS("Lawyer CSV import complete."))
        self.stdout.write(f"CSV file: {summary.path}")
        self.stdout.write(f"Total processed: {summary.total_processed}")
        self.stdout.write(f"Created: {summary.created}")
        self.stdout.write(f"Updated: {summary.updated}")
        self.stdout.write(f"Skipped: {summary.skipped}")
        self.stdout.write(f"Visible to clients: {Lawyer.objects.visible_to_clients().count()}")
