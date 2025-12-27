"""Rehash audit_logs with v2 hash algorithm

Revision ID: 0020_rehash_audit_v2
Revises: 0019_ai_settings_versioning
Create Date: 2025-12-17

Rehashes existing audit_logs entries using:
- Canonical JSON (sort_keys, compact separators)
- Full coverage of immutable columns

Note: This is a breaking change for hash verification of old entries.
Old hashes used v1 (details only), new hashes use v2 (all columns).
"""
from typing import Sequence, Union
import hashlib
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0020_rehash_audit_v2'
down_revision: Union[str, Sequence[str], None] = '0019_ai_settings_versioning'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Genesis hash for hash chain
GENESIS_HASH = "0" * 64


def canonical_json(obj: dict | None) -> str:
    """Serialize object to canonical JSON for consistent hashing."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"), default=str)


def compute_audit_hash_v2(
    prev_hash: str,
    entry_id: str,
    org_id: str,
    event_type: str,
    created_at: str,
    details_json: str,
    actor_user_id: str = "",
    target_type: str = "",
    target_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
    request_id: str = "",
    before_version_id: str = "",
    after_version_id: str = "",
) -> str:
    """V2 hash: includes all immutable columns."""
    data = "|".join([
        prev_hash, entry_id, org_id, event_type, created_at, details_json,
        actor_user_id, target_type, target_id, ip_address, user_agent,
        request_id, before_version_id, after_version_id,
    ])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def upgrade() -> None:
    """Rehash all audit entries with v2 algorithm."""
    conn = op.get_bind()
    
    # Get all existing audit logs ordered by created_at, id (for determinism)
    result = conn.execute(sa.text("""
        SELECT id, organization_id, actor_user_id, event_type, target_type, target_id,
               details, ip_address, user_agent, request_id,
               before_version_id, after_version_id, created_at
        FROM audit_logs
        ORDER BY organization_id, created_at, id
    """))
    
    rows = result.fetchall()
    
    # Track prev_hash per org
    org_hashes = {}
    
    for row in rows:
        entry_id = str(row[0])
        org_id = str(row[1])
        actor_user_id = str(row[2]) if row[2] else ""
        event_type = row[3]
        target_type = row[4] or ""
        target_id = str(row[5]) if row[5] else ""
        details_json = canonical_json(row[6]) if row[6] else "{}"
        ip_address = row[7] or ""
        user_agent = row[8] or ""
        request_id = str(row[9]) if row[9] else ""
        before_version_id = str(row[10]) if row[10] else ""
        after_version_id = str(row[11]) if row[11] else ""
        created_at = str(row[12])
        
        # Get previous hash for this org
        prev_hash = org_hashes.get(org_id, GENESIS_HASH)
        
        # Compute v2 entry hash
        entry_hash = compute_audit_hash_v2(
            prev_hash=prev_hash,
            entry_id=entry_id,
            org_id=org_id,
            event_type=event_type,
            created_at=created_at,
            details_json=details_json,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            before_version_id=before_version_id,
            after_version_id=after_version_id,
        )
        
        # Update record
        conn.execute(
            sa.text("UPDATE audit_logs SET prev_hash = :prev_hash, entry_hash = :entry_hash WHERE id = :id"),
            {"prev_hash": prev_hash, "entry_hash": entry_hash, "id": row[0]}
        )
        
        # Track for next entry
        org_hashes[org_id] = entry_hash


def downgrade() -> None:
    """Cannot restore v1 hashes - would require re-running migration 0017."""
    pass
