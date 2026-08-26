from fastapi import FastAPI

from .models import PaymentEvent


app = FastAPI(
    title="PayLens AI",
    description="AI-powered payment incident and root-cause investigator",
    version="0.1.0"
)


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
def ingest_payment_event(event: PaymentEvent):
    return {
        "status": "accepted",
        "payment_id": event.payment_id,
        "message": "Payment event received successfully"
    }