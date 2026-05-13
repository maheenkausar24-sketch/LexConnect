import csv
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from ..models import LawCategory, Lawyer, UserProfile, normalize_category_name
from ..utils import ensure_profile_role
from .auth import COMMON_DEMO_LAWYER_PASSWORD


CSV_FILENAMES = ("lawyers.csv", "lawyers_data.csv")
SKIPPED_SCAN_DIRS = {".git", "env", "venv", ".venv", "__pycache__", "media", "staticfiles"}


@dataclass
class LawyerImportSummary:
    path: Path
    total_processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0


def find_lawyer_csv(base_dir):
    base_path = Path(base_dir)
    for filename in CSV_FILENAMES:
        root_match = base_path / filename
        if root_match.exists():
            return root_match

    for current_root, dirnames, filenames in os.walk(base_path):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIPPED_SCAN_DIRS]
        for filename in CSV_FILENAMES:
            if filename in filenames:
                return Path(current_root) / filename
    return None


def create_empty_lawyer_csv(base_dir):
    path = Path(base_dir) / "lawyers_data.csv"
    if not path.exists():
        path.write_text("name,email,specialization,experience,city\n", encoding="utf-8")
    return path


def split_name(full_name):
    parts = (full_name or "").strip().split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name


def generate_unique_username(seed):
    base = "".join(ch for ch in (seed or "lawyer").lower() if ch.isalnum() or ch in "._+-")[:140] or "lawyer"
    candidate = base
    counter = 1
    while User.objects.filter(username=candidate).exists():
        suffix = f"_{counter}"
        candidate = f"{base[:150 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def safe_int(value, default=0):
    try:
        return max(int(str(value or "").strip()), 0)
    except (TypeError, ValueError):
        return default


def safe_decimal(value, default=Decimal("500.00")):
    try:
        return Decimal(str(value or "").strip() or default)
    except (InvalidOperation, ValueError):
        return default


def row_value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def import_lawyers_from_csv(base_dir, *, csv_path=None, create_if_missing=True, default_password=COMMON_DEMO_LAWYER_PASSWORD):
    path = Path(csv_path) if csv_path else find_lawyer_csv(base_dir)
    if path is None:
        if not create_if_missing:
            raise FileNotFoundError("No lawyer CSV file found.")
        path = create_empty_lawyer_csv(base_dir)

    summary = LawyerImportSummary(path=path)
    default_password_hash = make_password(default_password)

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            summary.total_processed += 1
            name = row_value(row, "name", "full_name")
            email = row_value(row, "email").lower()
            specialization = row_value(row, "specialization", "category", "practice_area")
            city = row_value(row, "city", "location")
            phone = row_value(row, "phone")
            experience_value = row_value(row, "experience")

            if not email or not specialization:
                summary.skipped += 1
                continue

            category_name = normalize_category_name(specialization)
            category, _ = LawCategory.objects.get_or_create(name=category_name)
            first_name, last_name = split_name(name)

            existing_lawyer = Lawyer.objects.filter(email__iexact=email).select_related("user").first()
            user = existing_lawyer.user if existing_lawyer else User.objects.filter(email__iexact=email).order_by("id").first()
            if user is None:
                username_seed = email.split("@", 1)[0] or name
                user = User.objects.create(
                    username=generate_unique_username(username_seed),
                    email=email,
                    password=default_password_hash,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                )
            else:
                user.email = email
                user.first_name = first_name or user.first_name
                user.last_name = last_name or user.last_name
                user.is_active = True
                user.password = default_password_hash
                user.save()

            profile = ensure_profile_role(user, role=UserProfile.Role.LAWYER)
            if not profile.email_verified:
                profile.email_verified = True
                profile.email_verified_at = timezone.now()
                profile.save(update_fields=["email_verified", "email_verified_at"])
            lawyer = existing_lawyer or getattr(user, "lawyer_profile", None)
            city = city or getattr(lawyer, "city", "") or getattr(lawyer, "location", "")
            phone = phone or getattr(lawyer, "phone", "")
            experience = safe_int(experience_value, default=getattr(lawyer, "experience", 0))
            fee = safe_decimal(row_value(row, "fee", "consultation_fee"), default=getattr(lawyer, "fee", Decimal("500.00")))

            defaults = {
                "user": user,
                "category": category,
                "name": name or user.get_full_name() or user.username,
                "phone": phone,
                "specialization": category_name,
                "experience": experience,
                "city": city,
                "location": city,
                "fee": fee,
                "is_verified": True,
            }
            bio = row_value(row, "bio")
            if bio:
                defaults["bio"] = bio

            if lawyer:
                for field, value in defaults.items():
                    setattr(lawyer, field, value)
                lawyer.email = email
                lawyer.save()
                created = False
            else:
                Lawyer.objects.create(email=email, **defaults)
                created = True

            if created:
                summary.created += 1
            else:
                summary.updated += 1

    return summary
