"""Link campaign recipients to immutable email messages.

Revision ID: 20260723_0150
Revises: 20260723_0140
Create Date: 2026-07-23 01:50:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260723_0150"
down_revision = "20260723_0140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaign_recipients",
        sa.Column("email_log_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "campaign_recipients",
        sa.Column(
            "send_revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Monotonic intentional-send occurrence used for provider idempotency",
        ),
    )
    op.create_foreign_key(
        "fk_campaign_recipients_email_log",
        "campaign_recipients",
        "email_logs",
        ["email_log_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_campaign_recipients_email_log",
        "campaign_recipients",
        ["email_log_id"],
    )
    op.create_check_constraint(
        "ck_campaign_recipients_send_revision_nonnegative",
        "campaign_recipients",
        "send_revision >= 0",
    )

    # Historical rows used external_message_id for either an EmailLog UUID or
    # a provider message ID. Tenant-scoped, unambiguous matches are safe to
    # backfill; ambiguous legacy rows remain nullable for manual reconciliation.
    op.execute(
        """
        WITH candidate_matches AS (
            SELECT
                cr.id AS campaign_recipient_id,
                min(el.id::text)::uuid AS email_log_id,
                bool_or(cr.external_message_id = el.id::text) AS stored_internal_id
            FROM campaign_recipients AS cr
            JOIN campaign_runs AS run
              ON run.id = cr.run_id
            JOIN email_logs AS el
              ON el.organization_id = run.organization_id
             AND (
                    cr.external_message_id = el.id::text
                 OR cr.external_message_id = el.external_id
             )
            WHERE cr.external_message_id IS NOT NULL
            GROUP BY cr.id
            HAVING count(*) = 1
        )
        UPDATE campaign_recipients AS cr
        SET
            email_log_id = candidate_matches.email_log_id,
            external_message_id = CASE
                WHEN candidate_matches.stored_internal_id THEN NULL
                ELSE cr.external_message_id
            END
        FROM candidate_matches
        WHERE cr.id = candidate_matches.campaign_recipient_id
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_campaign_recipients_send_revision_nonnegative",
        "campaign_recipients",
        type_="check",
    )
    op.drop_index(
        "idx_campaign_recipients_email_log",
        table_name="campaign_recipients",
    )
    op.drop_constraint(
        "fk_campaign_recipients_email_log",
        "campaign_recipients",
        type_="foreignkey",
    )
    op.drop_column("campaign_recipients", "send_revision")
    op.drop_column("campaign_recipients", "email_log_id")
