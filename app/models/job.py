from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class JobStatus(str, enum.Enum):
    """Lifecycle status of a processing job."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"


class ProcessingJob(Base):
    """SQLAlchemy model representing a document processing job."""

    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
