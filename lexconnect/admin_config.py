from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import Group, User

from main.models import Booking, Lawyer, Payment, UserProfile

admin.site.site_header = "LexConnect Administration"
admin.site.site_title = "LexConnect Admin"
admin.site.index_title = "Platform control center"
# Hide "View site" link to the public website on the admin port.
admin.site.site_url = None

_original_each_context = admin.site.each_context


def _admin_dashboard_stats():
    return {
        "users": User.objects.count(),
        "profiles": UserProfile.objects.count(),
        "lawyers": Lawyer.objects.count(),
        "bookings": Booking.objects.count(),
        "payments": Payment.objects.count(),
    }


def _lexconnect_admin_context(request):
    context = _original_each_context(request)
    context["lexconnect_admin_stats"] = _admin_dashboard_stats()
    context["lexconnect_admin_username"] = getattr(settings, "LEXCONNECT_ADMIN_USERNAME", "")
    return context


admin.site.each_context = _lexconnect_admin_context

# Ensure auth models are manageable in admin (users & permissions).
if not admin.site.is_registered(User):
    from django.contrib.auth.admin import GroupAdmin, UserAdmin

    admin.site.register(User, UserAdmin)
if not admin.site.is_registered(Group):
    from django.contrib.auth.admin import GroupAdmin

    admin.site.register(Group, GroupAdmin)
