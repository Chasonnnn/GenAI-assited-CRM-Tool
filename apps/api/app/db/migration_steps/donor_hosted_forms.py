"""Add hosted donor form targeting and promotion links."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.add_column(
        "forms",
        sa.Column(
            "lead_kind",
            sa.String(length=20),
            server_default=sa.text("'surrogate'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_forms_lead_kind",
        "forms",
        "lead_kind IN ('surrogate', 'egg_donor', 'sperm_donor')",
    )
    op.create_index(
        "idx_forms_org_lead_kind_status",
        "forms",
        ["organization_id", "lead_kind", "status"],
    )

    op.add_column(
        "published_intake_versions",
        sa.Column(
            "lead_kind_snapshot",
            sa.String(length=20),
            server_default=sa.text("'surrogate'"),
            nullable=False,
        ),
    )

    op.add_column(
        "form_submissions",
        sa.Column(
            "lead_kind",
            sa.String(length=20),
            server_default=sa.text("'surrogate'"),
            nullable=False,
        ),
    )
    op.add_column("form_submissions", sa.Column("donor_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_form_submissions_donor_id_donors",
        "form_submissions",
        "donors",
        ["donor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_form_submissions_donor", "form_submissions", ["donor_id"])
    op.create_index(
        "uq_form_submission_donor_non_null",
        "form_submissions",
        ["form_id", "donor_id"],
        unique=True,
        postgresql_where=sa.text("donor_id IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_form_submissions_lead_kind",
        "form_submissions",
        "lead_kind IN ('surrogate', 'egg_donor', 'sperm_donor')",
    )
    op.create_check_constraint(
        "ck_form_submissions_single_subject",
        "form_submissions",
        "surrogate_id IS NULL OR donor_id IS NULL",
    )

    op.add_column("intake_leads", sa.Column("promoted_donor_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_intake_leads_promoted_donor_id_donors",
        "intake_leads",
        "donors",
        ["promoted_donor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_intake_leads_promoted_donor",
        "intake_leads",
        ["promoted_donor_id"],
    )
    op.create_check_constraint(
        "ck_intake_leads_lead_type",
        "intake_leads",
        "lead_type IN ('surrogate', 'egg_donor', 'sperm_donor')",
    )
    op.create_check_constraint(
        "ck_intake_leads_single_promoted_subject",
        "intake_leads",
        "promoted_surrogate_id IS NULL OR promoted_donor_id IS NULL",
    )


def downgrade() -> None:
    # Donor intake records cannot be represented by the prior surrogate-only
    # form schema. Remove them before dropping their subject discriminators.
    # File objects live outside PostgreSQL, so block instead of orphaning them.
    op.execute(
        """
        LOCK TABLE
            legal_holds,
            forms,
            published_intake_versions,
            form_submissions,
            form_submission_files,
            intake_leads,
            jobs
        IN EXCLUSIVE MODE
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM legal_holds legal_hold
                WHERE legal_hold.released_at IS NULL
                  AND (
                      (
                          legal_hold.entity_type IS NULL
                          AND (
                              EXISTS (
                                  SELECT 1 FROM forms form
                                  WHERE form.organization_id = legal_hold.organization_id
                                    AND form.lead_kind IN ('egg_donor', 'sperm_donor')
                              )
                              OR EXISTS (
                                  SELECT 1 FROM form_submissions submission
                                  WHERE submission.organization_id = legal_hold.organization_id
                                    AND (
                                        submission.lead_kind
                                            IN ('egg_donor', 'sperm_donor')
                                        OR submission.donor_id IS NOT NULL
                                    )
                              )
                              OR EXISTS (
                                  SELECT 1 FROM intake_leads intake
                                  WHERE intake.organization_id = legal_hold.organization_id
                                    AND (
                                        intake.lead_type IN ('egg_donor', 'sperm_donor')
                                        OR intake.promoted_donor_id IS NOT NULL
                                    )
                              )
                              OR EXISTS (
                                  SELECT 1 FROM published_intake_versions version
                                  WHERE version.organization_id = legal_hold.organization_id
                                    AND version.lead_kind_snapshot
                                        IN ('egg_donor', 'sperm_donor')
                              )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'donor'
                          AND (
                              EXISTS (
                                  SELECT 1 FROM form_submissions submission
                                  WHERE submission.organization_id = legal_hold.organization_id
                                    AND submission.donor_id = legal_hold.entity_id
                              )
                              OR EXISTS (
                                  SELECT 1 FROM intake_leads intake
                                  WHERE intake.organization_id = legal_hold.organization_id
                                    AND intake.promoted_donor_id = legal_hold.entity_id
                              )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'form'
                          AND (
                              EXISTS (
                                  SELECT 1 FROM forms form
                                  WHERE form.organization_id = legal_hold.organization_id
                                    AND form.id = legal_hold.entity_id
                                    AND form.lead_kind IN ('egg_donor', 'sperm_donor')
                              )
                              OR EXISTS (
                                  SELECT 1 FROM published_intake_versions version
                                  WHERE version.organization_id = legal_hold.organization_id
                                    AND version.form_id = legal_hold.entity_id
                                    AND version.lead_kind_snapshot
                                        IN ('egg_donor', 'sperm_donor')
                              )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'published_intake_version'
                          AND EXISTS (
                              SELECT 1 FROM published_intake_versions version
                              WHERE version.organization_id = legal_hold.organization_id
                                AND version.id = legal_hold.entity_id
                                AND version.lead_kind_snapshot
                                    IN ('egg_donor', 'sperm_donor')
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'form_submission'
                          AND EXISTS (
                              SELECT 1 FROM form_submissions submission
                              WHERE submission.organization_id = legal_hold.organization_id
                                AND submission.id = legal_hold.entity_id
                                AND (
                                    submission.lead_kind IN ('egg_donor', 'sperm_donor')
                                    OR submission.donor_id IS NOT NULL
                                )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'form_submission_file'
                          AND EXISTS (
                              SELECT 1
                              FROM form_submission_files file
                              JOIN form_submissions submission
                                ON submission.id = file.submission_id
                              WHERE file.organization_id = legal_hold.organization_id
                                AND submission.organization_id = legal_hold.organization_id
                                AND file.id = legal_hold.entity_id
                                AND (
                                    submission.lead_kind IN ('egg_donor', 'sperm_donor')
                                    OR submission.donor_id IS NOT NULL
                                )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'intake_lead'
                          AND EXISTS (
                              SELECT 1 FROM intake_leads intake
                              WHERE intake.organization_id = legal_hold.organization_id
                                AND intake.id = legal_hold.entity_id
                                AND (
                                    intake.lead_type IN ('egg_donor', 'sperm_donor')
                                    OR intake.promoted_donor_id IS NOT NULL
                                )
                          )
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade hosted donor forms while donor data is under legal hold';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM form_submission_files file
                JOIN form_submissions submission
                  ON submission.id = file.submission_id
                WHERE submission.lead_kind IN ('egg_donor', 'sperm_donor')
                   OR submission.donor_id IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade hosted donor forms while stored donor files exist; '
                    'purge donor submissions through the application first';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DELETE FROM jobs
        WHERE job_type = 'form_submission_file_scan'
          AND payload->>'submission_file_id' IN (
              SELECT file.id::text
              FROM form_submission_files file
              JOIN form_submissions submission
                ON submission.id = file.submission_id
              WHERE submission.lead_kind IN ('egg_donor', 'sperm_donor')
                 OR submission.donor_id IS NOT NULL
          )
        """
    )
    op.execute(
        "DELETE FROM intake_leads "
        "WHERE lead_type IN ('egg_donor', 'sperm_donor') "
        "OR promoted_donor_id IS NOT NULL"
    )
    op.execute(
        "DELETE FROM form_submissions "
        "WHERE lead_kind IN ('egg_donor', 'sperm_donor') OR donor_id IS NOT NULL"
    )
    op.execute(
        "DELETE FROM published_intake_versions "
        "WHERE lead_kind_snapshot IN ('egg_donor', 'sperm_donor')"
    )
    op.execute("DELETE FROM forms WHERE lead_kind IN ('egg_donor', 'sperm_donor')")
    op.drop_constraint(
        "ck_intake_leads_single_promoted_subject",
        "intake_leads",
        type_="check",
    )
    op.drop_constraint("ck_intake_leads_lead_type", "intake_leads", type_="check")
    op.drop_index("idx_intake_leads_promoted_donor", table_name="intake_leads")
    op.drop_constraint(
        "fk_intake_leads_promoted_donor_id_donors",
        "intake_leads",
        type_="foreignkey",
    )
    op.drop_column("intake_leads", "promoted_donor_id")

    op.drop_constraint(
        "ck_form_submissions_single_subject",
        "form_submissions",
        type_="check",
    )
    op.drop_constraint(
        "ck_form_submissions_lead_kind",
        "form_submissions",
        type_="check",
    )
    op.drop_index("uq_form_submission_donor_non_null", table_name="form_submissions")
    op.drop_index("idx_form_submissions_donor", table_name="form_submissions")
    op.drop_constraint(
        "fk_form_submissions_donor_id_donors",
        "form_submissions",
        type_="foreignkey",
    )
    op.drop_column("form_submissions", "donor_id")
    op.drop_column("form_submissions", "lead_kind")

    op.drop_column("published_intake_versions", "lead_kind_snapshot")

    op.drop_index("idx_forms_org_lead_kind_status", table_name="forms")
    op.drop_constraint("ck_forms_lead_kind", "forms", type_="check")
    op.drop_column("forms", "lead_kind")
