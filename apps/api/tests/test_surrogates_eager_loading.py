from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Query, joinedload

from app.db.enums import Role
from app.db.models import EmailTemplate, Queue, Surrogate, SurrogateActivityLog
from app.routers.surrogates_shared import _surrogate_to_read
from app.schemas.surrogate import SurrogateCreate
from app.services import pipeline_service, queue_service, surrogate_service


@contextmanager
def _count_sql_statements(engine):
    count = {"n": 0, "statements": []}

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        count["n"] += 1
        # Keep a small sample for debugging when assertions fail.
        stmt = " ".join(statement.split())
        count["statements"].append(stmt[:300])

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield count
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)


def test_surrogate_to_read_uses_loaded_owner_user(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Owner User Loaded",
            email=f"owner-user-loaded-{uuid4().hex[:8]}@example.com",
        ),
    )

    surrogate_loaded = (
        db.query(Surrogate)
        .options(joinedload(Surrogate.owner_user))
        .filter(Surrogate.id == surrogate.id)
        .one()
    )
    assert surrogate_loaded.owner_user is not None

    with patch("app.routers.surrogates_shared.user_service.get_user_by_id") as mock_get:
        payload = _surrogate_to_read(surrogate_loaded, db)
        assert payload.owner_name == test_user.display_name
        mock_get.assert_not_called()


def test_surrogate_to_read_uses_loaded_owner_queue(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Owner Queue Loaded",
            email=f"owner-queue-loaded-{uuid4().hex[:8]}@example.com",
            assign_to_user=False,
        ),
    )

    surrogate_loaded = (
        db.query(Surrogate)
        .options(joinedload(Surrogate.owner_queue))
        .filter(Surrogate.id == surrogate.id)
        .one()
    )
    assert surrogate_loaded.owner_queue is not None

    with patch("app.routers.surrogates_shared.queue_service.get_queue") as mock_get:
        payload = _surrogate_to_read(surrogate_loaded, db)
        assert payload.owner_name == surrogate_loaded.owner_queue.name
        mock_get.assert_not_called()


def test_list_surrogates_eager_loads_in_single_statement(db, db_engine, test_org, test_user):
    # Make sure we have a default pipeline/stages so create_surrogate is consistent.
    pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)

    org_id = test_org.id
    user_id = test_user.id

    surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(
            full_name="List User Owned",
            email=f"list-user-owned-{uuid4().hex[:8]}@example.com",
        ),
    )
    surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(
            full_name="List Queue Owned",
            email=f"list-queue-owned-{uuid4().hex[:8]}@example.com",
            assign_to_user=False,
        ),
    )
    db.flush()

    with _count_sql_statements(db_engine) as counter:
        surrogates, total, next_cursor = surrogate_service.list_surrogates(
            db=db,
            org_id=org_id,
            page=1,
            per_page=20,
            include_total=False,
            role_filter=Role.DEVELOPER,
            user_id=user_id,
        )
        assert total is None
        assert next_cursor is None or isinstance(next_cursor, str)

        # Touch the exact relationship fields the list serializer needs.
        for surrogate in surrogates:
            assert surrogate.stage is not None
            _ = surrogate.stage.slug
            _ = surrogate.stage.stage_type
            assert hasattr(surrogate, "last_activity_at")

            if surrogate.owner_type == "user":
                assert surrogate.owner_user is not None
                _ = surrogate.owner_user.display_name
            if surrogate.owner_type == "queue":
                assert surrogate.owner_queue is not None
                _ = surrogate.owner_queue.name

    # Increased from 1 to 2 due to separate query for last_activity_at (avoiding correlated subquery)
    assert counter["n"] == 2, "\n".join(counter["statements"])


@pytest.mark.asyncio
async def test_list_surrogates_endpoint_uses_single_statement_for_data_fetch(
    db, db_engine, test_org, test_user, authed_client, monkeypatch
):
    from app.services import audit_service, permission_service

    pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Endpoint Statement Count",
            email=f"endpoint-statement-{uuid4().hex[:8]}@example.com",
        ),
    )

    monkeypatch.setattr(permission_service, "check_permission", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(audit_service, "log_phi_access", lambda *_args, **_kwargs: None)

    with _count_sql_statements(db_engine) as counter:
        response = await authed_client.get("/surrogates", params={"include_total": "false"})

    assert response.status_code == 200, response.text
    # Increased from 7 to 8 due to separate query for last_activity_at (avoiding correlated subquery)
    assert counter["n"] == 8, "\n".join(counter["statements"])
    # We now expect surrogate_activity_log to be queried separately
    assert any("surrogate_activity_log" in stmt for stmt in counter["statements"])


def test_list_claim_queue_eager_loads_in_few_statements(db, db_engine, test_org, test_user):
    org_id = test_org.id
    user_id = test_user.id

    # Pre-create the Surrogate Pool queue and default pipeline+stages so list_claim_queue doesn't create them.
    pool_queue = queue_service.get_or_create_surrogate_pool_queue(db, org_id)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, user_id)
    approved_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "approved")
    assert approved_stage is not None

    surrogate = surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(
            full_name="Claim Queue Item",
            email=f"claim-queue-{uuid4().hex[:8]}@example.com",
            assign_to_user=False,
        ),
    )
    surrogate.owner_type = "queue"
    surrogate.owner_id = pool_queue.id
    surrogate.stage_id = approved_stage.id
    surrogate.status_label = approved_stage.label
    db.flush()

    with _count_sql_statements(db_engine) as counter:
        surrogates, total = surrogate_service.list_claim_queue(
            db=db,
            org_id=org_id,
            page=1,
            per_page=20,
        )

        assert total >= 1
        assert any(s.id == surrogate.id for s in surrogates)
        for s in surrogates:
            assert s.stage is not None
            _ = s.stage.slug
            _ = s.stage.stage_type
            if s.owner_type == "user":
                _ = s.owner_user.display_name if s.owner_user else None
            if s.owner_type == "queue":
                _ = s.owner_queue.name if s.owner_queue else None

    # Expected:
    # - pool_queue lookup
    # - pipeline lookup (and possibly its stages if not already loaded)
    # - approved stage lookup
    # - count query
    # - list query (with joined eager loads)
    #
    # We allow a small ceiling to keep the test stable across ORM/dialect differences.
    assert counter["n"] <= 7


