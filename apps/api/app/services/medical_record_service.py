"""Dated medical and insurance records for surrogates and donors.

Services flush; callers commit. A record's corrections, audit event and activity
entry are written in the caller's transaction so they commit or roll back together.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.enums import AuditEventType
from app.db.models import (
    Donor,
    MedicalRecord,
    MedicalRecordCorrection,
    Organization,
    Surrogate,
    User,
)
from app.schemas.medical_record import (
    LEGACY_MEDICAL_FIELDS,
    REDACTED_FIELDS,
    SECTION_FIELDS,
    MedicalRecordCorrectionRead,
    MedicalRecordCreate,
    MedicalRecordFields,
    MedicalRecordListResponse,
    MedicalRecordRead,
    MedicalRecordUpdate,
)
from app.services import activity_service, audit_service, entity_activity_service

DEFAULT_TIMEZONE = "America/Los_Angeles"

OwnerKind = Literal["surrogate", "donor"]
RecordAction = Literal["created", "corrected", "archived", "restored"]

_AUDIT_EVENTS: dict[RecordAction, AuditEventType] = {
    "created": AuditEventType.MEDICAL_RECORD_CREATED,
    "corrected": AuditEventType.MEDICAL_RECORD_CORRECTED,
    "archived": AuditEventType.MEDICAL_RECORD_ARCHIVED,
    "restored": AuditEventType.MEDICAL_RECORD_RESTORED,
}


class MedicalRecordError(ValueError):
    """Request is valid JSON but cannot apply to this record."""


class MedicalRecordConflictError(MedicalRecordError):
    """Record state changed or does not allow the operation."""


class MedicalRecordNotFoundError(MedicalRecordError):
    """Record does not exist for this owner."""


@dataclass(frozen=True)
class RecordOwner:
    kind: OwnerKind
    id: UUID
    organization_id: UUID

    @classmethod
    def for_surrogate(cls, surrogate: Surrogate) -> RecordOwner:
        return cls("surrogate", surrogate.id, surrogate.organization_id)

    @classmethod
    def for_donor(cls, donor: Donor) -> RecordOwner:
        return cls("donor", donor.id, donor.organization_id)

    @property
    def column(self):
        return MedicalRecord.surrogate_id if self.kind == "surrogate" else MedicalRecord.donor_id

    def attach(self, record: MedicalRecord) -> None:
        if self.kind == "surrogate":
            record.surrogate_id = self.id
        else:
            record.donor_id = self.id

    def owns(self, record: MedicalRecord) -> bool:
        owner_id = record.surrogate_id if self.kind == "surrogate" else record.donor_id
        return record.organization_id == self.organization_id and owner_id == self.id


@dataclass(frozen=True)
class Placement:
    status: Literal["current", "past", "scheduled"]
    end_date: date | None


def _org_zone(db: Session, org_id: UUID) -> ZoneInfo:
    timezone_name = db.scalar(select(Organization.timezone).where(Organization.id == org_id))
    try:
        return ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def org_today(db: Session, org_id: UUID) -> date:
    return datetime.now(_org_zone(db, org_id)).date()


def org_local_date(db: Session, org_id: UUID, moment: datetime | None) -> date:
    """Organization-local calendar date of a timestamp; today when it is missing."""
    if moment is None:
        return org_today(db, org_id)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(_org_zone(db, org_id)).date()


def split_legacy_values(
    values: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Separate former flat medical field values, grouped by record section."""
    other: dict[str, object] = {}
    by_section: dict[str, dict[str, object]] = defaultdict(dict)
    for key, value in values.items():
        target = LEGACY_MEDICAL_FIELDS.get(key)
        if target is None:
            other[key] = value
        else:
            section, field = target
            by_section[section][field] = value
    return other, dict(by_section)


def _sort_key(record: MedicalRecord) -> tuple[date, datetime, str]:
    return (record.effective_date or date.min, record.created_at, str(record.id))


