"""PostgreSQL regression: concurrent first reads must share one default pipeline."""

import threading
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.db.models import Organization, Pipeline
from app.services import pipeline_service


@pytest.fixture
def committed_org_id(db_engine):
    # Each racing session needs to see the organization, so it is committed and deleted after.
    org_id = uuid4()
    with Session(bind=db_engine) as session:
        session.add(Organization(id=org_id, name="Pipeline Race", slug=f"pipeline-race-{org_id}"))
        session.commit()
    try:
        yield org_id
    finally:
        with db_engine.begin() as connection:
            # Pipelines, stages, and versions cascade from the organization.
            connection.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


def test_concurrent_default_pipeline_creation_returns_the_committed_pipeline(
    db_engine, committed_org_id
):
    entity_type = "egg_donor"
    # The racing sessions use the test engine's two pooled connections; the probe needs its own.
    probe_engine = create_engine(db_engine.url, poolclass=NullPool)
    outcome: dict[str, object] = {}

    def second_request():
        try:
            with Session(bind=db_engine) as session:
                pipeline = pipeline_service.get_or_create_default_pipeline(
                    session, committed_org_id, entity_type=entity_type
                )
                outcome["pipeline_id"] = pipeline.id
        except Exception as exc:  # reported through the assertion below
            outcome["error"] = exc

    try:
        with Session(bind=db_engine) as first:
            first_pid = first.execute(text("SELECT pg_backend_pid()")).scalar_one()
            created = pipeline_service.get_or_create_default_pipeline(
                first, committed_org_id, entity_type=entity_type, commit=False
            )
            created_id = created.id

            racer = threading.Thread(target=second_request)
            racer.start()
            # Commit only once the second request waits on the default-pipeline unique index.
            deadline = time.monotonic() + 10
            blocked = False
            while time.monotonic() < deadline and not blocked:
                with probe_engine.connect() as probe:
                    blocked = probe.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE :pid = ANY(pg_blocking_pids(pid)))"
                        ),
                        {"pid": first_pid},
                    ).scalar_one()
                if not blocked:
                    time.sleep(0.01)
            assert blocked, "the second request never waited on the first request's insert"
            first.commit()
        racer.join(timeout=10)
        assert not racer.is_alive()

        assert "error" not in outcome, outcome.get("error")
        assert outcome["pipeline_id"] == created_id
        with Session(bind=db_engine) as session:
            defaults = session.scalar(
                select(func.count())
                .select_from(Pipeline)
                .where(
                    Pipeline.organization_id == committed_org_id,
                    Pipeline.entity_type == entity_type,
                    Pipeline.is_default.is_(True),
                )
            )
        assert defaults == 1
    finally:
        probe_engine.dispose()
