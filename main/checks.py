import sys

from django.conf import settings
from django.core.checks import Warning, register


@register()
def production_security_checks(app_configs, **kwargs):
    if "test" in sys.argv:
        return []

    warnings = []
    if not settings.DEBUG:
        if not settings.SECURE_SSL_REDIRECT:
            warnings.append(
                Warning(
                    "SECURE_SSL_REDIRECT is disabled while DEBUG=False.",
                    hint="Set DJANGO_SECURE_SSL_REDIRECT=True behind HTTPS.",
                    id="lexconnect.W001",
                )
            )
        if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
            warnings.append(
                Warning(
                    "Secure session/CSRF cookies are not fully enabled while DEBUG=False.",
                    hint="Set DJANGO_SESSION_COOKIE_SECURE=True and DJANGO_CSRF_COOKIE_SECURE=True.",
                    id="lexconnect.W002",
                )
            )
    return warnings
