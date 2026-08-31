"""Normalized activity reads for CRM entities that use shared domain tables."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal, TypedDict
from uuid import UUID, uuid5

from sqlalchemy.orm import Session

from app.db.enums import EntityType
from app.db.models import (
    Attachment,
    Donor,
    DonorStatusHistory,
    EntityActivityLog,
    EntityNote,
    IntendedParent,
    IntendedParentStatusHistory,
    Membership,
    Pipeline,
    PipelineStage,
    Task,
    User,
)

ActivityEntityType = Literal["intended_parent", "donor"]

_ALLOWED_DETAIL_KEYS = {
    "attachment_id",
    "changed_fields",
    "from_owner_id",
    "from_owner_type",
    "match_id",
    "note_id",
    "task_id",
    "surrogate_id",
    "status_request_id",
    "target_stage_id",
    "to_owner_id",
    "to_owner_type",
}


class ActivityItem(TypedDict):
    id: UUID
    activity_type: str
    actor_user_id: UUID | None
    actor_name: str | None
    details: dict | None
    created_at: datetime


def _preview(value: str, limit: int = 180) -> str:
    plain = re.sub(r"<[^>]+>", " ", value)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain if len(plain) <= limit else f"{plain[: limit - 1].rstrip()}…"


def _synthetic_event_id(source_id: UUID, activity_type: str) -> UUID:
    """Return a stable ID for one event synthesized from a domain row."""
    return uuid5(source_id, activity_type)


def record_activity(
    db: Session,
    *,
    org_id: UUID,
    entity_type: ActivityEntityType,
    entity_id: UUID,
    activity_type: str,
    actor_user_id: UUID | None,
    details: dict | None = None,
    occurred_at: datetime | None = None,
) -> EntityActivityLog:
    """Record safe activity metadata without committing the caller's transaction."""
    unsafe_keys = set(details or {}) - _ALLOWED_DETAIL_KEYS
    if unsafe_keys:
        keys = ", ".join(sorted(unsafe_keys))
        raise ValueError(f"Unsupported activity detail keys: {keys}")
    subject_model = IntendedParent if entity_type == EntityType.INTENDED_PARENT.value else Donor
    subject_exists = (
        db.query(subject_model.id)
        .filter(
            subject_model.id == entity_id,
            subject_model.organization_id == org_id,
        )
        .first()
    )
    if subject_exists is None:
        raise ValueError("Activity subject not found in organization")
    activity = EntityActivityLog(
        organization_id=org_id,
        intended_parent_id=entity_id if entity_type == EntityType.INTENDED_PARENT.value else None,
        donor_id=entity_id if entity_type == EntityType.DONOR.value else None,
        activity_type=activity_type,
        actor_user_id=actor_user_id,
        details=details,
        occurred_at=occurred_at or datetime.now(UTC),
    )
    db.add(activity)
    db.flush()
    return activity


def _actor_names(
    db: Session,
    *,
    org_id: UUID,
    user_ids: Iterable[UUID | None],
) -> dict[UUID, str | None]:
    ids = {user_id for user_id in user_ids if user_id is not None}
    if not ids:
        return {}
    rows = (
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            User.id.in_(ids),
        )
        .all()
    )
    return {user_id: display_name for user_id, display_name in rows}


def _stage_labels(db: Session, *, org_id: UUID, stage_ids: set[UUID]) -> dict[UUID, str]:
    if not stage_ids:
        return {}
    rows = (
        db.query(PipelineStage.id, PipelineStage.label)
        .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
        .filter(
            Pipeline.organization_id == org_id,
            PipelineStage.id.in_(stage_ids),
        )
        .all()
    )
    return dict(rows)


