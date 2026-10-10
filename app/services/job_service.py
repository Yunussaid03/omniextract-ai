from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def get_job_by_id(
    db: AsyncSession, job_id: UUID
) -> ProcessingJob | None:
    """Retrieves a processing job by its UUID."""
    stmt = select(ProcessingJob).where(ProcessingJob.id == job_id)
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
