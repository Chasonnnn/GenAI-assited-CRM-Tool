"""Meta form mapping service for lead conversion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID
from app.db.enums import OwnerType, Role, TaskType
from app.db.models import Membership, MetaForm, MetaFormVersion, MetaLead, Task
from app.schemas.task import TaskCreate
from app.services import import_detection_service, queue_service, task_service


def get_form(db: Session, org_id: UUID, form_id: UUID) -> MetaForm | None:
    return db.scalar(
        select(MetaForm).where(
            MetaForm.id == form_id,
            MetaForm.organization_id == org_id,
        )
    )


def get_form_by_external_id(
    db: Session,
    org_id: UUID,
    form_external_id: str | None,
) -> MetaForm | None:
    if not form_external_id:
        return None
    return db.scalar(
        select(MetaForm).where(
            MetaForm.organization_id == org_id,
            MetaForm.form_external_id == form_external_id,
        )
    )


def list_forms(db: Session, org_id: UUID) -> list[MetaForm]:
    return list(
        db.scalars(
            select(MetaForm)
            .where(MetaForm.organization_id == org_id)
            .order_by(MetaForm.updated_at.desc())
        ).all()
    )


def get_form_version(db: Session, form: MetaForm) -> MetaFormVersion | None:
    if not form.current_version_id:
        return None
    return db.get(MetaFormVersion, form.current_version_id)


def get_lead_stats(db: Session, org_id: UUID) -> dict[str, dict[str, object]]:
    rows = db.execute(
        select(
            MetaLead.meta_form_id,
            func.count(MetaLead.id).label("total"),
            func.count(MetaLead.id).filter(MetaLead.is_converted.is_(False)).label("unconverted"),
            func.max(MetaLead.received_at).label("last_lead_at"),
        )
        .where(MetaLead.organization_id == org_id)
        .group_by(MetaLead.meta_form_id)
    ).all()
    stats: dict[str, dict[str, object]] = {}
    for form_id, total, unconverted, last_lead_at in rows:
        if form_id:
            stats[str(form_id)] = {
                "total": int(total or 0),
                "unconverted": int(unconverted or 0),
                "last_lead_at": last_lead_at,
            }
    return stats


def build_mapping_preview(
    db: Session,
    form: MetaForm,
) -> dict:
    version = get_form_version(db, form)
    if not version:
        raise ValueError("Form has no schema version yet. Sync forms first.")

    questions = version.field_schema or []
    columns: list[dict[str, str | None]] = []
    analysis_headers: list[str] = []
    keys: list[str] = []

    for question in questions:
        key = question.get("key") or question.get("name")
        if not key:
            continue
        label = question.get("label") or question.get("title")
        q_type = question.get("type")
        columns.append({"key": key, "label": label, "question_type": q_type})
        keys.append(key)
        analysis_headers.append(label or key)

    # Pull sample rows from live leads if available
    leads = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == form.organization_id,
            MetaLead.meta_form_id == form.form_external_id,
        )
        .order_by(MetaLead.received_at.desc())
        .limit(5)
        .all()
    )

    sample_rows: list[dict[str, str]] = []
    has_live_leads = len(leads) > 0

    if has_live_leads:
        for lead in leads:
            raw = lead.field_data_raw or lead.field_data or {}
            row: dict[str, str] = {}
            for key in keys:
                value = raw.get(key)
                row[key] = _format_sample_value(value)
            sample_rows.append(row)
    else:
        # Generate dummy rows for mapping/testing (Zapier-style)
        for idx in range(3):
            row = {}
            for question in questions:
                key = question.get("key") or question.get("name")
                if not key:
                    continue
                row[key] = _generate_dummy_value(question, idx)
            if row:
                sample_rows.append(row)

    # Build sample matrix for column analysis
    sample_matrix = [[row.get(key, "") for key in keys] for row in sample_rows]

    suggestions = import_detection_service.analyze_columns(
        analysis_headers,
        sample_matrix,
        allowed_fields=import_detection_service.AVAILABLE_SURROGATE_FIELDS,
    )

    # Override csv_column to use question keys
    for idx, suggestion in enumerate(suggestions):
        if idx < len(keys):
            suggestion.csv_column = keys[idx]

    # AI availability (for optional AI mapping)
    from app.services.import_ai_mapper_service import is_ai_available

    ai_available = is_ai_available(db, form.organization_id)

    return {
        "columns": columns,
        "column_suggestions": suggestions,
        "sample_rows": sample_rows,
        "has_live_leads": has_live_leads,
        "available_fields": import_detection_service.AVAILABLE_SURROGATE_FIELDS,
        "ai_available": ai_available,
    }


def save_mapping(
    db: Session,
    form: MetaForm,
    *,
    column_mappings: list[dict],
    unknown_column_behavior: str,
    user_id: UUID,
) -> None:
    _validate_required_mappings(column_mappings)

    if not form.current_version_id:
        raise ValueError("Form has no schema version yet. Sync forms first.")

    form.mapping_rules = column_mappings
    form.unknown_column_behavior = unknown_column_behavior
    form.mapping_status = "mapped"
    form.mapping_version_id = form.current_version_id
    form.mapping_updated_at = datetime.now(timezone.utc)
    form.mapping_updated_by_user_id = user_id
    form.updated_at = datetime.now(timezone.utc)

    db.commit()


def ensure_mapping_review_task(
    db: Session,
    form: MetaForm,
    *,
    reason: str,
) -> None:
    """Create a task for admins to review mapping if one doesn't exist."""
    title = f"Review Meta form mapping: {form.form_name}"
    marker = f"Form ID: {form.id}"
    open_task = (
        db.query(Task)
        .filter(
            Task.organization_id == form.organization_id,
            Task.is_completed.is_(False),
            Task.title == title,
            Task.description.ilike(f"%{marker}%"),
        )
        .first()
    )
    if open_task:
        return

    owner_type, owner_id, created_by = _resolve_task_owner(db, form.organization_id)
    due_date = (datetime.now(timezone.utc) + timedelta(days=2)).date()

    task_data = TaskCreate(
        title=title,
        description=(
            f"Review Meta lead form mapping.\n"
            f"Form: {form.form_name}\n"
            f"Form ID: {form.form_external_id}\n"
            f"{marker}\n"
            f"Reason: {reason}\n"
            f"Go to Settings → Integrations → Meta → Manage lead forms."
        ),
        task_type=TaskType.REVIEW,
        owner_type=owner_type,
        owner_id=owner_id,
        due_date=due_date,
    )

    task_service.create_task(
        db=db,
        org_id=form.organization_id,
        user_id=created_by,
        data=task_data,
    )


