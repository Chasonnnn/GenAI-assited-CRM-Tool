"""Promote the ticket id header out of email_message_contents.headers_json.

Revision ID: 20261103_1200_email_content_ticket_header
Revises: 20261012_0900_audit_work_indexes
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "20261103_1200_email_content_ticket_header"
down_revision = "20261012_0900_audit_work_indexes"
branch_labels = None
depends_on = None

# Frozen copy of the stitch header order; do not import application code in migrations.
TICKET_ID_HEADERS = ("X-SF-Ticket-ID", "X-OSS-Ticket-ID", "X-CRM-Ticket-ID")
BATCH_SIZE = 1000


def _ticket_header_id(values: tuple[str | None, ...]) -> uuid.UUID | None:
    # Same parse as the runtime helper: first header whose first value is a UUID.
    for value in values:
        if not value:
            continue
        try:
            return uuid.UUID(value)
        except ValueError:
            continue
    return None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    # Nullable without a default: a catalog-only change, no table rewrite.
    op.add_column(
        "email_message_contents",
        sa.Column("ticket_header_id", UUID(as_uuid=True), nullable=True),
    )
    connection = op.get_bind()
    # Stitching reads values[0] of a header list; ->> 0 would also unwrap a bare string.
    first_values = ",\n".join(
        f"CASE WHEN jsonb_typeof(headers_json -> '{key}') = 'array' "
        f"THEN headers_json -> '{key}' ->> 0 END"
        for key in TICKET_ID_HEADERS
    )
    select_batch = sa.text(
        f"""
        SELECT id, {first_values}
        FROM email_message_contents
        WHERE headers_json ?| CAST(:keys AS text[]) AND id > :after
        ORDER BY id
        LIMIT :limit
        """
    )
    update_row = sa.text(
        "UPDATE email_message_contents SET ticket_header_id = :ticket_id WHERE id = :id"
    )
    after = uuid.UUID(int=0)
    while True:
        rows = connection.execute(
            select_batch, {"keys": list(TICKET_ID_HEADERS), "after": after, "limit": BATCH_SIZE}
        ).all()
        if not rows:
            break
        updates = [
            {"id": row[0], "ticket_id": ticket_id}
            for row in rows
            if (ticket_id := _ticket_header_id(tuple(row[1:]))) is not None
        ]
        if updates:
            connection.execute(update_row, updates)
        after = rows[-1][0]


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_column("email_message_contents", "ticket_header_id")
