"""create processing_jobs table

Revision ID: 001_create_processing_jobs
Revises:
Create Date: 2026-09-27 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_create_processing_jobs"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jobstatus_enum = postgresql.ENUM("QUEUED", "PROCESSING", name="jobstatus")
    jobstatus_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("QUEUED", "PROCESSING", name="jobstatus"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_processing_jobs_status"), "processing_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_processing_jobs_status"), table_name="processing_jobs")
    op.drop_table("processing_jobs")

    jobstatus_enum = postgresql.ENUM("QUEUED", "PROCESSING", name="jobstatus")
    jobstatus_enum.drop(op.get_bind(), checkfirst=True)
