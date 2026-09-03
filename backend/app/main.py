import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from yaml import events

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException,  Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError

from .models import (
    PaymentEvent,
    PaymentEventDB,
    WebhookEventDB,
    IncidentDB,
)

from .razorpay_webhook import (
    SUPPORTED_EVENTS,
    get_webhook_secret,
    normalize_razorpay_payment,
    verify_razorpay_signature,
)

from .db import Base, SessionLocal, engine
from .incident_detector import analyze_incident
from .root_cause_engine import investigate_root_cause
from .ai_investigator import investigate_with_ai
from .remediation import build_remediation_analysis
from .evaluation import run_evaluation
from .telemetry import get_live_telemetry



# ---------------------------------------------------------
# Database initialization
# ---------------------------------------------------------

Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="PayLens AI",
    description=(
        "AI-powered payment incident "
        "and root-cause investigator"
    ),
    version="0.4.0"
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ---------------------------------------------------------
# Database dependency
# ---------------------------------------------------------

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# ---------------------------------------------------------
# Root
# ---------------------------------------------------------

@app.get("/")
def root():

    return {
        "project": "PayLens AI",
        "status": "running",
        "message": (
            "Payment incident investigation system"
        )
    }


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }




# ---------------------------------------------------------
# Model / system evaluation
# ---------------------------------------------------------

@app.get("/evaluation/run")
def evaluate_paylens():
    """
    Run deterministic end-to-end evaluation scenarios.

    The evaluation uses an isolated in-memory database, so
    it never modifies the production paylens.db database.

    Scenarios:
        - Gateway degradation
        - UPI degradation
        - Issuer degradation
        - Payment-method degradation
        - Healthy system
    """

    return run_evaluation()


# ---------------------------------------------------------
# Live telemetry
# ---------------------------------------------------------

@app.get("/telemetry/live")
def live_telemetry(
    window_minutes: int = 5,
    db: Session = Depends(get_db)
):
    """Return the latest payment-health snapshot for the live dashboard."""

    if window_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail="window_minutes must be greater than zero"
        )

    return get_live_telemetry(
        db=db,
        window_minutes=window_minutes
    )
    
    
    
# ---------------------------------------------------------
# Live incident detection
# ---------------------------------------------------------

@app.get("/incidents/live")
def live_incident_detection(
    window_minutes: int = 5,
    db: Session = Depends(get_db)
):
    """
    Combine live telemetry with the incident detection engine.

    The endpoint distinguishes between:

        HEALTHY
        INCIDENT_ACTIVE
        INSUFFICIENT_DATA

    This prevents insufficient telemetry from being
    incorrectly reported as a healthy payment system.
    """

    if window_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail="window_minutes must be greater than zero"
        )

    # -----------------------------------------------------
    # STEP 1 — Get live telemetry
    # -----------------------------------------------------

    telemetry = get_live_telemetry(
        db=db,
        window_minutes=window_minutes
    )

    # -----------------------------------------------------
    # STEP 2 — Run incident detection
    # -----------------------------------------------------

    incident = analyze_incident(
        db=db,
        window_minutes=window_minutes
    )

    incident_detected = bool(
        incident.get("incident_detected", False)
    )

    analysis_status = incident.get(
        "status",
        "unknown"
    )

    # -----------------------------------------------------
    # STEP 3 — Determine live state
    # -----------------------------------------------------

    if analysis_status == "insufficient_baseline_data":
        live_status = "INSUFFICIENT_DATA"

    elif incident_detected:
        live_status = "INCIDENT_ACTIVE"

    else:
        live_status = "HEALTHY"

    # -----------------------------------------------------
    # STEP 4 — Return unified live response
    # -----------------------------------------------------

    return {
        "status": "live",
        "live_status": live_status,
        "window_minutes": window_minutes,

        "telemetry": telemetry,

        "incident": {
            "detected": incident_detected,
            "severity": incident.get(
                "severity",
                "NONE"
            ),
            "analysis_status": analysis_status,
            "analysis": incident
        }
    }
    
