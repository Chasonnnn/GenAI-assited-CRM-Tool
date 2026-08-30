"""Pin donor campaign recipient identity and rendered content at launch."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op


def upgrade() -> None:
    op.add_column(
        "campaign_recipients",
        sa.Column("donor_launch_snapshot", JSONB(none_as_null=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_campaign_recipients_donor_launch_snapshot",
        "campaign_recipients",
        "donor_launch_snapshot IS NULL OR ("
        "entity_type IN ('egg_donor', 'sperm_donor') AND "
        "jsonb_typeof(donor_launch_snapshot) = 'object' AND "
        "donor_launch_snapshot ?& ARRAY["
        "'version', 'recipient_email', 'recipient_name', 'subject', 'body'"
        "] AND "
        "jsonb_typeof(donor_launch_snapshot->'version') = 'number' AND "
        "jsonb_typeof(donor_launch_snapshot->'recipient_email') = 'string' AND "
        "jsonb_typeof(donor_launch_snapshot->'recipient_name') = 'string' AND "
        "jsonb_typeof(donor_launch_snapshot->'subject') = 'string' AND "
        "jsonb_typeof(donor_launch_snapshot->'body') = 'string'"
        ")",
    )


def downgrade() -> None:
    op.execute(
        "LOCK TABLE legal_holds, campaigns, campaign_runs, campaign_recipients IN EXCLUSIVE MODE"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM campaign_recipients recipient
                JOIN campaign_runs run ON run.id = recipient.run_id
                JOIN campaigns campaign ON campaign.id = run.campaign_id
                JOIN legal_holds legal_hold
                  ON legal_hold.organization_id = run.organization_id
                 AND legal_hold.released_at IS NULL
                 AND (
                     legal_hold.entity_type IS NULL
                     OR (
                         legal_hold.entity_type = 'donor'
                         AND legal_hold.entity_id = recipient.entity_id
                     )
                     OR (
                         legal_hold.entity_type = 'campaign_recipient'
                         AND legal_hold.entity_id = recipient.id
                     )
                     OR (
                         legal_hold.entity_type = 'campaign_run'
                         AND legal_hold.entity_id = run.id
                     )
                     OR (
                         legal_hold.entity_type = 'campaign'
                         AND legal_hold.entity_id = campaign.id
                     )
                     OR (
                         legal_hold.entity_type = 'email_log'
                         AND legal_hold.entity_id = recipient.email_log_id
                     )
                 )
                WHERE recipient.donor_launch_snapshot IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot remove donor campaign launch snapshots while related data '
                    'is under legal hold';
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
                FROM campaigns campaign
                LEFT JOIN campaign_runs run ON run.campaign_id = campaign.id
                WHERE campaign.recipient_type IN ('egg_donor', 'sperm_donor')
                  AND campaign.channel = 'email'
                  AND (
                      campaign.status IN ('scheduled', 'sending')
                      OR run.status = 'running'
                  )
            ) OR EXISTS (
                SELECT 1
                FROM campaign_recipients recipient
                JOIN campaign_runs run ON run.id = recipient.run_id
                JOIN campaigns campaign ON campaign.id = run.campaign_id
                WHERE recipient.donor_launch_snapshot IS NOT NULL
                  AND recipient.entity_type IN ('egg_donor', 'sperm_donor')
                  AND (
                      recipient.status = 'pending'
                      OR (
                          recipient.status = 'failed'
                          AND campaign.status <> 'cancelled'
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot remove donor campaign launch snapshots while donor campaign '
                    'work is active or retryable';
            END IF;
        END $$
        """
    )
    op.drop_constraint(
        "ck_campaign_recipients_donor_launch_snapshot",
        "campaign_recipients",
        type_="check",
    )
    op.drop_column("campaign_recipients", "donor_launch_snapshot")
