import re

from django.contrib.auth.hashers import make_password
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def split_name(full_name):
    parts = (full_name or "").strip().split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name


def generate_unique_username(base_value, used_usernames):
    base = re.sub(r"[^A-Za-z0-9._+-]", "", (base_value or "").lower()) or "lawyer"
    base = base[:150] or "lawyer"
    candidate = base
    counter = 1

    while not candidate or candidate in used_usernames:
        suffix = f"_{counter}"
        trimmed_base = base[: 150 - len(suffix)] or "lawyer"
        candidate = f"{trimmed_base}{suffix}"
        counter += 1

    used_usernames.add(candidate)
    return candidate


def backfill_lawyer_accounts(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    UserProfile = apps.get_model("main", "UserProfile")
    Lawyer = apps.get_model("main", "Lawyer")

    used_usernames = set(User.objects.values_list("username", flat=True))

    for user in User.objects.all():
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.role:
            profile.role = "client"
            profile.save(update_fields=["role"])

    for lawyer in Lawyer.objects.select_related("user").all():
        user = lawyer.user

        if user is None:
            username_seed = (lawyer.email or "").split("@")[0] or lawyer.name or f"lawyer{lawyer.id}"
            username = generate_unique_username(username_seed, used_usernames)
            first_name, last_name = split_name(lawyer.name)
            user = User.objects.create(
                username=username,
                email=lawyer.email,
                first_name=first_name,
                last_name=last_name,
                is_active=False,
                password=make_password(None),
            )
            lawyer.user = user
            lawyer.is_online = False
            lawyer.save(update_fields=["user", "is_online"])
        else:
            user_updates = []
            first_name, last_name = split_name(lawyer.name)
            if not user.email and lawyer.email:
                user.email = lawyer.email
                user_updates.append("email")
            if not user.first_name and first_name:
                user.first_name = first_name
                user_updates.append("first_name")
            if not user.last_name and last_name:
                user.last_name = last_name
                user_updates.append("last_name")
            if user_updates:
                user.save(update_fields=user_updates)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.role != "lawyer":
            profile.role = "lawyer"
            profile.save(update_fields=["role"])

        if not user.is_active and lawyer.is_online:
            lawyer.is_online = False
            lawyer.save(update_fields=["is_online"])


def reverse_backfill_lawyer_accounts(apps, schema_editor):
    UserProfile = apps.get_model("main", "UserProfile")
    Lawyer = apps.get_model("main", "Lawyer")

    for lawyer in Lawyer.objects.select_related("user").all():
        user = lawyer.user
        if not user:
            continue

        profile = getattr(user, "profile", None)
        if profile:
            profile.role = "client"
            profile.save(update_fields=["role"])


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0005_notification_payment_userprofile_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[("client", "Client"), ("lawyer", "Lawyer")],
                default="client",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_lawyer_accounts, reverse_backfill_lawyer_accounts),
        migrations.RemoveField(
            model_name="userprofile",
            name="is_lawyer",
        ),
        migrations.AlterField(
            model_name="lawyer",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lawyer_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
