import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.job import ProcessingJob


class ParsedDocument(Base):
    """SQLAlchemy model representing extracted content and parsing metadata of an ingested document."""

    __tablename__ = "parsed_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    raw_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    pages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    page_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    requires_ocr: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="parsed_content",
    )
    job: Mapped["ProcessingJob"] = relationship(
        "ProcessingJob",
        back_populates="parsed_content",
    )
