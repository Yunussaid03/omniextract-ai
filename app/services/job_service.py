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
