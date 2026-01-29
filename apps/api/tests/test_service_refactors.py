import uuid

from app.db.enums import Role


def test_meta_admin_service_list_and_get_ad_accounts(db, test_org):
    from app.db.models import Organization, MetaAdAccount
    from app.services import meta_admin_service

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Org",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()

    account_org = MetaAdAccount(
        organization_id=test_org.id,
        ad_account_external_id="act_123",
        ad_account_name="Org Account",
    )
    account_other = MetaAdAccount(
        organization_id=other_org.id,
        ad_account_external_id="act_456",
        ad_account_name="Other Account",
    )
    db.add_all([account_org, account_other])
    db.commit()

    accounts = meta_admin_service.list_ad_accounts(db, test_org.id)
    account_ids = {account.id for account in accounts}
    assert account_org.id in account_ids
    assert account_other.id not in account_ids

    found = meta_admin_service.get_ad_account(db, account_org.id, test_org.id)
    assert found is not None
    assert found.id == account_org.id

    missing = meta_admin_service.get_ad_account(db, account_other.id, test_org.id)
    assert missing is None

    account_other.is_active = False
    db.commit()
    active_accounts = meta_admin_service.list_active_ad_accounts(db)
    active_ids = {account.id for account in active_accounts}
    assert account_org.id in active_ids
    assert account_other.id not in active_ids


def test_task_service_bulk_complete_emits_dashboard(db, test_org, test_user, monkeypatch):
    from app.db.models import Task
    from app.db.enums import TaskType
    from app.schemas.auth import UserSession
    from app.services import dashboard_events, task_service

    task_1 = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Task 1",
        task_type=TaskType.OTHER.value,
    )
    task_2 = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Task 2",
        task_type=TaskType.OTHER.value,
    )
    db.add_all([task_1, task_2])
    db.commit()

    session = UserSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.DEVELOPER,
        email=test_user.email,
        display_name=test_user.display_name,
    )

    calls = {"count": 0}

    def fake_push_stats(_db, _org_id):
        calls["count"] += 1

    monkeypatch.setattr(dashboard_events, "push_dashboard_stats", fake_push_stats)

    result = task_service.bulk_complete_tasks(db, session, [task_1.id, task_2.id])
    assert result.completed == 2
    assert len(result.failed) == 0
    assert calls["count"] == 1


def test_surrogate_change_status_emits_dashboard(db, test_org, test_user, monkeypatch):
    from app.schemas.surrogate import SurrogateCreate
    from app.services import dashboard_events, pipeline_service, surrogate_service

    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Dashboard Status Test",
            email=f"status-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )

    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    next_stage = pipeline_service.create_stage(
        db=db,
        pipeline_id=pipeline.id,
        slug=f"contacted-{uuid.uuid4().hex[:6]}",
        label="Contacted",
        color="#00AA00",
        stage_type="intake",
    )

    calls = {"count": 0}

    def fake_push_stats(_db, _org_id):
        calls["count"] += 1

    monkeypatch.setattr(dashboard_events, "push_dashboard_stats", fake_push_stats)

    result = surrogate_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=next_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        emit_events=True,
    )
    assert result["status"] == "applied"
    assert calls["count"] == 1
