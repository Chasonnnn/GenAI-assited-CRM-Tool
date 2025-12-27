"""Version control service - encrypted config snapshots and hash chain.

Enterprise-grade version control for configuration entities:
- Encrypted payloads (Fernet)
- SHA256 checksums for integrity
- Hash chain for tamper detection in audit logs
- Optimistic locking support
- Rollback without history rewriting

Versioned entities:
- Pipelines, email templates, AI settings, org settings
- Integration configs (tokens redacted)

NOT versioned: Cases, tasks, notes (use activity logs instead)
"""

import hashlib
import json
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditLog, EntityVersion


# =============================================================================
# Encryption (Fernet)
# =============================================================================

_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    """Get or create Fernet instance for version encryption."""
    global _fernet
    if _fernet is None:
        key = settings.VERSION_ENCRYPTION_KEY or settings.META_ENCRYPTION_KEY
        if not key:
            raise ValueError(
                "VERSION_ENCRYPTION_KEY or META_ENCRYPTION_KEY must be set. "
                "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_payload(payload: dict[str, Any]) -> bytes:
    """Encrypt JSON payload using Fernet."""
    json_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return get_fernet().encrypt(json_bytes)


def decrypt_payload(encrypted: bytes) -> dict[str, Any]:
    """Decrypt Fernet-encrypted payload to dict."""
    json_bytes = get_fernet().decrypt(encrypted)
    return json.loads(json_bytes.decode("utf-8"))


def compute_checksum(payload: dict[str, Any]) -> str:
    """Compute SHA256 checksum of payload for integrity verification."""
    json_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(json_bytes).hexdigest()


def verify_checksum(encrypted: bytes, expected_checksum: str) -> bool:
    """Verify payload integrity after decryption."""
    payload = decrypt_payload(encrypted)
    actual = compute_checksum(payload)
    return actual == expected_checksum


# =============================================================================
# Hash Chain (Tamper-Evident Audit Logs)
# =============================================================================

GENESIS_HASH = "0" * 64  # All zeros for first entry


def compute_audit_hash(
    prev_hash: str,
    entry_id: str,
    org_id: str,
    event_type: str,
    created_at: str,
    details_json: str,
    # Additional immutable fields for tamper detection
    actor_user_id: str = "",
    target_type: str = "",
    target_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
    request_id: str = "",
    before_version_id: str = "",
    after_version_id: str = "",
) -> str:
    """
    Compute hash for audit log entry.
    
    Hash = SHA256(all immutable fields joined with |)
    
    Expanded coverage ensures tampering with ANY column is detectable.
    v2 hash includes: actor, target, ip, user_agent, version links.
    """
    data = "|".join([
        prev_hash,
        entry_id,
        org_id,
        event_type,
        created_at,
        details_json,
        actor_user_id,
        target_type,
        target_id,
        ip_address,
        user_agent,
        request_id,
        before_version_id,
        after_version_id,
    ])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()



def get_last_audit_hash(db: Session, org_id: UUID) -> str:
    """Get the hash of the most recent audit log entry for an org.
    
    Uses created_at + id for deterministic ordering under concurrency.
    """
    result = db.execute(
        select(AuditLog.entry_hash)
        .where(AuditLog.organization_id == org_id)
        .where(AuditLog.entry_hash.isnot(None))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    ).scalar()
    return result or GENESIS_HASH


# =============================================================================
# Version Management
# =============================================================================

def create_version(
    db: Session,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
    payload: dict[str, Any],
    created_by_user_id: UUID | None,
    comment: str | None = None,
) -> EntityVersion:
    """
    Create a new version snapshot.
    
    Automatically increments version number.
    Encrypts payload and computes checksum.
    """
    def is_version_conflict(error: IntegrityError) -> bool:
        constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint_name and "entity_versions" in constraint_name:
            return True
        message = str(error.orig) if error.orig else str(error)
        return "entity_versions" in message and "version" in message

    for attempt in range(3):
        current_max = db.execute(
            select(func.max(EntityVersion.version))
            .where(EntityVersion.organization_id == org_id)
            .where(EntityVersion.entity_type == entity_type)
            .where(EntityVersion.entity_id == entity_id)
        ).scalar() or 0

        next_version = current_max + 1

        encrypted = encrypt_payload(payload)
        checksum = compute_checksum(payload)

        version = EntityVersion(
            organization_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            version=next_version,
            schema_version=1,
            payload_encrypted=encrypted,
            checksum=checksum,
            created_by_user_id=created_by_user_id,
            comment=comment,
        )
        try:
            with db.begin_nested():
                db.add(version)
                db.flush()
            return version
        except IntegrityError as exc:
            if is_version_conflict(exc) and attempt < 2:
                continue
            raise

    return version


def get_latest_version(
    db: Session,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> EntityVersion | None:
    """Get the most recent version of an entity."""
    return db.execute(
        select(EntityVersion)
        .where(EntityVersion.organization_id == org_id)
        .where(EntityVersion.entity_type == entity_type)
        .where(EntityVersion.entity_id == entity_id)
        .order_by(EntityVersion.version.desc())
        .limit(1)
    ).scalar()


def get_version(
    db: Session,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
    version: int,
) -> EntityVersion | None:
    """Get a specific version of an entity."""
    return db.execute(
        select(EntityVersion)
        .where(EntityVersion.organization_id == org_id)
        .where(EntityVersion.entity_type == entity_type)
        .where(EntityVersion.entity_id == entity_id)
        .where(EntityVersion.version == version)
    ).scalar()


def get_version_history(
    db: Session,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
    limit: int = 50,
) -> list[EntityVersion]:
    """Get version history for an entity (newest first)."""
    return list(db.execute(
        select(EntityVersion)
        .where(EntityVersion.organization_id == org_id)
        .where(EntityVersion.entity_type == entity_type)
        .where(EntityVersion.entity_id == entity_id)
        .order_by(EntityVersion.version.desc())
        .limit(limit)
    ).scalars().all())


def rollback_to_version(
    db: Session,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
    target_version: int,
    user_id: UUID,
) -> tuple[EntityVersion | None, str | None]:
    """
    Rollback to a previous version.
    
    Creates a NEW version with the old payload (never rewrites history).
    
    Returns:
        (new_version, error) - error is set if rollback failed
    """
    target = get_version(db, org_id, entity_type, entity_id, target_version)
    if not target:
        return None, f"Version {target_version} not found"
    
    # Decrypt and verify old payload
    try:
        payload = decrypt_payload(target.payload_encrypted)
        if not verify_checksum(target.payload_encrypted, target.checksum):
            return None, "Checksum verification failed - data may be corrupted"
    except Exception as e:
        return None, f"Failed to decrypt version: {e}"
    
    # Create new version with old payload
    new_version = create_version(
        db=db,
        org_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        created_by_user_id=user_id,
        comment=f"Rollback from v{target_version}",
    )
    
    return new_version, None


# =============================================================================
# Optimistic Locking
# =============================================================================

class VersionConflictError(Exception):
    """Raised when expected_version doesn't match current version."""
    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Version conflict: expected {expected}, got {actual}")


def check_version(
    current_version: int,
    expected_version: int,
) -> None:
    """
    Check if expected version matches current.
    
    Raises:
        VersionConflictError if mismatch
    """
    if current_version != expected_version:
        raise VersionConflictError(expected_version, current_version)


# =============================================================================
# Helper: Redact Secrets from Payloads
# =============================================================================

SECRET_FIELDS = {"api_key", "access_token", "refresh_token", "secret", "password"}


def redact_secrets(payload: dict[str, Any], key_id: str = "current") -> dict[str, Any]:
    """
    Recursively redact secret fields from payload.
    
    Replaces values with [REDACTED:{key_id}] for audit trail.
    """
    result = {}
    for key, value in payload.items():
        if key.lower() in SECRET_FIELDS:
            result[key] = f"[REDACTED:{key_id}]"
        elif isinstance(value, dict):
            result[key] = redact_secrets(value, key_id)
        else:
            result[key] = value
    return result
