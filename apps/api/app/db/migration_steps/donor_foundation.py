"""Add organization-scoped donor records and stage history."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.create_table(
        "donors",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("donor_number", sa.String(length=10), nullable=False),
        sa.Column("donor_type", sa.String(length=10), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("phone_hash", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("education", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("owner_type", sa.String(length=10), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("profile_photo_attachment_id", sa.UUID(), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("donor_type IN ('egg', 'sperm')", name="ck_donors_type"),
        sa.CheckConstraint(
            "donor_number ~ '^D[0-9]{5,9}$' AND "
            "CAST(substring(donor_number from '^D([0-9]{5,9})$') AS BIGINT) >= 10001",
            name="ck_donors_number",
        ),
        sa.CheckConstraint(
            "(owner_type IS NULL AND owner_id IS NULL) OR "
            "(owner_type IN ('user', 'queue') AND owner_id IS NOT NULL)",
            name="ck_donors_owner",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], ["pipeline_stages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["profile_photo_attachment_id"], ["attachments.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_donors_org_number",
        "donors",
        ["organization_id", "donor_number"],
        unique=True,
    )
    op.create_index(
        "uq_donors_active_email_hash",
        "donors",
        ["organization_id", "email_hash"],
        unique=True,
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index("idx_donors_org_type", "donors", ["organization_id", "donor_type"])
    op.create_index("idx_donors_org_stage", "donors", ["organization_id", "stage_id"])
    op.create_index(
        "idx_donors_org_owner",
        "donors",
        ["organization_id", "owner_type", "owner_id"],
    )
    op.create_index("idx_donors_org_created", "donors", ["organization_id", "created_at"])
    op.create_index("idx_donors_org_phone_hash", "donors", ["organization_id", "phone_hash"])

    op.create_table(
        "donor_status_history",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("donor_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("old_stage_id", sa.UUID(), nullable=True),
        sa.Column("new_stage_id", sa.UUID(), nullable=True),
        sa.Column("old_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column("old_label_snapshot", sa.String(length=100), nullable=True),
        sa.Column("new_label_snapshot", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["donor_id"], ["donors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["old_stage_id"], ["pipeline_stages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["new_stage_id"], ["pipeline_stages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_donor_history_donor_recorded",
        "donor_status_history",
        ["donor_id", "recorded_at"],
    )
    op.create_index(
        "idx_donor_history_org_recorded",
        "donor_status_history",
        ["organization_id", "recorded_at"],
    )
    op.execute(
        """
        INSERT INTO data_retention_policies (
            organization_id,
            entity_type,
            retention_days,
            is_active
        )
        SELECT
            organization.id,
            'donors',
            COALESCE(surrogate_policy.retention_days, 2190),
            COALESCE(surrogate_policy.is_active, TRUE)
        FROM organizations organization
        LEFT JOIN data_retention_policies surrogate_policy
          ON surrogate_policy.organization_id = organization.id
         AND surrogate_policy.entity_type = 'surrogates'
        ON CONFLICT (organization_id, entity_type) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO data_retention_policies (
            organization_id,
            entity_type,
            retention_days,
            is_active
        )
        SELECT
            organization.id,
            'donor_leads',
            COALESCE(surrogate_policy.retention_days, 2190),
            COALESCE(surrogate_policy.is_active, TRUE)
        FROM organizations organization
        LEFT JOIN data_retention_policies surrogate_policy
          ON surrogate_policy.organization_id = organization.id
         AND surrogate_policy.entity_type = 'surrogates'
        ON CONFLICT (organization_id, entity_type) DO NOTHING
        """
    )


def downgrade() -> None:
    # Keep the legal-hold and worker preflights true through every destructive
    # statement. EXCLUSIVE also waits for in-flight SELECT ... FOR UPDATE claims.
    op.execute(
        """
        LOCK TABLE
            legal_holds,
            data_retention_policies,
            notifications,
            entity_notes,
            jobs,
            email_logs,
            email_deliveries,
            messages,
            message_deliveries,
            campaign_recipients,
            campaigns,
            donor_status_history,
            donors,
            pipelines,
            org_counters
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
                                  SELECT 1 FROM donors donor
                                  WHERE donor.organization_id = legal_hold.organization_id
                              )
                              OR EXISTS (
                                  SELECT 1 FROM campaigns campaign
                                  WHERE campaign.organization_id = legal_hold.organization_id
                                    AND campaign.recipient_type
                                        IN ('egg_donor', 'sperm_donor')
                              )
                              OR EXISTS (
                                  SELECT 1 FROM entity_notes note
                                  WHERE note.organization_id = legal_hold.organization_id
                                    AND note.entity_type = 'donor'
                              )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'donor'
                          AND EXISTS (
                              SELECT 1 FROM donors donor
                              WHERE donor.organization_id = legal_hold.organization_id
                                AND donor.id = legal_hold.entity_id
                          )
                      )
                      OR (
                          legal_hold.entity_type IN ('entity_notes', 'entity_note', 'note')
                          AND EXISTS (
                              SELECT 1 FROM entity_notes note
                              WHERE note.organization_id = legal_hold.organization_id
                                AND note.id = legal_hold.entity_id
                                AND note.entity_type = 'donor'
                          )
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor foundation while donor data is under legal hold';
            END IF;
        END $$
        """
    )
    op.execute("DELETE FROM data_retention_policies WHERE entity_type IN ('donors', 'donor_leads')")
    op.execute("DELETE FROM notifications WHERE entity_type = 'donor'")
    op.execute("DELETE FROM entity_notes WHERE entity_type = 'donor'")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM jobs job
                WHERE job.job_type = 'campaign_send'
                  AND job.status = 'running'
                  AND job.payload->>'campaign_id' IN (
                      SELECT id::text
                      FROM campaigns
                      WHERE recipient_type IN ('egg_donor', 'sperm_donor')
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor campaigns while a donor campaign is running; '
                    'stop workers and retry';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM email_deliveries delivery
                JOIN campaign_recipients recipient
                  ON recipient.email_log_id = delivery.email_log_id
                WHERE delivery.status = 'leased'
                  AND recipient.entity_type IN ('egg_donor', 'sperm_donor')
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor campaigns while a donor email delivery is leased; '
                    'stop workers and retry';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM message_deliveries delivery
                JOIN campaign_recipients recipient
                  ON recipient.message_delivery_id = delivery.id
                WHERE delivery.status = 'leased'
                  AND recipient.entity_type IN ('egg_donor', 'sperm_donor')
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor campaigns while a donor message delivery is leased; '
                    'stop workers and retry';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DELETE FROM email_logs
        WHERE id IN (
            SELECT recipient.email_log_id
            FROM campaign_recipients recipient
            WHERE recipient.entity_type IN ('egg_donor', 'sperm_donor')
              AND recipient.email_log_id IS NOT NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM messages
        WHERE id IN (
            SELECT delivery.message_id
            FROM campaign_recipients recipient
            JOIN message_deliveries delivery
              ON delivery.id = recipient.message_delivery_id
            WHERE recipient.entity_type IN ('egg_donor', 'sperm_donor')
        )
        """
    )
    op.execute(
        """
        DELETE FROM jobs
        WHERE job_type = 'campaign_send'
          AND payload->>'campaign_id' IN (
              SELECT id::text
              FROM campaigns
              WHERE recipient_type IN ('egg_donor', 'sperm_donor')
          )
        """
    )
    op.execute("DELETE FROM campaign_recipients WHERE entity_type IN ('egg_donor', 'sperm_donor')")
    op.execute("DELETE FROM campaigns WHERE recipient_type IN ('egg_donor', 'sperm_donor')")
    op.drop_index("idx_donor_history_org_recorded", table_name="donor_status_history")
    op.drop_index("idx_donor_history_donor_recorded", table_name="donor_status_history")
    op.drop_table("donor_status_history")

    op.drop_index("idx_donors_org_phone_hash", table_name="donors")
    op.drop_index("idx_donors_org_created", table_name="donors")
    op.drop_index("idx_donors_org_owner", table_name="donors")
    op.drop_index("idx_donors_org_stage", table_name="donors")
    op.drop_index("idx_donors_org_type", table_name="donors")
    op.drop_index("uq_donors_active_email_hash", table_name="donors")
    op.drop_index("uq_donors_org_number", table_name="donors")
    op.drop_table("donors")
    op.execute("DELETE FROM pipelines WHERE entity_type IN ('egg_donor', 'sperm_donor')")
    op.execute("DELETE FROM org_counters WHERE counter_type = 'donor_number'")
