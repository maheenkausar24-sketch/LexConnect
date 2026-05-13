from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from ..decorators import admin_required
from ..forms import AdminLawyerVerificationForm, AdminPaymentStatusForm, AdminUserStatusForm
from ..models import Booking, Lawyer, Payment
from ..audit import audit_event
from ..rate_limit import rate_limit
from ..services.admin_panel import (
    admin_bookings_queryset,
    admin_clients_queryset,
    admin_dashboard_stats,
    admin_force_cancel_booking,
    admin_lawyers_queryset,
    admin_payments_queryset,
    admin_update_payment_status,
    set_lawyer_verification,
    set_user_active_state,
)


User = get_user_model()


@admin_required
def admin_dashboard(request):
    return render(
        request,
        "admin_dashboard.html",
        {
            "stats": admin_dashboard_stats(),
            "pending_lawyers": admin_lawyers_queryset().filter(verification_status__in=["pending", "under_review"])[:8],
            "recent_bookings": admin_bookings_queryset()[:8],
            "recent_payments": admin_payments_queryset()[:8],
        },
    )


@admin_required
def admin_lawyers(request):
    return render(
        request,
        "admin_lawyers.html",
        {
            "lawyers": admin_lawyers_queryset(),
            "verification_form": AdminLawyerVerificationForm(),
            "user_status_form": AdminUserStatusForm(),
        },
    )


@admin_required
def admin_clients(request):
    return render(
        request,
        "admin_clients.html",
        {
            "clients": admin_clients_queryset(),
            "user_status_form": AdminUserStatusForm(),
        },
    )


@admin_required
def admin_bookings(request):
    return render(request, "admin_bookings.html", {"bookings": admin_bookings_queryset()})


@admin_required
def admin_payments(request):
    return render(
        request,
        "admin_payments.html",
        {
            "payments": admin_payments_queryset(),
            "payment_form": AdminPaymentStatusForm(),
        },
    )


@admin_required
def admin_update_lawyer_verification(request, lawyer_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")

    lawyer = get_object_or_404(Lawyer.objects.select_related("user"), id=lawyer_id)
    form = AdminLawyerVerificationForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.first_error() or "Unable to update lawyer verification.")
        return redirect("admin_lawyers")

    set_lawyer_verification(lawyer, is_verified=form.cleaned_value())
    audit_event("admin_lawyer_verification_updated", request=request, actor=request.user, lawyer_id=lawyer.id, is_verified=form.cleaned_value())
    messages.success(request, f"Verification updated for {lawyer.name}.")
    return redirect("admin_lawyers")


@admin_required
def admin_update_user_status(request, user_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")

    user = get_object_or_404(User.objects.select_related("profile"), id=user_id)
    form = AdminUserStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.first_error() or "Unable to update account status.")
        return redirect("admin_clients")

    set_user_active_state(user, is_active=form.cleaned_value())
    audit_event("admin_user_active_state_updated", request=request, actor=request.user, target_user_id=user.id, is_active=form.cleaned_value())
    messages.success(request, f"Account status updated for {user.username}.")

    if hasattr(user, "lawyer_profile"):
        return redirect("admin_lawyers")
    return redirect("admin_clients")


@admin_required
def admin_cancel_booking(request, booking_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")

    booking = get_object_or_404(Booking.objects.select_related("client", "lawyer"), id=booking_id)
    try:
        admin_force_cancel_booking(booking, actor=request.user, reason="Cancelled by admin")
    except ValidationError as exc:
        messages.error(request, str(exc))
    else:
        audit_event("admin_booking_cancelled", request=request, actor=request.user, booking_id=booking.id)
        messages.success(request, f"Booking #{booking.id} was cancelled.")
    return redirect("admin_bookings")


@admin_required
@rate_limit("admin_payment_action", limit=20, period=300)
def admin_update_payment(request, payment_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")

    payment = get_object_or_404(Payment.objects.select_related("booking", "booking__client", "booking__lawyer"), id=payment_id)
    form = AdminPaymentStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.first_error() or "Unable to update payment.")
        return redirect("admin_payments")

    try:
        admin_update_payment_status(payment, next_status=form.cleaned_data["payment_status"], actor=request.user)
    except ValidationError as exc:
        messages.error(request, str(exc))
    else:
        audit_event("admin_payment_status_updated", request=request, actor=request.user, payment_id=payment.id, payment_status=form.cleaned_data["payment_status"])
        messages.success(request, f"Payment for booking #{payment.booking_id} updated.")
    return redirect("admin_payments")
