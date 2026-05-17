import re

from django.conf import settings
from django.urls import reverse
from django.utils.html import strip_tags

from .lawyers import available_lawyers_queryset, visible_lawyers_queryset

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - exercised when optional package is absent
    genai = None
    genai_types = None


DISCLAIMER = "This is general legal information, not legal advice. For decisions, consult a qualified lawyer."
DEFAULT_MODEL = "gemini-2.0-flash"


LEGAL_CATEGORY_RULES = {
    "Property Law": {
        "keywords": [
            "property",
            "land",
            "tenant",
            "rent",
            "lease",
            "house",
            "flat",
            "ownership",
            "registry",
            "partition",
            "builder",
        ],
        "next_step": "Collect ownership papers, rent agreement, notices, and a clear timeline before booking a property lawyer.",
    },
    "Family Law": {
        "keywords": [
            "divorce",
            "marriage",
            "custody",
            "alimony",
            "maintenance",
            "domestic",
            "family",
            "child",
            "separation",
        ],
        "next_step": "Prepare marriage, identity, financial, and child-related documents before speaking with a family lawyer.",
    },
    "Cyber Law": {
        "keywords": [
            "cyber",
            "hack",
            "hacked",
            "online fraud",
            "upi",
            "otp",
            "phishing",
            "account",
            "social media",
            "scam",
            "data",
        ],
        "next_step": "Preserve screenshots, transaction IDs, emails, URLs, and report urgent incidents to the cybercrime portal or police.",
    },
    "Criminal Law": {
        "keywords": [
            "crime",
            "police",
            "fir",
            "arrest",
            "bail",
            "theft",
            "assault",
            "fraud",
            "threat",
            "harassment",
        ],
        "next_step": "Keep evidence safe, write a timeline, and consult a criminal lawyer quickly if police action is involved.",
    },
    "Consumer Law": {
        "keywords": [
            "consumer",
            "refund",
            "defective",
            "warranty",
            "service",
            "delivery",
            "product",
            "seller",
            "complaint",
        ],
        "next_step": "Save invoices, warranty cards, chats, complaint IDs, and escalation emails before consulting a consumer lawyer.",
    },
    "Corporate Law": {
        "keywords": [
            "contract",
            "agreement",
            "company",
            "startup",
            "business",
            "partnership",
            "vendor",
            "shareholder",
            "nda",
        ],
        "next_step": "Gather signed agreements, emails, invoices, and company records for review by a corporate lawyer.",
    },
    "Labor Law": {
        "keywords": [
            "salary",
            "wages",
            "worker",
            "labour",
            "labor",
            "bonus",
            "factory",
            "overtime",
        ],
        "next_step": "Collect appointment letters, payslips, attendance records, and written demands before consulting a labour lawyer.",
    },
    "Employee Law": {
        "keywords": [
            "termination",
            "employee",
            "employer",
            "workplace",
            "hr",
            "resignation",
            "notice period",
            "pf",
            "gratuity",
            "work harassment",
        ],
        "next_step": "Save offer letters, HR emails, payslips, policy documents, and exit communication before booking an employment lawyer.",
    },
}


PLATFORM_INTENTS = {
    "booking": {
        "keywords": ["book", "consultation", "appointment", "schedule", "slot"],
        "answer": "To book a consultation, open a lawyer profile, choose Consult, describe your issue, select an available slot, and complete the demo payment step.",
    },
    "payment": {
        "keywords": ["payment", "pay", "refund", "transaction"],
        "answer": "For payments, finish the booking request first, then use the payment page to mark the demo payment status. Refund or status updates appear in your booking and notification areas.",
    },
    "chat": {
        "keywords": ["chat", "message", "lawyer chat"],
        "answer": "Chat unlocks after a booking is confirmed. Open Chats from your dashboard to continue the booking-linked conversation with your lawyer.",
    },
    "dashboard": {
        "keywords": ["dashboard", "notification", "profile", "login"],
        "answer": "Use the dashboard links to track bookings, chats, notifications, payments, and profile activity based on whether you are a client, lawyer, or admin.",
    },
    "documents": {
        "keywords": ["document", "documents", "prepare", "papers", "evidence"],
        "answer": "Before meeting a lawyer, prepare identity proof, notices or messages, payment records, agreements, screenshots, and a short date-wise timeline of what happened.",
    },
    "urgency": {
        "keywords": ["urgent", "urgency", "first", "immediate", "emergency"],
        "answer": "If there is danger, police action, court deadline, eviction, arrest, or money loss, treat it as urgent. Preserve evidence, avoid deleting messages, and book the most relevant lawyer quickly.",
    },
}


