from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from main.services.admin_user import get_admin_credentials


class Command(BaseCommand):
    help = "Run the LexConnect admin console on port 9000 (Django admin, .env credentials)."

    def add_arguments(self, parser):
        parser.add_argument(
            "addrport",
            nargs="?",
            default="127.0.0.1:9000",
            help="Host:port (default: 127.0.0.1:9000)",
        )
        parser.add_argument(
            "--noreload",
            action="store_true",
            help="Disable auto-reload.",
        )

    def handle(self, *args, **options):
        username, password, _ = get_admin_credentials()
        if not username or not password:
            raise CommandError(
                "Add LEXCONNECT_ADMIN_USERNAME and LEXCONNECT_ADMIN_PASSWORD to your .env file, "
                "then run: python manage.py ensure_admin_user"
            )

        call_command("ensure_admin_user", verbosity=options["verbosity"])

        addrport = options["addrport"]
        self.stdout.write(
            self.style.SUCCESS(
                f"\nLexConnect Admin Console: http://{addrport}/\n"
                f"Sign in with .env user: {username}\n"
                "(Full Django model admin — users, lawyers, bookings, payments, etc.)\n"
            )
        )
        call_command(
            "runserver",
            addrport,
            settings="lexconnect.settings_admin",
            use_reloader=not options["noreload"],
        )
