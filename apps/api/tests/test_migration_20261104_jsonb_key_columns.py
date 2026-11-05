"""Job subject and Meta attribution columns match the JSONB lookups they replace."""

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

# name: (field_data_raw, field_data); expected (meta_platform, meta_ad_id) follows.
LEAD_CASES = {
    "raw_first": ({"platform": "ig", "ad_id": "a1"}, {"meta_platform": "fb", "meta_ad_id": "a2"}),
    "normalized": ({"question": "yes"}, {"publisher_platform": "facebook", "ad_id": "a3"}),
    # Coalesce keeps an empty string, and analytics treats it with nullif.
    "empty": ({"meta_platform": ""}, {"meta_platform": "fb"}),
    "not_object": ([{"name": "platform"}], None),
    "none": (None, None),
}
LEAD_EXPECTED = {
    "raw_first": ("ig", "a1"),
    "normalized": ("facebook", "a3"),
    "empty": ("", None),
    "not_object": (None, None),
    "none": (None, None),
}


def _config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.attributes["connection"] = connection
    return config


def _columns(connection, table: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table)}


def _seed(connection, org_id) -> tuple[dict, dict]:
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
    leads = {
        name: connection.execute(
            text(
                "INSERT INTO meta_leads (organization_id, meta_lead_id, field_data_raw, field_data) "
                "VALUES (:org, :lead, CAST(:raw AS jsonb), CAST(:normalized AS jsonb)) RETURNING id"
            ),
            {
                "org": org_id,
                "lead": f"lead-{name}",
                "raw": None if raw is None else json.dumps(raw),
                "normalized": None if normalized is None else json.dumps(normalized),
            },
        ).scalar_one()
        for name, (raw, normalized) in LEAD_CASES.items()
    }
    return jobs, leads


def _stored(connection, jobs: dict, leads: dict) -> tuple[dict, dict]:
    job_rows = dict(
        (row[0], (row[1], row[2]))
        for row in connection.execute(text("SELECT id, subject_type, subject_id FROM jobs"))
    )
    lead_rows = dict(
        (row[0], (row[1], row[2]))
        for row in connection.execute(text("SELECT id, meta_platform, meta_ad_id FROM meta_leads"))
    )
    return (
        {name: job_rows[job_id] for name, job_id in jobs.items()},
        {name: lead_rows[lead_id] for name, lead_id in leads.items()},
    )


def test_backfill_and_triggers_match_the_jsonb_lookups(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _config(connection)
        try:
            command.downgrade(config, PREVIOUS)
            assert {"subject_type", "subject_id"}.isdisjoint(_columns(connection, "jobs"))
            assert {"meta_platform", "meta_ad_id"}.isdisjoint(_columns(connection, "meta_leads"))
            backfilled = _seed(connection, uuid.uuid4())
            payloads_before = connection.execute(
                text("SELECT id, payload FROM jobs ORDER BY id")
            ).all()

            command.upgrade(config, "head")

            assert _stored(connection, *backfilled) == (JOB_EXPECTED, LEAD_EXPECTED)
            assert (
                connection.execute(text("SELECT id, payload FROM jobs ORDER BY id")).all()
                == payloads_before
            )
            # Rows written after the upgrade, including by pre-release code, get the same values.
            assert _stored(connection, *_seed(connection, uuid.uuid4())) == (
                JOB_EXPECTED,
                LEAD_EXPECTED,
            )

            jobs, leads = backfilled
            connection.execute(
                text("UPDATE jobs SET job_type = 'send_email' WHERE id = :id"),
                {"id": jobs["workflow"]},
            )
            connection.execute(
                text(
                    'UPDATE meta_leads SET field_data_raw = \'{"meta_platform": "messenger"}\' '
                    "WHERE id = :id"
                ),
                {"id": leads["none"]},
            )
            job_values, lead_values = _stored(connection, jobs, leads)
            assert job_values["workflow"] == (None, None)
            assert lead_values["none"] == ("messenger", None)

            command.downgrade(config, PREVIOUS)
            assert {"subject_type", "subject_id"}.isdisjoint(_columns(connection, "jobs"))
            assert {"meta_platform", "meta_ad_id"}.isdisjoint(_columns(connection, "meta_leads"))
            command.upgrade(config, "head")
        finally:
            transaction.rollback()
