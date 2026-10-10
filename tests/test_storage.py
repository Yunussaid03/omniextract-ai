import os
from typing import AsyncGenerator
import uuid

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models
from app.api.routes.jobs import get_db
from app.core.config import settings
from app.db.session import Base
from app.main import app
from app.models.document import Document
from app.models.job import JobStatus, ProcessingJob
from app.services.job_service import create_job_with_document, get_job_by_id
from app.services.storage_service import delete_stored_file, detect_content_type

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
async def setup_test_db(tmp_path) -> AsyncGenerator[None, None]:
    """Creates database tables, overrides STORAGE_DIR, and manages get_db override for each test."""
    original_storage_dir = settings.STORAGE_DIR
    settings.STORAGE_DIR = str(tmp_path / "test_storage")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    settings.STORAGE_DIR = original_storage_dir


def test_magic_bytes_detection() -> None:
    """Verify content type detection for PDF, PNG, and JPEG magic bytes."""
    assert detect_content_type(b"%PDF-1.4 dummy header") == "application/pdf"
    assert detect_content_type(b"\x89PNG\r\n\x1a\n\x00\x00") == "image/png"
    assert detect_content_type(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"
    assert detect_content_type(b"PLAIN TEXT HEADER") is None


@pytest.mark.asyncio
async def test_successful_pdf_upload() -> None:
    """Verify PDF upload creates job, persists document metadata, and saves file to disk."""
    transport = ASGITransport(app=app)
    pdf_bytes = b"%PDF-1.5 %Valid PDF content header stream"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("vendor_quote.pdf", pdf_bytes, "application/pdf")}
        response = await client.post("/documents/upload", files=files)

    assert response.status_code == 202
    data = response.json()
    job_id = uuid.UUID(data["job_id"])

    async with TestingSessionLocal() as session:
        job = await get_job_by_id(session, job_id)
        assert job is not None
        assert job.status == JobStatus.QUEUED
        assert job.document is not None
        assert job.document.original_filename == "vendor_quote.pdf"
        assert job.document.content_type == "application/pdf"
        assert job.document.file_size == len(pdf_bytes)
        assert os.path.exists(job.document.storage_path)

        with open(job.document.storage_path, "rb") as f:
            saved_content = f.read()
        assert saved_content == pdf_bytes


@pytest.mark.asyncio
async def test_successful_png_upload() -> None:
    """Verify PNG upload creates job and persists document metadata."""
    transport = ASGITransport(app=app)
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("receipt.png", png_bytes, "image/png")}
        response = await client.post("/documents/upload", files=files)

    assert response.status_code == 202
    data = response.json()
    job_id = uuid.UUID(data["job_id"])

    async with TestingSessionLocal() as session:
        job = await get_job_by_id(session, job_id)
        assert job is not None
        assert job.document is not None
        assert job.document.content_type == "image/png"
        assert os.path.exists(job.document.storage_path)


@pytest.mark.asyncio
async def test_successful_jpeg_upload() -> None:
    """Verify JPEG upload creates job and persists document metadata."""
    transport = ASGITransport(app=app)
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("waybill.jpeg", jpeg_bytes, "image/jpeg")}
        response = await client.post("/documents/upload", files=files)

    assert response.status_code == 202
    data = response.json()
    job_id = uuid.UUID(data["job_id"])

    async with TestingSessionLocal() as session:
        job = await get_job_by_id(session, job_id)
        assert job is not None
        assert job.document is not None
        assert job.document.content_type == "image/jpeg"
        assert os.path.exists(job.document.storage_path)


@pytest.mark.asyncio
async def test_unsupported_file_type_magic_bytes() -> None:
    """Verify uploading an unsupported file format returns HTTP 415 Unsupported Media Type."""
    transport = ASGITransport(app=app)
    fake_txt_bytes = b"Hello, this is a plain text file pretending to be a document."

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("document.pdf", fake_txt_bytes, "application/pdf")}
        response = await client.post("/documents/upload", files=files)

    assert response.status_code == 415
    assert "Unsupported document format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_file_size_limit_exceeded() -> None:
    """Verify uploading a file larger than MAX_UPLOAD_SIZE_BYTES returns HTTP 413."""
    original_max_size = settings.MAX_UPLOAD_SIZE_BYTES
    settings.MAX_UPLOAD_SIZE_BYTES = 500  # Set low limit for testing

    transport = ASGITransport(app=app)
    large_pdf_bytes = b"%PDF-1.4 " + (b"X" * 1000)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("large_invoice.pdf", large_pdf_bytes, "application/pdf")}
            response = await client.post("/documents/upload", files=files)

        assert response.status_code == 413
        assert "exceeds maximum allowed limit" in response.json()["detail"]
    finally:
        settings.MAX_UPLOAD_SIZE_BYTES = original_max_size


@pytest.mark.asyncio
async def test_disk_cleanup_on_db_error(monkeypatch) -> None:
    """Verify disk cleanup removes stored file if database record creation fails."""
    transport = ASGITransport(app=app)
    pdf_bytes = b"%PDF-1.4 valid header stream"

    async def mock_create_job_error(*args, **kwargs):
        raise RuntimeError("Database connection failure simulation")

    monkeypatch.setattr(
        "app.api.routes.documents.create_job_with_document", mock_create_job_error
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("invoice.pdf", pdf_bytes, "application/pdf")}
        response = await client.post("/documents/upload", files=files)

    assert response.status_code == 500
    assert "Failed to record document metadata" in response.json()["detail"]

    # Verify storage directory is empty (file deleted)
    stored_files = os.listdir(settings.STORAGE_DIR)
    assert len(stored_files) == 0
