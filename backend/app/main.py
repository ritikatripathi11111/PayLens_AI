from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import PaymentEvent, PaymentEventDB


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="PayLens AI",
    description="AI-powered payment incident and root-cause investigator",
    version="0.2.0"
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "project": "PayLens AI",
        "status": "running",
        "message": "Payment incident investigation system"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


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
        "message": "Payment event stored successfully"
    }
    
@app.get("/events/{payment_id}")
def get_payment_event(
    payment_id: str,
    db: Session = Depends(get_db)
):
    event = (
        db.query(PaymentEventDB)
        .filter(PaymentEventDB.payment_id == payment_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Payment event '{payment_id}' not found"
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
        "retry_count": event.retry_count,
        "timestamp": event.timestamp
    }