def _resolve_task_owner(db: Session, org_id: UUID) -> tuple[str, UUID, UUID]:
    """Pick an admin/developer to own the mapping review task."""
    membership = (
        db.query(Membership)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            Membership.role.in_([Role.ADMIN, Role.DEVELOPER]),
        )
        .order_by(Membership.created_at.asc())
        .first()
    )
    if membership:
        return OwnerType.USER.value, membership.user_id, membership.user_id

    fallback = (
        db.query(Membership)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
        )
        .order_by(Membership.created_at.asc())
        .first()
    )
    if fallback:
        return OwnerType.USER.value, fallback.user_id, fallback.user_id

    queue = queue_service.get_or_create_default_queue(db, org_id)
    return OwnerType.QUEUE.value, queue.id, SYSTEM_USER_ID


def _validate_required_mappings(column_mappings: list[dict]) -> None:
    mapped_fields = {
        m.get("surrogate_field")
        for m in column_mappings
        if m.get("action") == "map" and m.get("surrogate_field")
    }
    if "full_name" not in mapped_fields or "email" not in mapped_fields:
        raise ValueError("Required fields missing: full_name and email must be mapped")

    for mapping in column_mappings:
        if mapping.get("action") == "map" and not mapping.get("surrogate_field"):
            raise ValueError("All mapped columns must select a surrogate field")


def _format_sample_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value)


def _generate_dummy_value(question: dict, idx: int) -> str:
    q_type = (question.get("type") or "").lower()
    label = (question.get("label") or "").lower()

    if "full_name" in q_type or "full name" in label:
        return f"Test User {idx + 1}"
    if "first_name" in q_type or "first name" in label:
        return "Test"
    if "last_name" in q_type or "last name" in label:
        return "User"
    if "email" in q_type or "email" in label:
        return f"test{idx + 1}@example.com"
    if "phone" in q_type or "phone" in label:
        return "+15551234567"
    if "date" in q_type or "date of birth" in label or "dob" in label:
        return "1990-01-15"
    if "zip" in q_type or "postal" in label:
        return "94105"
    if "state" in label:
        return "CA"
    if "number" in q_type:
        return str(idx + 1)
    if q_type in ("yes_no", "boolean", "checkbox"):
        return "Yes"

    options = question.get("options") or question.get("choices") or []
    if isinstance(options, list) and options:
        first = options[0]
        if isinstance(first, dict):
            return str(first.get("label") or first.get("value") or "Option A")
        return str(first)

    return "Sample response"