def test_list_surrogates_does_not_use_query_count(db, test_org, test_user, monkeypatch):
    surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Count Optimization Surrogate",
            email=f"count-opt-surrogate-{uuid4().hex[:8]}@example.com",
        ),
    )

    def _count_should_not_be_called(*_args, **_kwargs):
        raise AssertionError("list_surrogates should not call Query.count()")

    monkeypatch.setattr(Query, "count", _count_should_not_be_called)

    surrogates, total, _ = surrogate_service.list_surrogates(
        db=db,
        org_id=test_org.id,
        page=1,
        per_page=20,
        include_total=True,
        role_filter=Role.DEVELOPER,
        user_id=test_user.id,
    )

    assert total is not None
    assert len(surrogates) >= 1


def test_list_surrogate_activity_does_not_use_query_count(db, test_org, test_user, monkeypatch):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Activity Count Optimization",
            email=f"count-opt-activity-{uuid4().hex[:8]}@example.com",
        ),
    )

    db.add(
        SurrogateActivityLog(
            surrogate_id=surrogate.id,
            organization_id=test_org.id,
            activity_type="created",
            actor_user_id=test_user.id,
            details={"source": "test"},
        )
    )
    db.flush()

    original_count = Query.count

    def _count_should_not_be_called(self, *args, **kwargs):
        if (
            self.column_descriptions
            and self.column_descriptions[0].get("name") == "SurrogateActivityLog"
        ):
            raise AssertionError("list_surrogate_activity should not call Query.count()")
        return original_count(self, *args, **kwargs)

    monkeypatch.setattr(Query, "count", _count_should_not_be_called)
    items, total = surrogate_service.list_surrogate_activity(
        db=db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        page=1,
        per_page=20,
    )

    assert total >= 1
    assert len(items) >= 1


def test_list_surrogate_activity_includes_queue_names(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Activity Queue Name",
            email=f"activity-queue-name-{uuid4().hex[:8]}@example.com",
        ),
    )

    queue = Queue(
        organization_id=test_org.id,
        name=f"Escalations {uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(queue)
    db.flush()

    db.add(
        SurrogateActivityLog(
            surrogate_id=surrogate.id,
            organization_id=test_org.id,
            activity_type="surrogate_assigned_to_queue",
            actor_user_id=test_user.id,
            details={"to_queue_id": str(queue.id)},
        )
    )
    db.flush()

    items, total = surrogate_service.list_surrogate_activity(
        db=db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        page=1,
        per_page=20,
    )

    assert total >= 1
    assert len(items) >= 1
    queue_activity = next(
        (
            item
            for item in items
            if item["activity_type"] == "surrogate_assigned_to_queue"
            and isinstance(item["details"], dict)
            and item["details"].get("to_queue_id") == str(queue.id)
        ),
        None,
    )
    assert queue_activity is not None
    assert queue_activity["details"]["to_queue_name"] == queue.name


def test_list_surrogate_activity_includes_template_name(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Activity Template Name",
            email=f"activity-template-name-{uuid4().hex[:8]}@example.com",
        ),
    )

    template = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name=f"Welcome {uuid4().hex[:6]}",
        subject="Welcome",
        body="<p>Hello</p>",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.flush()

    db.add(
        SurrogateActivityLog(
            surrogate_id=surrogate.id,
            organization_id=test_org.id,
            activity_type="email_sent",
            actor_user_id=test_user.id,
            details={
                "template_id": str(template.id),
                "subject": "Welcome subject",
                "provider": "resend",
            },
        )
    )
    db.flush()

    items, total = surrogate_service.list_surrogate_activity(
        db=db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        page=1,
        per_page=20,
    )

    assert total >= 1
    assert len(items) >= 1
    email_activity = next(
        (
            item
            for item in items
            if item["activity_type"] == "email_sent"
            and isinstance(item["details"], dict)
            and item["details"].get("template_id") == str(template.id)
        ),
        None,
    )
    assert email_activity is not None
    assert email_activity["details"]["template_name"] == template.name


def test_list_assignees_selects_only_required_columns():
    from app.db.models import Membership, User

    org_id = uuid4()
    user_id = uuid4()

    fake_query = Mock()
    fake_query.join.return_value = fake_query
    fake_query.filter.return_value = fake_query
    fake_query.all.return_value = [(user_id, "Assignee Name", "case_manager")]

    db = Mock()
    db.query.return_value = fake_query

    result = surrogate_service.list_assignees(db, org_id)

    db.query.assert_called_once_with(User.id, User.display_name, Membership.role)
    assert result == [{"id": str(user_id), "name": "Assignee Name", "role": "case_manager"}]
