"""Rehearse expansion without reclassifying existing case history."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from alembic import command
from app.db.models import Organization, User
from app.services import pipeline_service
from tests.test_match_events import _create_case, _create_intended_parent

REVISION = "20260905_1400_match_cases"
PREVIOUS = "20260830_0100"


def test_match_case_upgrade_preserves_legacy_rows_and_refuses_lossy_downgrade(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, PREVIOUS)
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                org_id, user_id, match_id = uuid4(), uuid4(), uuid4()
                session.add(
                    Organization(id=org_id, name="Migration QA", slug=f"migration-{org_id}")
                )
                session.add(
                    User(
                        id=user_id,
                        email=f"migration-{user_id}@example.com",
                        display_name="Migration QA",
                        is_active=True,
                        token_version=1,
                    )
                )
                session.flush()
                pipeline = pipeline_service.get_or_create_default_pipeline(session, org_id)
                stage = pipeline_service.get_stage_by_system_role(session, pipeline.id, "matched")
                surrogate = _create_case(session, org_id, user_id, stage)
                ip = _create_intended_parent(session, org_id)
                params = {
                    "id": match_id,
                    "org": org_id,
                    "surrogate": surrogate.id,
                    "ip": ip.id,
                    "user": user_id,
                }
                session.execute(
                    text(
                        "INSERT INTO matches (id,organization_id,surrogate_id,intended_parent_id,match_number,status,proposed_by_user_id,notes) VALUES (:id,:org,:surrogate,:ip,'M10001','accepted',:user,'Legacy case note')"
                    ),
                    params,
                )
                session.commit()
            before = connection.execute(
                text("SELECT id,match_number,status,notes,proposed_at FROM matches WHERE id=:id"),
                {"id": match_id},
            ).one()
            command.upgrade(config, REVISION)
            command.upgrade(config, REVISION)
            after = connection.execute(
                text("SELECT id,match_number,status,notes,proposed_at FROM matches WHERE id=:id"),
                {"id": match_id},
            ).one()
            assert tuple(after) == tuple(before)
            fields = connection.execute(
                text("SELECT match_kind,donor_id,closed_at,outcome FROM matches WHERE id=:id"),
                {"id": match_id},
            ).one()
            assert tuple(fields) == ("surrogate", None, None, None)
            assert connection.execute(text("SELECT count(*) FROM match_attempts")).scalar() == 0
            indexes = {item["name"] for item in inspect(connection).get_indexes("matches")}
            assert {
                "uq_match_open_surrogate_ip",
                "uq_match_open_donor_ip",
                "uq_one_accepted_match_per_surrogate",
            } <= indexes
            connection.execute(
                text(
                    "INSERT INTO match_attempts (id,organization_id,match_id,sequence,attempt_type,status) VALUES (:attempt,:org,:id,1,'embryo_transfer','planned')"
                ),
                {"attempt": uuid4(), "org": org_id, "id": match_id},
            )
            with pytest.raises(RuntimeError, match="compatible forward revision"):
                command.downgrade(config, PREVIOUS)
            assert connection.execute(text("SELECT count(*) FROM match_attempts")).scalar() == 1
        finally:
            transaction.rollback()
