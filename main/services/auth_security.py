from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes

from ..audit import audit_event, security_event
from ..services.emails import send_verification_template_email
from ..tokens import email_verification_token
from ..utils import ensure_profile_role


User = get_user_model()


def build_absolute_url(request, route_name, *args):
    path = reverse(route_name, args=args)
    return request.build_absolute_uri(path)


def send_verification_email(request, user):
    if not user.email:
        return False
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    verify_url = build_absolute_url(request, "verify_email", uid, token)
    try:
        sent = send_verification_template_email(request, user, verify_url)
    except Exception as exc:
        security_event("email_verification_send_failed", request=request, actor=user, error=exc.__class__.__name__)
        return False
    if not sent:
        security_event("email_verification_send_failed", request=request, actor=user, error="EmailDispatchFailed")
        return False
    audit_event("email_verification_sent", request=request, actor=user)
    return True


def verify_email_token(uidb64, token, *, request=None):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.select_related("profile").get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        security_event("email_verification_invalid_uid", request=request)
        return None

    if not email_verification_token.check_token(user, token):
        security_event("email_verification_invalid_token", request=request, actor=user)
        return None

    profile = ensure_profile_role(user)
    if not profile.email_verified:
        profile.email_verified = True
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["email_verified", "email_verified_at"])
        audit_event("email_verified", request=request, actor=user)
    return user
