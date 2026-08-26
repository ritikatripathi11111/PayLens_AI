from fastapi import FastAPI

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