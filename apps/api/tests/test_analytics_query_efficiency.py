import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import event

from app.core.encryption import hash_email, hash_phone
from app.db.enums import TaskType
from app.db.models import MetaLead, Pipeline, PipelineStage, Surrogate, Task
from app.services import analytics_meta_service, analytics_service, analytics_surrogate_service


def _collect_sql_statements(db):
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    return statements, before_cursor_execute


def _remove_sql_listener(db, listener):
    event.remove(db.bind, "before_cursor_execute", listener)


def test_get_analytics_summary_uses_single_surrogates_count_query(
    db, test_org, default_stage, test_user
):
    # Seed one surrogate so the summary isn't trivially empty.
    email = "efficiency@test.com"
    phone = "555-0100"
    s = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        stage_id=default_stage.id,
        full_name="Efficiency User",
        status_label=default_stage.label,
        email=email,
        email_hash=hash_email(email),
        phone=phone,
        phone_hash=hash_phone(phone),
        source="website",
        surrogate_number="S99999",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(s)
    db.flush()

    start = datetime.now(timezone.utc) - timedelta(days=7)
    end = datetime.now(timezone.utc) + timedelta(days=1)

    statements, listener = _collect_sql_statements(db)
    try:
        data = analytics_surrogate_service.get_analytics_summary(db, test_org.id, start, end)
    finally:
        _remove_sql_listener(db, listener)

    # Only count the surrogate-count aggregate query; exclude other queries (pipeline stages, avg time, etc.).
    surrogate_count_selects = [
        s
        for s in statements
        if "from surrogates" in s.lower()
        and "count(" in s.lower()
        and s.lstrip().lower().startswith("select")
    ]
    assert len(surrogate_count_selects) == 1

    assert data["total_surrogates"] == 1
    assert data["new_this_period"] == 1


def test_get_summary_kpis_uses_single_surrogates_count_query(
    db, test_org, default_stage, test_user
):
    today = date.today()
    start_date = today - timedelta(days=7)
    end_date = today
    old_contact = datetime.now(timezone.utc) - timedelta(days=10)
    fresh_contact = datetime.now(timezone.utc)

    rows = [
        ("current-stale@example.com", start_date + timedelta(days=1), old_contact, False),
        ("current-fresh@example.com", end_date, fresh_contact, False),
        ("previous-stale@example.com", start_date - timedelta(days=2), old_contact, False),
        ("archived-current@example.com", end_date, old_contact, True),
    ]
    for index, (email, created_date, last_contacted_at, is_archived) in enumerate(rows):
        db.add(
            Surrogate(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                stage_id=default_stage.id,
                full_name=f"KPI User {index}",
                status_label=default_stage.label,
                email=email,
                email_hash=hash_email(email),
                phone=f"555-01{index:02d}",
                phone_hash=hash_phone(f"555-01{index:02d}"),
                source="website",
                surrogate_number=f"S98{index:03d}",
                created_by_user_id=test_user.id,
                owner_type="user",
                owner_id=test_user.id,
                created_at=datetime.combine(
                    created_date,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
                last_contacted_at=last_contacted_at,
                is_archived=is_archived,
            )
        )
    db.flush()

    statements, listener = _collect_sql_statements(db)
    try:
        data = analytics_surrogate_service.get_summary_kpis(
            db,
            test_org.id,
            start_date=start_date,
            end_date=end_date,
        )
    finally:
        _remove_sql_listener(db, listener)

    surrogate_count_selects = [
        statement
        for statement in statements
        if statement.lstrip().lower().startswith("select")
        and "from surrogates" in statement.lower()
        and "count(" in statement.lower()
    ]
    assert len(surrogate_count_selects) == 1

    assert data == {
        "new_surrogates": 2,
        "new_surrogates_change_pct": 100.0,
        "total_active": 3,
        "needs_attention": 2,
        "period_days": 7,
    }


def test_get_meta_performance_uses_single_meta_leads_count_query(db, test_org, test_user):
    now = datetime.now(timezone.utc)
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Analytics Efficiency Pipeline",
        is_default=True,
        current_version=1,
    )
    db.add(pipeline)
    db.flush()

    stages = {}
    for stage_key, label, order in [
        ("contacted", "Contacted", 1),
        ("pre_qualified", "Pre-Qualified", 2),
        ("application_submitted", "Application Submitted", 3),
    ]:
        stage = PipelineStage(
            id=uuid.uuid4(),
            pipeline_id=pipeline.id,
            stage_key=stage_key,
            slug=stage_key,
            label=label,
            color="#3b82f6",
            stage_type="intake",
            order=order,
            is_active=True,
        )
        db.add(stage)
        stages[stage_key] = stage
    db.flush()

    converted_surrogates = []
    for index, stage_key in enumerate(["pre_qualified", "application_submitted"]):
        email = f"meta-efficiency-{index}@example.com"
        phone = f"555-02{index:02d}"
        surrogate = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stages[stage_key].id,
            full_name=f"Meta Efficiency {index}",
            status_label=stages[stage_key].label,
            email=email,
            email_hash=hash_email(email),
            phone=phone,
            phone_hash=hash_phone(phone),
            source="meta",
            surrogate_number=f"S97{index:03d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=2),
        )
        db.add(surrogate)
        converted_surrogates.append(surrogate)
    db.flush()

    db.add(
        MetaLead(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            meta_page_id="page",
            meta_lead_id=f"lead-{uuid.uuid4().hex}",
            meta_created_time=now - timedelta(days=3),
            received_at=now - timedelta(days=3),
            is_converted=False,
            status="processed",
        )
    )
    for index, surrogate in enumerate(converted_surrogates):
        db.add(
            MetaLead(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                meta_page_id="page",
                meta_lead_id=f"lead-{uuid.uuid4().hex}",
                meta_created_time=now - timedelta(days=index + 1),
                received_at=now - timedelta(days=index + 1),
                is_converted=True,
                converted_surrogate_id=surrogate.id,
                converted_at=now,
                status="converted",
            )
        )
    db.flush()

    statements, listener = _collect_sql_statements(db)
    try:
        data = analytics_meta_service.get_meta_performance(
            db,
            test_org.id,
            start=now - timedelta(days=7),
            end=now + timedelta(days=1),
        )
    finally:
        _remove_sql_listener(db, listener)

    meta_leads_count_selects = [
        statement
        for statement in statements
        if statement.lstrip().lower().startswith("select")
        and "from meta_leads" in statement.lower()
        and "count(" in statement.lower()
    ]
    assert len(meta_leads_count_selects) == 1
    assert data["leads_received"] == 3
    assert data["leads_qualified"] == 2
    assert data["leads_converted"] == 1


