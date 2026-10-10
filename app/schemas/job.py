from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus


class JobCreateResponse(BaseModel):
    """Response returned when a document processing job is accepted."""

    job_id: UUID = Field(..., description="Unique identifier for the processing job")
    status: JobStatus = Field(..., description="Initial lifecycle status")
    created_at: datetime = Field(..., description="Timestamp when job was created")

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    """Response returned when querying processing job status."""

    job_id: UUID = Field(..., description="Unique identifier for the processing job")
    status: JobStatus = Field(..., description="Current lifecycle status")
    created_at: datetime = Field(..., description="Timestamp when job was created")
    started_at: datetime | None = Field(
        None, description="Timestamp when worker claimed job for processing"
    )
    completed_at: datetime | None = Field(
        None, description="Timestamp when job finished processing or failed"
    )
    error_message: str | None = Field(
        None, description="Error message description if job status is FAILED"
    )

    model_config = ConfigDict(from_attributes=True)
