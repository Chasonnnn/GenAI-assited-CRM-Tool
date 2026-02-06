from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.orm import joinedload

from app.db.enums import Role
from app.db.models import Surrogate
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

            if surrogate.owner_type == "user":
                assert surrogate.owner_user is not None
                _ = surrogate.owner_user.display_name
            if surrogate.owner_type == "queue":
                assert surrogate.owner_queue is not None
                _ = surrogate.owner_queue.name

    assert counter["n"] == 1, "\n".join(counter["statements"])


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
