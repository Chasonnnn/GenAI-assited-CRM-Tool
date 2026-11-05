"""Promoted job, Meta lead, and surrogate columns match the JSONB lookups they replace."""

import json
import uuid
from datetime import UTC, datetime
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

# name: (field_data_raw, field_data, raw_payload); expected columns follow.
LEAD_CASES = {
    "raw_first": (
        {"platform": "ig", "ad_id": "a1", "fbc": "fb.1.raw"},
        {"meta_platform": "fb", "meta_ad_id": "a2", "fbc": "fb.1.normalized"},
        None,
    ),
    "normalized": (
        {"question": "yes"},
        {"publisher_platform": "facebook", "ad_id": "a3"},
        {"tracking": [{"Click-ID": ["  fb.1.payload  "]}]},
    ),
    # Coalesce keeps an empty string, and analytics treats it with nullif.
    "empty": ({"meta_platform": ""}, {"meta_platform": "fb"}, None),
    # The first click id found decides, even when it lacks the fb. prefix.
    "not_meta_click": ({"click_id": "gclid-1"}, {"fbc": "fb.1.later"}, None),
    "not_object": ([{"name": "platform"}], None, None),
    "none": (None, None, None),
}
# (meta_platform, meta_ad_id, meta_click_id)
LEAD_EXPECTED = {
    "raw_first": ("ig", "a1", "fb.1.raw"),
    "normalized": ("facebook", "a3", "fb.1.payload"),
    "empty": ("", None, None),
    "not_meta_click": (None, None, None),
    "not_object": (None, None, None),
    "none": (None, None, None),
}
FROZEN_UPDATED_AT = datetime(2020, 1, 1, tzinfo=UTC)


def _config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.attributes["connection"] = connection
    return config


def _columns(connection, table: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table)}


def _json(value) -> str | None:
    return None if value is None else json.dumps(value)


def _seed_surrogates(connection, org_id) -> dict:
    """Seed surrogates, then freeze updated_at and search_vector with triggers off."""
    pipeline_id = connection.execute(
        text(
            "INSERT INTO pipelines (organization_id, name, is_default, current_version) "
            "VALUES (:org, 'Promote', false, 1) RETURNING id"
        ),
        {"org": org_id},
    ).scalar_one()
    stage_id = connection.execute(
        text(
            'INSERT INTO pipeline_stages (pipeline_id, stage_key, stage_type, label, color, "order", '
            "slug) VALUES (:pipeline, 'new', 'intake', 'New', '#000000', 1, 'new') RETURNING id"
        ),
        {"pipeline": pipeline_id},
    ).scalar_one()
    metadata = {
        "meta_ad": {"meta_ad_name": "Spring ad", "question": "yes"},
        "csv": {"Column A": "value"},
        "none": None,
    }
    ids = {
        name: connection.execute(
            text(
                """
                INSERT INTO surrogates (
                    organization_id, stage_id, status_label, owner_type, owner_id,
                    surrogate_number, full_name, email, email_hash, import_metadata
                ) VALUES (
                    :org, :stage, 'New', 'user', :owner, :number, 'Frozen Name',
                    'frozen@example.com', :hash, CAST(:metadata AS jsonb)
                ) RETURNING id
                """
            ),
            {
                "org": org_id,
                "stage": stage_id,
                "owner": uuid.uuid4(),
                "number": f"S{uuid.uuid4().hex[:8]}",
                "hash": uuid.uuid4().hex * 2,
                "metadata": _json(value),
            },
        ).scalar_one()
        for name, value in metadata.items()
    }
    connection.execute(text("SET LOCAL session_replication_role = replica"))
    connection.execute(
        text(
            "UPDATE surrogates SET updated_at = :frozen, "
            "search_vector = to_tsvector('simple', 'frozen') WHERE id = ANY(:ids)"
        ),
        {"frozen": FROZEN_UPDATED_AT, "ids": list(ids.values())},
    )
    connection.execute(text("SET LOCAL session_replication_role = origin"))
    return ids


def _surrogate_rows(connection, ids: dict) -> dict:
    rows = {
        row[0]: tuple(row[1:])
        for row in connection.execute(
            text("SELECT id, meta_ad_name, updated_at, search_vector::text FROM surrogates")
        )
    }
    return {name: rows[surrogate_id] for name, surrogate_id in ids.items()}


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
                "INSERT INTO meta_leads "
                "(organization_id, meta_lead_id, field_data_raw, field_data, raw_payload) "
                "VALUES (:org, :lead, CAST(:raw AS jsonb), CAST(:normalized AS jsonb), "
                "CAST(:payload AS jsonb)) RETURNING id"
            ),
            {
                "org": org_id,
                "lead": f"lead-{name}",
                "raw": _json(raw),
                "normalized": _json(normalized),
                "payload": _json(payload),
            },
        ).scalar_one()
        for name, (raw, normalized, payload) in LEAD_CASES.items()
    }
    return jobs, leads


def _stored(connection, jobs: dict, leads: dict) -> tuple[dict, dict]:
    job_rows = dict(
        (row[0], (row[1], row[2]))
        for row in connection.execute(text("SELECT id, subject_type, subject_id FROM jobs"))
    )
    lead_rows = dict(
        (row[0], tuple(row[1:]))
        for row in connection.execute(
            text("SELECT id, meta_platform, meta_ad_id, meta_click_id FROM meta_leads")
        )
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
            assert {"meta_platform", "meta_ad_id", "meta_click_id"}.isdisjoint(
                _columns(connection, "meta_leads")
            )
            assert "meta_ad_name" not in _columns(connection, "surrogates")
            org_id = uuid.uuid4()
            backfilled = _seed(connection, org_id)
            surrogates = _seed_surrogates(connection, org_id)
            payloads_before = connection.execute(
                text("SELECT id, payload FROM jobs ORDER BY id")
            ).all()

            command.upgrade(config, "head")

            assert _stored(connection, *backfilled) == (JOB_EXPECTED, LEAD_EXPECTED)
            assert (
                connection.execute(text("SELECT id, payload FROM jobs ORDER BY id")).all()
                == payloads_before
            )
            # The backfill is not a record edit, so updated_at and search_vector stay frozen.
            frozen = (FROZEN_UPDATED_AT, "'frozen':1")
            assert _surrogate_rows(connection, surrogates) == {
                "meta_ad": ("Spring ad", *frozen),
                "csv": (None, *frozen),
                "none": (None, *frozen),
            }
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
            connection.execute(
                text('UPDATE meta_leads SET raw_payload = \'{"fbc": "fb.1.late"}\' WHERE id = :id'),
                {"id": leads["empty"]},
            )
            connection.execute(
                text(
                    "UPDATE surrogates SET import_metadata = "
                    '\'{"meta_ad_name": "Imported ad"}\' WHERE id = :id'
                ),
                {"id": surrogates["csv"]},
            )
            job_values, lead_values = _stored(connection, jobs, leads)
            assert job_values["workflow"] == (None, None)
            assert lead_values["none"] == ("messenger", None, None)
            assert lead_values["empty"] == ("", None, "fb.1.late")
            assert _surrogate_rows(connection, surrogates)["csv"][0] == "Imported ad"

            command.downgrade(config, PREVIOUS)
            assert {"subject_type", "subject_id"}.isdisjoint(_columns(connection, "jobs"))
            assert {"meta_platform", "meta_ad_id", "meta_click_id"}.isdisjoint(
                _columns(connection, "meta_leads")
            )
            assert "meta_ad_name" not in _columns(connection, "surrogates")
            command.upgrade(config, "head")
        finally:
            transaction.rollback()
