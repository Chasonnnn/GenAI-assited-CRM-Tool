"""Rename form_field_mappings case_field to surrogate_field.

Revision ID: 20260113_1205
Revises: 20260113_1130
Create Date: 2026-01-13
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260113_1205"
down_revision: Union[str, Sequence[str], None] = "20260113_1130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: rename form_field_mappings case_field -> surrogate_field."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'form_field_mappings' AND column_name = 'case_field') THEN
                EXECUTE 'ALTER TABLE form_field_mappings RENAME COLUMN case_field TO surrogate_field';
            END IF;
        END $$;
    """)

    op.execute("ALTER TABLE form_field_mappings DROP CONSTRAINT IF EXISTS uq_form_case_field")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'form_field_mappings'
                  AND constraint_name = 'uq_form_surrogate_field'
            ) THEN
                EXECUTE 'ALTER TABLE form_field_mappings ADD CONSTRAINT uq_form_surrogate_field UNIQUE (form_id, surrogate_field)';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade: rename form_field_mappings surrogate_field -> case_field."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'form_field_mappings' AND column_name = 'surrogate_field') THEN
                EXECUTE 'ALTER TABLE form_field_mappings RENAME COLUMN surrogate_field TO case_field';
            END IF;
        END $$;
    """)

    op.execute("ALTER TABLE form_field_mappings DROP CONSTRAINT IF EXISTS uq_form_surrogate_field")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'form_field_mappings'
                  AND constraint_name = 'uq_form_case_field'
            ) THEN
                EXECUTE 'ALTER TABLE form_field_mappings ADD CONSTRAINT uq_form_case_field UNIQUE (form_id, case_field)';
            END IF;
        END $$;
    """)
