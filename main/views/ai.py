import json

from django.http import JsonResponse
from django.shortcuts import render

from ..audit import audit_event, security_event
from ..rate_limit import rate_limit
from ..services.lexora import ask_lexora as ask_lexora_service
from ..services.lexora import clean_issue_text


def chatbot(request):
    return render(request, "chatbot.html")


def request_question(request):
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return ""
        return payload.get("question") or payload.get("message") or payload.get("issue") or ""
    return request.POST.get("question", "")


@rate_limit("lexora_ai", limit=15, period=300, json_response=True)
def ask_lexora(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    question = clean_issue_text(request_question(request))
    if len(question) < 3:
        return JsonResponse({"error": "Please enter a little more detail so Lexora can guide you."}, status=400)

    audit_event("lexora_request", request=request, question_length=len(question))
    result = ask_lexora_service(question)

    if result.get("provider_error"):
        security_event("lexora_provider_error", request=request, error=result["provider_error"])
        result["provider_error"] = "Lexora AI is using safe local guidance because Gemini is temporarily unavailable."

    return JsonResponse(result)
