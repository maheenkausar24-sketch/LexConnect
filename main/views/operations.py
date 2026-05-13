from django.http import JsonResponse
from django.shortcuts import render

from ..decorators import admin_required
from ..models import OperationalEvent
from ..services.operations import health_report


def health_live(request):
    return JsonResponse({"status": "ok"})


def health_ready(request):
    report = health_report()
    status_code = 200 if report["status"] == "ok" else 503
    return JsonResponse(report, status=status_code)


@admin_required
def admin_health(request):
    return render(request, "admin_health.html", {"report": health_report()})


@admin_required
def admin_task_events(request):
    events = OperationalEvent.objects.filter(source=OperationalEvent.Source.TASK).select_related("actor")[:50]
    return render(request, "admin_task_events.html", {"events": events})