URGENT_KEYWORDS = [
    "arrest",
    "bail",
    "violence",
    "threat",
    "suicide",
    "stalking",
    "blackmail",
    "eviction today",
    "police",
    "fir",
    "hacked",
    "money debited",
]


def clean_issue_text(value, max_length=2400):
    return strip_tags(value or "").strip()[:max_length]


def classify_legal_issue(issue_text):
    text = clean_issue_text(issue_text).lower()
    scores = []

    for category, config in LEGAL_CATEGORY_RULES.items():
        matched = [keyword for keyword in config["keywords"] if keyword in text]
        if matched:
            scores.append((len(matched), len(" ".join(matched)), category, matched))

    if not scores:
        return {
            "name": "General Legal Guidance",
            "confidence": "low",
            "matched_keywords": [],
            "next_step": "Write a short timeline, collect relevant documents, and describe the issue so Lexora can match a lawyer category.",
            "urgency": urgency_hint(issue_text),
        }

    scores.sort(reverse=True)
    match_count, _, category, matched = scores[0]
    confidence = "high" if match_count >= 3 else "medium"
    return {
        "name": category,
        "confidence": confidence,
        "matched_keywords": matched,
        "next_step": LEGAL_CATEGORY_RULES[category]["next_step"],
        "urgency": urgency_hint(issue_text),
    }


def urgency_hint(issue_text):
    text = clean_issue_text(issue_text).lower()
    if any(keyword in text for keyword in URGENT_KEYWORDS):
        return "Potentially urgent. Preserve evidence and seek prompt help from a qualified lawyer or local authority if safety, police action, or money loss is involved."
    return "Normal priority based on the details shared. Act soon if deadlines, notices, hearings, or safety risks are involved."


def summarize_case(issue_text):
    issue = clean_issue_text(issue_text)
    category = classify_legal_issue(issue)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", issue) if part.strip()]
    if not sentences:
        summary = "No detailed issue was provided yet."
    elif len(issue) <= 280:
        summary = issue
    else:
        summary = " ".join(sentences[:2])[:360].rstrip()
        if len(summary) < len(issue):
            summary = f"{summary}..."

    return {
        "summary": summary,
        "probable_category": category["name"],
        "suggested_next_step": category["next_step"],
        "urgency": category["urgency"],
    }


def recommend_lawyers(issue_text="", category_name=None, limit=3):
    category = category_name or classify_legal_issue(issue_text)["name"]
    if category == "General Legal Guidance":
        queryset = visible_lawyers_queryset()
    else:
        queryset = visible_lawyers_queryset().filter(category__name=category)

    lawyers = list(queryset.order_by("-is_online", "-rating_avg", "-review_count", "-experience", "name")[:limit])

    if len(lawyers) < limit:
        fallback = visible_lawyers_queryset()
        if category != "General Legal Guidance":
            fallback = fallback.filter(category__name=category)
        fallback = fallback.exclude(id__in=[lawyer.id for lawyer in lawyers])
        lawyers.extend(
            list(fallback.order_by("-is_online", "-rating_avg", "-review_count", "-experience", "name")[: limit - len(lawyers)])
        )

    return [
        {
            "id": lawyer.id,
            "name": lawyer.name,
            "category": lawyer.category.name,
            "specialization": lawyer.specialization or lawyer.category.name,
            "experience": lawyer.experience,
            "location": lawyer.city or lawyer.location,
            "rating": str(lawyer.rating_avg),
            "fee": str(lawyer.fee),
            "status": lawyer.status_label,
            "profile_url": reverse("lawyer_profile", args=[lawyer.id]),
            "consult_url": reverse("consult_lawyer", args=[lawyer.id]),
        }
        for lawyer in lawyers
    ]


