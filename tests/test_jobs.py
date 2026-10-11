import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # Ensure all models are registered with Base.metadata
from app.api.routes.jobs import get_db
from app.db.session import Base
from app.main import app
from app.models import JobStatus
from app.services.job_service import (
    create_job,
    mark_job_completed,
    mark_job_failed,
)
from app.worker import claim_next_job

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
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Creates database tables and overrides get_db dependency for each test."""
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


@pytest.mark.asyncio
async def test_job_service_create_job() -> None:
    """Verify job creation service creates a QUEUED job."""
    async with TestingSessionLocal() as session:
        job = await create_job(session, filename="test_receipt.pdf")

        assert isinstance(job.id, uuid.UUID)
        assert job.status == JobStatus.QUEUED
        assert job.filename == "test_receipt.pdf"
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.error_message is None


@pytest.mark.asyncio
async def test_mark_job_completed() -> None:
    """Verify mark_job_completed transitions job to COMPLETED with timestamp."""
    async with TestingSessionLocal() as session:
        job = await create_job(session, filename="invoice.pdf")
        job_id = job.id

    async with TestingSessionLocal() as session:
        completed_job = await mark_job_completed(session, job_id)
        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETED
        assert completed_job.completed_at is not None


@pytest.mark.asyncio
async def test_mark_job_failed() -> None:
    """Verify mark_job_failed transitions job to FAILED with error message and timestamp."""
    async with TestingSessionLocal() as session:
        job = await create_job(session, filename="corrupt.pdf")
        job_id = job.id

    async with TestingSessionLocal() as session:
        failed_job = await mark_job_failed(session, job_id, error_message="Invalid PDF structure")
        assert failed_job is not None
        assert failed_job.status == JobStatus.FAILED
        assert failed_job.completed_at is not None
        assert failed_job.error_message == "Invalid PDF structure"


@pytest.mark.asyncio
async def test_upload_document_endpoint() -> None:
    """Verify POST /documents/upload returns HTTP 202 Accepted and job_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("invoice.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
        response = await client.post("/documents/upload", files=files)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "QUEUED"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_upload_document_endpoint_whitespace_filename() -> None:
    """Verify uploading a file with whitespace filename returns HTTP 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("   ", b"%PDF-1.4 dummy content", "application/pdf")}
        response = await client.post("/documents/upload", files=files)

    assert response.status_code == 400
    assert response.json()["detail"] == "Filename cannot be empty"


@pytest.mark.asyncio
async def test_get_job_status_endpoint() -> None:
    """Verify GET /jobs/{job_id} returns job details including completed_at and error_message."""
    async with TestingSessionLocal() as session:
        job = await create_job(session, filename="waybill.pdf")
        job_id = str(job.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "QUEUED"
    assert data["started_at"] is None
    assert data["completed_at"] is None
    assert data["error_message"] is None


@pytest.mark.asyncio
async def test_get_job_status_not_found() -> None:
    """Verify GET /jobs/{random_id} returns 404 Not Found for non-existent jobs."""
    random_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/jobs/{random_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_worker_claim_job_logic() -> None:
    """Verify worker claim_next_job transitions job from QUEUED to PROCESSING."""
    async with TestingSessionLocal() as session:
        created_job = await create_job(session, filename="fuel_receipt.jpg")
        job_id = created_job.id

    async with TestingSessionLocal() as session:
        claimed_job = await claim_next_job(session)

        assert claimed_job is not None
        assert claimed_job.id == job_id
        assert claimed_job.status == JobStatus.PROCESSING
        assert claimed_job.started_at is not None

    # Verify no QUEUED jobs remain
    async with TestingSessionLocal() as session:
        empty_claim = await claim_next_job(session)
        assert empty_claim is None
