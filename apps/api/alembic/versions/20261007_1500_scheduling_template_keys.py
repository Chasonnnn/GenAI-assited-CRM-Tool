"""Identify scheduling's default client email templates by system key, with readable names.

Scheduling created one org template per client email on first use and found it by a raw name
such as `appointment_confirmed`, which the template library showed as is. The rows keep their
content; each gains a `scheduling_*` system key, and takes a readable name unless the org already
uses that name. The template name is part of its version snapshot, so each rename also records
the renamed snapshot as the next version, as an edit in the template library does.

Revision ID: 20261007_1500_scheduling_template_keys
Revises: 20261005_0100_under_review_scope
"""

import sqlalchemy as sa
from cryptography.fernet import InvalidToken

from alembic import op
from app.services import version_service

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

_ENTITY_TYPE = "email_template"


def _rename(connection, template, name: str, comment: str) -> bool:
    """Rename a template and record the renamed snapshot as its next version.

    A template without a snapshot at its current version is renamed as is; the template service
    records its live content before the next edit. A snapshot that cannot be decrypted leaves the
    template unchanged and returns False.
    """
    recorded = connection.execute(
        sa.text(
            "SELECT payload_encrypted FROM entity_versions "
            "WHERE organization_id = :org AND entity_type = :entity_type "
            "AND entity_id = :id AND version = :version"
        ),
        {
            "org": template.organization_id,
            "entity_type": _ENTITY_TYPE,
            "id": template.id,
            "version": template.current_version,
        },
    ).scalar()
    current_version = template.current_version
    if recorded is not None:
        try:
            payload = version_service.decrypt_payload(recorded)
        except InvalidToken:
            return False
        payload["name"] = name
        current_version = connection.execute(
            sa.text(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM entity_versions "
                "WHERE organization_id = :org AND entity_type = :entity_type AND entity_id = :id"
            ),
            {"org": template.organization_id, "entity_type": _ENTITY_TYPE, "id": template.id},
        ).scalar_one()
        connection.execute(
            sa.text(
                "INSERT INTO entity_versions (organization_id, entity_type, entity_id, version, "
                "schema_version, payload_encrypted, checksum, comment) "
                "VALUES (:org, :entity_type, :id, :version, 1, :payload, :checksum, :comment)"
            ),
            {
                "org": template.organization_id,
                "entity_type": _ENTITY_TYPE,
                "id": template.id,
                "version": current_version,
                "payload": version_service.encrypt_payload(payload),
                "checksum": version_service.compute_checksum(payload),
                "comment": comment,
            },
        )
    connection.execute(
        sa.text(
            "UPDATE email_templates SET name = :name, current_version = :version WHERE id = :id"
        ),
        {"name": name, "version": current_version, "id": template.id},
    )
    return True


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    connection = op.get_bind()
    for legacy_name, system_key, readable_name in _TEMPLATES:
        templates = connection.execute(
            sa.text(
                """
                SELECT template.id, template.organization_id, template.current_version,
                       EXISTS (
                           SELECT 1 FROM email_templates AS other
                           WHERE other.organization_id = template.organization_id
                             AND other.scope = 'org'
                             AND other.name = :readable_name
                       ) AS name_taken
                FROM email_templates AS template
                WHERE template.scope = 'org'
                  AND template.name = :legacy_name
                  AND template.system_key IS NULL
                """
            ),
            {"legacy_name": legacy_name, "readable_name": readable_name},
        ).all()
        for template in templates:
            connection.execute(
                sa.text("UPDATE email_templates SET system_key = :system_key WHERE id = :id"),
                {"system_key": system_key, "id": template.id},
            )
            if not template.name_taken:
                _rename(connection, template, readable_name, "Renamed scheduling default template")


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
        templates = connection.execute(
            sa.text(
                "SELECT id, organization_id, current_version, name FROM email_templates "
                "WHERE system_key = :system_key"
            ),
            {"system_key": system_key},
        ).all()
        for template in templates:
            if template.name != legacy_name and not _rename(
                connection, template, legacy_name, "Restored scheduling template legacy name"
            ):
                raise RuntimeError(
                    f"Template {template.id} version history cannot be decrypted; "
                    "rename it before downgrade"
                )
            connection.execute(
                sa.text("UPDATE email_templates SET system_key = NULL WHERE id = :id"),
                {"id": template.id},
            )