# ---------------------------------------------------------
# Razorpay webhook ingestion
# ---------------------------------------------------------

@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive Razorpay payment webhooks.

    Flow:

        Razorpay Test Mode
                ↓
        Raw webhook body
                ↓
        HMAC-SHA256 verification
                ↓
        Event ID idempotency
                ↓
        Payment normalization
                ↓
        payment_events
    """

    # -----------------------------------------------------
    # STEP 1 — Read raw request body
    # -----------------------------------------------------
    #
    # Razorpay signature verification must use the raw
    # request body, not parsed JSON.
    #

    raw_body = await request.body()

    # -----------------------------------------------------
    # STEP 2 — Get signature
    # -----------------------------------------------------

    signature = request.headers.get(
        "X-Razorpay-Signature"
    )

    if not signature:

        raise HTTPException(
            status_code=400,
            detail="Missing X-Razorpay-Signature"
        )

    # -----------------------------------------------------
    # STEP 3 — Get webhook secret
    # -----------------------------------------------------

    webhook_secret = get_webhook_secret()

    if not webhook_secret:

        raise HTTPException(
            status_code=500,
            detail=(
                "RAZORPAY_WEBHOOK_SECRET is not configured"
            )
        )

    # -----------------------------------------------------
    # STEP 4 — Verify signature
    # -----------------------------------------------------

    if not verify_razorpay_signature(
        raw_body=raw_body,
        received_signature=signature,
        webhook_secret=webhook_secret,
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid Razorpay webhook signature"
        )

    # -----------------------------------------------------
    # STEP 5 — Parse JSON AFTER verification
    # -----------------------------------------------------

    try:

        payload = await request.json()

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload"
        )

    event_type = payload.get("event")

    # -----------------------------------------------------
    # STEP 6 — Get Razorpay event ID
    # -----------------------------------------------------

    razorpay_event_id = request.headers.get(
        "x-razorpay-event-id"
    )

    if not razorpay_event_id:

        raise HTTPException(
            status_code=400,
            detail="Missing x-razorpay-event-id"
        )

    # -----------------------------------------------------
    # STEP 7 — Idempotency check
    # -----------------------------------------------------

    existing_event = (
        db.query(WebhookEventDB)
        .filter(
            WebhookEventDB.event_id
            == razorpay_event_id
        )
        .first()
    )

    if existing_event:

        return {
            "status": "duplicate",
            "event_id": razorpay_event_id,
            "event": event_type,
            "message": (
                "Webhook already processed"
            ),
        }

    # -----------------------------------------------------
    # STEP 8 — Ignore unsupported events safely
    # -----------------------------------------------------

    if event_type not in SUPPORTED_EVENTS:

        webhook_record = WebhookEventDB(
            event_id=razorpay_event_id,
            provider="razorpay",
            event_type=event_type or "unknown",
            payment_id=None,
            processed=True,
        )

        db.add(webhook_record)

        try:

            db.commit()

        except IntegrityError:

            db.rollback()

        return {
            "status": "ignored",
            "event_id": razorpay_event_id,
            "event": event_type,
            "message": (
                "Webhook received but not used "
                "by PayLens"
            ),
        }

    # -----------------------------------------------------
    # STEP 9 — Normalize Razorpay event
    # -----------------------------------------------------

    normalized = normalize_razorpay_payment(
        payload
    )

    if not normalized:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to normalize Razorpay "
                "payment event"
            )
        )

    payment_id = normalized["payment_id"]

    # -----------------------------------------------------
    # STEP 10 — Store idempotency record
    # -----------------------------------------------------

    webhook_record = WebhookEventDB(
        event_id=razorpay_event_id,
        provider="razorpay",
        event_type=event_type,
        payment_id=payment_id,
        processed=True,
    )

    db.add(webhook_record)

    # -----------------------------------------------------
    # STEP 11 — Store normalized payment event
    # -----------------------------------------------------

    db_event = PaymentEventDB(
        payment_id=normalized["payment_id"],
        merchant_id=normalized["merchant_id"],
        amount=normalized["amount"],
        currency=normalized["currency"],
        payment_method=normalized["payment_method"],
        status=normalized["status"],
        error_code=normalized["error_code"],
        error_description=normalized[
            "error_description"
        ],
        latency_ms=normalized["latency_ms"],
        gateway=normalized["gateway"],
        issuer=normalized["issuer"],
        retry_count=normalized["retry_count"],
        timestamp=normalized["timestamp"],
    )

    db.add(db_event)

    # -----------------------------------------------------
    # STEP 12 — Commit atomically
    # -----------------------------------------------------

    try:

        db.commit()

    except IntegrityError:

        db.rollback()

        return {
            "status": "duplicate",
            "event_id": razorpay_event_id,
            "message": (
                "Webhook was already processed"
            ),
        }

    db.refresh(db_event)

    # -----------------------------------------------------
    # STEP 13 — Return immediately
    # -----------------------------------------------------

    return {
        "status": "accepted",
        "provider": "razorpay",
        "event_id": razorpay_event_id,
        "event": event_type,
        "payment_id": db_event.payment_id,
        "database_id": db_event.id,
        "message": (
            "Razorpay payment event ingested "
            "into PayLens"
        ),
    }


# ---------------------------------------------------------
# Event ingestion
# ---------------------------------------------------------

@app.post("/events")
def ingest_payment_event(
    event: PaymentEvent,
    db: Session = Depends(get_db)
):

    db_event = PaymentEventDB(
        payment_id=event.payment_id,
        merchant_id=event.merchant_id,
        amount=event.amount,
        currency=event.currency,
        payment_method=event.payment_method,
        status=event.status,
        error_code=event.error_code,
        error_description=event.error_description,
        latency_ms=event.latency_ms,
        gateway=event.gateway,
        issuer=event.issuer,
        retry_count=event.retry_count,
        timestamp=event.timestamp
    )

    db.add(db_event)

    db.commit()

    db.refresh(db_event)

    return {
        "status": "accepted",
        "payment_id": db_event.payment_id,
        "database_id": db_event.id,
        "message": (
            "Payment event stored successfully"
        )
    }


# ---------------------------------------------------------
# Get payment event
# ---------------------------------------------------------

@app.get("/events/{payment_id}")
def get_payment_event(
    payment_id: str,
    db: Session = Depends(get_db)
):

    event = (
        db.query(PaymentEventDB)
        .filter(
            PaymentEventDB.payment_id
            == payment_id
        )
        .first()
    )

    if event is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Payment event "
                f"'{payment_id}' not found"
            )
        )

    return {
        "payment_id": event.payment_id,
        "merchant_id": event.merchant_id,
        "amount": event.amount,
        "currency": event.currency,
        "payment_method": event.payment_method,
        "status": event.status,
        "error_code": event.error_code,
        "error_description": event.error_description,
        "latency_ms": event.latency_ms,
        "gateway": event.gateway,
        "issuer": event.issuer,
        "retry_count": event.retry_count,
        "timestamp": event.timestamp
    }


# ---------------------------------------------------------
# Incident detection
# ---------------------------------------------------------

@app.get("/incidents/analyze")
def detect_incident(
    window_minutes: int = 60,
    end_time: datetime = None,
    db: Session = Depends(get_db)
):

    if window_minutes <= 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "window_minutes must "
                "be greater than zero"
            )
        )

    result = analyze_incident(
        db=db,
        end_time=end_time,
        window_minutes=window_minutes
    )

    return result


# -------------------------------------------------------

def save_or_update_incident(
    db: Session,
    incident_analysis: dict,
    root_cause_analysis: dict
):
    """
    Create or update the currently active incident.

    Keeps incident history persistent while avoiding
    duplicate ACTIVE incident records.
    """

    if not incident_analysis.get("incident_detected"):
        return None

    current_data = incident_analysis.get(
        "current",
        {}
    )

    baseline_data = incident_analysis.get(
        "baseline",
        {}
    )

    dominant_signals = incident_analysis.get(
        "dominant_signals",
        {}
    )

    primary_root_cause = root_cause_analysis.get(
        "primary_root_cause",
        {}
    )

    root_cause = primary_root_cause.get(
        "cause",
        "GENERAL_PAYMENT_DEGRADATION"
    )

    root_cause_title = primary_root_cause.get(
        "title",
        root_cause
    )

    confidence = primary_root_cause.get(
        "confidence",
        0
    )

    dominant_gateway = dominant_signals.get(
        "gateway"
    )

    existing_incident = (
        db.query(IncidentDB)
        .filter(
            IncidentDB.status == "ACTIVE",
            IncidentDB.root_cause == root_cause,
            IncidentDB.gateway == dominant_gateway
        )
        .order_by(
            IncidentDB.detected_at.desc()
        )
        .first()
    )

    if existing_incident:

        existing_incident.severity = incident_analysis.get(
            "severity",
            "UNKNOWN"
        )

        existing_incident.root_cause_title = (
            root_cause_title
        )

        existing_incident.confidence = confidence

        existing_incident.failure_rate = (
            current_data.get(
                "failure_rate",
                0
            )
        )

        existing_incident.baseline_failure_rate = (
            baseline_data.get(
                "failure_rate",
                0
            )
        )

        existing_incident.average_latency_ms = (
            current_data.get(
                "average_latency_ms",
                0
            )
        )

        existing_incident.failed_events = (
            current_data.get(
                "failed_events",
                0
            )
        )

        existing_incident.failed_transaction_value = (
            current_data.get(
                "failed_transaction_value",
                0
            )
        )

        db.commit()
        db.refresh(existing_incident)

        return existing_incident

    incident_record = IncidentDB(
        severity=incident_analysis.get(
            "severity",
            "UNKNOWN"
        ),

        status="ACTIVE",

        root_cause=root_cause,

        root_cause_title=root_cause_title,

        confidence=confidence,

        failure_rate=current_data.get(
            "failure_rate",
            0
        ),

        baseline_failure_rate=baseline_data.get(
            "failure_rate",
            0
        ),

        average_latency_ms=current_data.get(
            "average_latency_ms",
            0
        ),

        failed_events=current_data.get(
            "failed_events",
            0
        ),

        failed_transaction_value=current_data.get(
            "failed_transaction_value",
            0
        ),

        gateway=dominant_gateway,
    )

    db.add(incident_record)

    db.commit()
    db.refresh(incident_record)

    return incident_record


# ---------------------------------------------------------
# Incident investigation
# ---------------------------------------------------------

@app.get("/incidents/investigate")
def investigate_incident(
    window_minutes: int = 60,
    end_time: datetime = None,
    db: Session = Depends(get_db)
):
    """
    Complete PayLens incident investigation pipeline.

    Flow:

        Telemetry
            ↓
        Detection
            ↓
        Root Cause Analysis
            ↓
        AI Investigation
            ↓
        Incident Persistence
            ↓
        Unified Response
    """

    if window_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "window_minutes must "
                "be greater than zero"
            )
        )

    # -----------------------------------------------------
    # STEP 1 — Detect incident
    # -----------------------------------------------------

    incident_analysis = analyze_incident(
        db=db,
        window_minutes=window_minutes,
        end_time=end_time
    )

    # -----------------------------------------------------
    # STEP 2 — No incident
    # -----------------------------------------------------

    if not incident_analysis.get(
        "incident_detected",
        False
    ):

        return {
            "status": "no_incident",

            "incident_analysis": incident_analysis,

            "message": (
                "No actionable payment incident "
                "was detected."
            )
        }

    # -----------------------------------------------------
    # STEP 3 — Root Cause Analysis
    # -----------------------------------------------------

    root_cause_analysis = investigate_root_cause(
        incident_analysis
    )

    # -----------------------------------------------------
    # STEP 4 — AI Investigation
    # -----------------------------------------------------

    ai_investigation = investigate_with_ai(
        incident_analysis,
        root_cause_analysis
    )

    # -----------------------------------------------------
    # STEP 5 — Persist incident
    # -----------------------------------------------------

    incident_record = save_or_update_incident(
        db=db,
        incident_analysis=incident_analysis,
        root_cause_analysis=root_cause_analysis
    )

    # -----------------------------------------------------
    # STEP 6 — Final unified response
    # -----------------------------------------------------

    return {
        "status": "investigation_complete",

        "incident": {
            "id": incident_record.id
            if incident_record else None,

            "severity": incident_analysis.get(
                "severity"
            ),

            "status": incident_record.status
            if incident_record else "ACTIVE",

            "detected_at": incident_record.detected_at
            if incident_record else None,
        },

        "detection": incident_analysis,

        "root_cause": root_cause_analysis,

        "ai_investigation": ai_investigation
    }


# ---------------------------------------------------------
# Incident remediation
# ---------------------------------------------------------

@app.get("/incidents/remediation")
def get_incident_remediation(
    window_minutes: int = 60,
    end_time: datetime = None,
    db: Session = Depends(get_db)
):
    """
    Generate remediation recommendations and
    simulate possible recovery for the latest incident.
    """

    # -----------------------------------------------------
    # Validate window
    # -----------------------------------------------------

    if window_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "window_minutes must "
                "be greater than zero"
            )
        )

    # -----------------------------------------------------
    # STEP 1 — Detect incident
    # -----------------------------------------------------

    incident_result = analyze_incident(
        db=db,
        window_minutes=window_minutes,
        end_time=end_time
    )

    # -----------------------------------------------------
    # No incident
    # -----------------------------------------------------

    if not incident_result.get("incident_detected"):
        return {
            "status": "no_incident",
            "message": (
                "No actionable incident detected. "
                "Remediation is not required."
            ),
            "incident_analysis": incident_result
        }

    # -----------------------------------------------------
    # STEP 2 — Root Cause Analysis
    # -----------------------------------------------------

    root_cause_analysis = investigate_root_cause(
        incident_result
    )

    primary_root_cause = root_cause_analysis.get(
        "primary_root_cause",
        {}
    )

    root_cause = primary_root_cause.get(
        "cause",
        "GENERAL_PAYMENT_DEGRADATION"
    )

    # -----------------------------------------------------
    # STEP 2.5 — Store / update incident history
    # -----------------------------------------------------

    current_data = incident_result.get(
        "current",
        {}
    )

    baseline_data = incident_result.get(
        "baseline",
        {}
    )

    dominant_signals = incident_result.get(
        "dominant_signals",
        {}
    )

    dominant_gateway = dominant_signals.get(
        "gateway"
    )

    # Check if the same incident is already active.
    existing_incident = (
        db.query(IncidentDB)
        .filter(
            IncidentDB.status == "ACTIVE",
            IncidentDB.root_cause == root_cause,
            IncidentDB.gateway == dominant_gateway
        )
        .order_by(
            IncidentDB.detected_at.desc()
        )
        .first()
    )

    # -----------------------------------------------------
    # Update existing incident
    # -----------------------------------------------------

    if existing_incident:

        existing_incident.severity = incident_result.get(
            "severity",
            "UNKNOWN"
        )

        existing_incident.root_cause_title = (
            primary_root_cause.get("title")
        )

        existing_incident.confidence = (
            primary_root_cause.get("confidence")
        )

        existing_incident.failure_rate = (
            current_data.get(
                "failure_rate",
                0
            )
        )

        existing_incident.baseline_failure_rate = (
            baseline_data.get(
                "failure_rate",
                0
            )
        )

        existing_incident.average_latency_ms = (
            current_data.get(
                "average_latency_ms",
                0
            )
        )

        existing_incident.failed_events = (
            current_data.get(
                "failed_events",
                0
            )
        )

        existing_incident.failed_transaction_value = (
            current_data.get(
                "failed_transaction_value",
                0
            )
        )

        db.commit()
        db.refresh(existing_incident)

        incident_record = existing_incident

    # -----------------------------------------------------
    # Create new incident
    # -----------------------------------------------------

    else:

        incident_record = IncidentDB(
            severity=incident_result.get(
                "severity",
                "UNKNOWN"
            ),

            status="ACTIVE",

            root_cause=root_cause,

            root_cause_title=primary_root_cause.get(
                "title"
            ),

            confidence=primary_root_cause.get(
                "confidence"
            ),

            failure_rate=current_data.get(
                "failure_rate",
                0
            ),

            baseline_failure_rate=baseline_data.get(
                "failure_rate",
                0
            ),

            average_latency_ms=current_data.get(
                "average_latency_ms",
                0
            ),

            failed_events=current_data.get(
                "failed_events",
                0
            ),

            failed_transaction_value=current_data.get(
                "failed_transaction_value",
                0
            ),

            gateway=dominant_gateway,
        )

        db.add(incident_record)

        db.commit()

        db.refresh(incident_record)

    # -----------------------------------------------------
    # STEP 3 — Extract metrics
    # -----------------------------------------------------

    baseline_failure_rate = baseline_data.get(
        "failure_rate",
        0
    )

    baseline_latency = baseline_data.get(
        "average_latency_ms",
        0
    )

    current_failure_rate = current_data.get(
        "failure_rate",
        0
    )

    current_latency = current_data.get(
        "average_latency_ms",
        0
    )

    failed_events = current_data.get(
        "failed_events",
        0
    )

    failed_transaction_value = current_data.get(
        "failed_transaction_value",
        0
    )

    # -----------------------------------------------------
    # STEP 4 — Dominant telemetry
    # -----------------------------------------------------

    dominant_error = dominant_signals.get(
        "error_code"
    )

    # -----------------------------------------------------
    # STEP 5 — Build remediation
    # -----------------------------------------------------

    remediation_result = build_remediation_analysis(
        root_cause=root_cause,
        current_failure_rate=current_failure_rate,
        current_latency=current_latency,
        baseline_failure_rate=baseline_failure_rate,
        baseline_latency=baseline_latency,
        failed_events=failed_events,
        failed_transaction_value=failed_transaction_value,
        dominant_gateway=dominant_gateway,
        dominant_error=dominant_error,
    )

    # -----------------------------------------------------
    # STEP 6 — Final response
    # -----------------------------------------------------

    return {
        "status": "remediation_ready",

        "incident": {
            "severity": incident_result.get(
                "severity"
            ),
            "root_cause": root_cause,
            "root_cause_title": (
                primary_root_cause.get(
                    "title"
                )
            ),
            "confidence": (
                primary_root_cause.get(
                    "confidence"
                )
            ),
        },

        "impact": {
            "current_failure_rate": (
                current_failure_rate
            ),
            "baseline_failure_rate": (
                baseline_failure_rate
            ),
            "average_latency_ms": (
                current_latency
            ),
            "failed_events": failed_events,
            "failed_transaction_value": (
                failed_transaction_value
            ),
        },

        **remediation_result,

        "root_cause_analysis": (
            root_cause_analysis
        )
    }
    
# ---------------------------------------------------------
# Controlled recovery telemetry
# ---------------------------------------------------------

@app.get("/incidents/recovery-demo")
def get_recovery_demo(
    window_minutes: int = 60,
    db: Session = Depends(get_db)
):
    """
    Return controlled post-mitigation telemetry for demo verification.

    IMPORTANT:
    This does not modify payment traffic or the database.
    It represents a deterministic recovery observation used
    to demonstrate the verification workflow.
    """

    if window_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail="window_minutes must be greater than zero"
        )

    incident_result = analyze_incident(
        db=db,
        window_minutes=window_minutes
    )

    if not incident_result.get("incident_detected"):
        return {
            "status": "no_incident",
            "verification": {
                "status": "NOT_AVAILABLE",
                "message": "No active incident available for recovery verification."
            }
        }

    current = incident_result.get(
        "current",
        {}
    )

    baseline = incident_result.get(
        "baseline",
        {}
    )

    current_failure_rate = float(
        current.get("failure_rate", 0)
    )

    current_latency = float(
        current.get("average_latency_ms", 0)
    )

    baseline_failure_rate = float(
        baseline.get("failure_rate", 0)
    )

    baseline_latency = float(
        baseline.get("average_latency_ms", 0)
    )

    # Controlled but conservative recovery observation.
    recovered_failure_rate = max(
        baseline_failure_rate * 1.10,
        current_failure_rate * 0.25
    )

    recovered_latency = max(
        baseline_latency * 1.10,
        current_latency * 0.35
    )

    failure_improvement = (
        (
            current_failure_rate -
            recovered_failure_rate
        )
        / max(current_failure_rate, 0.01)
    ) * 100

    latency_improvement = (
        (
            current_latency -
            recovered_latency
        )
        / max(current_latency, 0.01)
    ) * 100

    return {
        "status": "recovery_observed",

        "simulation_type": "CONTROLLED_RECOVERY_TELEMETRY",

        "execution": "DEMO_ONLY",

        "verification": {
            "status": "RECOVERY_OBSERVED",

            "observation_window_minutes": window_minutes,

            "before": {
                "failure_rate": round(
                    current_failure_rate,
                    2
                ),
                "average_latency_ms": round(
                    current_latency,
                    2
                )
            },

            "after": {
                "failure_rate": round(
                    recovered_failure_rate,
                    2
                ),
                "average_latency_ms": round(
                    recovered_latency,
                    2
                )
            },

            "improvement": {
                "failure_rate_percent": round(
                    failure_improvement,
                    2
                ),
                "latency_percent": round(
                    latency_improvement,
                    2
                )
            },

            "failure_recovered": (
                recovered_failure_rate <
                current_failure_rate
            ),

            "latency_recovered": (
                recovered_latency <
                current_latency
            )
        },

        "limitations": [
            "This is controlled recovery telemetry for demonstration.",
            "No real payment-routing action is executed.",
            "The database is not modified.",
            "Production verification must use observed post-mitigation telemetry."
        ]
    }


# ---------------------------------------------------------
# Payment topology
# ---------------------------------------------------------

@app.get("/incidents/topology")
def get_payment_topology(
    window_minutes: int = 60,
    db: Session = Depends(get_db),
):
    """
    Build payment topology from actual payment events
    in the current incident window.
    """

    analysis = analyze_incident(
        db=db,
        window_minutes=window_minutes,
    )

    if not analysis.get("incident_detected"):
        return {
            "status": "no_incident",
            "topology": [],
        }

    current = analysis.get("current", {})
    analysis_end = analysis.get("analysis_end_time")

    if analysis_end:
      end_time = (
        datetime.fromisoformat(analysis_end)
        if isinstance(analysis_end, str)
        else analysis_end
    )
    else:
      end_time = current.get("end")

    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)

    if not end_time:
      return {
        "status": "topology_unavailable",
        "topology": [],
        "reason": "Unable to determine analysis window end time.",
    }

    start_time = end_time - timedelta(
    minutes=window_minutes
)

    events = (
        db.query(PaymentEventDB)
        .filter(
            PaymentEventDB.timestamp >= start_time,
            PaymentEventDB.timestamp <= end_time,
        )
        .all()
    )

    if not events:
        return {
            "status": "topology_unavailable",
            "topology": [],
        }

    def pair_stats(items):
        total = len(items)
        failed = sum(
            1
            for event in items
            if str(event.status).lower()
            in {"failed", "failure"}
        )

        return {
            "events": total,
            "failed_events": failed,
            "failure_rate": round(
                (failed / total) * 100,
                2,
            ) if total else 0,
        }

    method_gateway = {}

    for event in events:
        key = (
            event.payment_method,
            event.gateway,
        )

        method_gateway.setdefault(
            key,
            [],
        ).append(event)

    gateway_issuer = {}

    for event in events:
        key = (
            event.gateway,
            event.issuer,
        )

        gateway_issuer.setdefault(
            key,
            [],
        ).append(event)

    issuer_error = {}

    for event in events:
        if not event.error_code:
            continue

        key = (
            event.issuer,
            event.error_code,
        )

        issuer_error.setdefault(
            key,
            [],
        ).append(event)

    method_gateway_stats = [
        {
            "payment_method": method,
            "gateway": gateway,
            **pair_stats(items),
        }
        for (method, gateway), items
        in method_gateway.items()
    ]

    gateway_issuer_stats = [
        {
            "gateway": gateway,
            "issuer": issuer,
            **pair_stats(items),
        }
        for (gateway, issuer), items
        in gateway_issuer.items()
    ]

    issuer_error_stats = [
        {
            "issuer": issuer,
            "error": error,
            **pair_stats(items),
        }
        for (issuer, error), items
        in issuer_error.items()
    ]

    # ---------------------------------------------------------
# True observed end-to-end payment paths
# ---------------------------------------------------------
    full_paths = {}

    for event in events:
    # For incident topology, focus on failed payment paths.
      if str(event.status).lower() not in {"failed", "failure"}:
        continue

      key = (
        event.payment_method,
        event.gateway,
        event.issuer,
        event.error_code,
      )

      full_paths.setdefault(
        key,
        [],
      ).append(event)


    full_path_stats = [
      {
        "payment_method": payment_method,
        "gateway": gateway,
        "issuer": issuer,
        "error": error,
        **pair_stats(items),
      }
      for (
        payment_method,
        gateway,
        issuer,
        error,
    ), items in full_paths.items()
]


# Prefer paths with the highest number of failed events,
# then highest failure rate, then highest event volume.
    dominant_full_path = max(
    full_path_stats,
    key=lambda item: (
        item["failed_events"],
        item["events"],
        item["failure_rate"],
    ),
    default=None,
)

    return {
        "status": "topology_available",

        "window_minutes": window_minutes,

        "incident": {
            "failure_rate": current.get(
                "failure_rate"
            ),
            "average_latency_ms": current.get(
                "average_latency_ms"
            ),
        },

        
        "dominant_path": dominant_full_path,

        "relationships": {
        "payment_method_gateway":
        method_gateway_stats,

        "gateway_issuer":
        gateway_issuer_stats,

        "issuer_error":
        issuer_error_stats,

        "full_payment_paths":
        full_path_stats,
     },
    }
    
# ---------------------------------------------------------
# Incident history
# ---------------------------------------------------------

@app.get("/incidents/history")
def get_incident_history(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Return recently detected incidents.
    """

    if limit <= 0:
        raise HTTPException(
            status_code=400,
            detail="limit must be greater than zero"
        )

    incidents = (
        db.query(IncidentDB)
        .order_by(
            IncidentDB.detected_at.desc()
        )
        .limit(limit)
        .all()
    )

    return {
        "status": "success",
        "count": len(incidents),
        "incidents": [
            {
                "id": incident.id,
                "severity": incident.severity,
                "status": incident.status,
                "root_cause": incident.root_cause,
                "root_cause_title": (
                    incident.root_cause_title
                ),
                "confidence": incident.confidence,
                "failure_rate": incident.failure_rate,
                "baseline_failure_rate": (
                    incident.baseline_failure_rate
                ),
                "average_latency_ms": (
                    incident.average_latency_ms
                ),
                "failed_events": incident.failed_events,
                "failed_transaction_value": (
                    incident.failed_transaction_value
                ),
                "gateway": incident.gateway,
                "detected_at": incident.detected_at,
                "resolved_at": incident.resolved_at,
            }
            for incident in incidents
        ]
    }