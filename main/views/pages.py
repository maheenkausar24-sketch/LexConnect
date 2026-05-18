from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Count, Q, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from ..decorators import client_required, lawyer_required
from ..forms import LawyerAvailabilityForm, LawyerSearchForm, ReviewForm
from ..models import Booking, Chat, LawCategory, Payment
from ..services.bookings import BOOKING_CHAT_STATUSES
from ..services.auth import get_dashboard_route, is_client_user
from ..services.bookings import eligible_booking_for_chat, eligible_review_bookings, get_client_bookings_queryset, get_lawyer_bookings_queryset
from ..services.lawyers import available_lawyers_queryset, filter_lawyers_queryset, paginate_queryset, visible_lawyers_queryset


def paginate_list(queryset, page_number, per_page=20):
    return Paginator(queryset, per_page).get_page(page_number)


def filter_booking_list(queryset, params):
    status = (params.get("status") or "").strip()
    payment_status = (params.get("payment_status") or "").strip()
    if status:
        queryset = queryset.filter(status=status)
    if payment_status:
        queryset = queryset.filter(payment__payment_status=payment_status)
    return queryset


def home(request):
    featured_lawyers = visible_lawyers_queryset()[:6]
    categories = LawCategory.objects.all()[:8]
    platform_stats = {
        "lawyer_count": visible_lawyers_queryset().count(),
        "booking_count": Booking.objects.count(),
        "category_count": LawCategory.objects.count(),
    }
    return render(
        request,
        "home.html",
        {
            "featured_lawyers": featured_lawyers,
            "categories": categories,
            "platform_stats": platform_stats,
        },
    )


@login_required
def dashboard(request):
    return redirect(get_dashboard_route(request.user))


@client_required
def client_dashboard(request):
    categories = LawCategory.objects.all()
    featured_lawyers = available_lawyers_queryset()[:6]
    client_bookings = get_client_bookings_queryset(request.user)
    recent_bookings = client_bookings[:8]
    recent_payments = Payment.objects.filter(booking__client=request.user).select_related("booking", "booking__lawyer")[:5]
    recent_chats = (
        Chat.objects.filter(client=request.user, booking__isnull=False)
        .select_related("lawyer", "lawyer__category", "booking")
        .annotate(unread_count=Count("messages", filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)))
    )[:5]
    booking_summary = client_bookings.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=Booking.Status.PENDING)),
        confirmed=Count("id", filter=Q(status=Booking.Status.CONFIRMED)),
        completed=Count("id", filter=Q(status=Booking.Status.COMPLETED)),
    )
    payment_summary = Payment.objects.filter(booking__client=request.user).aggregate(
        awaiting=Count("id", filter=Q(payment_status=Payment.PaymentStatus.AWAITING_VERIFICATION)),
        action_needed=Count("id", filter=Q(payment_status__in=[Payment.PaymentStatus.PENDING, Payment.PaymentStatus.FAILED])),
        successful=Count("id", filter=Q(payment_status=Payment.PaymentStatus.SUCCESS)),
    )

    return render(
        request,
        "dashboard.html",
        {
            "categories": categories,
            "featured_lawyers": featured_lawyers,
            "recent_bookings": recent_bookings,
            "recent_payments": recent_payments,
            "recent_chats": recent_chats,
            "recent_notifications": request.user.notifications.all()[:5],
            "booking_summary": booking_summary,
            "payment_summary": payment_summary,
        },
    )


@client_required
def client_bookings(request):
    bookings = filter_booking_list(get_client_bookings_queryset(request.user), request.GET)
    bookings_page = paginate_list(bookings, request.GET.get("page"), per_page=20)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(
        request,
        "client_bookings.html",
        {
            "bookings": bookings_page,
            "page_obj": bookings_page,
            "querystring": query_params.urlencode(),
            "booking_status_choices": Booking.Status.choices,
            "payment_status_choices": Payment.PaymentStatus.choices,
        },
    )


@client_required
def client_chats(request):
    chats = (
        Chat.objects.filter(
            client=request.user,
            booking__isnull=False,
            booking__status__in=BOOKING_CHAT_STATUSES,
            booking__payment__payment_status=Payment.PaymentStatus.SUCCESS,
        )
        .select_related("lawyer", "lawyer__category", "booking", "booking__payment")
        .annotate(unread_count=Count("messages", filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)))
        .order_by("-updated_at")
    )
    return render(
        request,
        "user_chats.html",
        {
            "chats": chats,
            "page_title": "Client Chats",
            "page_copy": "Continue every paid consultation from one booking-linked inbox.",
        },
    )


