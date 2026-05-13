from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .services.auth import get_dashboard_route, is_admin_user, is_client_user, is_lawyer_user


def role_required(role_check, error_message):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if role_check(request.user):
                return view_func(request, *args, **kwargs)

            messages.error(request, error_message)
            return redirect(get_dashboard_route(request.user))

        return wrapped_view

    return decorator


client_required = role_required(is_client_user, "Only clients can access that page.")
lawyer_required = role_required(is_lawyer_user, "Only lawyers can access that page.")
admin_required = role_required(is_admin_user, "Only platform admins can access that page.")