def test_get_pdf_export_data_batches_pending_and_overdue_task_counts(
    db, test_org, test_user, monkeypatch
):
    today = date.today()
    now = datetime.now(timezone.utc)

    tasks = [
        ("Pending task", TaskType.OTHER.value, False, None),
        ("Overdue task", TaskType.OTHER.value, False, today - timedelta(days=1)),
        ("Completed overdue task", TaskType.OTHER.value, True, today - timedelta(days=1)),
        ("Approval task", TaskType.WORKFLOW_APPROVAL.value, False, today - timedelta(days=1)),
    ]
    for title, task_type, is_completed, due_date in tasks:
        db.add(
            Task(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                created_by_user_id=test_user.id,
                owner_type="user",
                owner_id=test_user.id,
                title=title,
                task_type=task_type,
                is_completed=is_completed,
                due_date=due_date,
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()

    monkeypatch.setattr(
        analytics_service._surrogate, "get_surrogates_by_status", lambda *_, **__: []
    )
    monkeypatch.setattr(
        analytics_service._surrogate,
        "get_surrogates_by_assignee",
        lambda *_, **__: [],
    )
    monkeypatch.setattr(analytics_service._surrogate, "get_surrogates_trend", lambda *_, **__: [])
    monkeypatch.setattr(
        analytics_service._surrogate, "get_performance_by_user", lambda *_, **__: {}
    )
    monkeypatch.setattr(analytics_service._meta, "get_meta_performance", lambda *_, **__: {})
    monkeypatch.setattr(analytics_service._meta, "get_funnel_with_filter", lambda *_, **__: [])
    monkeypatch.setattr(
        analytics_service._meta,
        "get_surrogates_by_state_with_filter",
        lambda *_, **__: [],
    )

    statements, listener = _collect_sql_statements(db)
    try:
        data = analytics_service.get_pdf_export_data(
            db,
            test_org.id,
            start_dt=None,
            end_dt=None,
        )
    finally:
        _remove_sql_listener(db, listener)

    task_count_selects = [
        statement
        for statement in statements
        if statement.lstrip().lower().startswith("select")
        and "from tasks" in statement.lower()
        and "count(" in statement.lower()
    ]
    assert len(task_count_selects) == 1
    assert data["summary"]["pending_tasks"] == 2
    assert data["summary"]["overdue_tasks"] == 1
