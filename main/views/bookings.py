from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ..decorators import client_required, lawyer_required
from ..forms import BookingCancelForm, BookingForm, BookingRescheduleForm, BookingStatusForm, LawyerAvailabilityForm, PaymentStatusForm, ReviewForm
from ..models import Booking, Lawyer, Notification, Payment, Review
from ..rate_limit import rate_limit
from ..services.auth import is_lawyer_user
from ..services.bookings import cancel_booking, create_booking_with_payment, eligible_review_bookings, get_client_bookings_queryset, reschedule_booking, time_ranges_overlap, transition_booking_status, upcoming_available_slots, upcoming_slot_statuses
from ..services.payments import ensure_payment, request_demo_payment_verification
from ..services.lawyers import visible_lawyers_queryset
from ..utils import create_notification


@client_required
@rate_limit("booking_create", limit=10, period=600)
def consult_lawyer(request, lawyer_id):
    lawyer = get_object_or_404(visible_lawyers_queryset(), id=lawyer_id)
    upcoming_slots = upcoming_available_slots(lawyer)
    upcoming_statuses = upcoming_slot_statuses(lawyer)
    slot_choices = [
        (f"{slot['date'].isoformat()}|{slot['start_time'].isoformat(timespec='minutes')}", f"{slot['date']} at {slot['start_time'].strftime('%H:%M')}")
        for slot in upcoming_slots
    ]
    form = BookingForm(request.POST or None, slot_choices=slot_choices)

    if request.method == "POST" and form.is_valid():
        try:
            booking = create_booking_with_payment(request.user, lawyer, form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Consultation submitted successfully.")
            return redirect("payment_page", booking_id=booking.id)

    return render(
        request,
        "consult.html",
        {
            "lawyer": lawyer,
            "form": form,
            "error": form.first_error(),
            "availability_slots": lawyer.availability_slots.filter(is_active=True),
            "upcoming_slots": upcoming_slots,
            "upcoming_statuses": upcoming_statuses,
        },
    )


@login_required
def request_success(request):
    return render(request, "success.html")


@client_required
@rate_limit("payment_action", limit=6, period=300)
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related("lawyer", "payment"), id=booking_id, client=request.user)
    payment, _ = ensure_payment(booking)
    form = PaymentStatusForm(request.POST or None)

    if request.method == "POST" and payment.payment_status == Payment.PaymentStatus.SUCCESS:
        messages.info(request, "This payment is already marked successful. You can continue in chat.")
        return redirect("start_chat_for_booking", booking_id=booking.id)

    if request.method == "POST" and form.is_valid():
        try:
            request_demo_payment_verification(payment, actor=request.user)
            messages.success(request, "Demo payment verification requested. An admin must approve it before chat unlocks.")
            return redirect("payment_page", booking_id=booking.id)
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect("payment_page", booking_id=booking.id)

    return render(
        request,
        "payment.html",
        {
            "booking": booking,
            "payment": payment,
            "form": form,
            "chat_url": (
                reverse("start_chat_for_booking", args=[booking.id])
                if payment.payment_status == Payment.PaymentStatus.SUCCESS
                and booking.status in {Booking.Status.CONFIRMED, Booking.Status.COMPLETED}
                else None
            ),
        },
    )


@lawyer_required
@rate_limit("booking_status_action", limit=30, period=300)
def update_booking_status(request, booking_id, status):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")

    booking = get_object_or_404(Booking.objects.select_related("client", "lawyer"), id=booking_id)
    if booking.lawyer != request.user.lawyer_profile:
        return HttpResponseBadRequest("Only the assigned lawyer can update this booking.")

    form = BookingStatusForm({"status": status})
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid booking status.")

    next_status = form.cleaned_data["status"]
    if next_status == Booking.Status.CONFIRMED:
        return HttpResponseBadRequest("Bookings are confirmed automatically after successful payment.")

    try:
        if next_status == Booking.Status.COMPLETED:
            transition_booking_status(booking, Booking.Status.COMPLETED)
            create_notification(
                booking.client,
                "Booking completed",
                f"Consultation #{booking.id} has been marked as completed.",
                "/client/bookings/",
                notification_type=Notification.NotificationType.BOOKING,
            )
        elif next_status == Booking.Status.CANCELLED:
            cancel_booking(booking, actor=request.user)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("lawyer_bookings")

    messages.success(request, "Booking status updated.")
    return redirect("lawyer_bookings")


