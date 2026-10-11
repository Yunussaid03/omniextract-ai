import os
from collections.abc import AsyncGenerator

import pymupdf
import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.config import settings
from app.db.session import Base
from app.models.job import JobStatus
from app.services.job_service import (
    create_job_with_document,
    get_job_by_id,
    get_parsed_document_by_job_id,
)
from app.worker import claim_next_job, process_claimed_job

# SQLite in-memory engine for unit testing using StaticPool
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
async def setup_pipeline_test(tmp_path, monkeypatch) -> AsyncGenerator[None, None]:
    """Sets up database tables and overrides AsyncSessionLocal and STORAGE_DIR."""
    original_storage_dir = settings.STORAGE_DIR
    settings.STORAGE_DIR = str(tmp_path / "pipeline_storage")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    # Monkeypatch AsyncSessionLocal in app.worker and app.services
    monkeypatch.setattr("app.worker.AsyncSessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", TestingSessionLocal)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    settings.STORAGE_DIR = original_storage_dir


@pytest.mark.asyncio
async def test_worker_processes_pdf_to_completion(tmp_path) -> None:
    """Verify worker claims job, parses PDF, persists ParsedDocument, and marks job COMPLETED."""
    pdf_path = str(tmp_path / "pipeline_storage" / "valid_invoice.pdf")

    doc = pymupdf.open()
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 50), "Tax Invoice 2026-99")
    doc.save(pdf_path)
    doc.close()

    async with TestingSessionLocal() as session:
        job, _document = await create_job_with_document(
            db=session,
            original_filename="valid_invoice.pdf",
            storage_path=pdf_path,
            content_type="application/pdf",
            file_size=os.path.getsize(pdf_path),
        )
        job_id = job.id

    # Execute worker pass
    async with TestingSessionLocal() as session:
        claimed_job = await claim_next_job(session)
        assert claimed_job is not None
        assert claimed_job.id == job_id
        assert claimed_job.status == JobStatus.PROCESSING

    await process_claimed_job(job_id)

    # Verify job status and persisted parsed content
    async with TestingSessionLocal() as session:
        completed_job = await get_job_by_id(session, job_id)
        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETED
        assert completed_job.completed_at is not None
        assert completed_job.error_message is None
        assert completed_job.parsed_content is not None
        assert "Tax Invoice 2026-99" in completed_job.parsed_content.raw_text
        assert completed_job.parsed_content.page_count == 1
        assert completed_job.parsed_content.requires_ocr is False

        # Verify retrieval via standalone service function
        parsed_doc = await get_parsed_document_by_job_id(session, job_id)
        assert parsed_doc is not None
        assert parsed_doc.id == completed_job.parsed_content.id


@pytest.mark.asyncio
async def test_worker_processes_image_to_completion(tmp_path) -> None:
    """Verify worker claims image job, inspects metadata, persists result, and marks job COMPLETED."""
    img_path = str(tmp_path / "pipeline_storage" / "fuel_slip.png")

    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    img.save(img_path, format="PNG")

    async with TestingSessionLocal() as session:
        job, _document = await create_job_with_document(
            db=session,
            original_filename="fuel_slip.png",
            storage_path=img_path,
            content_type="image/png",
            file_size=os.path.getsize(img_path),
        )
        job_id = job.id

    async with TestingSessionLocal() as session:
        claimed_job = await claim_next_job(session)
        assert claimed_job is not None

    await process_claimed_job(job_id)

    async with TestingSessionLocal() as session:
        completed_job = await get_job_by_id(session, job_id)
        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETED
        assert completed_job.parsed_content is not None
        assert completed_job.parsed_content.metadata_json["width"] == 640
        assert completed_job.parsed_content.metadata_json["height"] == 480
        assert completed_job.parsed_content.metadata_json["format"] == "PNG"


@pytest.mark.asyncio
async def test_worker_handles_corrupt_file_as_failed(tmp_path) -> None:
    """Verify worker handles corrupted document gracefully and marks job FAILED."""
    corrupt_file = str(tmp_path / "pipeline_storage" / "broken.pdf")
    with open(corrupt_file, "wb") as f:
        f.write(b"%PDF-1.4 corrupt data bytes \x00\x00")

    async with TestingSessionLocal() as session:
        job, _document = await create_job_with_document(
            db=session,
            original_filename="broken.pdf",
            storage_path=corrupt_file,
            content_type="application/pdf",
            file_size=len(b"%PDF-1.4 corrupt data bytes \x00\x00"),
        )
        job_id = job.id

    async with TestingSessionLocal() as session:
        claimed_job = await claim_next_job(session)
        assert claimed_job is not None

    await process_claimed_job(job_id)

    async with TestingSessionLocal() as session:
        failed_job = await get_job_by_id(session, job_id)
        assert failed_job is not None
        assert failed_job.status == JobStatus.FAILED
        assert failed_job.completed_at is not None
        assert failed_job.error_message is not None
        assert "Failed to parse PDF document" in failed_job.error_message
        assert failed_job.parsed_content is None


@pytest.mark.asyncio
async def test_worker_handles_missing_file_as_failed(tmp_path) -> None:
    """Verify worker handles deleted or missing storage file and marks job FAILED."""
    ghost_path = str(tmp_path / "pipeline_storage" / "does_not_exist.pdf")

    async with TestingSessionLocal() as session:
        job, _document = await create_job_with_document(
            db=session,
            original_filename="ghost.pdf",
            storage_path=ghost_path,
            content_type="application/pdf",
            file_size=100,
        )
        job_id = job.id

    async with TestingSessionLocal() as session:
        claimed_job = await claim_next_job(session)
        assert claimed_job is not None

    await process_claimed_job(job_id)

    async with TestingSessionLocal() as session:
        failed_job = await get_job_by_id(session, job_id)
        assert failed_job is not None
        assert failed_job.status == JobStatus.FAILED
        assert "Document file not found on storage disk" in failed_job.error_message
