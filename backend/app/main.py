from fastapi import FastAPI

app = FastAPI(
    title="SKCT Platform",
    version="0.1.0",
    description="SKCT Online Examination and Analytics Platform",
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "skct-platform",
        "version": app.version,
    }
