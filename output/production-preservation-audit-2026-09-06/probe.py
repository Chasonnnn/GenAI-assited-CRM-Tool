"""Synthetic-only audit probes; run from apps/api with explicit DATABASE_URL."""

import json
import os
import runpy
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

sys.path.insert(0, str(Path.cwd()))
target = urlsplit(os.environ.get("DATABASE_URL", ""))
assert (target.hostname, target.port, target.path) == (
    "127.0.0.1", 55439, "/crm_preservation_audit"
), "This probe only supports the disposable audit database"
runpy.run_path("tests/conftest.py")

from alembic.config import Config
from sqlalchemy import MetaData, Table, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.db.models import Organization, User
from app.db.session import engine
from app.services import pipeline_service
from tests.test_match_events import _create_case, _create_intended_parent

PREVIOUS = "20260830_0100"
CASE = "20260905_1400_match_cases"
WORK = "20260905_1500_match_work"
HEAD = "20260905_1600_record_integrations"
results = {}


def config(connection):
    cfg = Config()
    cfg.set_main_option("script_location", str(Path("alembic").resolve()))
    cfg.attributes["connection"] = connection
    return cfg


def seed(connection):
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        org, user, match = uuid4(), uuid4(), uuid4()
        session.add(Organization(id=org, name="Synthetic audit", slug=f"audit-{org}"))
        session.add(
            User(
                id=user,
                email=f"{user}@example.com",
                display_name="Synthetic audit",
                is_active=True,
                token_version=1,
            )
        )
        session.flush()
        pipeline = pipeline_service.get_or_create_default_pipeline(session, org)
        stage = pipeline_service.get_stage_by_system_role(session, pipeline.id, "matched")
        surrogate = _create_case(session, org, user, stage)
        lead = _create_case(session, org, user, stage)
        ip = _create_intended_parent(session, org)
        session.commit()
        ids = dict(org=org, user=user, match=match, surrogate=surrogate.id, ip=ip.id, lead=lead.id)
    connection.execute(
        text(
            "INSERT INTO matches (id,organization_id,surrogate_id,intended_parent_id,match_number,status,proposed_by_user_id,notes) VALUES (:match,:org,:surrogate,:ip,'M10001','accepted',:user,'Synthetic legacy note')"
        ),
        ids,
    )
    return ids


def insert(connection, table, **values):
    reflected = Table(table, MetaData(), autoload_with=connection)
    connection.execute(reflected.insert().values(**values))


with engine.connect() as connection:
    tx = connection.begin()
    try:
        cfg = config(connection)
        command.downgrade(cfg, PREVIOUS)
        ids = seed(connection)
        now = datetime.now(UTC)
        insert(
            connection,
            "tasks",
            organization_id=ids["org"],
            surrogate_id=ids["surrogate"],
            created_by_user_id=ids["user"],
            owner_type="user",
            owner_id=ids["user"],
            title="Legacy task",
        )
        insert(
            connection,
            "entity_notes",
            organization_id=ids["org"],
            entity_type="surrogate",
            entity_id=ids["surrogate"],
            author_id=ids["user"],
            content="Legacy note",
        )
        insert(
            connection,
            "attachments",
            organization_id=ids["org"],
            surrogate_id=ids["surrogate"],
            filename="synthetic.txt",
            storage_key="audit/synthetic.txt",
            content_type="text/plain",
            file_size=1,
            checksum_sha256="0" * 64,
            scan_status="clean",
        )
        insert(
            connection,
            "appointments",
            organization_id=ids["org"],
            user_id=ids["user"],
            surrogate_id=ids["surrogate"],
            client_name="Synthetic",
            client_email="audit@example.com",
            client_phone="2025550100",
            client_timezone="UTC",
            scheduled_start=now,
            scheduled_end=now + timedelta(minutes=30),
            duration_minutes=30,
            meeting_mode="phone",
        )
        # Snapshot every pre-existing table and column, including encrypted values and FK IDs.
        tables = {
            name: Table(name, MetaData(), autoload_with=connection)
            for name in inspect(connection).get_table_names()
            if name != "alembic_version"
        }
        before = {
            name: sorted(map(repr, connection.execute(select(table)).all()))
            for name, table in tables.items()
        }
        command.upgrade(cfg, HEAD)
        command.upgrade(cfg, HEAD)
        after = {
            name: sorted(map(repr, connection.execute(select(table)).all()))
            for name, table in tables.items()
        }
        assert before == after
        results["full_chain_preservation"] = {
            "passed": True,
            "tables_compared": len(tables),
            "nonempty_tables": [name for name, rows in before.items() if rows],
        }
        results["legacy_work_without_match_context"] = {
            table: connection.execute(
                text(f"SELECT count(*) FROM {table} WHERE match_id IS NULL")
            ).scalar_one()
            for table in ("tasks", "entity_notes", "attachments", "appointments")
        }
    finally:
        tx.rollback()

