from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String

from .db import Base


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

    retry_count: int = Field(default=0, ge=0)

    timestamp: datetime


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

    retry_count = Column(Integer, nullable=False, default=0)

    timestamp = Column(DateTime, nullable=False)