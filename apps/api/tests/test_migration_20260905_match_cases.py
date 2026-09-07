"""Rehearse expansion without reclassifying existing case history."""

import importlib.util
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, Table, event, inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from alembic import command
from app.db.models import Organization, User
from app.services import pipeline_service
from tests.test_match_events import _create_case, _create_intended_parent
from tests.test_migration_20260829_donor_module import _insert_donor_fixture

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


WORK = "20260905_1500_match_work"
HEAD = "20260905_1600_record_integrations"
API_ROOT = Path(__file__).resolve().parents[1]


def _config(connection):
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


@contextmanager
def _at_revision(db_engine, revision):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _config(connection)
            command.downgrade(config, revision)
            yield connection, config
        finally:
            transaction.rollback()


def _insert(connection, table_name, **values):
    table = Table(table_name, MetaData(), autoload_with=connection)
    connection.execute(table.insert().values(**values))


def _legacy_case(connection):
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        org_id, user_id, match_id = uuid4(), uuid4(), uuid4()
        session.add(Organization(id=org_id, name="Migration QA", slug=f"migration-{org_id}"))
        session.add(User(id=user_id, email=f"{user_id}@example.com", display_name="Migration QA"))
        session.flush()
        pipeline = pipeline_service.get_or_create_default_pipeline(session, org_id)
        stage = pipeline_service.get_stage_by_system_role(session, pipeline.id, "matched")
        surrogate = _create_case(session, org_id, user_id, stage)
        ip = _create_intended_parent(session, org_id)
        ids = dict(org=org_id, user=user_id, match=match_id, surrogate=surrogate.id, ip=ip.id)
        session.commit()
    connection.execute(
        text(
            "INSERT INTO matches (id,organization_id,surrogate_id,intended_parent_id,match_number,status,proposed_by_user_id,notes) VALUES (:match,:org,:surrogate,:ip,'M10001','accepted',:user,'Legacy case note')"
        ),
        ids,
    )
    return ids


def test_full_chain_preserves_every_existing_column_and_record_context(db_engine):
    with _at_revision(db_engine, PREVIOUS) as (connection, config):
        ids = _legacy_case(connection)
        donor = _insert_donor_fixture(connection, label="Preserved")
        now = datetime.now(UTC)
        for subject, entity_id in (
            ("surrogate", ids["surrogate"]),
            ("intended_parent", ids["ip"]),
            ("donor", donor["donor_id"]),
        ):
            org_id = donor["org_id"] if subject == "donor" else ids["org"]
            user_id = donor["user_id"] if subject == "donor" else ids["user"]
            _insert(
                connection,
                "tasks",
                organization_id=org_id,
                **{f"{subject}_id": entity_id},
                created_by_user_id=user_id,
                owner_type="user",
                owner_id=user_id,
                title=f"Legacy {subject} task",
            )
            _insert(
                connection,
                "entity_notes",
                organization_id=org_id,
                entity_type=subject,
                entity_id=entity_id,
                author_id=user_id,
                content=f"Legacy {subject} note",
            )
            _insert(
                connection,
                "attachments",
                organization_id=org_id,
                **{f"{subject}_id": entity_id},
                filename="synthetic.txt",
                storage_key=f"migration/{entity_id}/synthetic.txt",
                content_type="text/plain",
                file_size=1,
                checksum_sha256="0" * 64,
                scan_status="clean",
            )
        _insert(
            connection,
            "appointments",
            organization_id=ids["org"],
            user_id=ids["user"],
            intended_parent_id=ids["ip"],
            surrogate_id=ids["surrogate"],
            client_name="Legacy appointment",
            client_email="migration@example.com",
            client_phone="2025550100",
            client_timezone="UTC",
            scheduled_start=now,
            scheduled_end=now + timedelta(minutes=30),
            duration_minutes=30,
            meeting_mode="phone",
        )
        for kind in ("surrogate", "egg_donor", "sperm_donor"):
            _insert(
                connection,
                "meta_leads",
                organization_id=ids["org"],
                meta_lead_id=str(uuid4()),
                lead_kind=kind,
                raw_payload={"fixture": kind},
                field_data_raw={"consent": ["yes"]},
            )
            _insert(
                connection,
                "intake_leads",
                organization_id=ids["org"],
                lead_type=kind,
                full_name=f"Legacy {kind} lead",
                email="encrypted-fixture-email",
                status="pending_review",
            )
        tables = {
            name: Table(name, MetaData(), autoload_with=connection)
            for name in inspect(connection).get_table_names()
            if name != "alembic_version"
        }
        before = {
            name: sorted(map(repr, connection.execute(select(table)).all()))
            for name, table in tables.items()
        }
        command.upgrade(config, HEAD)
        command.upgrade(config, HEAD)
        after = {
            name: sorted(map(repr, connection.execute(select(table)).all()))
            for name, table in tables.items()
        }
        assert after == before
        for table in ("tasks", "entity_notes", "attachments", "appointments"):
            assert (
                connection.scalar(
                    text(
                        f"SELECT count(*) FROM {table} WHERE match_id IS NOT NULL OR attempt_id IS NOT NULL"
                    )
                )
                == 0
            )
        assert connection.scalar(text("SELECT count(*) FROM match_attempts")) == 0
        assert connection.scalar(text("SELECT count(*) FROM record_ticket_links")) == 0


