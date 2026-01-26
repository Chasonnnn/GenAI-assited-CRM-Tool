"""Add import templates and custom fields.

Creates:
- import_templates: Reusable CSV import configurations
- custom_fields: Org-scoped custom field definitions
- custom_field_values: Custom field values for surrogates

Updates:
- surrogate_imports: Add detection, mapping, and approval workflow fields
- surrogates: Add import_metadata for tracking data

Revision ID: 20260126_1000
Revises: 20260125_2400
Create Date: 2026-01-26 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "20260126_1000"
down_revision: Union[str, Sequence[str], None] = "20260125_2400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create import templates and custom fields tables."""

    # ==========================================================================
    # 1. Create import_templates table FIRST (before surrogate_imports references it)
    # ==========================================================================
    op.create_table(
        "import_templates",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_default", sa.Boolean(), default=False, nullable=False),
        sa.Column("encoding", sa.String(20), default="auto", nullable=False),
        sa.Column("delimiter", sa.String(5), default="auto", nullable=False),
        sa.Column("has_header", sa.Boolean(), default=True, nullable=False),
        sa.Column("column_mappings", JSONB, nullable=True),
        sa.Column("transformations", JSONB, nullable=True),
        sa.Column("unknown_column_behavior", sa.String(20), default="ignore", nullable=False),
        sa.Column("usage_count", sa.Integer(), default=0, nullable=False),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index("idx_import_templates_org", "import_templates", ["organization_id"])

    # Partial unique index: only one default per org
    op.create_index(
        "uq_import_template_default",
        "import_templates",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_default = TRUE"),
    )

    # ==========================================================================
    # 2. Create custom_fields table
    # ==========================================================================
    op.create_table(
        "custom_fields",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column("options", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_unique_constraint(
        "uq_custom_field_key",
        "custom_fields",
        ["organization_id", "key"],
    )
    op.create_index("idx_custom_fields_org", "custom_fields", ["organization_id"])
    op.create_index(
        "idx_custom_fields_org_active",
        "custom_fields",
        ["organization_id", "is_active"],
    )

    # ==========================================================================
    # 3. Create custom_field_values table
    # ==========================================================================
    op.create_table(
        "custom_field_values",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "surrogate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("surrogates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "custom_field_id",
            UUID(as_uuid=True),
            sa.ForeignKey("custom_fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value_json", JSONB, nullable=True),
    )

    op.create_unique_constraint(
        "uq_custom_field_value",
        "custom_field_values",
        ["surrogate_id", "custom_field_id"],
    )
    op.create_index(
        "idx_custom_field_values_surrogate",
        "custom_field_values",
        ["surrogate_id"],
    )
    op.create_index(
        "idx_custom_field_values_field",
        "custom_field_values",
        ["custom_field_id"],
    )

    # ==========================================================================
    # 4. Add columns to surrogate_imports
    # ==========================================================================

    # Detection & mapping fields
    op.add_column(
        "surrogate_imports",
        sa.Column(
            "template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("import_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column("detected_encoding", sa.String(20), nullable=True),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column("detected_delimiter", sa.String(5), nullable=True),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column("column_mapping_snapshot", JSONB, nullable=True),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column("date_ambiguity_warnings", JSONB, nullable=True),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column(
            "unknown_column_behavior",
            sa.String(20),
            server_default=sa.text("'ignore'"),
            nullable=False,
        ),
    )

    # Approval workflow fields
    op.add_column(
        "surrogate_imports",
        sa.Column(
            "approved_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "surrogate_imports",
        sa.Column("deduplication_stats", JSONB, nullable=True),
    )

    # ==========================================================================
    # 5. Add import_metadata to surrogates
    # ==========================================================================
    op.add_column(
        "surrogates",
        sa.Column("import_metadata", JSONB, nullable=True),
    )


def downgrade() -> None:
    """Remove import templates and custom fields tables."""

    # Remove columns from surrogates
    op.drop_column("surrogates", "import_metadata")

    # Remove columns from surrogate_imports
    op.drop_column("surrogate_imports", "deduplication_stats")
    op.drop_column("surrogate_imports", "rejection_reason")
    op.drop_column("surrogate_imports", "approved_at")
    op.drop_column("surrogate_imports", "approved_by_user_id")
    op.drop_column("surrogate_imports", "date_ambiguity_warnings")
    op.drop_column("surrogate_imports", "column_mapping_snapshot")
    op.drop_column("surrogate_imports", "detected_delimiter")
    op.drop_column("surrogate_imports", "detected_encoding")
    op.drop_column("surrogate_imports", "unknown_column_behavior")
    op.drop_column("surrogate_imports", "template_id")

    # Drop custom_field_values
    op.drop_index("idx_custom_field_values_field", table_name="custom_field_values")
    op.drop_index("idx_custom_field_values_surrogate", table_name="custom_field_values")
    op.drop_constraint("uq_custom_field_value", "custom_field_values", type_="unique")
    op.drop_table("custom_field_values")

    # Drop custom_fields
    op.drop_index("idx_custom_fields_org_active", table_name="custom_fields")
    op.drop_index("idx_custom_fields_org", table_name="custom_fields")
    op.drop_constraint("uq_custom_field_key", "custom_fields", type_="unique")
    op.drop_table("custom_fields")

    # Drop import_templates
    op.drop_index("uq_import_template_default", table_name="import_templates")
    op.drop_index("idx_import_templates_org", table_name="import_templates")
    op.drop_table("import_templates")
