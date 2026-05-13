import csv
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone

from main.models import LawCategory, Lawyer, normalize_category_name
from main.utils import ensure_profile_role


CATEGORY_MAP = {
    "criminal": "Criminal Law",
    "civil": "Civil Law",
    "family": "Family Law",
    "corporate": "Corporate Law",
    "cyber": "Cyber Law",
    "property": "Property Law",
    "labor": "Labor Law",
    "environment": "Environmental Law",
    "intellectual": "Intellectual Property Law",
    "employee": "Employee Law",
    "consumer": "Consumer Law",
}


def split_name(full_name):
    parts = (full_name or "").strip().split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name


def create_placeholder_user(name, email):
    first_name, last_name = split_name(name)
    base_username = (email.split("@")[0] if email else "") or "lawyer"
    username = base_username
    counter = 1

    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1

    user = User.objects.create(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=False,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    profile = ensure_profile_role(user, role="lawyer")
    profile.email_verified = True
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified", "email_verified_at"])
    return user


with open("lawyers.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        specialization = (row.get("specialization") or "").strip()
        if not specialization:
            continue

        normalized_specialization = normalize_category_name(specialization)
        key = normalized_specialization.split()[0].lower()
        category_name = CATEGORY_MAP.get(key, normalized_specialization)
        category, _ = LawCategory.objects.get_or_create(name=normalize_category_name(category_name))
        email = row["email"].strip().lower()
        name = row["name"].strip()

        lawyer = Lawyer.objects.filter(email=email).select_related("user").first()
        if lawyer:
            user = lawyer.user
        else:
            existing_user = User.objects.filter(email=email, profile__role="lawyer").first()
            user = existing_user or create_placeholder_user(name, email)

        lawyer, created = Lawyer.objects.update_or_create(
            email=email,
            defaults={
                "user": user,
                "name": name,
                "phone": row["phone"].strip(),
                "specialization": normalized_specialization,
                "experience": int(row["experience"] or 0),
                "city": row["location"].strip(),
                "location": row["location"].strip(),
                "category": category,
                "fee": Decimal("500.00"),
                "certification": "",
                "certificate_file": None,
                "is_verified": True,
            },
        )

        profile = ensure_profile_role(lawyer.user, role="lawyer")
        if not profile.email_verified:
            profile.email_verified = True
            profile.email_verified_at = timezone.now()
            profile.save(update_fields=["email_verified", "email_verified_at"])

print("Lawyers imported successfully from CSV.")
