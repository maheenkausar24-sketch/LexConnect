from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from main.models import Lawyer, UserProfile
from main.utils import ensure_profile_role


DEFAULT_PASSWORD = "lawyer@123"


class Command(BaseCommand):
    help = "Generate test login credentials for all existing lawyers."

    def handle(self, *args, **options):
        output_path = Path(settings.BASE_DIR) / "lawyer_credentials.txt"
        created_users = 0
        linked_existing_users = 0
        updated_users = 0
        updated_lawyers = 0
        processed_lawyers = 0

        lines = []

        with transaction.atomic():
            lawyers = Lawyer.objects.select_related("user", "user__profile").order_by("name", "id")

            for lawyer in lawyers:
                processed_lawyers += 1
                email = (lawyer.email or "").strip().lower()
                if not email:
                    self.stderr.write(
                        self.style.WARNING(f"Skipped lawyer #{lawyer.id} because no email is set.")
                    )
                    continue

                user = lawyer.user if lawyer.user_id else None

                if user is None:
                    user = User.objects.filter(email=email).first()
                    if user is None:
                        user = User.objects.create_user(
                            username=email,
                            email=email,
                        )
                        created_users += 1
                    else:
                        linked_existing_users += 1

                user.username = email
                user.email = email
                user.first_name = lawyer.name.strip().split(" ", 1)[0] if lawyer.name else ""
                user.last_name = lawyer.name.strip().split(" ", 1)[1] if lawyer.name and " " in lawyer.name.strip() else ""
                user.is_active = True
                user.set_password(DEFAULT_PASSWORD)
                user.save()
                updated_users += 1

                ensure_profile_role(user, role=UserProfile.Role.LAWYER)

                lawyer.user = user
                lawyer.is_verified = True
                lawyer.is_online = True
                lawyer.save(update_fields=["user", "is_verified", "is_online", "updated_at"])
                updated_lawyers += 1

                profile = user.profile
                if not profile.is_online:
                    profile.is_online = True
                if not profile.email_verified:
                    profile.email_verified = True
                    profile.email_verified_at = timezone.now()
                profile.save(update_fields=["is_online", "email_verified", "email_verified_at"])

                lines.extend(
                    [
                        "---------------------------------",
                        f"Name: {lawyer.name}",
                        f"Email: {email}",
                        f"Username: {user.username}",
                        f"Password: {DEFAULT_PASSWORD}",
                        "---------------------------------",
                        "",
                    ]
                )

        output_path.write_text("\n".join(lines), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Lawyer credentials generated successfully."))
        self.stdout.write(f"Credentials file: {output_path}")
        self.stdout.write(f"Lawyers processed: {processed_lawyers}")
        self.stdout.write(f"Users created: {created_users}")
        self.stdout.write(f"Existing users linked: {linked_existing_users}")
        self.stdout.write(f"Users updated: {updated_users}")
        self.stdout.write(f"Lawyers updated: {updated_lawyers}")