@pytest.mark.parametrize(
    "column,value",
    [
        ("closed_at", "now()"),
        ("closed_by_user_id", ":user"),
        ("closure_reason", "'Historical closure reason'"),
        ("outcome", "'Historical outcome'"),
    ],
)
def test_downgrade_refuses_each_populated_closure_field(db_engine, column, value):
    with _at_revision(db_engine, PREVIOUS) as (connection, config):
        ids = _legacy_case(connection)
        command.upgrade(config, REVISION)
        connection.execute(
            text(f"UPDATE matches SET status='cancelled', {column}={value} WHERE id=:match"), ids
        )
        before = connection.execute(
            text(f"SELECT {column} FROM matches WHERE id=:match"), ids
        ).one()
        with pytest.raises(RuntimeError, match="compatible forward revision"):
            command.downgrade(config, PREVIOUS)
        assert (
            connection.execute(text(f"SELECT {column} FROM matches WHERE id=:match"), ids).one()
            == before
        )
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION


def test_commitment_conflict_preflight_precedes_schema_changes(db_engine):
    with _at_revision(db_engine, PREVIOUS) as (connection, config):
        ids = _legacy_case(connection)
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
        before = connection.execute(text("SELECT * FROM matches ORDER BY id")).all()
        statements = []

        def capture(_conn, _cursor, statement, _params, _context, _many):
            statements.append(statement.strip().upper())

        event.listen(connection, "before_cursor_execute", capture)
        try:
            with pytest.raises(RuntimeError, match="Conflicting surrogate commitments"):
                command.upgrade(config, REVISION)
        finally:
            event.remove(connection, "before_cursor_execute", capture)
        assert not any(sql.startswith(("ALTER ", "CREATE ", "DROP ")) for sql in statements)
        assert connection.execute(text("SELECT * FROM matches ORDER BY id")).all() == before
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREVIOUS


@pytest.mark.parametrize(
    "previous,revision", [(PREVIOUS, REVISION), (REVISION, WORK), (WORK, HEAD)]
)
@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_each_revision_sets_its_own_timeout_budgets(db_engine, previous, revision, direction):
    starting = previous if direction == "upgrade" else revision
    with _at_revision(db_engine, starting) as (connection, config):
        connection.execute(text("SET LOCAL lock_timeout='0'"))
        connection.execute(text("SET LOCAL statement_timeout='0'"))
        if direction == "upgrade":
            command.upgrade(config, revision)
        else:
            command.downgrade(config, previous)
        assert connection.execute(
            text("SELECT current_setting('lock_timeout'), current_setting('statement_timeout')")
        ).one() == ("3s", "1min")


@pytest.mark.parametrize(
    "revision,tables",
    [
        (REVISION, ("matches", "match_attempts")),
        (WORK, ("tasks", "entity_notes", "attachments")),
        (HEAD, ("appointments", "record_ticket_links")),
    ],
)
def test_downgrade_blocks_concurrent_inserts_before_history_guard(db_engine, revision, tables):
    # A fresh connection matters: preparatory downgrades would themselves hold
    # table locks and could conceal an unprotected guard in the target revision.
    module_path = API_ROOT / "alembic" / "versions" / f"{revision}.py"
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class GuardObserved(Exception):
        pass

    observed = []
    with db_engine.connect() as connection:
        transaction = connection.begin()

        def after_guard(_conn, _cursor, statement, _params, _context, _many):
            if not statement.lstrip().upper().startswith("SELECT EXISTS"):
                return
            for table in tables:
                with db_engine.connect() as writer, writer.begin():
                    writer.execute(text("SET LOCAL lock_timeout='100ms'"))
                    # The zero-row INSERT requires the same table write lock as
                    # a real insert without committing fixture data to the suite DB.
                    with pytest.raises(OperationalError) as error:
                        writer.execute(
                            text(f"INSERT INTO {table} (id) SELECT gen_random_uuid() WHERE FALSE")
                        )
                    assert error.value.orig.sqlstate == "55P03"
                    writer.rollback()
                    observed.append(table)
            raise GuardObserved

        event.listen(connection, "after_cursor_execute", after_guard)
        try:
            with Operations.context(MigrationContext.configure(connection)):
                with pytest.raises(GuardObserved):
                    module.downgrade()
        finally:
            event.remove(connection, "after_cursor_execute", after_guard)
            transaction.rollback()
    assert observed == list(tables)
