from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from ..audit import audit_event
from ..models import Booking, BookingStatusHistory, Lawyer, LawyerBlockedDate, Payment
from ..utils import create_notification


BOOKING_ACTIVE_STATUSES = [Booking.Status.PENDING, Booking.Status.CONFIRMED]
BOOKING_CHAT_STATUSES = [Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
ALLOWED_BOOKING_TRANSITIONS = {
    Booking.Status.PENDING: {Booking.Status.CONFIRMED, Booking.Status.CANCELLED},
    Booking.Status.CONFIRMED: {Booking.Status.COMPLETED, Booking.Status.CANCELLED},
    Booking.Status.RESCHEDULED: {Booking.Status.CONFIRMED, Booking.Status.CANCELLED},
    Booking.Status.COMPLETED: set(),
    Booking.Status.CANCELLED: set(),
    Booking.Status.REFUNDED: set(),
}


def appointment_starts_at(appointment_date, appointment_time):
    return timezone.make_aware(
        datetime.combine(appointment_date, appointment_time),
        timezone.get_current_timezone(),
    )


def slot_is_past(appointment_date, appointment_time):
    return appointment_starts_at(appointment_date, appointment_time) <= timezone.now()


def slot_end_time(start_time, duration_minutes):
    return (datetime.combine(timezone.localdate(), start_time) + timedelta(minutes=duration_minutes)).time()


def booking_time_window(booking):
    return booking.appointment_time, slot_end_time(booking.appointment_time, booking.duration_minutes)


def time_ranges_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def lock_lawyer_for_booking(lawyer):
    return Lawyer.objects.select_for_update().select_related("user").get(pk=lawyer.pk)


def lock_booking_for_update(booking):
    return (
        Booking.objects.select_for_update()
        .select_related("client", "lawyer", "lawyer__user", "payment")
        .get(pk=booking.pk)
    )


def get_client_bookings_queryset(user):
    return Booking.objects.filter(client=user).select_related("lawyer", "payment").order_by("-created_at")


def get_lawyer_bookings_queryset(lawyer):
    return Booking.objects.filter(lawyer=lawyer).select_related("client", "payment").order_by("-created_at")


def active_bookings_for_date(lawyer, appointment_date, *, exclude_booking=None, for_update=False):
    queryset = Booking.objects.filter(
        lawyer=lawyer,
        appointment_date=appointment_date,
        status__in=BOOKING_ACTIVE_STATUSES,
    )
    if exclude_booking:
        queryset = queryset.exclude(id=exclude_booking.id)
    if for_update:
        queryset = queryset.select_for_update()
    return queryset


def slot_overlaps_bookings(slot, bookings):
    slot_start = slot["start_time"]
    slot_end = slot["end_time"]
    for booking in bookings:
        booking_start, booking_end = booking_time_window(booking)
        if time_ranges_overlap(slot_start, slot_end, booking_start, booking_end):
            return True
    return False


def assert_no_booking_overlap(lawyer, appointment_date, start_time, duration_minutes, *, exclude_booking=None, for_update=False):
    proposed_end_time = slot_end_time(start_time, duration_minutes)
    active_bookings = active_bookings_for_date(
        lawyer,
        appointment_date,
        exclude_booking=exclude_booking,
        for_update=for_update,
    )
    for booking in active_bookings:
        booking_start, booking_end = booking_time_window(booking)
        if time_ranges_overlap(start_time, proposed_end_time, booking_start, booking_end):
            raise ValidationError("That appointment time overlaps an existing booking. Please choose another slot.")


def availability_breaks_contain(slot_start, slot_end, breaks):
    for break_period in breaks:
        if time_ranges_overlap(slot_start, slot_end, break_period.start_time, break_period.end_time):
            return True
    return False


def generated_slots_for_date(lawyer, appointment_date):
    if LawyerBlockedDate.objects.filter(lawyer=lawyer, date=appointment_date).exists():
        return []

    generated = []
    availability_rows = (
        lawyer.availability_slots.filter(weekday=appointment_date.weekday(), is_active=True)
        .prefetch_related("breaks")
        .order_by("start_time")
    )
    for availability in availability_rows:
        cursor = datetime.combine(appointment_date, availability.start_time)
        availability_end = datetime.combine(appointment_date, availability.end_time)
        duration = timedelta(minutes=availability.slot_duration_minutes)
        breaks = list(availability.breaks.all())

        while cursor + duration <= availability_end:
            start_time = cursor.time().replace(second=0, microsecond=0)
            end_time = (cursor + duration).time().replace(second=0, microsecond=0)
            if not availability_breaks_contain(start_time, end_time, breaks):
                generated.append(
                    {
                        "availability": availability,
                        "date": appointment_date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration_minutes": availability.slot_duration_minutes,
                        "timezone_name": availability.timezone_name,
                    }
                )
            cursor += duration

    return generated


def available_slots_for_date(lawyer, appointment_date, *, exclude_booking=None):
    bookings = list(active_bookings_for_date(lawyer, appointment_date, exclude_booking=exclude_booking))
    return [
        slot
        for slot in generated_slots_for_date(lawyer, appointment_date)
        if not slot_is_past(appointment_date, slot["start_time"]) and not slot_overlaps_bookings(slot, bookings)
    ]


def slot_statuses_for_date(lawyer, appointment_date, *, exclude_booking=None):
    bookings = list(active_bookings_for_date(lawyer, appointment_date, exclude_booking=exclude_booking))
    statuses = []
    for slot in generated_slots_for_date(lawyer, appointment_date):
        is_past = slot_is_past(appointment_date, slot["start_time"])
        is_booked = slot_overlaps_bookings(slot, bookings)
        statuses.append(
            {
                "date": appointment_date,
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "duration_minutes": slot["duration_minutes"],
                "is_available": not is_past and not is_booked,
                "status_label": "Past slot" if is_past else "Slot Full" if is_booked else "Available",
            }
        )
    return statuses


def upcoming_available_slots(lawyer, *, days=10, limit=8):
    upcoming_slots = []
    today = timezone.localdate()

    for offset in range(days):
        appointment_date = today + timedelta(days=offset)
        slots = available_slots_for_date(lawyer, appointment_date)
        for slot in slots:
            upcoming_slots.append(slot)
            if len(upcoming_slots) >= limit:
                return upcoming_slots

    return upcoming_slots


def upcoming_slot_statuses(lawyer, *, days=10, limit=16):
    upcoming_slots = []
    today = timezone.localdate()

    for offset in range(days):
        appointment_date = today + timedelta(days=offset)
        for slot in slot_statuses_for_date(lawyer, appointment_date):
            upcoming_slots.append(slot)
            if len(upcoming_slots) >= limit:
                return upcoming_slots

    return upcoming_slots


def validate_booking_slot(lawyer, appointment_date, appointment_time, *, exclude_booking=None):
    if slot_is_past(appointment_date, appointment_time):
        raise ValidationError("Selected appointment slot has already passed.")

    matching_slot = next(
        (slot for slot in generated_slots_for_date(lawyer, appointment_date) if slot["start_time"] == appointment_time),
        None,
    )
    if not matching_slot:
        raise ValidationError("Selected appointment time is not one of the lawyer's generated consultation slots.")

    assert_no_booking_overlap(
        lawyer,
        appointment_date,
        matching_slot["start_time"],
        matching_slot["duration_minutes"],
        exclude_booking=exclude_booking,
    )

    return matching_slot


def create_booking_with_payment(client, lawyer, cleaned_data):
    with transaction.atomic():
        lawyer = lock_lawyer_for_booking(lawyer)
        list(active_bookings_for_date(lawyer, cleaned_data["appointment_date"], for_update=True))
        slot = validate_booking_slot(lawyer, cleaned_data["appointment_date"], cleaned_data["appointment_time"])
        assert_no_booking_overlap(
            lawyer,
            cleaned_data["appointment_date"],
            slot["start_time"],
            slot["duration_minutes"],
            for_update=True,
        )
        try:
            booking = Booking.objects.create(
                client=client,
                lawyer=lawyer,
                issue=cleaned_data["issue"],
                appointment_date=cleaned_data["appointment_date"],
                appointment_time=cleaned_data["appointment_time"],
                duration_minutes=slot["duration_minutes"],
                timezone_name=slot["timezone_name"],
                price_snapshot=lawyer.fee,
                status=Booking.Status.PENDING,
            )
            Payment.objects.create(booking=booking, amount=booking.price_snapshot or lawyer.fee)
            BookingStatusHistory.objects.create(booking=booking, to_status=booking.status, actor=client, reason="Booking created")
        except IntegrityError as exc:
            raise ValidationError("That appointment slot has just been booked. Please choose another slot.") from exc
    create_notification(
        lawyer.user,
        "New booking request",
        f"{client.username} requested a consultation for {booking.appointment_date} at {booking.appointment_time.strftime('%H:%M')}.",
        reverse("lawyer_dashboard"),
    )
    audit_event("booking_created", actor=client, booking_id=booking.id, lawyer_id=lawyer.id)
    return booking


def validate_booking_transition(booking, next_status):
    try:
        next_status = Booking.Status(next_status)
    except ValueError as exc:
        raise ValidationError("Invalid booking status transition.") from exc

    if next_status == booking.status:
        raise ValidationError(f"Booking is already {booking.get_status_display().lower()}.")

    allowed_next_statuses = ALLOWED_BOOKING_TRANSITIONS.get(booking.status, set())
    if next_status not in allowed_next_statuses:
        raise ValidationError(
            f"Booking cannot move from {booking.get_status_display().lower()} to {next_status.label.lower()}."
        )

    payment = getattr(booking, "payment", None)
    if next_status in {Booking.Status.CONFIRMED, Booking.Status.COMPLETED}:
        if not payment or payment.payment_status != Payment.PaymentStatus.SUCCESS:
            raise ValidationError("A successful payment is required before confirming or completing a booking.")


def transition_booking_status(booking, next_status, *, reason="", actor=None):
    with transaction.atomic():
        booking = lock_booking_for_update(booking)
        validate_booking_transition(booking, next_status)

        previous_status = booking.status
        booking.status = Booking.Status(next_status)
        update_fields = ["status", "updated_at"]

        if booking.status == Booking.Status.CANCELLED:
            booking.cancel_reason = reason
            booking.cancelled_at = timezone.now()
            update_fields.extend(["cancel_reason", "cancelled_at"])

        booking.save(update_fields=update_fields)
        BookingStatusHistory.objects.create(
            booking=booking,
            from_status=previous_status,
            to_status=booking.status,
            actor=actor,
            reason=reason,
        )
    audit_event("booking_status_transition", actor=actor, booking_id=booking.id, from_status=previous_status, to_status=booking.status)
    return booking


def cancel_booking(booking, *, actor, reason=""):
    booking = transition_booking_status(booking, Booking.Status.CANCELLED, reason=reason, actor=actor)

    recipient = booking.lawyer.user if actor == booking.client else booking.client
    create_notification(
        recipient,
        "Booking cancelled",
        f"Consultation #{booking.id} was cancelled.",
        reverse("dashboard" if recipient == booking.client else "lawyer_dashboard"),
    )
    return booking


def reschedule_booking(booking, cleaned_data, *, actor):
    with transaction.atomic():
        booking = lock_booking_for_update(booking)
        if booking.status not in BOOKING_ACTIVE_STATUSES:
            raise ValidationError("Only pending or confirmed bookings can be rescheduled.")

        lawyer = lock_lawyer_for_booking(booking.lawyer)
        list(active_bookings_for_date(lawyer, cleaned_data["appointment_date"], exclude_booking=booking, for_update=True))
        slot = validate_booking_slot(
            lawyer,
            cleaned_data["appointment_date"],
            cleaned_data["appointment_time"],
            exclude_booking=booking,
        )
        assert_no_booking_overlap(
            lawyer,
            cleaned_data["appointment_date"],
            slot["start_time"],
            slot["duration_minutes"],
            exclude_booking=booking,
            for_update=True,
        )
        previous_schedule = f"{booking.appointment_date} {booking.appointment_time.strftime('%H:%M')}"
        booking.appointment_date = cleaned_data["appointment_date"]
        booking.appointment_time = cleaned_data["appointment_time"]
        booking.duration_minutes = slot["duration_minutes"]
        booking.timezone_name = slot["timezone_name"]
        booking.last_rescheduled_at = timezone.now()
        try:
            booking.save(update_fields=["appointment_date", "appointment_time", "duration_minutes", "timezone_name", "last_rescheduled_at", "updated_at"])
        except IntegrityError as exc:
            raise ValidationError("That appointment slot has just been booked. Please choose another slot.") from exc
        BookingStatusHistory.objects.create(
            booking=booking,
            from_status=booking.status,
            to_status=Booking.Status.RESCHEDULED,
            actor=actor,
            reason=f"Moved from {previous_schedule}",
        )

    recipient = booking.lawyer.user if actor == booking.client else booking.client
    create_notification(
        recipient,
        "Booking rescheduled",
        f"Consultation #{booking.id} has been moved to {booking.appointment_date} at {booking.appointment_time.strftime('%H:%M')}.",
        reverse("dashboard" if recipient == booking.client else "lawyer_dashboard"),
    )
    return booking


def eligible_booking_for_chat(client, lawyer):
    return (
        Booking.objects.filter(
            client=client,
            lawyer=lawyer,
            status__in=BOOKING_CHAT_STATUSES,
            payment__payment_status=Payment.PaymentStatus.SUCCESS,
        )
        .select_related("payment")
        .order_by("-appointment_date", "-appointment_time", "-created_at")
        .first()
    )


def eligible_review_bookings(client, lawyer):
    return (
        Booking.objects.filter(
            client=client,
            lawyer=lawyer,
            status=Booking.Status.COMPLETED,
        )
        .exclude(review__isnull=False)
        .order_by("-appointment_date", "-appointment_time", "-created_at")
    )
