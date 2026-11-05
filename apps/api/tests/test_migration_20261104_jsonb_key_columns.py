"""Job subject columns match the JSONB lookup they replace."""

import json
import uuid
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

PREVIOUS = "20261103_1200_email_content_ticket_header"
SUBJECT = uuid.uuid4()

# name: (job_type, payload); expected (subject_type, subject_id) follows.
JOB_CASES = {
    "workflow": ("workflow_email", {"subject_type": "egg_donor", "subject_id": str(SUBJECT)}),
    # The old text comparison matched only str(uuid), so other spellings stay unmatched.
    "uppercase": (
        "workflow_email",
        {"subject_type": "egg_donor", "subject_id": str(SUBJECT).upper()},
    ),
    "invalid": ("workflow_email", {"subject_type": "egg_donor", "subject_id": "not-a-uuid"}),
    "missing": ("workflow_email", {"recipient_email": "a@example.com"}),
    "other_type": ("notification", {"subject_type": "egg_donor", "subject_id": str(SUBJECT)}),
}
JOB_EXPECTED = {
    "workflow": ("egg_donor", SUBJECT),
    "uppercase": ("egg_donor", None),
    "invalid": ("egg_donor", None),
    "missing": (None, None),
    "other_type": (None, None),
}


def _config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.attributes["connection"] = connection
    return config


def _columns(connection, table: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table)}


def _seed(connection, org_id) -> dict:
    connection.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Promote', :slug)"),
        {"id": org_id, "slug": f"promote-{org_id}"},
    )
    jobs = {
        name: connection.execute(
            text(
                "INSERT INTO jobs (organization_id, job_type, payload) "
                "VALUES (:org, :job_type, CAST(:payload AS jsonb)) RETURNING id"
            ),
            {"org": org_id, "job_type": job_type, "payload": json.dumps(payload)},
        ).scalar_one()
        for name, (job_type, payload) in JOB_CASES.items()
    }
    return jobs


def _stored(connection, jobs: dict) -> dict:
    rows = dict(
        (row[0], (row[1], row[2]))
        for row in connection.execute(text("SELECT id, subject_type, subject_id FROM jobs"))
    )
    return {name: rows[job_id] for name, job_id in jobs.items()}


def test_backfill_and_triggers_match_the_jsonb_lookups(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _config(connection)
        try:
            command.downgrade(config, PREVIOUS)
            assert {"subject_type", "subject_id"}.isdisjoint(_columns(connection, "jobs"))
            backfilled = _seed(connection, uuid.uuid4())
            payloads_before = connection.execute(
                text("SELECT id, payload FROM jobs ORDER BY id")
            ).all()

            command.upgrade(config, "head")

            assert _stored(connection, backfilled) == JOB_EXPECTED
            assert (
                connection.execute(text("SELECT id, payload FROM jobs ORDER BY id")).all()
                == payloads_before
            )
            # Rows written after the upgrade, including by pre-release code, get the same values.
            assert _stored(connection, _seed(connection, uuid.uuid4())) == JOB_EXPECTED

            jobs = backfilled
            connection.execute(
                text("UPDATE jobs SET job_type = 'send_email' WHERE id = :id"),
                {"id": jobs["workflow"]},
            )
            assert _stored(connection, jobs)["workflow"] == (None, None)

            command.downgrade(config, PREVIOUS)
            assert {"subject_type", "subject_id"}.isdisjoint(_columns(connection, "jobs"))
            command.upgrade(config, "head")
        finally:
            transaction.rollback()
