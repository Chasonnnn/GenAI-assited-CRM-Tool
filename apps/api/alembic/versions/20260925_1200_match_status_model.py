"""Unify match review and decline statuses and workflow triggers.

Deploy API and workers together: old writers use the replaced status values.
Migration history preserves the original status and existing reason text.

Downgrade is lossy: never-accepted cancelled rows become rejected.
match_cancelled workflows and match_status_migrated audit rows remain.

Revision ID: 20260925_1200_match_status_model
Revises: 20260924_0930_scheduling_permission_heads
"""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260925_1200_match_status_model"
down_revision = "20260924_0930_scheduling_permission_heads"
branch_labels = None
depends_on = None


def _indexes(open_statuses: str, committed_statuses: str) -> None:
    for name, columns, predicate in (
        (
            "uq_match_open_surrogate_ip",
            ["organization_id", "surrogate_id", "intended_parent_id"],
            open_statuses,
        ),
        (
            "uq_match_open_donor_ip",
            ["organization_id", "donor_id", "intended_parent_id"],
            open_statuses,
        ),
        (
            "uq_one_accepted_match_per_surrogate",
            ["organization_id", "surrogate_id"],
            committed_statuses,
        ),
    ):
        op.drop_index(name, table_name="matches")
        op.create_index(
            name,
            "matches",
            columns,
            unique=True,
            postgresql_where=sa.text(f"status IN ({predicate})"),
        )


def _history(connection, row, status: str) -> None:
    # Freeze the audit-chain v2 contract here: migrations must not depend on live ORM/services.
    org_id = row.organization_id
    lock_key = int.from_bytes(
        hashlib.blake2b(org_id.bytes, digest_size=8, person=b"audit-chain-v1").digest(),
        "big",
        signed=True,
    )
    connection.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    previous = (
        connection.execute(
            sa.text(
                "SELECT entry_hash FROM audit_logs WHERE organization_id=:org AND entry_hash IS NOT NULL ORDER BY created_at DESC, id DESC LIMIT 1"
            ),
            {"org": org_id},
        ).scalar()
        or "0" * 64
    )
    entry_id, now = uuid4(), datetime.now(UTC)
    details = {
        "match_id": str(row.id),
        "original_status": row.status,
        "status": status,
        "migration": revision,
    }
    for field in ("decline_reason", "closure_reason"):
        if getattr(row, field) is not None:
            details[field] = getattr(row, field)
    payload = json.dumps(details, sort_keys=True, separators=(",", ":"))
    event = "match_status_migrated"
    digest = hashlib.sha256(
        "|".join(
            [
                previous,
                str(entry_id),
                str(org_id),
                event,
                str(now),
                payload,
                "",
                "match",
                str(row.id),
                "",
                "",
                "",
                "",
                "",
            ]
        ).encode()
    ).hexdigest()
    connection.execute(
        sa.text("""
        INSERT INTO audit_logs (id, organization_id, event_type, target_type, target_id, details, prev_hash, entry_hash, created_at)
        VALUES (:id, :org, :event, 'match', :match, CAST(:details AS jsonb), :previous, :digest, :now)
    """),
        {
            "id": entry_id,
            "org": org_id,
            "event": event,
            "match": row.id,
            "details": payload,
            "previous": previous,
            "digest": digest,
            "now": now,
        },
    )


def _triggers(old: str, new: str) -> None:
    for table in ("automation_workflows", "workflow_templates"):
        op.execute(
            sa.text(f"UPDATE {table} SET trigger_type=:new WHERE trigger_type=:old").bindparams(
                old=old, new=new
            )
        )
        if table != "workflow_templates":
            continue
        op.execute(
            sa.text(
                f"UPDATE {table} SET draft_config=jsonb_set(draft_config, '{{trigger_type}}', to_jsonb(CAST(:new AS text))) WHERE draft_config->>'trigger_type'=:old"
            ).bindparams(old=old, new=new)
        )


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.execute("LOCK TABLE matches IN ACCESS EXCLUSIVE MODE")
    connection = op.get_bind()
    unknown = connection.execute(
        sa.text("""
        SELECT status, count(*) AS count FROM matches
        WHERE status NOT IN ('proposed', 'reviewing', 'rejected', 'cancel_pending',
            'under_review', 'accepted', 'cancellation_pending', 'declined', 'cancelled', 'completed')
        GROUP BY status ORDER BY status
    """)
    ).all()
    if unknown:
        count = sum(row.count for row in unknown)
        values = ", ".join(row.status for row in unknown)
        raise RuntimeError(f"Cannot migrate {count} matches with unknown statuses: {values}")
    op.alter_column(
        "matches",
        "rejection_reason",
        new_column_name="decline_reason",
        existing_type=sa.Text(),
        existing_nullable=True,
    )
    # Viewing historically populated reviewed_at, so it cannot prove acceptance.
    # Acceptance audit history or an approved cancellation request does prove it.
    rows = connection.execute(
        sa.text("""
        SELECT m.id, m.organization_id, m.status, m.decline_reason, m.closure_reason FROM matches m
        WHERE m.status IN ('proposed', 'reviewing', 'rejected', 'cancel_pending')
        OR (m.status = 'cancelled'
            AND NOT EXISTS (SELECT 1 FROM audit_logs a WHERE a.organization_id=m.organization_id AND a.target_type='match' AND a.target_id=m.id AND a.event_type='match_accepted')
            AND NOT EXISTS (SELECT 1 FROM status_change_requests r WHERE r.organization_id=m.organization_id AND r.entity_type='match' AND r.entity_id=m.id AND r.target_status='cancelled' AND r.status='approved'))
        ORDER BY m.organization_id, m.id
    """)
    ).all()
    for row in rows:
        status = {
            "proposed": "under_review",
            "reviewing": "under_review",
            "rejected": "declined",
            "cancelled": "declined",
            "cancel_pending": "cancellation_pending",
        }[row.status]
        _history(connection, row, status)
        connection.execute(
            sa.text("UPDATE matches SET status=:status WHERE id=:id"),
            {"id": row.id, "status": status},
        )
    _indexes(
        "'under_review','accepted','cancellation_pending'", "'accepted','cancellation_pending'"
    )
    _triggers("match_rejected", "match_declined")


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.execute("LOCK TABLE matches IN ACCESS EXCLUSIVE MODE")
    # The old reader can consume proposed/rejected; legacy reasons remain null.
    op.execute(
        "UPDATE matches SET status=CASE status WHEN 'under_review' THEN 'proposed' WHEN 'declined' THEN 'rejected' WHEN 'cancellation_pending' THEN 'cancel_pending' ELSE status END"
    )
    _indexes("'proposed','reviewing','accepted','cancel_pending'", "'accepted','cancel_pending'")
    _triggers("match_declined", "match_rejected")
    op.alter_column(
        "matches",
        "decline_reason",
        new_column_name="rejection_reason",
        existing_type=sa.Text(),
        existing_nullable=True,
    )
