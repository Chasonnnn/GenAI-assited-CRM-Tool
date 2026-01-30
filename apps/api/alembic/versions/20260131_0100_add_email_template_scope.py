"""Add personal scope support to email templates.

Adds scope, owner_user_id, and source_template_id columns to enable
personal email templates with copy/share functionality.

Revision ID: 20260131_0100
Revises: 20260130_2310
Create Date: 2026-01-31 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260131_0100"
down_revision: Union[str, Sequence[str], None] = "20260130_2310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns
    op.add_column(
        "email_templates",
        sa.Column(
            "scope",
            sa.String(length=20),
            server_default=sa.text("'org'"),
            nullable=False,
            comment="Template scope: 'org' or 'personal'",
        ),
    )
    op.add_column(
        "email_templates",
        sa.Column(
            "owner_user_id",
            sa.UUID(),
            nullable=True,
            comment="Owner for personal templates (NULL for org templates)",
        ),
    )
    op.add_column(
        "email_templates",
        sa.Column(
            "source_template_id",
            sa.UUID(),
            nullable=True,
            comment="Source template when copied/shared",
        ),
    )

    # 2. Add foreign keys
    op.create_foreign_key(
        "fk_email_templates_owner_user",
        "email_templates",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_email_templates_source",
        "email_templates",
        "email_templates",
        ["source_template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Drop old unique constraint (org_id + name)
    op.drop_constraint("uq_email_template_name", "email_templates", type_="unique")

    # 4. Create partial unique indexes
    # Org templates: unique name per organization
    op.execute(
        """
        CREATE UNIQUE INDEX uq_email_template_org_name
        ON email_templates (organization_id, name)
        WHERE scope = 'org'
        """
    )
    # Personal templates: unique name per user within organization
    op.execute(
        """
        CREATE UNIQUE INDEX uq_email_template_personal_name
        ON email_templates (organization_id, owner_user_id, name)
        WHERE scope = 'personal'
        """
    )

    # 5. Add check constraint for scope/owner consistency
    op.execute(
        """
        ALTER TABLE email_templates ADD CONSTRAINT chk_email_template_scope_owner
        CHECK (
            (scope = 'org' AND owner_user_id IS NULL) OR
            (scope = 'personal' AND owner_user_id IS NOT NULL)
        )
        """
    )

    # 6. Add index for scope filtering
    op.create_index(
        "idx_email_templates_scope",
        "email_templates",
        ["organization_id", "scope", "owner_user_id"],
    )


def downgrade() -> None:
    # Drop scope index
    op.drop_index("idx_email_templates_scope", table_name="email_templates")

    # Drop check constraint
    op.execute(
        "ALTER TABLE email_templates DROP CONSTRAINT IF EXISTS chk_email_template_scope_owner"
    )

    # Drop partial unique indexes
    op.execute("DROP INDEX IF EXISTS uq_email_template_personal_name")
    op.execute("DROP INDEX IF EXISTS uq_email_template_org_name")

    # Recreate original unique constraint (will fail if personal templates exist)
    op.create_unique_constraint(
        "uq_email_template_name", "email_templates", ["organization_id", "name"]
    )

    # Drop foreign keys
    op.drop_constraint("fk_email_templates_source", "email_templates", type_="foreignkey")
    op.drop_constraint("fk_email_templates_owner_user", "email_templates", type_="foreignkey")

    # Drop columns
    op.drop_column("email_templates", "source_template_id")
    op.drop_column("email_templates", "owner_user_id")
    op.drop_column("email_templates", "scope")
