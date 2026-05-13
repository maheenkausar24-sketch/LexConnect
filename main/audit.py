import logging


audit_logger = logging.getLogger("main.audit")
security_logger = logging.getLogger("main.security")


def request_metadata(request):
    if request is None:
        return {}
    return {
        "path": getattr(request, "path", ""),
        "method": getattr(request, "method", ""),
        "ip": request.META.get("REMOTE_ADDR", ""),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:180],
    }


def audit_event(event, *, request=None, actor=None, **details):
    actor_id = getattr(actor or getattr(request, "user", None), "id", None)
    payload = {"event": event, "actor_id": actor_id, **request_metadata(request), **details}
    audit_logger.info(payload)


def security_event(event, *, request=None, actor=None, **details):
    actor_id = getattr(actor or getattr(request, "user", None), "id", None)
    payload = {"event": event, "actor_id": actor_id, **request_metadata(request), **details}
    security_logger.warning(payload)
