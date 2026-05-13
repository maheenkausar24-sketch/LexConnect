from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from ..models import Booking, Lawyer, Payment, UserProfile
from ..utils import create_notification, ensure_profile_role, mark_user_offline
from .bookings import cancel_booking
from .payments import mark_payment_failed, mark_payment_pending, mark_payment_refunded, mark_payment_success


def admin_lawyers_queryset():
    return Lawyer.objects.select_related("user", "user__profile", "category").order_by("verification_status", "name")


def admin_clients_queryset():
    return User.objects.filter(profile__role=UserProfile.Role.CLIENT).select_related("profile").order_by("username")


def admin_bookings_queryset():
    return Booking.objects.select_related("client", "lawyer", "payment").order_by("-created_at")


def admin_payments_queryset():
    return Payment.objects.select_related("booking", "booking__client", "booking__lawyer").order_by("-created_at")


def admin_dashboard_stats():
    return {
        "total_users": User.objects.count(),
        "total_clients": User.objects.filter(profile__role=UserProfile.Role.CLIENT).count(),
        "total_lawyers": User.objects.filter(profile__role=UserProfile.Role.LAWYER).count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "verified_lawyers": Lawyer.objects.filter(is_verified=True).count(),
        "total_bookings": Booking.objects.count(),
        "completed_bookings": Booking.objects.filter(status=Booking.Status.COMPLETED).count(),
        "pending_lawyer_verifications": Lawyer.objects.filter(
            verification_status__in=[Lawyer.VerificationStatus.PENDING, Lawyer.VerificationStatus.UNDER_REVIEW]
        ).count(),
        "pending_payments": Payment.objects.filter(payment_status=Payment.PaymentStatus.PENDING).count(),
        "successful_payments": Payment.objects.filter(payment_status=Payment.PaymentStatus.SUCCESS).count(),
        "total_revenue": Payment.objects.filter(payment_status=Payment.PaymentStatus.SUCCESS).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00"),
    }


def set_lawyer_verification(lawyer, *, is_verified):
    lawyer.is_verified = is_verified
    if is_verified:
        lawyer.verification_status = Lawyer.VerificationStatus.APPROVED
        lawyer.verified_at = timezone.now()
        lawyer.verification_notes = ""
    else:
        lawyer.verification_status = Lawyer.VerificationStatus.REJECTED
        lawyer.verified_at = None
        lawyer.is_online = False
        if lawyer.user_id:
            mark_user_offline(lawyer.user)
    lawyer.save(update_fields=["is_verified", "verification_status", "verified_at", "verification_notes", "is_online", "updated_at"])
    if lawyer.user_id:
        create_notification(
            lawyer.user,
            "Lawyer verification updated",
            f"Your lawyer account is now {'verified' if is_verified else 'unverified'}.",
            "/lawyer/dashboard/",
        )
    return lawyer


def set_user_active_state(user, *, is_active):
    user.is_active = is_active
    user.save(update_fields=["is_active"])
    profile = ensure_profile_role(user)
    if not is_active:
        mark_user_offline(user)
        if hasattr(user, "lawyer_profile"):
            user.lawyer_profile.is_online = False
            user.lawyer_profile.save(update_fields=["is_online", "updated_at"])
    return user


def admin_force_cancel_booking(booking, *, actor, reason="Cancelled by admin"):
    if booking.status == Booking.Status.CANCELLED:
        raise ValidationError("Booking is already cancelled.")
    if booking.status == Booking.Status.COMPLETED:
        raise ValidationError("Completed bookings cannot be force-cancelled.")
    return cancel_booking(booking, actor=actor, reason=reason)


def admin_update_payment_status(payment, *, next_status, actor=None):
    booking = payment.booking

    if booking.status == Booking.Status.COMPLETED and next_status not in {
        Payment.PaymentStatus.SUCCESS,
        Payment.PaymentStatus.REFUNDED,
    }:
        raise ValidationError("Completed bookings must keep a successful payment record.")

    if next_status == payment.payment_status:
        return payment

    if next_status == Payment.PaymentStatus.SUCCESS:
        return mark_payment_success(payment, actor=actor)

    if next_status == Payment.PaymentStatus.FAILED:
        return mark_payment_failed(payment)

    if next_status == Payment.PaymentStatus.REFUNDED:
        return mark_payment_refunded(payment, actor=actor)

    return mark_payment_pending(payment)
