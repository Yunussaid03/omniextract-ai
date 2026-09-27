import argparse
import asyncio
from datetime import datetime, timezone
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.job import JobStatus, ProcessingJob

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
        job.started_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        return job

    await db.rollback()
    return None


async def run_worker_loop(poll_interval: float = 1.0, once: bool = False) -> None:
    """Continuous polling loop for claiming and processing queued jobs."""
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
                # Processing pipeline integration point for future slices
            else:
                if once:
                    logger.info("No queued jobs found. Exiting single-pass worker execution.")
                    break
                await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled. Shutting down worker.")
            break
        except Exception as exc:
            logger.error("Error in worker loop: %s", exc, exc_info=True)
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
