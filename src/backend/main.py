from fastapi import FastAPI

app = FastAPI(title="DeepCode Orchestrator API")


@app.get("/health")
def health() -> dict[str, str]:
    """Simple readiness probe for deployment automation."""
    return {"status": "ok"}
