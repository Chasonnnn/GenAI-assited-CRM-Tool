"""Meta form mapping service for lead conversion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID
from app.db.enums import OwnerType, Role, TaskType
from app.db.models import Membership, MetaAd, MetaForm, MetaFormVersion, MetaLead, Task
from app.schemas.task import TaskCreate
from app.services import import_detection_service, queue_service, task_service


META_SYSTEM_COLUMNS: list[tuple[str, str]] = [
    ("meta_ad_id", "Ad ID"),
    ("meta_ad_name", "Ad name"),
    ("meta_form_name", "Form name"),
    ("meta_platform", "Platform"),
]


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

    if "created_time" not in keys:
        columns.append(
            {
                "key": "created_time",
                "label": "Lead created time",
                "question_type": "meta",
            }
        )
        keys.append("created_time")
        analysis_headers.append("Lead created time")

    for key, label in META_SYSTEM_COLUMNS:
        if key not in keys:
            columns.append(
                {
                    "key": key,
                    "label": label,
                    "question_type": "meta",
                }
            )
            keys.append(key)
            analysis_headers.append(label)

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
                if key == "created_time":
                    value = lead.meta_created_time or lead.received_at
                    row[key] = value.isoformat() if value else ""
                elif key == "meta_ad_id":
                    row[key] = _format_sample_value(raw.get("meta_ad_id") or raw.get("ad_id"))
                elif key == "meta_ad_name":
                    ad_name = raw.get("meta_ad_name") or raw.get("ad_name")
                    if not ad_name:
                        ad_id = raw.get("meta_ad_id") or raw.get("ad_id")
                        if ad_id:
                            meta_ad = (
                                db.query(MetaAd)
                                .filter(
                                    MetaAd.organization_id == form.organization_id,
                                    MetaAd.ad_external_id == str(ad_id),
                                )
                                .first()
                            )
                            ad_name = meta_ad.ad_name if meta_ad else None
                    row[key] = _format_sample_value(ad_name)
                elif key == "meta_form_name":
                    row[key] = form.form_name or ""
                elif key == "meta_platform":
                    row[key] = _format_sample_value(
                        raw.get("meta_platform")
                        or raw.get("platform")
                        or raw.get("publisher_platform")
                    )
                else:
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
            if "created_time" in keys:
                row["created_time"] = (datetime.now(timezone.utc) - timedelta(days=idx)).isoformat()
            if "meta_ad_id" in keys:
                row["meta_ad_id"] = f"ad_{1000 + idx}"
            if "meta_ad_name" in keys:
                row["meta_ad_name"] = f"Sample Ad {idx + 1}"
            if "meta_form_name" in keys:
                row["meta_form_name"] = form.form_name
            if "meta_platform" in keys:
                row["meta_platform"] = "facebook" if idx % 2 == 0 else "instagram"
            if row:
                sample_rows.append(row)

    # Build sample matrix for column analysis
    sample_matrix = [[row.get(key, "") for key in keys] for row in sample_rows]

    # Analyze columns with learning from previous corrections
    suggestions = import_detection_service.analyze_columns_with_learning(
        db,
        form.organization_id,
        analysis_headers,
        sample_matrix,
        allowed_fields=import_detection_service.AVAILABLE_SURROGATE_FIELDS,
    )

    system_keys = {key for key, _ in META_SYSTEM_COLUMNS}

    # Override csv_column to use question keys
    for idx, suggestion in enumerate(suggestions):
        if idx < len(keys):
            suggestion.csv_column = keys[idx]
            if keys[idx] in system_keys:
                suggestion.default_action = "metadata"

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
    original_suggestions: list[dict] | None = None,
) -> None:
    """
    Save Meta form mapping and store corrections for learning.

    Args:
        db: Database session
        form: MetaForm to update
        column_mappings: Final user-approved mappings
        unknown_column_behavior: How to handle unknown columns
        user_id: User saving the mapping
        original_suggestions: Optional list of original suggestions for learning
    """
    _validate_required_mappings(column_mappings)

    if not form.current_version_id:
        raise ValueError("Form has no schema version yet. Sync forms first.")

    # Store corrections for learning (before saving)
    if original_suggestions:
        from app.services.import_service import ColumnMapping, store_mapping_corrections

        # Convert final mappings to ColumnMapping format
        # column_mappings can use csv_column (from API) or key (from form schema)
        final_mappings = [
            ColumnMapping(
                csv_column=m.get("csv_column", m.get("form_field", m.get("key", ""))),
                surrogate_field=m.get("surrogate_field"),
                transformation=m.get("transformation"),
                action=m.get("action", "map"),
                custom_field_key=m.get("custom_field_key"),
            )
            for m in column_mappings
        ]

        # Convert original suggestions to dict format
        # original_suggestions use csv_column (from analyze_columns)
        original_dicts = [
            {
                "csv_column": s.get("csv_column", s.get("form_field", s.get("key", ""))),
                "suggested_field": s.get("suggested_field"),
            }
            for s in original_suggestions
        ]

        store_mapping_corrections(db, form.organization_id, original_dicts, final_mappings)

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
