from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.job import JobStatus, ProcessingJob


async def create_job(
    db: AsyncSession, filename: str | None = None
) -> ProcessingJob:
    """Creates a new durable processing job in QUEUED status."""
    job = ProcessingJob(
        status=JobStatus.QUEUED,
        filename=filename,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def create_job_with_document(
    db: AsyncSession,
    original_filename: str,
    storage_path: str,
    content_type: str,
    file_size: int,
) -> tuple[ProcessingJob, Document]:
    """Creates a QUEUED job and linked Document metadata record in a single transaction."""
    job = ProcessingJob(
        status=JobStatus.QUEUED,
        filename=original_filename,
    )
    document = Document(
        job=job,
        original_filename=original_filename,
        storage_path=storage_path,
        content_type=content_type,
        file_size=file_size,
    )
    db.add(job)
    db.add(document)
    await db.commit()
    await db.refresh(job)
    await db.refresh(document)
    return job, document


async def get_job_by_id(
    db: AsyncSession, job_id: UUID
) -> ProcessingJob | None:
    """Retrieves a processing job by its UUID, including linked document relationship."""
    stmt = (
        select(ProcessingJob)
        .options(selectinload(ProcessingJob.document))
        .where(ProcessingJob.id == job_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def mark_job_completed(
    db: AsyncSession, job_id: UUID
) -> ProcessingJob | None:
    """Transitions job status to COMPLETED and sets completed_at timestamp."""
    job = await get_job_by_id(db, job_id)
    if job is not None:
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
    return job


async def mark_job_failed(
    db: AsyncSession, job_id: UUID, error_message: str
) -> ProcessingJob | None:
    """Transitions job status to FAILED and records error message and completed_at timestamp."""
    job = await get_job_by_id(db, job_id)
    if job is not None:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = error_message
        await db.commit()
        await db.refresh(job)
    return job
