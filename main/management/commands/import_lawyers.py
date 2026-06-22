from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Import or update lawyer accounts and profiles from lawyers.csv."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            dest="path",
            default="",
            help="Optional CSV path. Defaults to lawyers.csv or lawyers_data.csv found under the project root.",
        )

    def handle(self, *args, **options):
        command_options = {}
        if options.get("path"):
            command_options["path"] = options["path"]
        call_command("import_lawyers_csv", **command_options)
