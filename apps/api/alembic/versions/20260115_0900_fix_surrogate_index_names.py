"""Fix surrogate index and constraint names for renamed tables.

Revision ID: 20260115_0900
Revises: 20260113_1205
Create Date: 2026-01-15
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260115_0900"
down_revision: Union[str, Sequence[str], None] = "20260113_1205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Align index/constraint names with surrogate schema."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_form_tokens_case') THEN
                EXECUTE 'DROP INDEX idx_form_tokens_case';
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_form_submission_tokens_surrogate')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_form_tokens_surrogate') THEN
                EXECUTE 'ALTER INDEX idx_form_submission_tokens_surrogate RENAME TO idx_form_tokens_surrogate';
            END IF;
        END $$;
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_form_tokens_surrogate ON form_submission_tokens (surrogate_id)"
    )

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'matches'
                  AND constraint_name = 'uq_match_org_case_ip'
            )
            AND NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'matches'
                  AND constraint_name = 'uq_match_org_surrogate_ip'
            ) THEN
                EXECUTE 'ALTER TABLE matches RENAME CONSTRAINT uq_match_org_case_ip TO uq_match_org_surrogate_ip';
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_one_accepted_match_per_case')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_one_accepted_match_per_surrogate') THEN
                EXECUTE 'ALTER INDEX uq_one_accepted_match_per_case RENAME TO uq_one_accepted_match_per_surrogate';
            END IF;
        END $$;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_one_accepted_match_per_surrogate
        ON matches (organization_id, surrogate_id)
        WHERE status = 'accepted'
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_case_imports_org_created')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_surrogate_imports_org_created') THEN
                EXECUTE 'ALTER INDEX idx_case_imports_org_created RENAME TO idx_surrogate_imports_org_created';
            END IF;
        END $$;
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_surrogate_imports_org_created ON surrogate_imports (organization_id, created_at)"
    )

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_case_interviews_org_conducted')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_surrogate_interviews_org_conducted') THEN
                EXECUTE 'ALTER INDEX ix_case_interviews_org_conducted RENAME TO ix_surrogate_interviews_org_conducted';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_case_interviews_search_vector')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_surrogate_interviews_search_vector') THEN
                EXECUTE 'ALTER INDEX ix_case_interviews_search_vector RENAME TO ix_surrogate_interviews_search_vector';
            END IF;
        END $$;
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_surrogate_interviews_org_conducted ON surrogate_interviews (organization_id, conducted_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_surrogate_interviews_search_vector ON surrogate_interviews USING gin (search_vector)"
    )


def downgrade() -> None:
    """Revert index/constraint names to case-era values."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_form_tokens_surrogate')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_form_submission_tokens_surrogate') THEN
                EXECUTE 'ALTER INDEX idx_form_tokens_surrogate RENAME TO idx_form_submission_tokens_surrogate';
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'matches'
                  AND constraint_name = 'uq_match_org_surrogate_ip'
            )
            AND NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'matches'
                  AND constraint_name = 'uq_match_org_case_ip'
            ) THEN
                EXECUTE 'ALTER TABLE matches RENAME CONSTRAINT uq_match_org_surrogate_ip TO uq_match_org_case_ip';
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_one_accepted_match_per_surrogate')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_one_accepted_match_per_case') THEN
                EXECUTE 'ALTER INDEX uq_one_accepted_match_per_surrogate RENAME TO uq_one_accepted_match_per_case';
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_surrogate_imports_org_created')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_case_imports_org_created') THEN
                EXECUTE 'ALTER INDEX idx_surrogate_imports_org_created RENAME TO idx_case_imports_org_created';
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_surrogate_interviews_org_conducted')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_case_interviews_org_conducted') THEN
                EXECUTE 'ALTER INDEX ix_surrogate_interviews_org_conducted RENAME TO ix_case_interviews_org_conducted';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_surrogate_interviews_search_vector')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_case_interviews_search_vector') THEN
                EXECUTE 'ALTER INDEX ix_surrogate_interviews_search_vector RENAME TO ix_case_interviews_search_vector';
            END IF;
        END $$;
    """)
