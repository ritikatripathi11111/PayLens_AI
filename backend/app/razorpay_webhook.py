import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Optional


SUPPORTED_EVENTS = {
    "payment.authorized",
    "payment.captured",
    "payment.failed",
}


def get_webhook_secret() -> Optional[str]:
    return os.getenv("RAZORPAY_WEBHOOK_SECRET")


def verify_razorpay_signature(
    raw_body: bytes,
    received_signature: str,
    webhook_secret: str,
) -> bool:

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected_signature,
        received_signature,
    )


def unix_to_datetime(value) -> datetime:

    if value is None:
        return datetime.now(timezone.utc).replace(
            tzinfo=None
        )

    return datetime.fromtimestamp(
        int(value),
        tz=timezone.utc,
    ).replace(tzinfo=None)


def extract_payment_entity(payload: dict) -> dict:

    return (
        payload
        .get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )


def normalize_razorpay_payment(
    payload: dict,
) -> Optional[dict]:

    event_type = payload.get("event")

    if event_type not in SUPPORTED_EVENTS:
        return None

    payment = extract_payment_entity(payload)

    if not payment:
        return None

    payment_id = payment.get("id")

    if not payment_id:
        return None

    status = payment.get("status")

    if event_type == "payment.failed":
        status = "failed"

    elif event_type == "payment.authorized":
        status = "authorized"

    elif event_type == "payment.captured":
        status = "captured"

    error_code = (
        payment.get("error_code")
        or payment.get("error_reason")
    )

    error_description = (
        payment.get("error_description")
        or payment.get("error_reason")
    )

    issuer = (
        payment.get("bank")
        or payment.get("issuer")
    )

    return {
        "payment_id": payment_id,

        "merchant_id": (
            payload.get("account_id")
            or "razorpay_test"
        ),

        # Razorpay amounts are represented in the
        # smallest currency unit (for INR: paise).
        "amount": int(
            payment.get("amount", 0)
        ),

        "currency": (
            payment.get("currency")
            or "INR"
        ),

        "payment_method": (
            payment.get("method")
            or "unknown"
        ),

        "status": status or "unknown",

        "error_code": error_code,

        "error_description": error_description,

        # Razorpay webhooks do not provide the same
        # latency field as PayLens synthetic telemetry.
        "latency_ms": None,

        # This identifies the external payment provider.
        "gateway": "razorpay",

        "issuer": issuer,

        "retry_count": 0,

        "timestamp": unix_to_datetime(
            payment.get("created_at")
            or payload.get("created_at")
        ),

        "event_type": event_type,
    }