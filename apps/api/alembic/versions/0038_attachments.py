"""Add attachments table.

Revision ID: 0038_attachments
Revises: 0037_pipeline_cutover
Create Date: 2025-12-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "0038_attachments"
down_revision = "0037_pipeline_cutover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by_user_id", UUID(as_uuid=True), nullable=False),
        
        # File metadata
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        
        # Security / Virus scan
        sa.Column("scan_status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("scanned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("quarantined", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        
        # Soft-delete
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", UUID(as_uuid=True), nullable=True),
        
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    
    # Indexes
    op.create_index("idx_attachments_case", "attachments", ["case_id"])
    op.create_index("idx_attachments_org_scan", "attachments", ["organization_id", "scan_status"])
    op.create_index(
        "idx_attachments_active",
        "attachments",
        ["case_id"],
        postgresql_where=sa.text("deleted_at IS NULL AND quarantined = FALSE")
    )


def downgrade() -> None:
    op.drop_index("idx_attachments_active", table_name="attachments")
    op.drop_index("idx_attachments_org_scan", table_name="attachments")
    op.drop_index("idx_attachments_case", table_name="attachments")
    op.drop_table("attachments")
