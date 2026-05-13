import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..services.payments import process_provider_webhook


@csrf_exempt
@require_POST
def provider_webhook(request, provider):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        signature = request.META.get("HTTP_X_LEXCONNECT_SIGNATURE", "")
        if getattr(settings, "LEXCONNECT_ASYNC_WEBHOOKS", False):
            from ..tasks import process_provider_webhook_task

            task = process_provider_webhook_task.delay(provider, payload, signature)
            return JsonResponse({"accepted": True, "task_id": task.id}, status=202)
        provider_event, processed = process_provider_webhook(
            provider,
            payload,
            signature=signature,
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid webhook payload."}, status=400)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "event_id": provider_event.event_id,
            "status": provider_event.processing_status,
            "processed": processed,
        }
    )
