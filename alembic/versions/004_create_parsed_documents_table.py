"""create parsed_documents table

Revision ID: 004_create_parsed_documents_table
Revises: 003_create_documents_table
Create Date: 2026-10-11 19:50:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_create_parsed_documents_table"
down_revision: str | None = "003_create_documents_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parsed_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("pages", sa.JSON(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("requires_ocr", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parsed_documents_document_id"), "parsed_documents", ["document_id"], unique=True)
    op.create_index(op.f("ix_parsed_documents_job_id"), "parsed_documents", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_parsed_documents_job_id"), table_name="parsed_documents")
    op.drop_index(op.f("ix_parsed_documents_document_id"), table_name="parsed_documents")
    op.drop_table("parsed_documents")