def local_guidance(issue_text):
    issue = clean_issue_text(issue_text)
    category = classify_legal_issue(issue)
    case_summary = summarize_case(issue)
    lawyers = recommend_lawyers(issue, category["name"])
    platform_answer = platform_guidance(issue)

    if platform_answer:
        answer = platform_answer
    elif "summar" in issue.lower() or len(issue) > 420:
        answer = (
            f"Summary: {case_summary['summary']}\n\n"
            f"Probable category: {case_summary['probable_category']}.\n"
            f"Next step: {case_summary['suggested_next_step']}\n"
            f"Urgency: {case_summary['urgency']}"
        )
    else:
        answer = (
            f"This looks most aligned with {category['name']} ({category['confidence']} confidence). "
            f"{category['next_step']} "
            "You can compare recommended lawyers and book a consultation when you are ready."
        )

    if lawyers:
        names = ", ".join(lawyer["name"] for lawyer in lawyers[:2])
        answer = f"{answer}\n\nMatching lawyers available: {names}."

    return {
        "answer": answer,
        "category": category,
        "summary": case_summary,
        "lawyers": lawyers,
        "provider_status": "local",
        "provider_error": "",
    }


def platform_guidance(issue_text):
    text = clean_issue_text(issue_text).lower()
    for intent in PLATFORM_INTENTS.values():
        if any(keyword in text for keyword in intent["keywords"]):
            return intent["answer"]
    return ""


def gemini_client():
    api_key = getattr(settings, "GEMINI_API_KEY", "").strip()
    if not api_key or genai is None or genai_types is None:
        return None
    timeout_ms = getattr(settings, "LEXORA_GEMINI_TIMEOUT_MS", 5000)
    return genai.Client(api_key=api_key, http_options=genai_types.HttpOptions(timeout=timeout_ms))


def gemini_enhancement(issue_text, local_result):
    client = gemini_client()
    if client is None:
        return ""

    model = getattr(settings, "LEXORA_GEMINI_MODEL", DEFAULT_MODEL)
    prompt = f"""
You are Lexora AI inside LexConnect, an Indian legal consultation platform.
Use the local classification as truth unless the user clearly says otherwise.
Give concise, practical, demo-friendly legal information.
Do not claim to be a lawyer. Do not guarantee outcomes. Do not ask for sensitive secrets.
Return:
- short answer
- likely category
- next step
- urgency hint if relevant
- booking guidance through LexConnect

Local classification: {local_result['category']['name']} ({local_result['category']['confidence']})
Local next step: {local_result['category']['next_step']}
User issue: {issue_text}
"""
    config = genai_types.GenerateContentConfig(
        maxOutputTokens=420,
        temperature=0.35,
        httpOptions=genai_types.HttpOptions(timeout=getattr(settings, "LEXORA_GEMINI_TIMEOUT_MS", 5000)),
    )
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    return clean_issue_text(getattr(response, "text", ""), max_length=1800)


def ask_lexora(issue_text):
    issue = clean_issue_text(issue_text)
    result = local_guidance(issue)

    try:
        ai_text = gemini_enhancement(issue, result)
        if ai_text:
            result["answer"] = ai_text
            result["provider_status"] = "gemini"
    except Exception as exc:
        result["provider_status"] = "fallback"
        result["provider_error"] = exc.__class__.__name__

    result["answer"] = with_disclaimer(result["answer"])
    return result


def with_disclaimer(answer):
    if DISCLAIMER in answer:
        return answer
    return f"{answer}\n\n{DISCLAIMER}"
