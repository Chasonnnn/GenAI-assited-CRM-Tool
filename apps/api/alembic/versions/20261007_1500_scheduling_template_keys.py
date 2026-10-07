"""Identify scheduling's default client email templates by system key, with readable names.

Scheduling created one org template per client email on first use and found it by a raw name
such as `appointment_confirmed`, which the template library showed as is. The rows keep their
content; each gains a `scheduling_*` system key, and takes a readable name unless the org already
uses that name.

Revision ID: 20261007_1500_scheduling_template_keys
Revises: 20261005_0100_under_review_scope
"""

import sqlalchemy as sa

from alembic import op

revision = "20261007_1500_scheduling_template_keys"
down_revision = "20261005_0100_under_review_scope"
branch_labels = None
depends_on = None

# (legacy name, system key, readable name); mirrors appointment_email_service.DEFAULT_TEMPLATES.
_TEMPLATES = (
    ("appointment_request_received", "scheduling_request_received", "Booking Request Received"),
    ("appointment_confirmed", "scheduling_confirmed", "Booking Confirmed"),
    ("appointment_rescheduled", "scheduling_rescheduled", "Booking Rescheduled"),
    ("appointment_cancelled", "scheduling_cancelled", "Booking Cancelled"),
    ("appointment_reminder", "scheduling_reminder", "Booking Reminder"),
)


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    connection = op.get_bind()
    for legacy_name, system_key, readable_name in _TEMPLATES:
        connection.execute(
            sa.text(
                """
                UPDATE email_templates AS template
                SET system_key = :system_key,
                    name = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM email_templates AS other
                            WHERE other.organization_id = template.organization_id
                              AND other.scope = 'org'
                              AND other.name = :readable_name
                        ) THEN template.name
                        ELSE :readable_name
                    END
                WHERE template.scope = 'org'
                  AND template.name = :legacy_name
                  AND template.system_key IS NULL
                """
            ),
            {"legacy_name": legacy_name, "system_key": system_key, "readable_name": readable_name},
        )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    connection = op.get_bind()
    for legacy_name, system_key, _ in _TEMPLATES:
        # The earlier code finds these templates by the legacy name only.
        if connection.execute(
            sa.text(
                """
                SELECT 1 FROM email_templates AS template
                WHERE template.system_key = :system_key
                  AND template.name <> :legacy_name
                  AND EXISTS (
                      SELECT 1 FROM email_templates AS other
                      WHERE other.organization_id = template.organization_id
                        AND other.scope = 'org'
                        AND other.name = :legacy_name
                        AND other.id <> template.id
                  )
                LIMIT 1
                """
            ),
            {"system_key": system_key, "legacy_name": legacy_name},
        ).scalar():
            raise RuntimeError(
                f"Another org template is named {legacy_name}; rename it before downgrade"
            )
        connection.execute(
            sa.text(
                "UPDATE email_templates SET name = :legacy_name, system_key = NULL "
                "WHERE system_key = :system_key"
            ),
            {"system_key": system_key, "legacy_name": legacy_name},
        )
