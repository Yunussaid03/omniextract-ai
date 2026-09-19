from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic health check endpoint")
async def health_check() -> dict[str, str]:
    """Returns application health status."""
    return {"status": "ok"}
