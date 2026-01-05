"""Add interview tables.

Revision ID: g1a2b3c4d5e6
Revises: f8b3c2d1e4a5
Create Date: 2026-01-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "g1a2b3c4d5e6"
down_revision = "f8b3c2d1e4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create case_interviews table
    op.create_table(
        "case_interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Metadata
        sa.Column("interview_type", sa.String(20), nullable=False),
        sa.Column("conducted_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("conducted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        # Current transcript (denormalized)
        sa.Column("transcript_html", sa.Text(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("transcript_storage_key", sa.String(500), nullable=True),
        sa.Column("transcript_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("transcript_hash", sa.String(64), nullable=True),
        sa.Column("transcript_size_bytes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        # Status
        sa.Column("status", sa.String(20), server_default=sa.text("'completed'"), nullable=False),
        # Retention
        sa.Column("retention_policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Full-text search
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["conducted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["retention_policy_id"], ["data_retention_policies.id"]),
    )

    # Create indexes for case_interviews
    op.create_index("ix_case_interviews_case_id", "case_interviews", ["case_id"])
    op.create_index("ix_case_interviews_org_conducted", "case_interviews", ["organization_id", "conducted_at"])
    op.create_index("ix_case_interviews_search_vector", "case_interviews", ["search_vector"], postgresql_using="gin")

    # Create interview_transcript_versions table
    op.create_table(
        "interview_transcript_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        # Content
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_storage_key", sa.String(500), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_size_bytes", sa.Integer(), nullable=False),
        # Metadata
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["interview_id"], ["case_interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        # Unique constraint
        sa.UniqueConstraint("interview_id", "version", name="uq_interview_version"),
    )

    # Create indexes for interview_transcript_versions
    op.create_index("ix_interview_versions_interview", "interview_transcript_versions", ["interview_id", "version"])
    op.create_index("ix_interview_versions_org", "interview_transcript_versions", ["organization_id"])

    # Create interview_notes table
    op.create_table(
        "interview_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Content
        sa.Column("content", sa.Text(), nullable=False),
        # Anchor to specific version
        sa.Column("transcript_version", sa.Integer(), nullable=False),
        sa.Column("anchor_start", sa.Integer(), nullable=True),
        sa.Column("anchor_end", sa.Integer(), nullable=True),
        sa.Column("anchor_text", sa.String(500), nullable=True),
        # Recalculated anchor for current version
        sa.Column("current_anchor_start", sa.Integer(), nullable=True),
        sa.Column("current_anchor_end", sa.Integer(), nullable=True),
        sa.Column("anchor_status", sa.String(20), nullable=True),
        # Metadata
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["interview_id"], ["case_interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        # Check constraints
        sa.CheckConstraint("anchor_end IS NULL OR anchor_end >= anchor_start", name="ck_interview_notes_anchor_range"),
        sa.CheckConstraint(
            "(anchor_start IS NULL AND anchor_end IS NULL AND anchor_text IS NULL) OR "
            "(anchor_start IS NOT NULL AND anchor_end IS NOT NULL AND anchor_text IS NOT NULL)",
            name="ck_interview_notes_anchor_complete"
        ),
    )

    # Create indexes for interview_notes
    op.create_index("ix_interview_notes_interview", "interview_notes", ["interview_id"])
    op.create_index("ix_interview_notes_org", "interview_notes", ["organization_id"])

    # Create interview_attachments table (link table)
    op.create_table(
        "interview_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        # AI transcription
        sa.Column("transcription_status", sa.String(20), nullable=True),
        sa.Column("transcription_job_id", sa.String(100), nullable=True),
        sa.Column("transcription_error", sa.Text(), nullable=True),
        sa.Column("transcription_completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["interview_id"], ["case_interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        # Unique constraint
        sa.UniqueConstraint("interview_id", "attachment_id", name="uq_interview_attachment"),
    )

    # Create indexes for interview_attachments
    op.create_index("ix_interview_attachments_interview", "interview_attachments", ["interview_id"])

    # Create trigger for updating search_vector on case_interviews
    op.execute("""
        CREATE OR REPLACE FUNCTION update_case_interviews_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.transcript_text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_case_interviews_search_vector
        BEFORE INSERT OR UPDATE OF transcript_text
        ON case_interviews
        FOR EACH ROW
        EXECUTE FUNCTION update_case_interviews_search_vector();
    """)

    # Create trigger for updating updated_at on case_interviews
    op.execute("""
        CREATE OR REPLACE FUNCTION update_case_interviews_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_case_interviews_updated_at
        BEFORE UPDATE ON case_interviews
        FOR EACH ROW
        EXECUTE FUNCTION update_case_interviews_updated_at();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_case_interviews_updated_at ON case_interviews")
    op.execute("DROP FUNCTION IF EXISTS update_case_interviews_updated_at()")
    op.execute("DROP TRIGGER IF EXISTS trg_case_interviews_search_vector ON case_interviews")
    op.execute("DROP FUNCTION IF EXISTS update_case_interviews_search_vector()")

    # Drop tables in reverse order
    op.drop_table("interview_attachments")
    op.drop_table("interview_notes")
    op.drop_table("interview_transcript_versions")
    op.drop_table("case_interviews")
