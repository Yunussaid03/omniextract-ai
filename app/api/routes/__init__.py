"""API routes package."""

from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router

__all__ = ["documents_router", "health_router", "jobs_router"]