def _status_items(
    db: Session,
    *,
    org_id: UUID,
    entity_type: ActivityEntityType,
    entity_id: UUID,
) -> list[ActivityItem]:
    if entity_type == EntityType.INTENDED_PARENT.value:
        rows = (
            db.query(IntendedParentStatusHistory)
            .join(
                IntendedParent,
                IntendedParent.id == IntendedParentStatusHistory.intended_parent_id,
            )
            .filter(
                IntendedParent.organization_id == org_id,
                IntendedParentStatusHistory.organization_id == org_id,
                IntendedParentStatusHistory.intended_parent_id == entity_id,
            )
            .all()
        )
        stage_ids = {
            stage_id
            for row in rows
            for stage_id in (row.old_stage_id, row.new_stage_id)
            if stage_id is not None
        }
        labels = _stage_labels(db, org_id=org_id, stage_ids=stage_ids)
        return [
            {
                "id": row.id,
                "activity_type": "status_changed",
                "actor_user_id": row.changed_by_user_id,
                "actor_name": None,
                "details": {
                    "from": row.old_label_snapshot
                    or labels.get(row.old_stage_id)
                    or ((row.old_status or "").replace("_", " ").title() or "Start"),
                    "to": row.new_label_snapshot
                    or labels.get(row.new_stage_id)
                    or row.new_status.replace("_", " ").title(),
                    "from_stage_id": str(row.old_stage_id) if row.old_stage_id else None,
                    "to_stage_id": str(row.new_stage_id) if row.new_stage_id else None,
                    "reason": row.reason,
                    "effective_at": row.effective_at.isoformat() if row.effective_at else None,
                    "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                    "is_undo": row.is_undo,
                },
                "created_at": row.effective_at or row.changed_at,
            }
            for row in rows
        ]

    rows = (
        db.query(DonorStatusHistory)
        .filter(
            DonorStatusHistory.organization_id == org_id,
            DonorStatusHistory.donor_id == entity_id,
        )
        .all()
    )
    return [
        {
            "id": row.id,
            "activity_type": "status_changed",
            "actor_user_id": row.changed_by_user_id,
            "actor_name": None,
            "details": {
                "from": row.old_label_snapshot or "Start",
                "to": row.new_label_snapshot,
                "from_stage_id": str(row.old_stage_id) if row.old_stage_id else None,
                "to_stage_id": str(row.new_stage_id) if row.new_stage_id else None,
                "reason": row.reason,
                "effective_at": row.effective_at.isoformat(),
                "recorded_at": row.recorded_at.isoformat(),
                "is_undo": row.is_undo,
            },
            "created_at": row.effective_at,
        }
        for row in rows
    ]


