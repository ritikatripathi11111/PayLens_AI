from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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