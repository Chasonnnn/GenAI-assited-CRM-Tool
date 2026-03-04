import re

dashboard_file = "apps/api/app/services/dashboard_service.py"
with open(dashboard_file, "r") as f:
    dashboard_content = f.read()

# Refactor get_attention_items stuck surrogates query
new_dashboard_content = dashboard_content.replace('''
    # Correlated subquery for each surrogate's latest stage change.
    # Uses NOT EXISTS to avoid a full-table GROUP BY over history.
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
    stuck_query = (
        db.query(
            Surrogate,
            PipelineStage.label.label("stage_label"),
            last_change_col.label("last_change"),
        )
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            last_change_col < stuck_cutoff,
            *owner_filters,
        )
    )
''', '''
    # Pre-aggregate latest stage change for each surrogate
    latest_change_subquery = (
        db.query(
            SurrogateStatusHistory.surrogate_id,
            func.max(SurrogateStatusHistory.changed_at).label("changed_at"),
        )
        .filter(
            SurrogateStatusHistory.organization_id == org_id,
            SurrogateStatusHistory.to_stage_id.is_not(None),
        )
        .group_by(SurrogateStatusHistory.surrogate_id)
        .subquery()
    )

    last_change_col = func.coalesce(latest_change_subquery.c.changed_at, Surrogate.created_at)
    stuck_query = (
        db.query(
            Surrogate,
            PipelineStage.label.label("stage_label"),
            last_change_col.label("last_change"),
        )
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_change_subquery,
            Surrogate.id == latest_change_subquery.c.surrogate_id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            last_change_col < stuck_cutoff,
            *owner_filters,
        )
    )
''')

# Also fix the count query which refers to last_change_col
new_dashboard_content = new_dashboard_content.replace('''
    # Total count for stuck (without limit)
    stuck_total_query = (
        db.query(func.count(Surrogate.id))
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            last_change_col < stuck_cutoff,
            *owner_filters,
        )
    )
''', '''
    # Total count for stuck (without limit)
    stuck_total_query = (
        db.query(func.count(Surrogate.id))
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_change_subquery,
            Surrogate.id == latest_change_subquery.c.surrogate_id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            last_change_col < stuck_cutoff,
            *owner_filters,
        )
    )
''')

with open(dashboard_file, "w") as f:
    f.write(new_dashboard_content)


intel_file = "apps/api/app/services/intelligent_suggestions_service.py"
with open(intel_file, "r") as f:
    intel_content = f.read()

# _stage_inactivity_ids optimization
intel_content = intel_content.replace('''
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
            *_strict_owner_filters(user_role, user_id),
        )
    )
''', '''
    last_activity_subquery = (
        db.query(
            SurrogateActivityLog.surrogate_id,
            func.max(SurrogateActivityLog.created_at).label("last_activity_at"),
        )
        .filter(SurrogateActivityLog.organization_id == org_id)
        .group_by(SurrogateActivityLog.surrogate_id)
        .subquery()
    )

    last_activity_col = func.coalesce(last_activity_subquery.c.last_activity_at, Surrogate.created_at).label(
        "last_activity_at"
    )

    query = (
        db.query(Surrogate.id, last_activity_col)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            last_activity_subquery,
            Surrogate.id == last_activity_subquery.c.surrogate_id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            *_strict_owner_filters(user_role, user_id),
        )
    )
''')

# _meeting_outcome_missing_ids optimization
intel_content = intel_content.replace('''
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
''', '''
    meeting_anchor = func.coalesce(
        Appointment.meeting_ended_at,
        Appointment.scheduled_end,
        Appointment.scheduled_start,
    )
    latest_meeting_subquery = (
        db.query(
            Appointment.surrogate_id,
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
            SurrogateActivityLog.surrogate_id,
            func.max(SurrogateActivityLog.created_at).label("latest_outcome_at"),
        )
        .filter(
            SurrogateActivityLog.organization_id == org_id,
            SurrogateActivityLog.activity_type == SurrogateActivityType.INTERVIEW_OUTCOME_LOGGED.value,
        )
        .group_by(SurrogateActivityLog.surrogate_id)
        .subquery()
    )

    query = (
        db.query(
            Surrogate.id,
            latest_meeting_subquery.c.latest_meeting_at.label("latest_meeting_at"),
            latest_outcome_subquery.c.latest_outcome_at.label("latest_outcome_at"),
        )
        .outerjoin(
            latest_meeting_subquery,
            Surrogate.id == latest_meeting_subquery.c.surrogate_id,
        )
        .outerjoin(
            latest_outcome_subquery,
            Surrogate.id == latest_outcome_subquery.c.surrogate_id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            latest_meeting_subquery.c.latest_meeting_at.is_not(None),
            latest_meeting_subquery.c.latest_meeting_at <= now_utc,
            or_(
                latest_outcome_subquery.c.latest_outcome_at.is_(None),
                latest_outcome_subquery.c.latest_outcome_at <= latest_meeting_subquery.c.latest_meeting_at,
            ),
            *_strict_owner_filters(user_role, user_id),
        )
    )
''')

# _attention_stuck_ids optimization
intel_content = intel_content.replace('''
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
''', '''
    latest_change_subquery = (
        db.query(
            SurrogateStatusHistory.surrogate_id,
            func.max(SurrogateStatusHistory.changed_at).label("changed_at"),
        )
        .filter(
            SurrogateStatusHistory.organization_id == org_id,
            SurrogateStatusHistory.to_stage_id.is_not(None),
        )
        .group_by(SurrogateStatusHistory.surrogate_id)
        .subquery()
    )
    last_change_col = func.coalesce(latest_change_subquery.c.changed_at, Surrogate.created_at)
    rows = (
        db.query(Surrogate.id)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_change_subquery,
            Surrogate.id == latest_change_subquery.c.surrogate_id,
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
''')

with open(intel_file, "w") as f:
    f.write(intel_content)