with engine.connect() as connection:
    tx = connection.begin()
    try:
        cfg = config(connection)
        command.downgrade(cfg, PREVIOUS)
        ids = seed(connection)
        command.upgrade(cfg, CASE)
        connection.execute(
            text(
                "UPDATE matches SET status='cancelled', closed_at=now(), closed_by_user_id=:user, closure_reason='Synthetic closure' WHERE id=:match"
            ),
            ids,
        )
        command.downgrade(cfg, PREVIOUS)
        results["closure_only_downgrade_data_loss_reproduced"] = (
            "closed_at" not in {col["name"] for col in inspect(connection).get_columns("matches")}
            and connection.execute(text("SELECT count(*) FROM matches")).scalar_one() == 1
        )
    finally:
        tx.rollback()

with engine.connect() as connection:
    tx = connection.begin()
    try:
        cfg = config(connection)
        command.downgrade(cfg, WORK)
        connection.execute(text("SET LOCAL lock_timeout = '0'"))
        connection.execute(text("SET LOCAL statement_timeout = '0'"))
        command.upgrade(cfg, HEAD)
        results["standalone_1600_timeouts"] = dict(
            zip(
                ("lock_timeout", "statement_timeout"),
                connection.execute(
                    text(
                        "SELECT current_setting('lock_timeout'), current_setting('statement_timeout')"
                    )
                ).one(),
            )
        )
    finally:
        tx.rollback()

with engine.connect() as connection:
    tx = connection.begin()
    try:
        cfg = config(connection)
        command.downgrade(cfg, PREVIOUS)
        ids = seed(connection)
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            other_ip = _create_intended_parent(session, ids["org"])
            session.commit()
            ids["other_ip"] = other_ip.id
        ids["other_match"] = uuid4()
        connection.execute(
            text(
                "INSERT INTO matches (id,organization_id,surrogate_id,intended_parent_id,match_number,status,proposed_by_user_id) VALUES (:other_match,:org,:surrogate,:other_ip,'M10002','cancel_pending',:user)"
            ),
            ids,
        )
        savepoint = connection.begin_nested()
        try:
            command.upgrade(cfg, HEAD)
        except IntegrityError as exc:
            results["legacy_conflict_rejected"] = exc.orig.diag.constraint_name
            savepoint.rollback()
        else:
            raise AssertionError("Expected stronger surrogate commitment constraint to fail")
        results["conflict_rollback_preserves_rows"] = (
            connection.execute(text("SELECT count(*) FROM matches")).scalar_one() == 2
        )
        results["conflict_rollback_revision"] = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    finally:
        tx.rollback()