@lawyer_required
def lawyer_dashboard(request):
    lawyer = request.user.lawyer_profile
    lawyer_bookings = get_lawyer_bookings_queryset(lawyer)
    incoming_bookings = lawyer_bookings[:12]
    active_chats = (
        lawyer.chats.filter(
            booking__isnull=False,
            booking__status__in=BOOKING_CHAT_STATUSES,
            booking__payment__payment_status=Payment.PaymentStatus.SUCCESS,
        )
        .select_related("client", "booking", "booking__payment")
        .annotate(unread_count=Count("messages", filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)))
        .order_by("-updated_at")
    )[:8]
    payment_summary = Payment.objects.filter(
        booking__lawyer=lawyer,
    ).aggregate(
        total=Sum("amount", filter=Q(payment_status=Payment.PaymentStatus.SUCCESS)),
        awaiting=Count("id", filter=Q(payment_status=Payment.PaymentStatus.AWAITING_VERIFICATION)),
        successful=Count("id", filter=Q(payment_status=Payment.PaymentStatus.SUCCESS)),
    )
    booking_summary = lawyer_bookings.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=Booking.Status.PENDING)),
        confirmed=Count("id", filter=Q(status=Booking.Status.CONFIRMED)),
        completed=Count("id", filter=Q(status=Booking.Status.COMPLETED)),
    )

    return render(
        request,
        "lawyer_dashboard.html",
        {
            "lawyer": lawyer,
            "incoming_bookings": incoming_bookings,
            "active_chats": active_chats,
            "earnings": payment_summary["total"] or Decimal("0.00"),
            "availability_slots": lawyer.availability_slots.filter(is_active=True).order_by("weekday", "start_time")[:8],
            "booking_summary": booking_summary,
            "payment_summary": payment_summary,
        },
    )


@lawyer_required
def lawyer_bookings(request):
    lawyer = request.user.lawyer_profile
    bookings = filter_booking_list(get_lawyer_bookings_queryset(lawyer), request.GET)
    bookings_page = paginate_list(bookings, request.GET.get("page"), per_page=20)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(
        request,
        "lawyer_bookings.html",
        {
            "lawyer": lawyer,
            "bookings": bookings_page,
            "page_obj": bookings_page,
            "querystring": query_params.urlencode(),
            "booking_status_choices": Booking.Status.choices,
            "payment_status_choices": Payment.PaymentStatus.choices,
        },
    )


@ensure_csrf_cookie
@lawyer_required
def lawyer_availability(request):
    lawyer = request.user.lawyer_profile
    return render(
        request,
        "lawyer_availability.html",
        {
            "lawyer": lawyer,
            "availability_form": LawyerAvailabilityForm(),
            "availability_slots": lawyer.availability_slots.all(),
        },
    )


@lawyer_required
def lawyer_chats(request):
    chats = (
        Chat.objects.filter(
            lawyer=request.user.lawyer_profile,
            booking__isnull=False,
            booking__status__in=BOOKING_CHAT_STATUSES,
            booking__payment__payment_status=Payment.PaymentStatus.SUCCESS,
        )
        .select_related("client", "booking", "booking__payment")
        .annotate(unread_count=Count("messages", filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)))
        .order_by("-updated_at")
    )
    return render(
        request,
        "user_chats.html",
        {
            "chats": chats,
            "page_title": "Lawyer Chats",
            "page_copy": "Respond to confirmed, paid consultation chats and keep each case in context.",
        },
    )


def lawyers_by_category(request, category_id):
    category = get_object_or_404(LawCategory, id=category_id)
    form = LawyerSearchForm(request.GET or None)
    queryset = visible_lawyers_queryset().filter(category=category)
    specialization_options = (
        visible_lawyers_queryset()
        .filter(category=category)
        .exclude(specialization="")
        .values_list("specialization", flat=True)
        .distinct()
        .order_by("specialization")
    )
    if form.is_valid():
        queryset = filter_lawyers_queryset(queryset, form.cleaned_data)

    lawyers_page = paginate_queryset(queryset, request.GET.get("page"), per_page=9)
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        "lawyers.html",
        {
            "category": category,
            "lawyers": lawyers_page,
            "page_obj": lawyers_page,
            "search_form": form,
            "specialization_options": specialization_options,
            "querystring": query_params.urlencode(),
        },
    )


def lawyer_profile(request, lawyer_id):
    lawyer = get_object_or_404(visible_lawyers_queryset(), id=lawyer_id)
    reviews = lawyer.reviews.select_related("client", "booking")[:10]
    completed_bookings_count = Booking.objects.filter(lawyer=lawyer, status=Booking.Status.COMPLETED).count()
    existing_chat = None
    can_start_chat = False
    review_form = None
    review_booking_choices = []

    chat_booking = None
    if request.user.is_authenticated and is_client_user(request.user):
        eligible_booking = eligible_booking_for_chat(request.user, lawyer)
        if eligible_booking:
            can_start_chat = True
            chat_booking = eligible_booking
            existing_chat = getattr(eligible_booking, "chat", None)

        review_booking_choices = list(eligible_review_bookings(request.user, lawyer))
        if review_booking_choices:
            review_form = ReviewForm(initial={"booking_id": review_booking_choices[0].id})

    return render(
        request,
        "lawyer_profile.html",
        {
            "lawyer": lawyer,
            "reviews": reviews,
            "existing_chat": existing_chat,
            "chat_booking": chat_booking,
            "can_start_chat": can_start_chat,
            "review_form": review_form,
            "review_booking_choices": review_booking_choices,
            "completed_bookings_count": completed_bookings_count,
        },
    )


@lawyer_required
def toggle_lawyer_status(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")

    lawyer = request.user.lawyer_profile
    if not lawyer.is_verified:
        messages.error(request, "Your profile must be approved before you can appear online to clients.")
        return redirect("lawyer_dashboard")
    lawyer.is_online = not lawyer.is_online
    lawyer.save(update_fields=["is_online"])
    messages.success(request, f"Status updated to {'online' if lawyer.is_online else 'offline'}.")
    return redirect("lawyer_dashboard")