def list_entity_activity(
    db: Session,
    *,
    org_id: UUID,
    entity_type: ActivityEntityType,
    entity_id: UUID,
    page: int,
    per_page: int,
    include_note_previews: bool = False,
    include_task_previews: bool = False,
) -> tuple[list[ActivityItem], int]:
    """Combine shared entity sources into one deterministic, paginated feed."""
    entity_id_column = (
        Task.intended_parent_id
        if entity_type == EntityType.INTENDED_PARENT.value
        else Task.donor_id
    )
    attachment_id_column = (
        Attachment.intended_parent_id
        if entity_type == EntityType.INTENDED_PARENT.value
        else Attachment.donor_id
    )

    activity_id_column = (
        EntityActivityLog.intended_parent_id
        if entity_type == EntityType.INTENDED_PARENT.value
        else EntityActivityLog.donor_id
    )
    activity_rows = (
        db.query(EntityActivityLog)
        .filter(
            EntityActivityLog.organization_id == org_id,
            activity_id_column == entity_id,
        )
        .all()
    )
    notes = (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == org_id,
            EntityNote.entity_type == entity_type,
            EntityNote.entity_id == entity_id,
        )
        .all()
    )
    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            entity_id_column == entity_id,
        )
        .all()
    )
    attachments = (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == org_id,
            attachment_id_column == entity_id,
        )
        .all()
    )

    notes_by_id = {note.id: note for note in notes}
    tasks_by_id = {task.id: task for task in tasks}
    attachments_by_id = {attachment.id: attachment for attachment in attachments}

    items = _status_items(
        db,
        org_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    logged_events: set[tuple[str, str]] = set()
    for activity in activity_rows:
        details = dict(activity.details or {})
        for key, source_by_id, presentation_key, presentation_value, can_present in (
            (
                "note_id",
                notes_by_id,
                "preview",
                lambda source: _preview(source.content),
                include_note_previews,
            ),
            (
                "task_id",
                tasks_by_id,
                "title",
                lambda source: source.title,
                include_task_previews,
            ),
            (
                "attachment_id",
                attachments_by_id,
                "filename",
                lambda source: source.filename,
                True,
            ),
        ):
            source_id = details.get(key)
            if not source_id:
                continue
            try:
                source = source_by_id.get(UUID(str(source_id)))
            except TypeError, ValueError:
                source = None
            if source is not None and can_present:
                details[presentation_key] = presentation_value(source)
            logged_events.add((activity.activity_type, str(source_id)))
        items.append(
            {
                "id": activity.id,
                "activity_type": activity.activity_type,
                "actor_user_id": activity.actor_user_id,
                "actor_name": None,
                "details": details or None,
                "created_at": activity.occurred_at,
            }
        )

    items.extend(
        {
            "id": _synthetic_event_id(note.id, "note_added"),
            "activity_type": "note_added",
            "actor_user_id": note.author_id,
            "actor_name": None,
            "details": {
                "note_id": str(note.id),
                **({"preview": _preview(note.content)} if include_note_previews else {}),
            },
            "created_at": note.created_at,
        }
        for note in notes
        if ("note_added", str(note.id)) not in logged_events
    )
    for task in tasks:
        if ("task_created", str(task.id)) not in logged_events:
            items.append(
                {
                    "id": _synthetic_event_id(task.id, "task_created"),
                    "activity_type": "task_created",
                    "actor_user_id": task.created_by_user_id,
                    "actor_name": None,
                    "details": {
                        "task_id": str(task.id),
                        **(
                            {
                                "title": task.title,
                                "due_date": task.due_date.isoformat() if task.due_date else None,
                            }
                            if include_task_previews
                            else {}
                        ),
                    },
                    "created_at": task.created_at,
                }
            )
        if task.completed_at is not None and ("task_completed", str(task.id)) not in logged_events:
            items.append(
                {
                    "id": _synthetic_event_id(task.id, "task_completed"),
                    "activity_type": "task_completed",
                    "actor_user_id": task.completed_by_user_id,
                    "actor_name": None,
                    "details": {
                        "task_id": str(task.id),
                        **({"title": task.title} if include_task_previews else {}),
                    },
                    "created_at": task.completed_at,
                }
            )
    for attachment in attachments:
        if ("attachment_added", str(attachment.id)) not in logged_events:
            items.append(
                {
                    "id": _synthetic_event_id(attachment.id, "attachment_added"),
                    "activity_type": "attachment_added",
                    "actor_user_id": attachment.uploaded_by_user_id,
                    "actor_name": None,
                    "details": {
                        "attachment_id": str(attachment.id),
                        "filename": attachment.filename,
                    },
                    "created_at": attachment.created_at,
                }
            )
        if (
            attachment.deleted_at is not None
            and ("attachment_deleted", str(attachment.id)) not in logged_events
        ):
            items.append(
                {
                    "id": _synthetic_event_id(attachment.id, "attachment_deleted"),
                    "activity_type": "attachment_deleted",
                    "actor_user_id": attachment.deleted_by_user_id,
                    "actor_name": None,
                    "details": {
                        "attachment_id": str(attachment.id),
                        "filename": attachment.filename,
                    },
                    "created_at": attachment.deleted_at,
                }
            )

    names = _actor_names(
        db,
        org_id=org_id,
        user_ids=(item["actor_user_id"] for item in items),
    )
    for item in items:
        actor_user_id = item["actor_user_id"]
        item["actor_name"] = names.get(actor_user_id) if actor_user_id else None

    items.sort(key=lambda item: (item["created_at"], str(item["id"])), reverse=True)
    total = len(items)
    offset = (page - 1) * per_page
    return items[offset : offset + per_page], total
