"""Snapshot Meta lead routing independently from mutable form configuration."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.add_column(
        "meta_leads",
        sa.Column("lead_kind", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "ck_meta_leads_lead_kind",
        "meta_leads",
        "lead_kind IS NULL OR lead_kind IN ('surrogate', 'egg_donor', 'sperm_donor')",
    )
    op.execute(
        """
        UPDATE meta_leads
        SET lead_kind = 'surrogate'
        WHERE converted_surrogate_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE meta_leads AS lead
        SET lead_kind = CASE donor.donor_type
            WHEN 'egg' THEN 'egg_donor'
            WHEN 'sperm' THEN 'sperm_donor'
        END
        FROM donors AS donor
        WHERE lead.converted_donor_id = donor.id
          AND lead.organization_id = donor.organization_id
        """
    )
    op.execute(
        """
        UPDATE meta_leads AS lead
        SET lead_kind = form.lead_kind
        FROM meta_forms AS form
        WHERE lead.organization_id = form.organization_id
          AND lead.meta_form_id = form.form_external_id
          AND lead.lead_kind IS NULL
          AND form.mapping_status <> 'unmapped'
        """
    )


def downgrade() -> None:
    # The next downgrade step restores a schema where every Meta lead is
    # surrogate-shaped. Remove immutable donor snapshots before discarding the
    # discriminator so reclassified/deleted forms cannot expose them to that path.
    op.execute("LOCK TABLE legal_holds, meta_leads IN EXCLUSIVE MODE")
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
                          AND EXISTS (
                              SELECT 1 FROM meta_leads lead
                              WHERE lead.organization_id = legal_hold.organization_id
                                AND lead.lead_kind IN ('egg_donor', 'sperm_donor')
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'donor'
                          AND EXISTS (
                              SELECT 1 FROM meta_leads lead
                              WHERE lead.organization_id = legal_hold.organization_id
                                AND lead.converted_donor_id = legal_hold.entity_id
                                AND lead.lead_kind IN ('egg_donor', 'sperm_donor')
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'meta_lead'
                          AND EXISTS (
                              SELECT 1 FROM meta_leads lead
                              WHERE lead.organization_id = legal_hold.organization_id
                                AND lead.id = legal_hold.entity_id
                                AND lead.lead_kind IN ('egg_donor', 'sperm_donor')
                          )
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor Meta snapshots while donor data is under legal hold';
            END IF;
        END $$
        """
    )
    op.execute("DELETE FROM meta_leads WHERE lead_kind IN ('egg_donor', 'sperm_donor')")
    op.drop_constraint("ck_meta_leads_lead_kind", "meta_leads", type_="check")
    op.drop_column("meta_leads", "lead_kind")
