from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from ..models import Lawyer, UserProfile
from ..utils import ensure_profile_role, is_lawyer_account


COMMON_DEMO_LAWYER_PASSWORD = "lawyer@123"


def split_name(full_name):
    parts = (full_name or "").strip().split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name


def is_lawyer_user(user):
    return is_lawyer_account(user)


def is_admin_user(user):
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_active", False) and (user.is_staff or user.is_superuser))


def is_client_user(user):
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if is_admin_user(user) or is_lawyer_user(user):
        return False
    profile = ensure_profile_role(user)
    return profile.role == UserProfile.Role.CLIENT


def get_dashboard_route(user):
    if is_admin_user(user):
        return "admin_dashboard"
    if is_lawyer_user(user):
        return "lawyer_dashboard"
    return "client_dashboard"


def lawyer_accounts_queryset():
    return (
        User.objects.filter(profile__role=UserProfile.Role.LAWYER)
        .select_related("profile", "lawyer_profile")
        .order_by("email", "username")
    )


def reset_all_lawyer_accounts(common_password=COMMON_DEMO_LAWYER_PASSWORD):
    accounts = []
    password_hash = make_password(common_password)

    for user in lawyer_accounts_queryset():
        user.is_active = True
        user.password = password_hash
        user.save(update_fields=["is_active", "password"])

        profile = ensure_profile_role(user, role=UserProfile.Role.LAWYER)
        if not profile.email_verified:
            profile.email_verified = True
            profile.email_verified_at = timezone.now()
            profile.save(update_fields=["email_verified", "email_verified_at"])
        lawyer = getattr(user, "lawyer_profile", None)
        accounts.append(
            {
                "username": user.username,
                "email": user.email or (lawyer.email if lawyer else ""),
                "role": profile.get_role_display(),
                "lawyer_name": lawyer.name if lawyer else (user.get_full_name() or user.username),
            }
        )

    return accounts


def register_client_user(cleaned_data):
    user = User.objects.create_user(
        username=cleaned_data["username"],
        email=cleaned_data["email"].lower(),
        password=cleaned_data["password"],
    )
    ensure_profile_role(user, role=UserProfile.Role.CLIENT)
    return user


def register_lawyer_user(cleaned_data):
    username = cleaned_data["username"]
    email = cleaned_data["email"].lower()
    password = cleaned_data["password"]
    name = cleaned_data["name"]
    phone = cleaned_data["phone"]
    location = cleaned_data["location"]
    experience = cleaned_data["experience"]
    fee = cleaned_data["fee"]
    bio = cleaned_data["bio"]
    certification = cleaned_data.get("certification", "")
    certificate_file = cleaned_data.get("certificate_file")
    category = cleaned_data["category"]

    existing_lawyer = Lawyer.objects.select_related("user", "user__profile").filter(email=email).first()
    claimed_user = existing_lawyer.user if existing_lawyer else None

    username_query = User.objects.filter(username=username)
    if claimed_user:
        username_query = username_query.exclude(id=claimed_user.id)
    if username_query.exists():
        raise ValueError("Username already exists")

    email_query = User.objects.filter(email=email)
    if claimed_user:
        email_query = email_query.exclude(id=claimed_user.id)
    if email_query.exists():
        raise ValueError("Email already exists")

    first_name, last_name = split_name(name)

    if existing_lawyer and claimed_user and existing_lawyer.is_verified and getattr(claimed_user, "profile", None):
        if claimed_user.profile.role == UserProfile.Role.LAWYER:
            raise ValueError("Lawyer account already exists. Please log in.")

    if existing_lawyer and claimed_user:
        user = claimed_user
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.set_password(password)
        user.save()
        ensure_profile_role(user, role=UserProfile.Role.LAWYER)

        lawyer = existing_lawyer
        lawyer.category = category
        lawyer.name = name or lawyer.name
        lawyer.phone = phone
        lawyer.experience = experience
        lawyer.city = location
        lawyer.location = location
        lawyer.bio = bio
        lawyer.certification = certification
        if certificate_file:
            lawyer.certificate_file = certificate_file
        lawyer.specialization = category.name
        lawyer.fee = fee
        lawyer.is_verified = False
        lawyer.verification_status = Lawyer.VerificationStatus.UNDER_REVIEW
        lawyer.verification_submitted_at = timezone.now()
        lawyer.user = user
        lawyer.save()
        return user, "Lawyer account submitted successfully. Admin verification is required before clients can book you."

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    ensure_profile_role(user, role=UserProfile.Role.LAWYER)
    Lawyer.objects.create(
        user=user,
        category=category,
        name=name,
        email=email,
        phone=phone,
        specialization=category.name,
        experience=experience,
        city=location,
        location=location,
        bio=bio,
        certification=certification,
        certificate_file=certificate_file,
        fee=fee,
        is_verified=False,
        verification_status=Lawyer.VerificationStatus.UNDER_REVIEW,
        verification_submitted_at=timezone.now(),
    )
    return user, "Lawyer account submitted successfully. Admin verification is required before clients can book you."
