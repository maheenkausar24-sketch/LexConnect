from django.conf import settings
from django.contrib.auth import get_user_model


def get_admin_credentials():
    username = getattr(settings, "LEXCONNECT_ADMIN_USERNAME", "").strip()
    password = getattr(settings, "LEXCONNECT_ADMIN_PASSWORD", "")
    email = getattr(settings, "LEXCONNECT_ADMIN_EMAIL", "admin@lexconnect.local").strip()
    return username, password, email


def ensure_lexconnect_admin_user(*, force_password=False):
    """
    Create or update the superuser defined in .env (LEXCONNECT_ADMIN_*).
  Returns (user, created) or (None, False) when credentials are not configured.
    """
    username, password, email = get_admin_credentials()
    if not username or not password:
        return None, False

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email or f"{username}@lexconnect.local",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    updated = False
    if not user.is_staff or not user.is_superuser or not user.is_active:
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        updated = True

    if email and user.email != email:
        user.email = email
        updated = True

    if created or force_password or not user.has_usable_password():
        user.set_password(password)
        updated = True

    if updated or created:
        user.save()

    return user, created
