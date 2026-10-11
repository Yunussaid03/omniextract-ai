from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.job import JobStatus, ProcessingJob
from app.models.parsed_document import ParsedDocument
from app.processors.document_parser import ParsedDocumentResult


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
    """Retrieves a processing job by its UUID, including linked document and parsed content relationships."""
    stmt = (
        select(ProcessingJob)
        .options(
            selectinload(ProcessingJob.document),
            selectinload(ProcessingJob.parsed_content),
        )
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
        job.completed_at = datetime.now(UTC)
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
        job.completed_at = datetime.now(UTC)
        job.error_message = error_message
        await db.commit()
        await db.refresh(job)
    return job


async def save_parsed_document(
    db: AsyncSession,
    job_id: UUID,
    document_id: UUID,
    parse_result: ParsedDocumentResult,
) -> ParsedDocument:
    """Persists parsed document content and metadata, and transitions job to COMPLETED status."""
    parsed_doc = ParsedDocument(
        document_id=document_id,
        job_id=job_id,
        raw_text=parse_result.raw_text,
        pages=parse_result.pages,
        page_count=parse_result.page_count,
        requires_ocr=parse_result.requires_ocr,
        metadata_json=parse_result.metadata_json,
    )
    db.add(parsed_doc)

    stmt = select(ProcessingJob).where(ProcessingJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is not None:
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(parsed_doc)
    return parsed_doc


async def get_parsed_document_by_job_id(
    db: AsyncSession, job_id: UUID
) -> ParsedDocument | None:
    """Retrieves parsed document record associated with a job ID."""
    stmt = select(ParsedDocument).where(ParsedDocument.job_id == job_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
