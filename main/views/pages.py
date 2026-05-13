from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from ..decorators import client_required, lawyer_required
from ..forms import LawyerAvailabilityForm, LawyerSearchForm, ReviewForm
from ..models import Booking, Chat, LawCategory, Lawyer, Payment
from ..services.auth import get_dashboard_route, is_client_user, lawyer_accounts_queryset
from ..services.bookings import eligible_booking_for_chat, eligible_review_bookings, get_client_bookings_queryset, get_lawyer_bookings_queryset
from ..services.lawyers import available_lawyers_queryset, filter_lawyers_queryset, paginate_queryset, visible_lawyers_queryset


def home(request):
    featured_lawyers = visible_lawyers_queryset()[:6]
    categories = LawCategory.objects.all()[:8]
    return render(request, "home.html", {"featured_lawyers": featured_lawyers, "categories": categories})


@login_required
def dashboard(request):
    return redirect(get_dashboard_route(request.user))


@client_required
def client_dashboard(request):
    categories = LawCategory.objects.all()
    featured_lawyers = available_lawyers_queryset()[:6]
    recent_bookings = get_client_bookings_queryset(request.user)[:8]
    recent_payments = Payment.objects.filter(booking__client=request.user).select_related("booking", "booking__lawyer")[:5]
    recent_chats = Chat.objects.filter(client=request.user, booking__isnull=False).select_related("lawyer", "booking")[:5]

    return render(
        request,
        "dashboard.html",
        {
            "categories": categories,
            "featured_lawyers": featured_lawyers,
            "recent_bookings": recent_bookings,
            "recent_payments": recent_payments,
            "recent_chats": recent_chats,
            "booking_total": Booking.objects.filter(client=request.user).count(),
            "completed_total": Booking.objects.filter(client=request.user, status=Booking.Status.COMPLETED).count(),
        },
    )


@client_required
def client_bookings(request):
    bookings = get_client_bookings_queryset(request.user)
    return render(request, "client_bookings.html", {"bookings": bookings})


@client_required
def client_chats(request):
    chats = Chat.objects.filter(client=request.user, booking__isnull=False).select_related("lawyer", "booking")
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
    incoming_bookings = get_lawyer_bookings_queryset(lawyer)[:12]
    active_chats = lawyer.chats.filter(booking__isnull=False).select_related("client", "booking")[:8]
    earnings = Payment.objects.filter(
        booking__lawyer=lawyer,
        payment_status=Payment.PaymentStatus.SUCCESS,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    return render(
        request,
        "lawyer_dashboard.html",
        {
            "lawyer": lawyer,
            "incoming_bookings": incoming_bookings,
            "active_chats": active_chats,
            "earnings": earnings,
            "availability_slots": lawyer.availability_slots.all(),
            "confirmed_total": Booking.objects.filter(lawyer=lawyer, status=Booking.Status.CONFIRMED).count(),
            "completed_total": Booking.objects.filter(lawyer=lawyer, status=Booking.Status.COMPLETED).count(),
        },
    )


@lawyer_required
def lawyer_bookings(request):
    lawyer = request.user.lawyer_profile
    bookings = get_lawyer_bookings_queryset(lawyer)
    return render(request, "lawyer_bookings.html", {"lawyer": lawyer, "bookings": bookings})


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
    chats = Chat.objects.filter(lawyer=request.user.lawyer_profile, booking__isnull=False).select_related("client", "booking")
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

    if request.user.is_authenticated and is_client_user(request.user):
        eligible_booking = eligible_booking_for_chat(request.user, lawyer)
        if eligible_booking:
            can_start_chat = True
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


def demo_accounts_page(request):
    lawyer_accounts = lawyer_accounts_queryset()
    return render(
        request,
        "demo_accounts.html",
        {
            "lawyer_accounts": lawyer_accounts,
            "client_account": {"username": "demo_client", "password": "client@123"},
            "lawyer_password": "lawyer@123",
        },
    )
