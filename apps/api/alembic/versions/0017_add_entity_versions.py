"""Add entity_versions table and enhance audit_logs with hash chain

Revision ID: 0017_add_entity_versions
Revises: 0016_add_pipelines
Create Date: 2025-12-17

Enterprise version control system:
- entity_versions: encrypted config snapshots
- audit_logs: hash chain for tamper detection, version links
- Genesis hash backfill for existing entries
"""
from typing import Sequence, Union
import hashlib

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0017_add_entity_versions'
down_revision: Union[str, Sequence[str], None] = '0016_add_pipelines'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Genesis hash for hash chain
GENESIS_HASH = "0" * 64


def upgrade() -> None:
    """
    Create entity_versions table and enhance audit_logs.
    """
    # 1. Create entity_versions table FIRST (before audit_logs FK references it)
    op.create_table(
        'entity_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('payload_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('comment', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    
    # Unique constraint and index
    op.create_unique_constraint(
        'uq_entity_version',
        'entity_versions',
        ['organization_id', 'entity_type', 'entity_id', 'version']
    )
    op.create_index(
        'idx_entity_versions_lookup',
        'entity_versions',
        ['organization_id', 'entity_type', 'entity_id', 'created_at']
    )
    
    # 2. Add new columns to audit_logs
    op.add_column('audit_logs', sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('audit_logs', sa.Column('prev_hash', sa.String(64), nullable=True))
    op.add_column('audit_logs', sa.Column('entry_hash', sa.String(64), nullable=True))
    op.add_column('audit_logs', sa.Column(
        'before_version_id', 
        postgresql.UUID(as_uuid=True), 
        sa.ForeignKey('entity_versions.id', ondelete='SET NULL'),
        nullable=True
    ))
    op.add_column('audit_logs', sa.Column(
        'after_version_id', 
        postgresql.UUID(as_uuid=True), 
        sa.ForeignKey('entity_versions.id', ondelete='SET NULL'),
        nullable=True
    ))
    
    # 3. Add current_version to pipelines for optimistic locking
    op.add_column('pipelines', sa.Column('current_version', sa.Integer(), server_default='1', nullable=False))
    
    # 4. Backfill genesis hash for existing audit entries
    # This creates a hash chain starting from the earliest entry
    conn = op.get_bind()
    
    # Get all existing audit logs ordered by created_at
    result = conn.execute(sa.text("""
        SELECT id, organization_id, event_type, created_at, details
        FROM audit_logs
        ORDER BY organization_id, created_at
    """))
    
    rows = result.fetchall()
    
    # Track prev_hash per org
    org_hashes = {}
    
    for row in rows:
        entry_id = str(row[0])
        org_id = str(row[1])
        event_type = row[2]
        created_at = str(row[3])
        details_json = str(row[4]) if row[4] else "{}"
        
        # Get previous hash for this org
        prev_hash = org_hashes.get(org_id, GENESIS_HASH)
        
        # Compute entry hash
        data = f"{prev_hash}|{entry_id}|{org_id}|{event_type}|{created_at}|{details_json}"
        entry_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()
        
        # Update record
        conn.execute(
            sa.text("UPDATE audit_logs SET prev_hash = :prev_hash, entry_hash = :entry_hash WHERE id = :id"),
            {"prev_hash": prev_hash, "entry_hash": entry_hash, "id": row[0]}
        )
        
        # Track for next entry
        org_hashes[org_id] = entry_hash


def downgrade() -> None:
    """Remove entity_versions and audit_logs enhancements."""
    # Remove columns from audit_logs
    op.drop_column('audit_logs', 'after_version_id')
    op.drop_column('audit_logs', 'before_version_id')
    op.drop_column('audit_logs', 'entry_hash')
    op.drop_column('audit_logs', 'prev_hash')
    op.drop_column('audit_logs', 'request_id')
    
    # Remove current_version from pipelines
    op.drop_column('pipelines', 'current_version')
    
    # Drop entity_versions table
    op.drop_index('idx_entity_versions_lookup', 'entity_versions')
    op.drop_constraint('uq_entity_version', 'entity_versions', type_='unique')
    op.drop_table('entity_versions')
