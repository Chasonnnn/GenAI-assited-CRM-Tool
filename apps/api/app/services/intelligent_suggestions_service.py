"""Services for intelligent suggestions and dynamic surrogate lead filters."""

from __future__ import annotations

from datetime import datetime, timedelta, time, timezone
from typing import Iterable
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, or_, select
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
    OrgIntelligentSuggestionSettings,
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


def _new_unread_stale_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    threshold_business_days: int,
    now_utc: datetime,
    org_tz: str,
) -> set[UUID]:
    last_activity_subquery = (
        select(func.max(SurrogateActivityLog.created_at))
        .where(
            SurrogateActivityLog.organization_id == org_id,
            SurrogateActivityLog.surrogate_id == Surrogate.id,
        )
        .correlate(Surrogate)
        .scalar_subquery()
    )
    last_activity_col = func.coalesce(last_activity_subquery, Surrogate.created_at).label(
        "last_activity_at"
    )

    query = (
        db.query(Surrogate.id, last_activity_col)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.slug == "new_unread",
            *_strict_owner_filters(user_role, user_id),
        )
    )

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
        select(func.max(meeting_anchor))
        .where(
            Appointment.organization_id == org_id,
            Appointment.surrogate_id == Surrogate.id,
            Appointment.surrogate_id.is_not(None),
            Appointment.status.in_(
                [
                    AppointmentStatus.CONFIRMED.value,
                    AppointmentStatus.COMPLETED.value,
                    AppointmentStatus.NO_SHOW.value,
                ]
            ),
        )
        .correlate(Surrogate)
        .scalar_subquery()
    )
    latest_outcome_subquery = (
        select(func.max(SurrogateActivityLog.created_at))
        .where(
            SurrogateActivityLog.organization_id == org_id,
            SurrogateActivityLog.surrogate_id == Surrogate.id,
            SurrogateActivityLog.activity_type == SurrogateActivityType.INTERVIEW_OUTCOME_LOGGED.value,
        )
        .correlate(Surrogate)
        .scalar_subquery()
    )

    query = (
        db.query(
            Surrogate.id,
            latest_meeting_subquery.label("latest_meeting_at"),
            latest_outcome_subquery.label("latest_outcome_at"),
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            latest_meeting_subquery.is_not(None),
            latest_meeting_subquery <= now_utc,
            or_(
                latest_outcome_subquery.is_(None),
                latest_outcome_subquery <= latest_meeting_subquery,
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


def _stuck_preapproval_ids(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    threshold_business_days: int,
    now_utc: datetime,
    org_tz: str,
) -> set[UUID]:
    last_activity_subquery = (
        select(func.max(SurrogateActivityLog.created_at))
        .where(
            SurrogateActivityLog.organization_id == org_id,
            SurrogateActivityLog.surrogate_id == Surrogate.id,
        )
        .correlate(Surrogate)
        .scalar_subquery()
    )
    last_activity_col = func.coalesce(last_activity_subquery, Surrogate.created_at).label(
        "last_activity_at"
    )

    query = (
        db.query(Surrogate.id, last_activity_col)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.slug.in_(INTAKE_PREAPPROVAL_STAGE_SLUGS),
            *_strict_owner_filters(user_role, user_id),
        )
    )

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
    owner_filters = _attention_owner_filters(db, org_id=org_id, user_id=user_id, user_role=user_role)
    rows = (
        db.query(Surrogate.id)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.stage_type == "intake",
            PipelineStage.order <= 2,
            Surrogate.created_at < cutoff,
            Surrogate.updated_at < cutoff,
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
    owner_filters = _attention_owner_filters(db, org_id=org_id, user_id=user_id, user_role=user_role)
    cutoff = now_utc - timedelta(days=30)

    latest_history = SurrogateStatusHistory.__table__.alias("latest_history")
    newer_history = SurrogateStatusHistory.__table__.alias("newer_history")
    latest_change_subquery = (
        select(latest_history.c.changed_at)
        .where(
            latest_history.c.organization_id == org_id,
            latest_history.c.surrogate_id == Surrogate.id,
            latest_history.c.to_stage_id.is_not(None),
            ~exists(
                select(1).where(
                    newer_history.c.organization_id == org_id,
                    newer_history.c.surrogate_id == latest_history.c.surrogate_id,
                    newer_history.c.to_stage_id.is_not(None),
                    newer_history.c.changed_at > latest_history.c.changed_at,
                )
            ),
        )
        .limit(1)
        .scalar_subquery()
    )
    last_change_col = func.coalesce(latest_change_subquery, Surrogate.created_at)
    rows = (
        db.query(Surrogate.id)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
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
    org_tz = (
        db.query(Organization.timezone).filter(Organization.id == org_id).scalar()
        or "UTC"
    )
    settings = get_or_create_settings(db, org_id)
    if not settings.enabled:
        return set()

    if rule_key == FILTER_INTELLIGENT_NEW_UNREAD and settings.new_unread_enabled:
        return _new_unread_stale_ids(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            threshold_business_days=settings.new_unread_business_days,
            now_utc=now_utc,
            org_tz=org_tz,
        )
    if rule_key == FILTER_INTELLIGENT_MEETING_OUTCOME and settings.meeting_outcome_enabled:
        return _meeting_outcome_missing_ids(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            threshold_business_days=settings.meeting_outcome_business_days,
            now_utc=now_utc,
            org_tz=org_tz,
        )
    if rule_key == FILTER_INTELLIGENT_STUCK_PREAPPROVAL and settings.stuck_enabled:
        return _stuck_preapproval_ids(
            db,
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            threshold_business_days=settings.stuck_business_days,
            now_utc=now_utc,
            org_tz=org_tz,
        )
    return set()


def get_intelligent_summary(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str,
    now_utc: datetime | None = None,
) -> dict:
    counts = {rule_key: 0 for rule_key in INTELLIGENT_RULE_KEYS}
    settings = get_or_create_settings(db, org_id)
    if not settings.enabled:
        return {"total": 0, "counts": counts}

    for rule_key in INTELLIGENT_RULE_KEYS:
        counts[rule_key] = len(
            get_intelligent_rule_ids(
                db,
                org_id=org_id,
                user_id=user_id,
                user_role=user_role,
                rule_key=rule_key,
                now_utc=now_utc,
            )
        )

    return {
        "total": sum(counts.values()),
        "counts": counts,
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
        matched: set[UUID] = set()
        for rule_key in INTELLIGENT_RULE_KEYS:
            matched.update(
                get_intelligent_rule_ids(
                    db,
                    org_id=org_id,
                    user_id=user_id,
                    user_role=user_role,
                    rule_key=rule_key,
                    now_utc=now_utc,
                )
            )
        return matched

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
