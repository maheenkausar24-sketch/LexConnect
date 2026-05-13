import hashlib
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse

from .audit import security_event


class RateLimitExceeded(Exception):
    pass


def client_ip(request):
    if getattr(settings, "LEXCONNECT_TRUST_PROXY_HEADERS", False):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def client_identifier(request):
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        return f"user:{user.id}"
    ip_hash = hashlib.sha256(client_ip(request).encode("utf-8")).hexdigest()[:24]
    return f"ip:{ip_hash}"


def consume_rate_limit(request, action, *, limit=5, period=60, identifier=None):
    if not getattr(settings, "RATELIMIT_ENABLED", True):
        return True

    user = getattr(request, "user", None)
    if (
        getattr(settings, "RATELIMIT_BYPASS_AUTHENTICATED_ADMINS", True)
        and getattr(user, "is_authenticated", False)
        and (user.is_staff or user.is_superuser)
    ):
        return True

    identity = identifier or client_identifier(request)
    key = f"rl:{action}:{identity}"
    count = cache.get(key, 0)
    if count >= limit:
        security_event("rate_limit_exceeded", request=request, action=action, limit=limit, period=period)
        raise RateLimitExceeded(f"Too many {action} requests. Please wait before trying again.")

    if count == 0:
        cache.set(key, 1, period)
    else:
        cache.incr(key)
    return True


def rate_limit(action, *, limit=5, period=60, methods=("POST",), json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.method in methods:
                try:
                    consume_rate_limit(request, action, limit=limit, period=period)
                except RateLimitExceeded as exc:
                    if json_response or request.headers.get("x-requested-with") == "XMLHttpRequest":
                        return JsonResponse({"error": str(exc)}, status=429)
                    messages.error(request, str(exc))
                    return HttpResponse(str(exc), status=429)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
