from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.job import JobResponse
from app.services.job_service import get_job_by_id

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get processing job status by ID",
)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Retrieves processing job status, created_at, and started_at timestamps."""
    job = await get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
    )