@login_required
@rate_limit("booking_reschedule", limit=10, period=600)
def reschedule_booking_view(request, booking_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")
    booking = get_object_or_404(Booking.objects.select_related("lawyer", "client"), id=booking_id)
    if booking.client != request.user and (not is_lawyer_user(request.user) or booking.lawyer != request.user.lawyer_profile):
        return HttpResponseBadRequest("You cannot reschedule this booking.")

    form = BookingRescheduleForm(request.POST or None, instance=booking)
    if request.method == "POST" and form.is_valid():
        try:
            reschedule_booking(booking, form.cleaned_data, actor=request.user)
        except ValidationError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Booking rescheduled successfully.")
            return redirect("client_bookings" if booking.client == request.user else "lawyer_bookings")

    messages.error(request, form.first_error() or "Unable to reschedule booking.")
    return redirect("client_bookings" if booking.client == request.user else "lawyer_bookings")


@login_required
@rate_limit("booking_cancel", limit=10, period=600)
def cancel_booking_view(request, booking_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")
    booking = get_object_or_404(Booking.objects.select_related("lawyer", "client"), id=booking_id)
    if booking.client != request.user and (not is_lawyer_user(request.user) or booking.lawyer != request.user.lawyer_profile):
        return HttpResponseBadRequest("You cannot cancel this booking.")

    form = BookingCancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cancel_booking(booking, actor=request.user, reason=form.cleaned_data["cancel_reason"])
        messages.success(request, "Booking cancelled successfully.")
    else:
        messages.error(request, form.first_error() or "Unable to cancel booking.")
    return redirect("client_bookings" if booking.client == request.user else "lawyer_bookings")


@client_required
@rate_limit("review_create", limit=10, period=600)
def add_review(request, lawyer_id):
    lawyer = get_object_or_404(Lawyer, id=lawyer_id)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        booking = get_object_or_404(
            Booking,
            id=form.cleaned_data["booking_id"],
            client=request.user,
            lawyer=lawyer,
            status=Booking.Status.COMPLETED,
        )
        if hasattr(booking, "review"):
            messages.error(request, "This consultation has already been reviewed.")
            return redirect("lawyer_profile", lawyer_id=lawyer.id)

        Review.objects.create(
            booking=booking,
            client=request.user,
            lawyer=lawyer,
            rating=form.cleaned_data["rating"],
            comment=form.cleaned_data["comment"],
        )
        create_notification(
            lawyer.user,
            "New review received",
            f"{request.user.username} left a review for booking #{booking.id}.",
            f"/lawyer/profile/{lawyer.id}/",
            notification_type=Notification.NotificationType.BOOKING,
        )
        messages.success(request, "Review submitted successfully.")
    else:
        messages.error(request, form.first_error() or "Unable to submit review.")
    return redirect("lawyer_profile", lawyer_id=lawyer.id)


@lawyer_required
@rate_limit("availability_action", limit=30, period=300)
def add_schedule_slot(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request.")

    form = LawyerAvailabilityForm(request.POST)
    if form.is_valid():
        slot = form.save(commit=False)
        slot.lawyer = request.user.lawyer_profile
        overlapping = any(
            time_ranges_overlap(slot.start_time, slot.end_time, existing.start_time, existing.end_time)
            for existing in slot.lawyer.availability_slots.filter(weekday=slot.weekday, is_active=True)
        )
        if overlapping:
            messages.error(request, "This availability overlaps an existing active window.")
        else:
            slot.save()
            messages.success(request, "Availability slot added.")
    else:
        messages.error(request, form.first_error() or "Unable to add availability slot.")
    return redirect("lawyer_availability")
