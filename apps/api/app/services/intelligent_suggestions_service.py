"""Services for intelligent suggestions and dynamic surrogate lead filters."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Iterable
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.enums import (
    AppointmentStatus,
    NotificationType,
    OwnerType,
    Role,
    SurrogateActivityType,
)
from app.db.models import (
    Appointment,
    Membership,
    Organization,
    OrgIntelligentSuggestionRule,
    OrgIntelligentSuggestionSettings,
    Pipeline,
    PipelineStage,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    User,
)
from app.services import dashboard_service, notification_facade
from app.utils.business_hours import is_business_day

# Dynamic filter values used by /surrogates endpoint.
FILTER_INTELLIGENT_ANY = "intelligent_any"
FILTER_INTELLIGENT_NEW_UNREAD = "intelligent_new_unread_stale"
FILTER_INTELLIGENT_MEETING_OUTCOME = "intelligent_meeting_outcome_missing"
FILTER_INTELLIGENT_STUCK_PREAPPROVAL = "intelligent_stuck_preapproval"
FILTER_ATTENTION_UNREACHED = "attention_unreached"
FILTER_ATTENTION_STUCK = "attention_stuck"

ALLOWED_DYNAMIC_FILTERS = {
    FILTER_INTELLIGENT_ANY,
    FILTER_INTELLIGENT_NEW_UNREAD,
    FILTER_INTELLIGENT_MEETING_OUTCOME,
    FILTER_INTELLIGENT_STUCK_PREAPPROVAL,
    FILTER_ATTENTION_UNREACHED,
    FILTER_ATTENTION_STUCK,
}

INTAKE_PREAPPROVAL_STAGE_SLUGS = (
    "contacted",
    "qualified",
    "interview_scheduled",
    "application_submitted",
    "under_review",
)

INTELLIGENT_RULE_KEYS = (
    FILTER_INTELLIGENT_NEW_UNREAD,
    FILTER_INTELLIGENT_MEETING_OUTCOME,
    FILTER_INTELLIGENT_STUCK_PREAPPROVAL,
)

RULE_KIND_STAGE_INACTIVITY = "stage_inactivity"
RULE_KIND_MEETING_OUTCOME_MISSING = "meeting_outcome_missing"

TEMPLATE_NEW_UNREAD_FOLLOWUP = "new_unread_followup"
TEMPLATE_STAGE_FOLLOWUP_CUSTOM = "stage_followup_custom"
TEMPLATE_PREAPPROVAL_STUCK = "preapproval_stuck"
TEMPLATE_MEETING_OUTCOME_MISSING = "meeting_outcome_missing"

STAGE_FOLLOWUP_TEMPLATE_DEFS = [
    {
        "template_key": TEMPLATE_NEW_UNREAD_FOLLOWUP,
        "name": "New unread follow-up",
        "description": "No updates after X business days in New Unread.",
        "default_stage_slug": "new_unread",
        "default_business_days": 1,
        "is_default": True,
    },
    {
        "template_key": "contacted_followup",
        "name": "Contacted follow-up",
        "description": "No updates after X business days in Contacted.",
        "default_stage_slug": "contacted",
        "default_business_days": 2,
        "is_default": False,
    },
    {
        "template_key": "qualified_followup",
        "name": "Qualified follow-up",
        "description": "No updates after X business days in Qualified.",
        "default_stage_slug": "qualified",
        "default_business_days": 2,
        "is_default": False,
    },
    {
        "template_key": "interview_scheduled_followup",
        "name": "Interview scheduled follow-up",
        "description": "No updates after X business days in Interview Scheduled.",
        "default_stage_slug": "interview_scheduled",
        "default_business_days": 1,
        "is_default": False,
    },
    {
        "template_key": "application_submitted_followup",
        "name": "Application submitted follow-up",
        "description": "No updates after X business days in Application Submitted.",
        "default_stage_slug": "application_submitted",
        "default_business_days": 2,
        "is_default": False,
    },
    {
        "template_key": "under_review_followup",
        "name": "Under review follow-up",
        "description": "No updates after X business days in Under Review.",
        "default_stage_slug": "under_review",
        "default_business_days": 3,
        "is_default": False,
    },
    {
        "template_key": "approved_followup",
        "name": "Approved follow-up",
        "description": "No updates after X business days in Approved.",
        "default_stage_slug": "approved",
        "default_business_days": 3,
        "is_default": False,
    },
    {
        "template_key": "ready_to_match_followup",
        "name": "Ready to match follow-up",
        "description": "No updates after X business days in Ready to Match.",
        "default_stage_slug": "ready_to_match",
        "default_business_days": 3,
        "is_default": False,
    },
    {
        "template_key": "matched_followup",
        "name": "Matched follow-up",
        "description": "No updates after X business days in Matched.",
        "default_stage_slug": "matched",
        "default_business_days": 5,
        "is_default": False,
    },
    {
        "template_key": "medical_clearance_followup",
        "name": "Medical clearance follow-up",
        "description": "No updates after X business days in Medical Clearance Passed.",
        "default_stage_slug": "medical_clearance_passed",
        "default_business_days": 3,
        "is_default": False,
    },
    {
        "template_key": "legal_clearance_followup",
        "name": "Legal clearance follow-up",
        "description": "No updates after X business days in Legal Clearance Passed.",
        "default_stage_slug": "legal_clearance_passed",
        "default_business_days": 3,
        "is_default": False,
    },
    {
        "template_key": "transfer_cycle_followup",
        "name": "Transfer cycle follow-up",
        "description": "No updates after X business days in Transfer Cycle.",
        "default_stage_slug": "transfer_cycle",
        "default_business_days": 4,
        "is_default": False,
    },
    {
        "template_key": "second_hcg_followup",
        "name": "Second HCG follow-up",
        "description": "No updates after X business days in Second HCG Confirmed.",
        "default_stage_slug": "second_hcg_confirmed",
        "default_business_days": 4,
        "is_default": False,
    },
    {
        "template_key": "heartbeat_followup",
        "name": "Heartbeat follow-up",
        "description": "No updates after X business days in Heartbeat Confirmed.",
        "default_stage_slug": "heartbeat_confirmed",
        "default_business_days": 5,
        "is_default": False,
    },
    {
        "template_key": "ob_care_followup",
        "name": "OB care follow-up",
        "description": "No updates after X business days in OB Care Established.",
        "default_stage_slug": "ob_care_established",
        "default_business_days": 5,
        "is_default": False,
    },
    {
        "template_key": "anatomy_scan_followup",
        "name": "Anatomy scan follow-up",
        "description": "No updates after X business days in Anatomy Scanned.",
        "default_stage_slug": "anatomy_scanned",
        "default_business_days": 7,
        "is_default": False,
    },
]

RULE_TEMPLATES = [
    {
        "template_key": TEMPLATE_STAGE_FOLLOWUP_CUSTOM,
        "name": "Custom stage follow-up",
        "description": "No updates after X business days at a selected stage.",
        "rule_kind": RULE_KIND_STAGE_INACTIVITY,
        "default_stage_slug": "new_unread",
        "default_business_days": 2,
        "is_default": False,
    },
    *[
        {
            "template_key": template["template_key"],
            "name": template["name"],
            "description": template["description"],
            "rule_kind": RULE_KIND_STAGE_INACTIVITY,
            "default_stage_slug": template["default_stage_slug"],
            "default_business_days": template["default_business_days"],
            "is_default": template["is_default"],
        }
        for template in STAGE_FOLLOWUP_TEMPLATE_DEFS
    ],
    {
        "template_key": TEMPLATE_PREAPPROVAL_STUCK,
        "name": "Pre-approval stuck",
        "description": "No updates after X business days across intake pre-approval stages.",
        "rule_kind": RULE_KIND_STAGE_INACTIVITY,
        "default_stage_slug": None,
        "default_business_days": 5,
        "is_default": True,
    },
    {
        "template_key": TEMPLATE_MEETING_OUTCOME_MISSING,
        "name": "Meeting outcome missing",
        "description": "Interview outcome still missing X business days after a meeting.",
        "rule_kind": RULE_KIND_MEETING_OUTCOME_MISSING,
        "default_stage_slug": None,
        "default_business_days": 1,
        "is_default": True,
    },
]

RULE_TEMPLATE_MAP = {template["template_key"]: template for template in RULE_TEMPLATES}

DEFAULTS = {
    "enabled": True,
    "new_unread_enabled": True,
    "new_unread_business_days": 1,
    "meeting_outcome_enabled": True,
    "meeting_outcome_business_days": 1,
    "stuck_enabled": True,
    "stuck_business_days": 5,
    "daily_digest_enabled": True,
    "digest_hour_local": 9,
}


def _to_role_value(role: Role | str | None) -> str:
    if isinstance(role, Role):
        return role.value
    return (role or "").strip().lower()


def _strict_owner_filters(role: Role | str | None, user_id: UUID) -> list:
    role_value = _to_role_value(role)
    if role_value in {Role.INTAKE_SPECIALIST.value, Role.CASE_MANAGER.value}:
        return [
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.owner_id == user_id,
        ]
    return []


def _business_days_elapsed(
    *,
    start_at_utc: datetime,
    end_at_utc: datetime,
    timezone_name: str,
) -> int:
    """Return elapsed business days between two UTC timestamps in org local timezone."""
    tz = ZoneInfo(timezone_name)
    start_local_date = start_at_utc.astimezone(tz).date()
    end_local_date = end_at_utc.astimezone(tz).date()
    if end_local_date <= start_local_date:
        return 0

    days = 0
    cursor = start_local_date
    while cursor < end_local_date:
        cursor += timedelta(days=1)
        local_dt = datetime.combine(cursor, time.min, tzinfo=tz)
        if is_business_day(local_dt):
            days += 1
    return days


def get_or_create_settings(
    db: Session,
    organization_id: UUID,
) -> OrgIntelligentSuggestionSettings:
    settings = (
        db.query(OrgIntelligentSuggestionSettings)
        .filter(OrgIntelligentSuggestionSettings.organization_id == organization_id)
        .first()
    )
    if settings:
        return settings

    settings = OrgIntelligentSuggestionSettings(organization_id=organization_id, **DEFAULTS)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def serialize_settings(settings: OrgIntelligentSuggestionSettings) -> dict:
    return {
        "enabled": settings.enabled,
        "new_unread_enabled": settings.new_unread_enabled,
        "new_unread_business_days": settings.new_unread_business_days,
        "meeting_outcome_enabled": settings.meeting_outcome_enabled,
        "meeting_outcome_business_days": settings.meeting_outcome_business_days,
        "stuck_enabled": settings.stuck_enabled,
        "stuck_business_days": settings.stuck_business_days,
        "daily_digest_enabled": settings.daily_digest_enabled,
        "digest_hour_local": settings.digest_hour_local,
    }


def update_settings(
    db: Session,
    organization_id: UUID,
    updates: dict,
) -> OrgIntelligentSuggestionSettings:
    settings = get_or_create_settings(db, organization_id)
    for key, value in updates.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings


def list_rule_templates() -> list[dict]:
    return [dict(template) for template in RULE_TEMPLATES]


def serialize_rule(rule: OrgIntelligentSuggestionRule) -> dict:
    return {
        "id": str(rule.id),
        "organization_id": str(rule.organization_id),
        "template_key": rule.template_key,
        "name": rule.name,
        "rule_kind": rule.rule_kind,
        "stage_slug": rule.stage_slug,
        "business_days": rule.business_days,
        "enabled": rule.enabled,
        "sort_order": rule.sort_order,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _stage_slug_exists_for_org(db: Session, org_id: UUID, stage_slug: str) -> bool:
    return (
        db.query(PipelineStage.id)
        .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
        .filter(
            Pipeline.organization_id == org_id,
            PipelineStage.slug == stage_slug,
            PipelineStage.is_active.is_(True),
        )
        .first()
        is not None
    )


def _validate_rule_payload(
    db: Session,
    *,
    org_id: UUID,
    template_key: str,
    rule_kind: str,
    stage_slug: str | None,
) -> None:
    template = RULE_TEMPLATE_MAP.get(template_key)
    if not template:
        raise ValueError("Unknown template_key")

    if rule_kind != template["rule_kind"]:
        raise ValueError("rule_kind does not match template")

    if rule_kind == RULE_KIND_STAGE_INACTIVITY:
        if template_key == TEMPLATE_PREAPPROVAL_STUCK:
            return
        if not stage_slug:
            raise ValueError("stage_slug is required for stage inactivity rules")
        if not _stage_slug_exists_for_org(db, org_id, stage_slug):
            raise ValueError("stage_slug is not valid for this organization")
    else:
        # Meeting outcome rules ignore stage.
        if stage_slug:
            raise ValueError("stage_slug is not allowed for meeting outcome rules")


def _default_rules_from_settings(
    settings: OrgIntelligentSuggestionSettings,
) -> list[dict]:
    return [
        {
            "template_key": TEMPLATE_NEW_UNREAD_FOLLOWUP,
            "name": "New unread follow-up",
            "rule_kind": RULE_KIND_STAGE_INACTIVITY,
            "stage_slug": "new_unread",
            "business_days": settings.new_unread_business_days,
            "enabled": settings.new_unread_enabled,
            "sort_order": 0,
        },
        {
            "template_key": TEMPLATE_MEETING_OUTCOME_MISSING,
            "name": "Meeting outcome missing",
            "rule_kind": RULE_KIND_MEETING_OUTCOME_MISSING,
            "stage_slug": None,
            "business_days": settings.meeting_outcome_business_days,
            "enabled": settings.meeting_outcome_enabled,
            "sort_order": 1,
        },
        {
            "template_key": TEMPLATE_PREAPPROVAL_STUCK,
            "name": "Pre-approval stuck",
            "rule_kind": RULE_KIND_STAGE_INACTIVITY,
            "stage_slug": None,
            "business_days": settings.stuck_business_days,
            "enabled": settings.stuck_enabled,
            "sort_order": 2,
        },
    ]


def _ensure_default_rules(db: Session, org_id: UUID) -> None:
    existing_count = (
        db.query(func.count(OrgIntelligentSuggestionRule.id))
        .filter(OrgIntelligentSuggestionRule.organization_id == org_id)
        .scalar()
        or 0
    )
    if existing_count > 0:
        return

    settings = get_or_create_settings(db, org_id)
    for payload in _default_rules_from_settings(settings):
        db.add(
            OrgIntelligentSuggestionRule(
                organization_id=org_id,
                template_key=payload["template_key"],
                name=payload["name"],
                rule_kind=payload["rule_kind"],
                stage_slug=payload["stage_slug"],
                business_days=payload["business_days"],
                enabled=payload["enabled"],
                sort_order=payload["sort_order"],
            )
        )
    db.commit()


def list_rules(db: Session, organization_id: UUID) -> list[OrgIntelligentSuggestionRule]:
    _ensure_default_rules(db, organization_id)
    return (
        db.query(OrgIntelligentSuggestionRule)
        .filter(OrgIntelligentSuggestionRule.organization_id == organization_id)
        .order_by(
            OrgIntelligentSuggestionRule.sort_order.asc(),
            OrgIntelligentSuggestionRule.created_at.asc(),
        )
        .all()
    )


def create_rule(db: Session, organization_id: UUID, payload: dict) -> OrgIntelligentSuggestionRule:
    template_key = str(payload.get("template_key") or "").strip()
    template = RULE_TEMPLATE_MAP.get(template_key)
    if not template:
        raise ValueError("Unknown template_key")

    rule_kind = str(payload.get("rule_kind") or template["rule_kind"]).strip()
    stage_slug = payload.get("stage_slug")
    if isinstance(stage_slug, str):
        stage_slug = stage_slug.strip() or None
    business_days = int(payload.get("business_days") or template["default_business_days"])
    enabled = bool(payload.get("enabled", True))
    name = str(payload.get("name") or template["name"]).strip() or template["name"]

    _validate_rule_payload(
        db,
        org_id=organization_id,
        template_key=template_key,
        rule_kind=rule_kind,
        stage_slug=stage_slug,
    )

    if business_days < 1 or business_days > 60:
        raise ValueError("business_days must be between 1 and 60")

    max_sort = (
        db.query(func.max(OrgIntelligentSuggestionRule.sort_order))
        .filter(OrgIntelligentSuggestionRule.organization_id == organization_id)
        .scalar()
    )
    sort_order = int(max_sort or 0) + 1

    rule = OrgIntelligentSuggestionRule(
        organization_id=organization_id,
        template_key=template_key,
        name=name,
        rule_kind=rule_kind,
        stage_slug=stage_slug,
        business_days=business_days,
        enabled=enabled,
        sort_order=sort_order,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(
    db: Session,
    organization_id: UUID,
    rule_id: UUID,
    updates: dict,
) -> OrgIntelligentSuggestionRule:
    rule = (
        db.query(OrgIntelligentSuggestionRule)
        .filter(
            OrgIntelligentSuggestionRule.id == rule_id,
            OrgIntelligentSuggestionRule.organization_id == organization_id,
        )
        .first()
    )
    if not rule:
        raise ValueError("Rule not found")

    template_key = str(updates.get("template_key") or rule.template_key).strip()
    rule_kind = str(updates.get("rule_kind") or rule.rule_kind).strip()
    stage_slug = updates.get("stage_slug", rule.stage_slug)
    if isinstance(stage_slug, str):
        stage_slug = stage_slug.strip() or None

    _validate_rule_payload(
        db,
        org_id=organization_id,
        template_key=template_key,
        rule_kind=rule_kind,
        stage_slug=stage_slug,
    )

    if "business_days" in updates:
        business_days = int(updates["business_days"])
        if business_days < 1 or business_days > 60:
            raise ValueError("business_days must be between 1 and 60")
        rule.business_days = business_days

    if "enabled" in updates:
        rule.enabled = bool(updates["enabled"])
    if "name" in updates:
        next_name = str(updates["name"] or "").strip()
        if not next_name:
            raise ValueError("name cannot be empty")
        rule.name = next_name
    if "sort_order" in updates:
        rule.sort_order = int(updates["sort_order"])

    rule.template_key = template_key
    rule.rule_kind = rule_kind
    rule.stage_slug = stage_slug

    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, organization_id: UUID, rule_id: UUID) -> None:
    rule = (
        db.query(OrgIntelligentSuggestionRule)
        .filter(
            OrgIntelligentSuggestionRule.id == rule_id,
            OrgIntelligentSuggestionRule.organization_id == organization_id,
        )
        .first()
    )
    if not rule:
        raise ValueError("Rule not found")
    db.delete(rule)
    db.commit()


def _stage_inactivity_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    threshold_business_days: int,
    now_utc: datetime,
    org_tz: str,
    stage_slug: str | None,
    template_key: str,
) -> set[UUID]:
    latest_activity_subquery = (
        db.query(
            SurrogateActivityLog.surrogate_id.label("surrogate_id"),
            func.max(SurrogateActivityLog.created_at).label("last_activity_at"),
        )
        .filter(SurrogateActivityLog.organization_id == org_id)
        .group_by(SurrogateActivityLog.surrogate_id)
        .subquery()
    )
    last_activity_col = func.coalesce(
        latest_activity_subquery.c.last_activity_at,
        Surrogate.created_at,
    ).label("last_activity_at")

    query = (
        db.query(Surrogate.id, last_activity_col)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_activity_subquery,
            latest_activity_subquery.c.surrogate_id == Surrogate.id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            *_strict_owner_filters(user_role, user_id),
        )
    )

    if template_key == TEMPLATE_PREAPPROVAL_STUCK and stage_slug is None:
        query = query.filter(PipelineStage.slug.in_(INTAKE_PREAPPROVAL_STAGE_SLUGS))
    elif stage_slug:
        query = query.filter(PipelineStage.slug == stage_slug)
    else:
        return set()

    matched: set[UUID] = set()
    for surrogate_id, last_activity_at in query.all():
        if last_activity_at is None:
            continue
        if (
            _business_days_elapsed(
                start_at_utc=last_activity_at,
                end_at_utc=now_utc,
                timezone_name=org_tz,
            )
            >= threshold_business_days
        ):
            matched.add(surrogate_id)
    return matched


def _meeting_outcome_missing_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    threshold_business_days: int,
    now_utc: datetime,
    org_tz: str,
) -> set[UUID]:
    meeting_anchor = func.coalesce(
        Appointment.meeting_ended_at,
        Appointment.scheduled_end,
        Appointment.scheduled_start,
    )
    latest_meeting_subquery = (
        db.query(
            Appointment.surrogate_id.label("surrogate_id"),
            func.max(meeting_anchor).label("latest_meeting_at"),
        )
        .filter(
            Appointment.organization_id == org_id,
            Appointment.surrogate_id.is_not(None),
            Appointment.status.in_(
                [
                    AppointmentStatus.CONFIRMED.value,
                    AppointmentStatus.COMPLETED.value,
                    AppointmentStatus.NO_SHOW.value,
                ]
            ),
        )
        .group_by(Appointment.surrogate_id)
        .subquery()
    )
    latest_outcome_subquery = (
        db.query(
            SurrogateActivityLog.surrogate_id.label("surrogate_id"),
            func.max(SurrogateActivityLog.created_at).label("latest_outcome_at"),
        )
        .filter(
            SurrogateActivityLog.organization_id == org_id,
            SurrogateActivityLog.activity_type
            == SurrogateActivityType.INTERVIEW_OUTCOME_LOGGED.value,
        )
        .group_by(SurrogateActivityLog.surrogate_id)
        .subquery()
    )

    query = (
        db.query(
            Surrogate.id,
            latest_meeting_subquery.c.latest_meeting_at,
            latest_outcome_subquery.c.latest_outcome_at,
        )
        .outerjoin(
            latest_meeting_subquery,
            latest_meeting_subquery.c.surrogate_id == Surrogate.id,
        )
        .outerjoin(
            latest_outcome_subquery,
            latest_outcome_subquery.c.surrogate_id == Surrogate.id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            latest_meeting_subquery.c.latest_meeting_at.is_not(None),
            latest_meeting_subquery.c.latest_meeting_at <= now_utc,
            or_(
                latest_outcome_subquery.c.latest_outcome_at.is_(None),
                latest_outcome_subquery.c.latest_outcome_at
                <= latest_meeting_subquery.c.latest_meeting_at,
            ),
            *_strict_owner_filters(user_role, user_id),
        )
    )

    matched: set[UUID] = set()
    for surrogate_id, latest_meeting_at, _latest_outcome_at in query.all():
        if latest_meeting_at is None:
            continue
        if (
            _business_days_elapsed(
                start_at_utc=latest_meeting_at,
                end_at_utc=now_utc,
                timezone_name=org_tz,
            )
            >= threshold_business_days
        ):
            matched.add(surrogate_id)
    return matched


def _attention_owner_filters(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
) -> list:
    owner_only = dashboard_service._should_scope_attention_to_owner(db, org_id, user_id, user_role)
    effective_owner_id = user_id if owner_only else None
    if effective_owner_id:
        return [
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.owner_id == effective_owner_id,
        ]
    if owner_only:
        return [Surrogate.id.is_(None)]
    return []


def _attention_unreached_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    now_utc: datetime,
) -> set[UUID]:
    cutoff = now_utc - timedelta(days=7)
    owner_filters = _attention_owner_filters(
        db, org_id=org_id, user_id=user_id, user_role=user_role
    )
    latest_activity_subquery = (
        db.query(
            SurrogateActivityLog.surrogate_id.label("surrogate_id"),
            func.max(SurrogateActivityLog.created_at).label("last_activity_at"),
        )
        .filter(SurrogateActivityLog.organization_id == org_id)
        .group_by(SurrogateActivityLog.surrogate_id)
        .subquery()
    )
    last_touch_at = func.coalesce(
        latest_activity_subquery.c.last_activity_at,
        Surrogate.updated_at,
        Surrogate.created_at,
    )
    rows = (
        db.query(Surrogate.id)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_activity_subquery,
            latest_activity_subquery.c.surrogate_id == Surrogate.id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.stage_type == "intake",
            PipelineStage.order <= 2,
            Surrogate.created_at < cutoff,
            last_touch_at < cutoff,
            or_(Surrogate.last_contacted_at.is_(None), Surrogate.last_contacted_at < cutoff),
            *owner_filters,
        )
        .all()
    )
    return {row[0] for row in rows}


def _attention_stuck_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    now_utc: datetime,
) -> set[UUID]:
    owner_filters = _attention_owner_filters(
        db, org_id=org_id, user_id=user_id, user_role=user_role
    )
    cutoff = now_utc - timedelta(days=30)

    latest_stage_change_subquery = (
        db.query(
            SurrogateStatusHistory.surrogate_id.label("surrogate_id"),
            func.max(SurrogateStatusHistory.changed_at).label("last_change_at"),
        )
        .filter(
            SurrogateStatusHistory.organization_id == org_id,
            SurrogateStatusHistory.to_stage_id.is_not(None),
        )
        .group_by(SurrogateStatusHistory.surrogate_id)
        .subquery()
    )
    last_change_col = func.coalesce(
        latest_stage_change_subquery.c.last_change_at,
        Surrogate.created_at,
    )
    rows = (
        db.query(Surrogate.id)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_stage_change_subquery,
            latest_stage_change_subquery.c.surrogate_id == Surrogate.id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.stage_type == "intake",
            last_change_col < cutoff,
            *owner_filters,
        )
        .all()
    )
    return {row[0] for row in rows}


def _rule_ids_for_user(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    now_utc: datetime,
) -> tuple[list[OrgIntelligentSuggestionRule], dict[UUID, set[UUID]]]:
    settings = get_or_create_settings(db, org_id)
    if not settings.enabled:
        return [], {}

    org_tz = db.query(Organization.timezone).filter(Organization.id == org_id).scalar() or "UTC"
    rules = [rule for rule in list_rules(db, org_id) if rule.enabled]

    results: dict[UUID, set[UUID]] = {}
    for rule in rules:
        if rule.rule_kind == RULE_KIND_STAGE_INACTIVITY:
            results[rule.id] = _stage_inactivity_ids(
                db,
                org_id=org_id,
                user_id=user_id,
                user_role=user_role,
                threshold_business_days=rule.business_days,
                now_utc=now_utc,
                org_tz=org_tz,
                stage_slug=rule.stage_slug,
                template_key=rule.template_key,
            )
        elif rule.rule_kind == RULE_KIND_MEETING_OUTCOME_MISSING:
            results[rule.id] = _meeting_outcome_missing_ids(
                db,
                org_id=org_id,
                user_id=user_id,
                user_role=user_role,
                threshold_business_days=rule.business_days,
                now_utc=now_utc,
                org_tz=org_tz,
            )
        else:
            results[rule.id] = set()

    return rules, results


def get_intelligent_rule_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    rule_key: str,
    now_utc: datetime | None = None,
) -> set[UUID]:
    now_utc = now_utc or datetime.now(timezone.utc)
    rules, results = _rule_ids_for_user(
        db,
        org_id=org_id,
        user_id=user_id,
        user_role=user_role,
        now_utc=now_utc,
    )
    if not rules:
        return set()

    matched: set[UUID] = set()
    for rule in rules:
        rule_ids = results.get(rule.id, set())
        if rule_key == FILTER_INTELLIGENT_NEW_UNREAD:
            if rule.template_key == TEMPLATE_NEW_UNREAD_FOLLOWUP or rule.stage_slug == "new_unread":
                matched.update(rule_ids)
        elif rule_key == FILTER_INTELLIGENT_MEETING_OUTCOME:
            if rule.rule_kind == RULE_KIND_MEETING_OUTCOME_MISSING:
                matched.update(rule_ids)
        elif rule_key == FILTER_INTELLIGENT_STUCK_PREAPPROVAL:
            if rule.template_key == TEMPLATE_PREAPPROVAL_STUCK:
                matched.update(rule_ids)

    return matched


def get_intelligent_summary(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    now_utc: datetime | None = None,
) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    counts = {rule_key: 0 for rule_key in INTELLIGENT_RULE_KEYS}
    settings = get_or_create_settings(db, org_id)
    if not settings.enabled:
        return {"total": 0, "counts": counts, "rules": []}

    rules, results = _rule_ids_for_user(
        db,
        org_id=org_id,
        user_id=user_id,
        user_role=user_role,
        now_utc=now_utc,
    )

    for rule in rules:
        rule_ids = results.get(rule.id, set())
        if rule.template_key == TEMPLATE_NEW_UNREAD_FOLLOWUP or rule.stage_slug == "new_unread":
            counts[FILTER_INTELLIGENT_NEW_UNREAD] += len(rule_ids)
        if rule.rule_kind == RULE_KIND_MEETING_OUTCOME_MISSING:
            counts[FILTER_INTELLIGENT_MEETING_OUTCOME] += len(rule_ids)
        if rule.template_key == TEMPLATE_PREAPPROVAL_STUCK:
            counts[FILTER_INTELLIGENT_STUCK_PREAPPROVAL] += len(rule_ids)

    total = len({sid for ids in results.values() for sid in ids})
    rule_summaries = []
    for rule in rules:
        serialized = serialize_rule(rule)
        serialized["match_count"] = len(results.get(rule.id, set()))
        rule_summaries.append(serialized)

    return {
        "total": total,
        "counts": counts,
        "rules": rule_summaries,
    }


def get_dynamic_filter_surrogate_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    dynamic_filter: str,
    now_utc: datetime | None = None,
) -> set[UUID]:
    now_utc = now_utc or datetime.now(timezone.utc)

    if dynamic_filter == FILTER_INTELLIGENT_ANY:
        rules, results = _rule_ids_for_user(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            now_utc=now_utc,
        )
        if not rules:
            return set()
        return {sid for ids in results.values() for sid in ids}

    if dynamic_filter in INTELLIGENT_RULE_KEYS:
        return get_intelligent_rule_ids(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            rule_key=dynamic_filter,
            now_utc=now_utc,
        )

    if dynamic_filter == FILTER_ATTENTION_UNREACHED:
        return _attention_unreached_ids(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            now_utc=now_utc,
        )

    if dynamic_filter == FILTER_ATTENTION_STUCK:
        return _attention_stuck_ids(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            now_utc=now_utc,
        )

    return set()


def process_daily_digest_for_org(
    db: Session,
    *,
    org_id: UUID,
    now_utc: datetime | None = None,
) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return {"users_checked": 0, "notifications_created": 0, "skipped": True}

    settings = get_or_create_settings(db, org_id)
    if not settings.enabled or not settings.daily_digest_enabled:
        return {"users_checked": 0, "notifications_created": 0, "skipped": True}

    tz = ZoneInfo(org.timezone or "UTC")
    local_now = now_utc.astimezone(tz)
    if local_now.hour != settings.digest_hour_local:
        return {"users_checked": 0, "notifications_created": 0, "skipped": True}

    memberships = (
        db.query(User.id, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .all()
    )

    today_key = local_now.date().isoformat()
    users_checked = 0
    created = 0
    for user_id, role in memberships:
        users_checked += 1
        if not notification_facade.should_notify(
            db, user_id, org_id, "intelligent_suggestion_digest"
        ):
            continue
        summary = get_intelligent_summary(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=role,
            now_utc=now_utc,
        )
        total = int(summary.get("total", 0))
        if total <= 0:
            continue

        notification = notification_facade.create_notification(
            db=db,
            org_id=org_id,
            user_id=user_id,
            type=NotificationType.INTELLIGENT_SUGGESTION_DIGEST,
            title="Intelligent suggestions ready",
            body=f"{total} suggested lead{'s' if total != 1 else ''} need attention.",
            entity_type=None,
            entity_id=None,
            dedupe_key=f"intelligent_suggestion_digest:{user_id}:{today_key}",
            dedupe_window_hours=None,
        )
        if notification:
            created += 1

    return {
        "users_checked": users_checked,
        "notifications_created": created,
        "skipped": False,
    }


def process_daily_digest_for_all_orgs(
    db: Session,
    *,
    now_utc: datetime | None = None,
) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    org_ids: Iterable[UUID] = [row[0] for row in db.query(Organization.id).all()]
    orgs_processed = 0
    users_checked = 0
    notifications_created = 0
    errors: list[dict] = []

    for org_id in org_ids:
        try:
            result = process_daily_digest_for_org(db, org_id=org_id, now_utc=now_utc)
            orgs_processed += 1
            users_checked += int(result.get("users_checked", 0))
            notifications_created += int(result.get("notifications_created", 0))
        except Exception as exc:  # pragma: no cover - defensive
            errors.append({"org_id": str(org_id), "error": str(exc)})

    return {
        "orgs_processed": orgs_processed,
        "users_checked": users_checked,
        "notifications_created": notifications_created,
        "errors": errors,
    }
