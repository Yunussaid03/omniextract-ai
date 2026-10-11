"""add completed_at and error_message to processing_jobs

Revision ID: 002_add_job_completion_states
Revises: 001_create_processing_jobs
Create Date: 2026-10-10 13:35:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_job_completion_states"
down_revision: str | None = "001_create_processing_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("processing_jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("processing_jobs", sa.Column("error_message", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("processing_jobs", "error_message")
    op.drop_column("processing_jobs", "completed_at")