def place_records(records: list[MedicalRecord], today: date) -> dict[UUID, Placement]:
    """Return each record's status and last effective day within its section."""
    by_section: dict[str, list[MedicalRecord]] = defaultdict(list)
    for record in records:
        by_section[record.section].append(record)
    placements: dict[UUID, Placement] = {}
    for section_records in by_section.values():
        ordered = sorted(section_records, key=_sort_key)
        active = [r for r in ordered if r.effective_date is None or r.effective_date <= today]
        current = active[-1] if active and active[-1].archived_on is None else None
        for index, record in enumerate(active):
            following = active[index + 1] if index + 1 < len(active) else None
            end = (
                following.effective_date - timedelta(days=1)
                if following and following.effective_date
                else None
            )
            if record.archived_on and (end is None or record.archived_on < end):
                end = record.archived_on
            if end and record.effective_date and end < record.effective_date:
                end = record.effective_date
            placements[record.id] = Placement("current" if record is current else "past", end)
        for record in ordered:
            if record.id not in placements:
                placements[record.id] = Placement("scheduled", None)
    return placements


def current_record(records: list[MedicalRecord], today: date) -> MedicalRecord | None:
    placements = place_records(records, today)
    return next((r for r in records if placements[r.id].status == "current"), None)


def _load(
    db: Session, owner: RecordOwner, *, section: str | None = None, lock: bool = False
) -> list[MedicalRecord]:
    stmt = (
        select(MedicalRecord)
        .where(
            MedicalRecord.organization_id == owner.organization_id,
            owner.column == owner.id,
        )
        .options(selectinload(MedicalRecord.corrections))
    )
    if section is not None:
        stmt = stmt.where(MedicalRecord.section == section)
    if lock:
        stmt = stmt.with_for_update()
    return list(db.scalars(stmt))


def _get_record(db: Session, owner: RecordOwner, record_id: UUID) -> MedicalRecord:
    record = db.scalar(
        select(MedicalRecord)
        .where(
            MedicalRecord.id == record_id,
            MedicalRecord.organization_id == owner.organization_id,
            owner.column == owner.id,
        )
        .with_for_update()
    )
    if record is None:
        raise MedicalRecordNotFoundError("Medical record not found")
    return record


def _existing_for_key(
    db: Session, owner: RecordOwner, key: str | None, section: str
) -> MedicalRecord | None:
    if not key:
        return None
    existing = db.scalar(
        select(MedicalRecord).where(
            MedicalRecord.organization_id == owner.organization_id,
            MedicalRecord.idempotency_key == key,
        )
    )
    if existing is not None and not (owner.owns(existing) and existing.section == section):
        raise MedicalRecordConflictError("This request key was already used for another record")
    return existing


def _insert(db: Session, owner: RecordOwner, record: MedicalRecord) -> MedicalRecord:
    """Insert a record; a concurrent retry with the same key returns the first insert."""
    owner.attach(record)
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        existing = _existing_for_key(db, owner, record.idempotency_key, record.section)
        if existing is None:
            raise
        return existing
    return record


def _field_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _apply_corrections(
    record: MedicalRecord,
    changes: dict[str, object],
    *,
    user_id: UUID | None,
    source: str,
    now: datetime,
) -> list[str]:
    changed: list[str] = []
    for field in sorted(changes):
        old_value = getattr(record, field)
        new_value = changes[field]
        if old_value == new_value:
            continue
        setattr(record, field, new_value)
        redacted = field in REDACTED_FIELDS
        record.corrections.append(
            MedicalRecordCorrection(
                organization_id=record.organization_id,
                field=field,
                old_value=None if redacted else _field_text(old_value),
                new_value=None if redacted else _field_text(new_value),
                redacted=redacted,
                source=source,
                corrected_by_user_id=user_id,
                corrected_at=now,
            )
        )
        changed.append(field)
    return changed


def _check_fields(section: str, fields: set[str]) -> None:
    unknown = sorted(fields - set(SECTION_FIELDS[section]))
    if unknown:
        raise MedicalRecordError(f"Fields not used by {section}: {', '.join(unknown)}")


