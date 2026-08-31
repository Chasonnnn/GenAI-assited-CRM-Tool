"""Link attachments to donors."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.add_column("attachments", sa.Column("donor_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_attachments_donor_id_donors",
        "attachments",
        "donors",
        ["donor_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_attachments_donor", "attachments", ["donor_id"])
    op.create_check_constraint(
        "ck_attachments_donor_subject_exclusive",
        "attachments",
        "donor_id IS NULL OR (surrogate_id IS NULL AND intended_parent_id IS NULL)",
    )


def downgrade() -> None:
    # The prior attachment schema has no safe owner for donor documents.
    # Alembic cannot remove external file objects, so require the application
    # retention path to erase them before a schema rollback.
    op.execute("LOCK TABLE attachments, jobs IN EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM attachments WHERE donor_id IS NOT NULL) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor attachments while stored donor files exist; '
                    'purge donor files through the application first';
            END IF;
        END $$
        """
    )
    op.execute(
        "DELETE FROM jobs WHERE job_type = 'attachment_scan' "
        "AND payload->>'attachment_id' IN "
        "(SELECT id::text FROM attachments WHERE donor_id IS NOT NULL)"
    )
    op.execute("DELETE FROM attachments WHERE donor_id IS NOT NULL")
    op.drop_constraint(
        "ck_attachments_donor_subject_exclusive",
        "attachments",
        type_="check",
    )
    op.drop_index("idx_attachments_donor", table_name="attachments")
    op.drop_constraint(
        "fk_attachments_donor_id_donors",
        "attachments",
        type_="foreignkey",
    )
    op.drop_column("attachments", "donor_id")
