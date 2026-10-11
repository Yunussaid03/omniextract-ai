import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.parsed_document import ParsedDocument


class JobStatus(str, enum.Enum):
    """Lifecycle status of a processing job."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


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
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    document: Mapped["Document | None"] = relationship(
        "Document",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    parsed_content: Mapped["ParsedDocument | None"] = relationship(
        "ParsedDocument",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )
