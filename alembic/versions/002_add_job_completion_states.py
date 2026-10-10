"""add completed_at and error_message to processing_jobs

Revision ID: 002_add_job_completion_states
Revises: 001_create_processing_jobs
Create Date: 2026-10-10 13:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_job_completion_states"
down_revision: Union[str, None] = "001_create_processing_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("processing_jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("processing_jobs", sa.Column("error_message", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("processing_jobs", "error_message")
    op.drop_column("processing_jobs", "completed_at")
