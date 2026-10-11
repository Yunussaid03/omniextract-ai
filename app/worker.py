import argparse
import asyncio
import logging
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.job import JobStatus, ProcessingJob
from app.processors.document_parser import DocumentParsingError, parse_document
from app.services.job_service import (
    get_job_by_id,
    mark_job_failed,
    save_parsed_document,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omniextract.worker")


async def claim_next_job(db: AsyncSession) -> ProcessingJob | None:
    """Safely claims the oldest QUEUED job using FOR UPDATE SKIP LOCKED.

    Executes a short transaction:
    1. Locks one QUEUED row with SKIP LOCKED semantics.
    2. Updates status to PROCESSING and sets started_at timestamp.
    3. Commits transaction immediately.
    """
    stmt = (
        select(ProcessingJob)
        .where(ProcessingJob.status == JobStatus.QUEUED)
        .order_by(ProcessingJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is not None:
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(job)
        return job

    await db.rollback()
    return None


async def process_claimed_job(job_id: uuid.UUID) -> None:
    """Parses document content for a claimed job and persists results outside active DB locks."""
    # 1. Retrieve document metadata in a short read transaction
    async with AsyncSessionLocal() as db:
        job = await get_job_by_id(db, job_id)
        if not job:
            logger.error("Job %s not found in database.", job_id)
            return

        if not job.document:
            error_msg = "No document metadata record associated with this job."
            logger.error("Job %s failed: %s", job_id, error_msg)
            await mark_job_failed(db, job_id, error_msg)
            return

        document_id = job.document.id
        storage_path = job.document.storage_path
        content_type = job.document.content_type
        original_filename = job.document.original_filename

    # 2. Parse file outside of database transaction
    try:
        logger.info("Parsing document for job %s (file: %s)...", job_id, original_filename)
        parse_result = parse_document(storage_path, content_type)
    except DocumentParsingError as err:
        logger.warning("Document parsing failed for job %s: %s", job_id, err)
        async with AsyncSessionLocal() as db:
            await mark_job_failed(db, job_id, str(err))
        return
    except Exception:
        logger.exception("Unexpected error parsing document for job %s", job_id)
        async with AsyncSessionLocal() as db:
            await mark_job_failed(db, job_id, "An unexpected error occurred during document parsing.")
        return

    # 3. Persist parsed content and mark job COMPLETED
    try:
        async with AsyncSessionLocal() as db:
            await save_parsed_document(db, job_id, document_id, parse_result)
        logger.info(
            "Successfully parsed and completed job %s (pages: %d, requires_ocr: %s)",
            job_id,
            parse_result.page_count,
            parse_result.requires_ocr,
        )
    except Exception:
        logger.exception("Failed to persist parsed document for job %s", job_id)
        async with AsyncSessionLocal() as db:
            await mark_job_failed(db, job_id, "Failed to persist parsed document results.")


async def run_worker_loop(poll_interval: float = 1.0, once: bool = False) -> None:
    """Continuous polling loop for claiming, parsing, and persisting queued jobs."""
    logger.info("Starting OmniExtract AI worker (poll_interval=%.1fs, once=%s)...", poll_interval, once)

    while True:
        try:
            async with AsyncSessionLocal() as db:
                claimed_job = await claim_next_job(db)

            if claimed_job is not None:
                logger.info(
                    "Claimed job %s (file: %s) -> Status updated to PROCESSING",
                    claimed_job.id,
                    claimed_job.filename,
                )
                await process_claimed_job(claimed_job.id)
            else:
                if once:
                    logger.info("No queued jobs found. Exiting single-pass worker execution.")
                    break
                await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled. Shutting down worker.")
            break
        except Exception:
            logger.exception("Error in worker loop")
            if once:
                break
            await asyncio.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="OmniExtract AI Document Processing Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single polling pass and exit if no jobs are available.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0s).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_worker_loop(poll_interval=args.poll_interval, once=args.once))
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