def _log(
    db: Session,
    owner: RecordOwner,
    user_id: UUID | None,
    action: RecordAction,
    record: MedicalRecord,
    fields: list[str],
    request: Request | None,
) -> None:
    audit_service.log_event(
        db=db,
        org_id=owner.organization_id,
        event_type=_AUDIT_EVENTS[action],
        actor_user_id=user_id,
        target_type=owner.kind,
        target_id=owner.id,
        details={"record_id": str(record.id), "section": record.section, "fields": fields},
        request=request,
    )
    if owner.kind == "surrogate":
        log = (
            activity_service.log_insurance_info_updated
            if record.section == "insurance"
            else activity_service.log_medical_info_updated
        )
        log(
            db=db,
            surrogate_id=owner.id,
            organization_id=owner.organization_id,
            actor_user_id=user_id,
        )
    else:
        entity_activity_service.record_activity(
            db,
            org_id=owner.organization_id,
            entity_type="donor",
            entity_id=owner.id,
            activity_type="info_edited",
            actor_user_id=user_id,
            details={"changed_fields": [f"medical_records.{record.section}"]},
        )


def list_records(db: Session, owner: RecordOwner) -> MedicalRecordListResponse:
    records = _load(db, owner)
    today = org_today(db, owner.organization_id)
    placements = place_records(records, today)
    user_ids = {
        user_id
        for record in records
        for user_id in (
            record.created_by_user_id,
            record.archived_by_user_id,
            *(c.corrected_by_user_id for c in record.corrections),
        )
        if user_id
    }
    names = (
        dict(db.execute(select(User.id, User.display_name).where(User.id.in_(user_ids))).all())
        if user_ids
        else {}
    )
    ordered = sorted(records, key=lambda r: (r.section, _sort_key(r)), reverse=True)
    return MedicalRecordListResponse(
        today=today,
        records=[
            MedicalRecordRead(
                id=record.id,
                section=record.section,
                status=placements[record.id].status,
                effective_date=record.effective_date,
                end_date=placements[record.id].end_date,
                source=record.source,
                **{field: getattr(record, field) for field in MedicalRecordFields.model_fields},
                archived_on=record.archived_on,
                archived_by_name=names.get(record.archived_by_user_id),
                revision=record.revision,
                created_by_name=names.get(record.created_by_user_id),
                created_at=record.created_at,
                corrections=[
                    MedicalRecordCorrectionRead(
                        id=correction.id,
                        field=correction.field,
                        old_value=correction.old_value,
                        new_value=correction.new_value,
                        redacted=correction.redacted,
                        source=correction.source,
                        corrected_by_name=names.get(correction.corrected_by_user_id),
                        corrected_at=correction.corrected_at,
                    )
                    for correction in record.corrections
                ],
            )
            for record in ordered
        ],
    )


def create_record(
    db: Session,
    owner: RecordOwner,
    user_id: UUID,
    data: MedicalRecordCreate,
    *,
    request: Request | None = None,
) -> MedicalRecord:
    existing = _existing_for_key(db, owner, data.idempotency_key, data.section)
    if existing is not None:
        return existing
    now = datetime.now(UTC)
    fields = data.provided_fields()
    for key in ("section", "effective_date", "idempotency_key"):
        fields.pop(key, None)
    record = MedicalRecord(
        organization_id=owner.organization_id,
        section=data.section,
        effective_date=data.effective_date,
        source="manual",
        idempotency_key=data.idempotency_key,
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
        **fields,
    )
    inserted = _insert(db, owner, record)
    if inserted is record:
        _log(db, owner, user_id, "created", record, sorted(fields), request)
    return inserted


def correct_record(
    db: Session,
    owner: RecordOwner,
    user_id: UUID,
    record_id: UUID,
    data: MedicalRecordUpdate,
    *,
    request: Request | None = None,
) -> MedicalRecord:
    record = _get_record(db, owner, record_id)
    if record.revision != data.expected_revision:
        raise MedicalRecordConflictError("This record changed. Refresh and try again.")
    changes = data.provided_fields()
    _check_fields(record.section, set(changes))
    now = datetime.now(UTC)
    changed = _apply_corrections(record, changes, user_id=user_id, source="manual", now=now)
    if not changed:
        return record
    if not (record.name or record.provider_name):
        raise MedicalRecordError("Enter a name")
    record.revision += 1
    record.updated_at = now
    db.flush()
    _log(db, owner, user_id, "corrected", record, changed, request)
    return record


