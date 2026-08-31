"""Route Meta forms to surrogate or donor lead records."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.add_column(
        "meta_forms",
        sa.Column(
            "lead_kind",
            sa.String(length=20),
            server_default=sa.text("'surrogate'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_meta_forms_lead_kind",
        "meta_forms",
        "lead_kind IN ('surrogate', 'egg_donor', 'sperm_donor')",
    )

    op.add_column("meta_leads", sa.Column("converted_donor_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_meta_leads_converted_donor_id_donors",
        "meta_leads",
        "donors",
        ["converted_donor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_meta_leads_converted_donor",
        "meta_leads",
        ["converted_donor_id"],
    )
    op.create_check_constraint(
        "ck_meta_leads_single_converted_subject",
        "meta_leads",
        "converted_surrogate_id IS NULL OR converted_donor_id IS NULL",
    )


def downgrade() -> None:
    # The previous schema treats every Meta form as surrogate intake. Remove
    # donor form configurations and their raw leads so they cannot be retried
    # through the surrogate conversion path after rollback.
    op.execute("LOCK TABLE legal_holds, meta_forms, meta_leads IN EXCLUSIVE MODE")
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
                                  SELECT 1 FROM meta_forms form
                                  WHERE form.organization_id = legal_hold.organization_id
                                    AND form.lead_kind IN ('egg_donor', 'sperm_donor')
                              )
                              OR EXISTS (
                                  SELECT 1
                                  FROM meta_leads lead
                                  LEFT JOIN meta_forms form
                                    ON form.organization_id = lead.organization_id
                                   AND form.form_external_id = lead.meta_form_id
                                  WHERE lead.organization_id = legal_hold.organization_id
                                    AND (
                                        lead.converted_donor_id IS NOT NULL
                                        OR form.lead_kind
                                            IN ('egg_donor', 'sperm_donor')
                                    )
                              )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'donor'
                          AND EXISTS (
                              SELECT 1 FROM meta_leads lead
                              WHERE lead.organization_id = legal_hold.organization_id
                                AND lead.converted_donor_id = legal_hold.entity_id
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'meta_lead'
                          AND EXISTS (
                              SELECT 1
                              FROM meta_leads lead
                              LEFT JOIN meta_forms form
                                ON form.organization_id = lead.organization_id
                               AND form.form_external_id = lead.meta_form_id
                              WHERE lead.organization_id = legal_hold.organization_id
                                AND lead.id = legal_hold.entity_id
                                AND (
                                    lead.converted_donor_id IS NOT NULL
                                    OR form.lead_kind
                                        IN ('egg_donor', 'sperm_donor')
                                )
                          )
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor Meta routing while donor data is under legal hold';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DELETE FROM meta_leads lead
        USING meta_forms form
        WHERE lead.organization_id = form.organization_id
          AND lead.meta_form_id = form.form_external_id
          AND form.lead_kind IN ('egg_donor', 'sperm_donor')
        """
    )
    op.execute("DELETE FROM meta_leads WHERE converted_donor_id IS NOT NULL")
    op.execute("DELETE FROM meta_forms WHERE lead_kind IN ('egg_donor', 'sperm_donor')")
    op.drop_constraint(
        "ck_meta_leads_single_converted_subject",
        "meta_leads",
        type_="check",
    )
    op.drop_index("idx_meta_leads_converted_donor", table_name="meta_leads")
    op.drop_constraint(
        "fk_meta_leads_converted_donor_id_donors",
        "meta_leads",
        type_="foreignkey",
    )
    op.drop_column("meta_leads", "converted_donor_id")

    op.drop_constraint("ck_meta_forms_lead_kind", "meta_forms", type_="check")
    op.drop_column("meta_forms", "lead_kind")
