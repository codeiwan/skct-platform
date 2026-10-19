from fastapi import FastAPI

from app.api.auth import router as auth_router


app = FastAPI(
    title="SKCT Platform",
    version="0.1.0",
    description="SKCT Online Examination and Analytics Platform",
)


app.include_router(auth_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "skct-platform",
        "version": app.version,
    }
