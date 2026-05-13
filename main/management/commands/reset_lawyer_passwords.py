from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from main.services.auth import COMMON_DEMO_LAWYER_PASSWORD, reset_all_lawyer_accounts


class Command(BaseCommand):
    help = "Reset all lawyer accounts to a common demo password and ensure they are active."

    def handle(self, *args, **options):
        accounts = reset_all_lawyer_accounts()
        output_path = Path(settings.BASE_DIR) / "demo_accounts.txt"

        lines = [
            "LexConnect Demo Lawyer Accounts",
            "===============================",
            "",
            f"Common lawyer password: {COMMON_DEMO_LAWYER_PASSWORD}",
            "",
        ]

        for account in accounts:
            email_or_username = account["email"] or account["username"]
            lines.append(f"{email_or_username} | role: {account['role']}")
            self.stdout.write(f"{account['lawyer_name']} | username: {account['username']} | email: {account['email'] or '-'}")

        output_path.write_text("\n".join(lines), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Reset {len(accounts)} lawyer account(s)."))
        self.stdout.write(f"Accounts file: {output_path}")