def archive_record(
    db: Session,
    owner: RecordOwner,
    user_id: UUID,
    record_id: UUID,
    expected_revision: int,
    *,
    request: Request | None = None,
) -> MedicalRecord:
    record = _get_record(db, owner, record_id)
    if record.revision != expected_revision:
        raise MedicalRecordConflictError("This record changed. Refresh and try again.")
    today = org_today(db, owner.organization_id)
    current = current_record(_load(db, owner, section=record.section, lock=True), today)
    if current is None or current.id != record.id:
        raise MedicalRecordConflictError("Only the current record can be archived")
    now = datetime.now(UTC)
    record.archived_on = today
    record.archived_at = now
    record.archived_by_user_id = user_id
    record.revision += 1
    record.updated_at = now
    db.flush()
    _log(db, owner, user_id, "archived", record, [], request)
    return record


def restore_section(
    db: Session,
    owner: RecordOwner,
    user_id: UUID,
    section: str,
    idempotency_key: str | None,
    *,
    request: Request | None = None,
) -> MedicalRecord:
    """Start a new record dated today from the archived record's details."""
    existing = _existing_for_key(db, owner, idempotency_key, section)
    if existing is not None:
        return existing
    today = org_today(db, owner.organization_id)
    records = _load(db, owner, section=section, lock=True)
    placements = place_records(records, today)
    if any(p.status in ("current", "scheduled") for p in placements.values()):
        raise MedicalRecordConflictError("This section is not archived")
    active = sorted(
        (r for r in records if placements[r.id].status == "past"),
        key=_sort_key,
    )
    archived = active[-1] if active else None
    if archived is None or archived.archived_on is None:
        raise MedicalRecordConflictError("This section has no archived record")
    now = datetime.now(UTC)
    record = MedicalRecord(
        organization_id=owner.organization_id,
        section=section,
        effective_date=today,
        source="restore",
        idempotency_key=idempotency_key,
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
        **{field: getattr(archived, field) for field in SECTION_FIELDS[section]},
    )
    inserted = _insert(db, owner, record)
    if inserted is record:
        _log(db, owner, user_id, "restored", record, [], request)
    return inserted


def apply_form_values(
    db: Session,
    owner: RecordOwner,
    user_id: UUID | None,
    values_by_section: dict[str, dict[str, object]],
    submitted_on: date,
) -> list[str]:
    """Correct each section's current record from mapped form answers.

    A section without a current record gets a new record dated on the
    submission date. Returns the sections that changed.
    """
    today = org_today(db, owner.organization_id)
    changed_sections: list[str] = []
    for section, raw_values in sorted(values_by_section.items()):
        _check_fields(section, set(raw_values))
        values = MedicalRecordFields.model_validate(raw_values).provided_fields()
        nonempty = {field: value for field, value in values.items() if value is not None}
        now = datetime.now(UTC)
        current = current_record(_load(db, owner, section=section, lock=True), today)
        if current is not None:
            changed = _apply_corrections(current, nonempty, user_id=user_id, source="form", now=now)
            if not changed:
                continue
            current.revision += 1
            current.updated_at = now
            db.flush()
            _log(db, owner, user_id, "corrected", current, changed, None)
        else:
            if not nonempty:
                continue
            record = _insert(
                db,
                owner,
                MedicalRecord(
                    organization_id=owner.organization_id,
                    section=section,
                    effective_date=submitted_on,
                    source="form",
                    created_by_user_id=user_id,
                    created_at=now,
                    updated_at=now,
                    **nonempty,
                ),
            )
            _log(db, owner, user_id, "created", record, sorted(nonempty), None)
        changed_sections.append(section)
    return changed_sections
