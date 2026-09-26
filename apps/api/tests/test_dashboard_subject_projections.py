from datetime import UTC, datetime, timedelta

from sqlalchemy import event

from app.core.encryption import hash_email
from app.db.models import Donor, Surrogate, Task, ZoomMeeting
from app.services import dashboard_service, pipeline_service


def test_dashboard_subject_lookups_select_only_display_fields(
    db, test_org, test_user, default_stage
):
    surrogate = Surrogate(
        organization_id=test_org.id,
        surrogate_number="S30001",
        full_name="Dashboard surrogate",
        email="dashboard-surrogate@example.test",
        email_hash=hash_email("dashboard-surrogate@example.test"),
        stage_id=default_stage.id,
        status_label=default_stage.label,
        source="manual",
        owner_type="user",
        owner_id=test_user.id,
    )
    donor_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    donor_stage = pipeline_service.get_stages(db, donor_pipeline.id)[0]
    donor = Donor(
        organization_id=test_org.id,
        donor_number="D30001",
        donor_type="egg",
        full_name="Dashboard donor",
        email="dashboard-donor@example.test",
        email_hash=hash_email("dashboard-donor@example.test"),
        stage_id=donor_stage.id,
    )
    db.add_all([surrogate, donor])
    db.flush()
    now = datetime.now(UTC)
    tasks = [
        Task(
            organization_id=test_org.id,
            title=title,
            owner_type="user",
            owner_id=test_user.id,
            created_by_user_id=test_user.id,
            due_date=now.date() - timedelta(days=1),
            **subject,
        )
        for title, subject in [
            ("Surrogate task", {"surrogate_id": surrogate.id}),
            ("Donor task", {"donor_id": donor.id}),
            ("Unlinked task", {}),
        ]
    ]
    meeting = ZoomMeeting(
        organization_id=test_org.id,
        user_id=test_user.id,
        surrogate_id=surrogate.id,
        zoom_meeting_id="projection-test",
        topic="Dashboard meeting",
        start_time=now + timedelta(hours=1),
        join_url="https://example.test/join",
        start_url="https://example.test/start",
    )
    db.add_all([*tasks, meeting])
    db.flush()
    org_id, user_id = test_org.id, test_user.id
    projections = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        for table in ("surrogates", "donors"):
            if f"FROM {table} " in statement and f"{table}.id IN (" in statement:
                projections.append(statement.split("\nFROM", 1)[0])

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", capture)
    try:
        upcoming, meetings = dashboard_service.get_upcoming_items(
            db, org_id, user_id, days=7, include_overdue=True, can_view_donors=True
        )
        attention = dashboard_service.get_attention_items(
            db, org_id, user_id, user_role="developer", can_view_donors=True
        )
    finally:
        event.remove(bind, "before_cursor_execute", capture)

    by_title = {item["title"]: item for item in upcoming}
    assert by_title["Surrogate task"]["surrogate_number"] == "S30001"
    assert by_title["Donor task"]["donor_number"] == "D30001"
    assert by_title["Donor task"]["donor_type"] == "egg"
    assert by_title["Unlinked task"]["surrogate_number"] is None
    assert by_title["Unlinked task"]["donor_number"] is None
    assert meetings[0]["surrogate_number"] == "S30001"
    overdue = next(item for item in attention["overdue_tasks"] if item["title"] == "Donor task")
    assert (overdue["donor_number"], overdue["donor_type"]) == ("D30001", "egg")
    assert len(projections) == 4
    assert all(".email" not in sql and ".full_name" not in sql for sql in projections)