with engine.connect() as connection:
    tx = connection.begin()
    try:
        ids = seed(connection)
        from app.core.encryption import hash_email
        from app.db.models import Donor, Match
        from app.services.compliance_service import _build_retention_query

        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            pipeline = pipeline_service.get_or_create_default_pipeline(
                session, ids["org"], entity_type="egg_donor"
            )
            stage = pipeline_service.get_stage_by_key(session, pipeline.id, "new_unread")
            if stage is None:
                from app.db.models import PipelineStage

                stage = (
                    session.query(PipelineStage)
                    .filter(PipelineStage.pipeline_id == pipeline.id)
                    .first()
                )
            donor = Donor(
                id=uuid4(),
                organization_id=ids["org"],
                donor_number="D10001",
                donor_type="egg",
                full_name="Synthetic donor",
                email="donor@example.com",
                email_hash=hash_email("donor@example.com"),
                stage_id=stage.id,
            )
            session.add(donor)
            session.flush()
            donor_match = Match(
                id=uuid4(),
                organization_id=ids["org"],
                donor_id=donor.id,
                intended_parent_id=ids["ip"],
                match_kind="donor",
                match_number="M10002",
                status="accepted",
                proposed_by_user_id=ids["user"],
            )
            session.add(donor_match)
            session.flush()
            cutoff = datetime.now(UTC) + timedelta(days=1)
            held_query = _build_retention_query(
                session, ids["org"], "matches", cutoff, set(), {"donor": {donor.id}}
            )
            results["donor_held_case_selected_for_purge"] = donor_match.id in {
                row.id for row in held_query.all()
            }
            unrelated_hold_query = _build_retention_query(
                session, ids["org"], "matches", cutoff, {ids["lead"]}, {}
            )
            results["unrelated_surrogate_hold_excludes_donor_case"] = donor_match.id not in {
                row.id for row in unrelated_hold_query.all()
            }
            session.commit()
            donor_match_id = donor_match.id
        insert(
            connection,
            "match_attempts",
            id=uuid4(),
            organization_id=ids["org"],
            match_id=donor_match_id,
            sequence=1,
            attempt_type="retrieval",
            status="planned",
        )
        connection.execute(text("DELETE FROM matches WHERE id=:id"), {"id": donor_match_id})
        results["selected_donor_case_delete_cascades_attempt"] = (
            connection.execute(text("SELECT count(*) FROM match_attempts")).scalar_one() == 0
        )
        insert(
            connection,
            "entity_notes",
            organization_id=ids["org"],
            entity_type="match",
            entity_id=ids["match"],
            match_id=ids["match"],
            author_id=ids["user"],
            content="New case note",
        )
        savepoint = connection.begin_nested()
        try:
            connection.execute(text("DELETE FROM matches WHERE id=:match"), ids)
        except IntegrityError as exc:
            results["case_work_blocks_bulk_delete"] = exc.orig.diag.constraint_name
            savepoint.rollback()
        else:
            raise AssertionError("Expected case note to restrict match deletion")
    finally:
        tx.rollback()

# Commit a synthetic concurrent write after the guard reads empty, before DDL.
# Unlike the probes above this deliberately uses two committed transactions.
from sqlalchemy import event

with engine.connect() as connection:
    cfg = config(connection)
    command.downgrade(cfg, CASE)
    ids = seed(connection)
    connection.commit()
    race = {"writer_committed": False}

    def insert_after_guard(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT EXISTS (SELECT 1 FROM match_attempts)"):
            with engine.begin() as writer:
                writer.execute(
                    text(
                        "INSERT INTO match_attempts (id,organization_id,match_id,sequence,attempt_type,status) VALUES (:attempt,:org,:match,1,'embryo_transfer','planned')"
                    ),
                    {**ids, "attempt": uuid4()},
                )
            race["writer_committed"] = True

    event.listen(connection, "after_cursor_execute", insert_after_guard)
    try:
        command.downgrade(cfg, PREVIOUS)
        connection.commit()
        race["attempt_table_dropped"] = not inspect(connection).has_table("match_attempts")
        results["concurrent_downgrade_data_loss_reproduced"] = race
    finally:
        event.remove(connection, "after_cursor_execute", insert_after_guard)
        connection.rollback()
        command.upgrade(cfg, HEAD)
        connection.execute(text("DELETE FROM organizations WHERE id=:org"), ids)
        connection.execute(text("DELETE FROM users WHERE id=:user"), ids)
        connection.commit()

print(json.dumps(results, indent=2))
