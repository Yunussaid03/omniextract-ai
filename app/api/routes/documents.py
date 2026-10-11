from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.job import JobCreateResponse
from app.services.job_service import create_job_with_document
from app.services.storage_service import delete_stored_file, save_uploaded_file

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
    """Validates file magic bytes and size, persists document to disk and DB, and returns 202 Accepted."""
    storage_path, content_type, file_size = await save_uploaded_file(file)

    try:
        job, _document = await create_job_with_document(
            db=db,
            original_filename=file.filename or "document",
            storage_path=storage_path,
            content_type=content_type,
            file_size=file_size,
        )
    except Exception as exc:
        delete_stored_file(storage_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record document metadata: {exc}",
        ) from exc

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
    )
