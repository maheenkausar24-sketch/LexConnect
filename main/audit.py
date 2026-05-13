import logging

from django.db import DatabaseError, OperationalError, ProgrammingError


audit_logger = logging.getLogger("main.audit")
security_logger = logging.getLogger("main.security")
operations_logger = logging.getLogger("main.operations")


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
    record_operational_event("audit", event, actor=actor or getattr(request, "user", None), request=request, metadata=details)


def security_event(event, *, request=None, actor=None, **details):
    actor_id = getattr(actor or getattr(request, "user", None), "id", None)
    payload = {"event": event, "actor_id": actor_id, **request_metadata(request), **details}
    security_logger.warning(payload)
    record_operational_event("security", event, level="warning", actor=actor or getattr(request, "user", None), request=request, metadata=details)


def record_operational_event(source, event, *, level="info", actor=None, request=None, summary="", metadata=None):
    try:
        from .models import OperationalEvent

        request_data = request_metadata(request)
        if actor is not None and not getattr(actor, "is_authenticated", True):
            actor = None
        OperationalEvent.objects.create(
            source=source,
            level=level,
            event=event,
            actor=actor,
            path=request_data.get("path", ""),
            method=request_data.get("method", ""),
            ip_address=request_data.get("ip", ""),
            user_agent=request_data.get("user_agent", ""),
            summary=summary[:255],
            metadata=metadata or {},
        )
    except (DatabaseError, OperationalError, ProgrammingError):
        operations_logger.debug({"event": "operational_event_record_skipped", "source": source, "operation": event})
    except Exception:
        operations_logger.exception({"event": "operational_event_record_failed", "source": source, "operation": event})
