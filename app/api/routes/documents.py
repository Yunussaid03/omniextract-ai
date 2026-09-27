from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.job import JobCreateResponse
from app.services.job_service import create_job

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document to initiate processing job",
)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> JobCreateResponse:
    """Ingests a document file, creates a QUEUED processing job, and returns 202 Accepted."""
    if not file.filename or not file.filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )

    job = await create_job(db, filename=file.filename)
    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
    )
