"""Prevent record deletion from cascading through retained match history."""

import hashlib
from uuid import UUID

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.db.models import LegalHold, Match

LEGAL_HOLD_ENTITY_ALIASES = {
    "intended_parent": ("intended_parent", "ip"),
    "match_attempt": ("match_attempt", "attempt"),
    "entity_note": ("entity_note", "entity_notes", "note"),
}
PRESERVATION_LOCK_NAMESPACE = 0x43524D50


def legal_hold_entity_types(entity_type: str) -> tuple[str, ...]:
    return LEGAL_HOLD_ENTITY_ALIASES.get(entity_type, (entity_type,))


def legal_hold_ids(holds: dict[str, set[UUID]], entity_type: str) -> set[UUID]:
    return set().union(*(holds.get(alias, set()) for alias in legal_hold_entity_types(entity_type)))


def lock_org_preservation(db: Session, org_id: UUID) -> None:
    """Serialize destructive retention and legal holds without locking normal org writes."""
    org_key = int.from_bytes(hashlib.blake2s(org_id.bytes, digest_size=4).digest(), signed=True)
    db.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :org_key)"),
        {"namespace": PRESERVATION_LOCK_NAMESPACE, "org_key": org_key},
    )


class PreservationDependencyError(ValueError):
    """A record must remain available while preservation dependencies exist."""


def record_match_exists(model, entity_type: str):
    return (
        select(Match.id)
        .where(
            Match.organization_id == model.organization_id,
            getattr(Match, f"{entity_type}_id") == model.id,
        )
        .exists()
    )


def ensure_record_deletable(db: Session, record, entity_type: str) -> None:
    lock_org_preservation(db, record.organization_id)
    model = type(record)
    # A new match FK cannot commit between the dependency check and deletion.
    db.query(model).filter(
        model.organization_id == record.organization_id, model.id == record.id
    ).populate_existing().with_for_update().one()
    if not record.is_archived:
        raise PreservationDependencyError(
            "Cannot permanently delete a record that is no longer archived"
        )
    held = (
        db.query(LegalHold.id)
        .filter(
            LegalHold.organization_id == record.organization_id,
            LegalHold.released_at.is_(None),
            or_(
                LegalHold.entity_type.is_(None),
                and_(
                    LegalHold.entity_type.in_(legal_hold_entity_types(entity_type)),
                    LegalHold.entity_id == record.id,
                ),
            ),
        )
        .first()
    )
    if held:
        raise PreservationDependencyError("Cannot permanently delete a record under legal hold")
    if (
        db.query(model.id)
        .filter(
            model.organization_id == record.organization_id,
            model.id == record.id,
            record_match_exists(model, entity_type),
        )
        .first()
    ):
        raise PreservationDependencyError(
            "Cannot permanently delete a record with retained match history"
        )
