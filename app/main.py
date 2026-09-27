from fastapi import FastAPI

from app.api.routes import documents_router, health_router, jobs_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Enterprise-grade multimodal document ingestion and structured-data extraction microservice.",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(jobs_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
