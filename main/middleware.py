import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .utils import ensure_profile, mark_stale_users_offline


request_logger = logging.getLogger("main.requests")

CSP_KEYWORD_SOURCES = {
    "self",
    "none",
    "unsafe-inline",
    "unsafe-eval",
    "strict-dynamic",
    "report-sample",
}


def format_csp_source(value):
    """Ensure CSP keywords like self/none are quoted for browser enforcement."""
    token = (value or "").strip()
    if not token:
        return token
    if (token.startswith("'") and token.endswith("'")) or (token.startswith('"') and token.endswith('"')):
        return token if token.startswith("'") else f"'{token[1:-1]}'"
    if token.endswith(":"):
        return token
    if token in CSP_KEYWORD_SOURCES:
        return f"'{token}'"
    return token


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        if not request.path.startswith(settings.STATIC_URL):
            request_logger.info(
                {
                    "event": "request_finished",
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "duration_ms": elapsed_ms,
                    "user_id": request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None,
                }
            )
        return response


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def content_security_policy(self):
        directives = []
        for directive, values in getattr(settings, "LEXCONNECT_CONTENT_SECURITY_POLICY", {}).items():
            if not values:
                continue
            formatted_values = [format_csp_source(value) for value in values]
            directives.append(f"{directive} {' '.join(formatted_values)}")
        return "; ".join(directives)

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        csp = self.content_security_policy()
        if csp:
            header_name = "Content-Security-Policy-Report-Only" if getattr(settings, "LEXCONNECT_CSP_REPORT_ONLY", False) else "Content-Security-Policy"
            response.setdefault(header_name, csp)
        return response


class PresenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if cache.add("presence:stale-user-scan", "1", getattr(settings, "PRESENCE_STALE_SCAN_INTERVAL", 60)):
            mark_stale_users_offline()
        response = self.get_response(request)

        if request.user.is_authenticated:
            profile = ensure_profile(request.user)
            if not profile.is_online:
                profile.is_online = True
            profile.last_seen = timezone.now()
            profile.save(update_fields=["is_online", "last_seen"])

        return response
