import os

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.html import strip_tags
from dotenv import load_dotenv
from google import genai

from ..audit import audit_event, security_event
from ..rate_limit import rate_limit
from ..services.lawyers import available_lawyers_queryset


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def chatbot(request):
    return render(request, "chatbot.html")


def fallback_legal_response(question):
    q = (question or "").lower()

    if any(word in q for word in ["crime", "fraud", "theft", "assault", "police"]):
        return "Criminal matters usually need an FIR, evidence collection, and a criminal lawyer."
    if any(word in q for word in ["divorce", "marriage", "custody", "alimony"]):
        return "Family disputes usually involve mediation, documentation, and a family lawyer."
    if any(word in q for word in ["property", "land", "ownership", "house"]):
        return "Property issues typically require document verification and a property lawyer."
    if any(word in q for word in ["hack", "cyber", "scam", "account"]):
        return "Cyber incidents need fast reporting, evidence capture, and a cyber lawyer."
    return "Gather your documents, note the timeline of events, and consult the right lawyer category."


def safe_question_text(value):
    return strip_tags(value or "").strip()[:1200]


def with_disclaimer(answer):
    disclaimer = "This is general legal information, not legal advice. For decisions, consult a qualified lawyer."
    return f"{answer}\n\n{disclaimer}"


@rate_limit("lexora_ai", limit=10, period=300, json_response=True)
def ask_lexora(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    question = safe_question_text(request.POST.get("question", ""))
    if len(question) < 8:
        return JsonResponse({"error": "Please enter a more specific legal question."}, status=400)

    answer = fallback_legal_response(question)
    provider_error = ""
    audit_event("lexora_request", request=request, question_length=len(question))

    if client and question:
        try:
            prompt = f"""
You are Lexora AI, a legal assistant for an Indian legal consultation platform.
Give practical, non-definitive legal information in short steps.
Do not claim to be a lawyer. Do not provide a guaranteed legal outcome.
Recommend the most relevant lawyer category.

User question:
{question}
"""
            response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            answer = response.text or answer
        except Exception as exc:
            provider_error = "Lexora AI provider is temporarily unavailable. Showing safe fallback guidance."
            security_event("lexora_provider_error", request=request, error=exc.__class__.__name__)

    category = None
    q = question.lower()
    mapping = {
        "Property Law": ["land", "property"],
        "Family Law": ["divorce", "family", "marriage", "custody"],
        "Cyber Law": ["cyber", "hack", "online fraud"],
        "Criminal Law": ["crime", "police", "fraud", "theft"],
        "Consumer Law": ["consumer", "product", "refund"],
        "Corporate Law": ["contract", "agreement", "company", "startup"],
        "Labor Law": ["salary", "worker", "labor", "wages"],
        "Employee Law": ["termination", "harassment", "employee"],
    }

    for category_name, keywords in mapping.items():
        if any(keyword in q for keyword in keywords):
            category = category_name
            break

    recommended_lawyers = []
    if category:
        recommended = available_lawyers_queryset().filter(category__name=category).order_by("-rating_avg")[:3]
        recommended_lawyers = [
            {
                "id": lawyer.id,
                "name": lawyer.name,
                "experience": lawyer.experience,
                "location": lawyer.location,
                "email": lawyer.email,
                "phone": lawyer.phone,
            }
            for lawyer in recommended
        ]

    return JsonResponse({"answer": with_disclaimer(answer), "lawyers": recommended_lawyers, "provider_error": provider_error})
