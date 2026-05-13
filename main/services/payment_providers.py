import hashlib
import hmac
import json
from dataclasses import dataclass
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class ProviderWebhookEvent:
    event_id: str
    event_type: str
    payment_reference: str = ""
    provider_payment_id: str = ""
    provider_order_id: str = ""
    provider_refund_id: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True)
class RefundResult:
    refund_id: str


def canonical_payload(payload):
    return json.dumps(payload or {}, separators=(",", ":"), sort_keys=True).encode("utf-8")


def payload_hash(payload):
    return hashlib.sha256(canonical_payload(payload)).hexdigest()


def sign_demo_payload(payload):
    secret = getattr(settings, "DEMO_PAYMENT_WEBHOOK_SECRET", settings.SECRET_KEY)
    return hmac.new(secret.encode("utf-8"), canonical_payload(payload), hashlib.sha256).hexdigest()


class DemoPaymentProvider:
    name = "Secure Demo"
    supported_events = {"payment.success", "payment.failed", "payment.refunded", "refund.processed", "refund.failed"}

    def verify_event(self, *, payload=None, signature=""):
        if payload is None:
            return True
        if not signature:
            return False
        return hmac.compare_digest(signature, sign_demo_payload(payload))

    def normalize_event(self, payload):
        event_id = str(payload.get("event_id", "")).strip()
        event_type = str(payload.get("event_type", "")).strip()
        if not event_id or not event_type:
            raise ValidationError("Provider event payload is missing an event id or event type.")
        if event_type not in self.supported_events:
            raise ValidationError("Unsupported provider event type.")
        return ProviderWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payment_reference=str(payload.get("payment_reference", "")).strip(),
            provider_payment_id=str(payload.get("provider_payment_id", "")).strip(),
            provider_order_id=str(payload.get("provider_order_id", "")).strip(),
            provider_refund_id=str(payload.get("provider_refund_id", "")).strip(),
            idempotency_key=str(payload.get("idempotency_key", "")).strip(),
        )

    def refund_payment(self, refund_request, *, idempotency_key=""):
        refund_id = refund_request.provider_refund_id or f"DEMO-REFUND-{uuid4().hex[:12].upper()}"
        return RefundResult(refund_id=refund_id)


PROVIDERS = {
    "Demo Manual": DemoPaymentProvider(),
    "Secure Demo": DemoPaymentProvider(),
}


def get_payment_provider(provider_name):
    try:
        return PROVIDERS[provider_name]
    except KeyError as exc:
        raise ValidationError("Unsupported payment provider.") from exc


def verify_provider_event(provider_name, *, payload=None, signature=""):
    return get_payment_provider(provider_name).verify_event(payload=payload, signature=signature)
