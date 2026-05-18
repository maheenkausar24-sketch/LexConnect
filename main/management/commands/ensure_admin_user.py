from django.core.management.base import BaseCommand, CommandError

from main.services.admin_user import ensure_lexconnect_admin_user, get_admin_credentials


class Command(BaseCommand):
    help = "Create or update the LexConnect superuser from LEXCONNECT_ADMIN_* variables in .env"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password from .env even if the user already exists.",
        )

    def handle(self, *args, **options):
        username, password, _email = get_admin_credentials()
        if not username or not password:
            raise CommandError(
                "Set LEXCONNECT_ADMIN_USERNAME and LEXCONNECT_ADMIN_PASSWORD in your .env file."
            )

        user, created = ensure_lexconnect_admin_user(force_password=options["force_password"])
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} administrator '{user.username}' (staff + superuser)."))
