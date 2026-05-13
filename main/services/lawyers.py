from django.core.paginator import Paginator
from django.db.models import Q

from ..models import Lawyer, UserProfile


def visible_lawyers_queryset():
    return Lawyer.objects.visible_to_clients().select_related("category", "user", "user__profile").prefetch_related(
        "availability_slots"
    )


def available_lawyers_queryset():
    return visible_lawyers_queryset().filter(is_online=True)


def filter_lawyers_queryset(queryset, cleaned_data):
    availability = cleaned_data.get("availability", "")
    if availability == "online":
        queryset = queryset.filter(is_online=True)

    query = cleaned_data.get("q")
    specialization = cleaned_data.get("specialization")
    location = cleaned_data.get("location")
    min_experience = cleaned_data.get("min_experience")
    max_experience = cleaned_data.get("max_experience")
    min_rating = cleaned_data.get("min_rating")
    sort = cleaned_data.get("sort")

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(specialization__icontains=query)
            | Q(category__name__icontains=query)
        )
    if specialization:
        queryset = queryset.filter(Q(specialization__icontains=specialization) | Q(category__name__icontains=specialization))
    if location:
        queryset = queryset.filter(Q(city__icontains=location) | Q(location__icontains=location))
    if min_experience is not None:
        queryset = queryset.filter(experience__gte=min_experience)
    if max_experience is not None:
        queryset = queryset.filter(experience__lte=max_experience)
    if min_rating is not None:
        queryset = queryset.filter(rating_avg__gte=min_rating)

    if sort == "rating_desc":
        queryset = queryset.order_by("-rating_avg", "-review_count", "-experience", "name")
    elif sort == "experience_desc":
        queryset = queryset.order_by("-experience", "-rating_avg", "name")

    return queryset


def paginate_queryset(queryset, page_number, per_page=12):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page_number)


def lawyer_is_chat_visible(lawyer):
    return bool(
        lawyer.is_verified
        and lawyer.is_online
        and lawyer.user_id
        and getattr(getattr(lawyer.user, "profile", None), "role", None) == UserProfile.Role.LAWYER
    )
