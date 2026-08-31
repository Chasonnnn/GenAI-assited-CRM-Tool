"""Meta form mapping service for lead conversion."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID
from app.core.encryption import hash_email
from app.db.enums import OwnerType, Role, TaskType
from app.db.models import (
    Donor,
    Membership,
    MetaAd,
    MetaForm,
    MetaFormVersion,
    MetaLead,
    Surrogate,
    Task,
)
from app.schemas.task import TaskCreate
from app.services import import_detection_service, queue_service, task_service
from app.utils.normalization import normalize_email
from app.utils.pagination import paginate_query_by_offset

META_SYSTEM_COLUMNS: list[tuple[str, str]] = [
    ("meta_ad_id", "Ad ID"),
    ("meta_ad_name", "Ad name"),
    ("meta_form_name", "Form name"),
    ("meta_platform", "Platform"),
]
AUTO_SAFE_SCHEMA_KEYS = {"lead_id"}
TEST_LEAD_PATTERN = re.compile(r"test lead:|dummy data", re.IGNORECASE)
DONOR_META_MAPPING_FIELDS = ["full_name", "email", "phone", "state", "education", "source"]


def _schema_keys(field_schema: list[dict[str, object]] | None) -> set[str]:
    return {
        str(key)
        for item in (field_schema or [])
        for key in [item.get("key") or item.get("name")]
        if key
    }


def _should_preserve_mapping_for_schema_refresh(
    form: MetaForm,
    current_version: MetaFormVersion | None,
    current_keys: set[str],
    next_keys: set[str],
) -> bool:
    added_keys = next_keys - current_keys
    return bool(
        current_version
        and form.mapping_status == "mapped"
        and form.mapping_version_id == current_version.id
        and added_keys
        and added_keys.issubset(AUTO_SAFE_SCHEMA_KEYS)
    )


def get_form(db: Session, org_id: UUID, form_id: UUID) -> MetaForm | None:
    return db.scalar(
        select(MetaForm).where(
            MetaForm.id == form_id,
            MetaForm.organization_id == org_id,
        )
    )


def delete_form(db: Session, org_id: UUID, form_id: UUID) -> bool:
    form = get_form(db, org_id, form_id)
    if not form:
        return False
    db.delete(form)
    db.commit()
    return True


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


def list_active_forms(db: Session, org_id: UUID) -> list[MetaForm]:
    """List active Meta forms for an organization."""
    return list(
        db.scalars(
            select(MetaForm)
            .where(
                MetaForm.organization_id == org_id,
                MetaForm.is_active.is_(True),
            )
            .order_by(MetaForm.created_at.desc())
        ).all()
    )


def upsert_form_from_payload(
    db: Session,
    org_id: UUID,
    *,
    form_external_id: str | None,
    form_name: str | None,
    field_keys: list[str] | None = None,
    page_id: str | None = None,
) -> MetaForm | None:
    """Create or update a Meta form definition from inbound payload fields."""
    if not form_external_id:
        return None

    form = get_form_by_external_id(db, org_id, form_external_id)
    if not form:
        form = MetaForm(
            organization_id=org_id,
            page_id=page_id or "zapier",
            form_external_id=form_external_id,
            form_name=form_name or f"Form {form_external_id}",
        )
        db.add(form)
        db.flush()
    else:
        if form_name and form.form_name != form_name:
            form.form_name = form_name
        if page_id and form.page_id in {"zapier", "unknown"} and form.page_id != page_id:
            form.page_id = page_id

    unique_keys: list[str] = []
    seen_keys: set[str] = set()
    for key in field_keys or []:
        if not key:
            continue
        key_str = str(key)
        if key_str in seen_keys:
            continue
        seen_keys.add(key_str)
        unique_keys.append(key_str)

    questions: list[dict[str, str]] = []
    for key in unique_keys:
        label = key.replace("_", " ").strip().title()
        questions.append({"key": key, "label": label, "type": "text"})

    schema_json = json.dumps(questions, sort_keys=True)
    schema_hash = hashlib.sha256(schema_json.encode()).hexdigest()

    existing_version = db.scalar(
        select(MetaFormVersion).where(
            MetaFormVersion.form_id == form.id,
            MetaFormVersion.schema_hash == schema_hash,
        )
    )
    key_set = _schema_keys(questions)
    current = db.get(MetaFormVersion, form.current_version_id) if form.current_version_id else None
    current_keys = _schema_keys(current.field_schema if current else None)
    if not existing_version:
        versions = list(
            db.scalars(select(MetaFormVersion).where(MetaFormVersion.form_id == form.id)).all()
        )
        if current:
            if key_set.issubset(current_keys):
                existing_version = current
        if not existing_version:
            for version in versions:
                version_keys = _schema_keys(version.field_schema)
                if key_set.issubset(version_keys):
                    existing_version = version
                    break

    if not existing_version:
        max_version = (
            db.scalar(
                select(func.max(MetaFormVersion.version_number)).where(
                    MetaFormVersion.form_id == form.id
                )
            )
            or 0
        )
        new_version = MetaFormVersion(
            form_id=form.id,
            version_number=max_version + 1,
            field_schema=questions,
            schema_hash=schema_hash,
        )
        db.add(new_version)
        db.flush()
        form.current_version_id = new_version.id
        if form.mapping_version_id and form.mapping_version_id != new_version.id:
            if _should_preserve_mapping_for_schema_refresh(form, current, current_keys, key_set):
                form.mapping_version_id = new_version.id
            else:
                form.mapping_status = "outdated"
    else:
        form.current_version_id = existing_version.id
        if form.mapping_version_id and form.mapping_version_id != existing_version.id:
            if _should_preserve_mapping_for_schema_refresh(form, current, current_keys, key_set):
                form.mapping_version_id = existing_version.id
            else:
                form.mapping_status = "outdated"

    form.updated_at = datetime.now(UTC)
    return form


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


def get_donor_lead_form_external_ids(db: Session, org_id: UUID) -> set[str]:
    """Return form identifiers containing any donor-routed lead snapshot."""
    return {
        str(form_external_id)
        for form_external_id in db.scalars(
            select(MetaLead.meta_form_id)
            .where(
                MetaLead.organization_id == org_id,
                MetaLead.meta_form_id.isnot(None),
                MetaLead.lead_kind.in_({"egg_donor", "sperm_donor"}),
            )
            .distinct()
        ).all()
        if form_external_id
    }


def form_has_donor_leads(db: Session, org_id: UUID, form_external_id: str) -> bool:
    return bool(
        db.scalar(
            select(MetaLead.id)
            .where(
                MetaLead.organization_id == org_id,
                MetaLead.meta_form_id == form_external_id,
                MetaLead.lead_kind.in_({"egg_donor", "sperm_donor"}),
            )
            .limit(1)
        )
    )


def list_unconverted_leads_for_form(
    db: Session,
    org_id: UUID,
    form_external_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[MetaLead], int]:
    """Return unconverted leads and total count for a specific form."""
    base_query = db.query(MetaLead).filter(
        MetaLead.organization_id == org_id,
        MetaLead.meta_form_id == form_external_id,
        MetaLead.is_converted.is_(False),
    )
    items, total = paginate_query_by_offset(
        base_query.order_by(MetaLead.received_at.desc()),
        offset=offset,
        limit=limit,
        count_query=base_query,
    )
    return items, total


def get_reprocess_eligibility_for_leads(
    db: Session,
    org_id: UUID,
    leads: list[MetaLead],
    *,
    lead_kind: str = "surrogate",
) -> tuple[dict[UUID, str | None], dict[str, int]]:
    """Classify which unconverted leads are safe to reprocess automatically."""
    email_hashes: dict[UUID, str] = {}
    subject_group_by_lead: dict[UUID, str] = {}
    duplicate_hashes_within_batch: set[tuple[str, str]] = set()
    seen_hashes: set[tuple[str, str]] = set()
    hashes_by_subject_group: dict[str, set[str]] = {
        "surrogate": set(),
        "donor": set(),
    }

    for lead in leads:
        effective_lead_kind = getattr(lead, "lead_kind", None) or lead_kind
        subject_group = (
            "donor"
            if effective_lead_kind in {"egg_donor", "sperm_donor"}
            else "surrogate"
        )
        subject_group_by_lead[lead.id] = subject_group
        email = _extract_lead_email(lead)
        if not email:
            continue
        normalized = normalize_email(email)
        if not normalized:
            continue
        email_hash = hash_email(normalized)
        email_hashes[lead.id] = email_hash
        hashes_by_subject_group[subject_group].add(email_hash)
        subject_hash = (subject_group, email_hash)
        if subject_hash in seen_hashes:
            duplicate_hashes_within_batch.add(subject_hash)
        else:
            seen_hashes.add(subject_hash)

    existing_hashes_by_subject_group: dict[str, set[str]] = {
        "surrogate": set(),
        "donor": set(),
    }
    for subject_group, subject_model in (("surrogate", Surrogate), ("donor", Donor)):
        subject_hashes = hashes_by_subject_group[subject_group]
        if not subject_hashes:
            continue
        existing_hashes_by_subject_group[subject_group] = set(
            db.scalars(
                select(subject_model.email_hash).where(
                    subject_model.organization_id == org_id,
                    subject_model.is_archived.is_(False),
                    subject_model.email_hash.in_(subject_hashes),
                )
            ).all()
        )

    reasons_by_lead: dict[UUID, str | None] = {}
    reason_counts: dict[str, int] = {}
    for lead in leads:
        reason: str | None = None
        if _looks_like_test_lead(lead):
            reason = "test_lead"
        else:
            email_hash = email_hashes.get(lead.id)
            subject_group = subject_group_by_lead[lead.id]
            if email_hash and (
                email_hash in existing_hashes_by_subject_group[subject_group]
                or (subject_group, email_hash) in duplicate_hashes_within_batch
            ):
                reason = "duplicate_email"

        reasons_by_lead[lead.id] = reason
        if reason:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return reasons_by_lead, reason_counts


def get_reprocess_plan_for_form(
    db: Session,
    org_id: UUID,
    form_external_id: str,
) -> tuple[list[MetaLead], list[UUID], dict[UUID, str | None], dict[str, int]]:
    leads = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == org_id,
            MetaLead.meta_form_id == form_external_id,
            MetaLead.is_converted.is_(False),
        )
        .order_by(MetaLead.received_at.desc())
        .all()
    )
    form = get_form_by_external_id(db, org_id, form_external_id)
    lead_kind = form.lead_kind if form else "surrogate"
    reasons_by_lead, reason_counts = get_reprocess_eligibility_for_leads(
        db,
        org_id,
        leads,
        lead_kind=lead_kind,
    )
    eligible_ids = [lead.id for lead in leads if reasons_by_lead.get(lead.id) is None]
    return leads, eligible_ids, reasons_by_lead, reason_counts


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
                row["created_time"] = (datetime.now(UTC) - timedelta(days=idx)).isoformat()
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
    available_fields = (
        DONOR_META_MAPPING_FIELDS
        if form.lead_kind in {"egg_donor", "sperm_donor"}
        else import_detection_service.AVAILABLE_SURROGATE_FIELDS
    )
    suggestions = import_detection_service.analyze_columns_with_learning(
        db,
        form.organization_id,
        analysis_headers,
        sample_matrix,
        allowed_fields=available_fields,
    )

    system_keys = {key for key, _ in META_SYSTEM_COLUMNS}

    # Override csv_column to use question keys
    for idx, suggestion in enumerate(suggestions):
        if idx < len(keys):
            suggestion.csv_column = keys[idx]
            if keys[idx] in system_keys:
                if keys[idx] == "meta_platform" and suggestion.suggested_field == "source":
                    continue
                suggestion.default_action = "metadata"

    # AI availability (for optional AI mapping)
    from app.services.import_ai_mapper_service import is_ai_available

    ai_available = is_ai_available(db, form.organization_id)

    return {
        "columns": columns,
        "column_suggestions": suggestions,
        "sample_rows": sample_rows,
        "has_live_leads": has_live_leads,
        "available_fields": available_fields,
        "ai_available": ai_available,
    }


def save_mapping(
    db: Session,
    form: MetaForm,
    *,
    column_mappings: list[dict],
    unknown_column_behavior: str,
    lead_kind: str,
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
    if lead_kind not in {"surrogate", "egg_donor", "sperm_donor"}:
        raise ValueError("Unsupported Meta lead kind")
    _validate_required_mappings(column_mappings)
    _validate_mapping_targets(column_mappings, lead_kind)

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
    form.lead_kind = lead_kind
    form.mapping_status = "mapped"
    form.mapping_version_id = form.current_version_id
    form.mapping_updated_at = datetime.now(UTC)
    form.mapping_updated_by_user_id = user_id
    form.updated_at = datetime.now(UTC)

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
    due_date = (datetime.now(UTC) + timedelta(days=2)).date()

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


def _validate_mapping_targets(column_mappings: list[dict], lead_kind: str) -> None:
    if lead_kind not in {"egg_donor", "sperm_donor"}:
        return
    allowed_fields = set(DONOR_META_MAPPING_FIELDS)
    unsupported_fields = sorted(
        {
            str(mapping["surrogate_field"])
            for mapping in column_mappings
            if mapping.get("action") == "map"
            and mapping.get("surrogate_field")
            and mapping["surrogate_field"] not in allowed_fields
        }
    )
    if unsupported_fields:
        raise ValueError(
            "Unsupported donor mapping field(s): " + ", ".join(unsupported_fields)
        )


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


def _extract_lead_email(lead: MetaLead) -> str | None:
    raw = lead.field_data_raw or lead.field_data or {}
    value = raw.get("email")
    if value in (None, ""):
        return None
    return str(value)


def _looks_like_test_lead(lead: MetaLead) -> bool:
    raw = lead.field_data_raw or lead.field_data or {}
    candidates = [
        lead.meta_lead_id,
        raw.get("full_name"),
        raw.get("name"),
        raw.get("email"),
        raw.get("phone"),
        raw.get("phone_number"),
    ]
    haystack = " ".join(str(value) for value in candidates if value).strip()
    if not haystack:
        return False
    return bool(TEST_LEAD_PATTERN.search(haystack))
