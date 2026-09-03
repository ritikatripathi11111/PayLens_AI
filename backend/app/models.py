from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


from .db import Base
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Boolean,
    UniqueConstraint,
    Float
)


# =========================================================
# PAYLENS INTERNAL PAYMENT EVENT
# =========================================================

class PaymentEvent(BaseModel):
    payment_id: str = Field(..., min_length=3)
    merchant_id: str = Field(..., min_length=3)

    amount: int = Field(..., gt=0)
    currency: str = "INR"

    payment_method: str
    status: str

    error_code: Optional[str] = None
    error_description: Optional[str] = None

    latency_ms: Optional[int] = Field(default=None, ge=0)

    gateway: Optional[str] = None
    issuer: Optional[str] = None

    retry_count: int = Field(default=0, ge=0)

    timestamp: datetime


# =========================================================
# PAYMENT EVENT DATABASE MODEL
# =========================================================

class PaymentEventDB(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(String, index=True, nullable=False)
    merchant_id = Column(String, index=True, nullable=False)

    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)

    payment_method = Column(String, nullable=False)
    status = Column(String, nullable=False)

    error_code = Column(String, nullable=True)
    error_description = Column(String, nullable=True)

    latency_ms = Column(Integer, nullable=True)

    gateway = Column(String, nullable=True)
    issuer = Column(String, nullable=True)

    retry_count = Column(Integer, nullable=False, default=0)

    timestamp = Column(DateTime, nullable=False)


# =========================================================
# RAZORPAY WEBHOOK IDEMPOTENCY
# =========================================================
#
# Razorpay sends x-razorpay-event-id with every webhook.
# We store that ID so a retried webhook cannot create
# duplicate payment events in PayLens.
#
# =========================================================

class WebhookEventDB(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    provider = Column(
        String,
        nullable=False,
        default="razorpay"
    )

    event_type = Column(
        String,
        nullable=False
    )

    payment_id = Column(
        String,
        nullable=True,
        index=True
    )

    processed = Column(
        Boolean,
        nullable=False,
        default=True
    )

    received_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            name="uq_webhook_event_id"
        ),
    )
    
# =========================================================
# INCIDENT HISTORY
# =========================================================

class IncidentDB(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)

    severity = Column(
        String,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="ACTIVE"
    )

    root_cause = Column(
        String,
        nullable=True
    )

    root_cause_title = Column(
        String,
        nullable=True
    )

    confidence = Column(
        Float,
        nullable=True
    )

    failure_rate = Column(
        Float,
        nullable=True
    )

    baseline_failure_rate = Column(
        Float,
        nullable=True
    )

    average_latency_ms = Column(
        Float,
        nullable=True
    )

    failed_events = Column(
        Integer,
        nullable=False,
        default=0
    )

    failed_transaction_value = Column(
        Integer,
        nullable=False,
        default=0
    )

    gateway = Column(
        String,
        nullable=True
    )

    detected_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    resolved_at = Column(
        DateTime,
        nullable=True
    )