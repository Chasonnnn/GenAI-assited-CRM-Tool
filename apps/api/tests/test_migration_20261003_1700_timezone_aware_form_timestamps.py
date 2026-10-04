"""UTC wall-clock data survives both conversions, independent of the session timezone."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command

PREVIOUS = "20261003_1600_notification_daily_digest"
REVISION = "20261003_1700_timezone_aware_form_timestamps"


def _insert(connection, table, **values):
    row_id = uuid4()
    values = {"id": row_id, **values}
    expressions = [
        f"CAST(:{key} AS jsonb)" if isinstance(value, (dict, list)) else f":{key}"
        for key, value in values.items()
    ]
    columns = ", ".join(f'"{key}"' for key in values)
    connection.execute(
        text(f"INSERT INTO {table} ({columns}) VALUES ({', '.join(expressions)})"),
        {
            key: json.dumps(value) if isinstance(value, (dict, list)) else value
            for key, value in values.items()
        },
    )
    return row_id


def _seed_rows(connection):
    rows = {}
    org = _insert(connection, "organizations", name="UTC migration", slug=uuid4().hex)
    user = _insert(connection, "users", email=f"{uuid4()}@example.com", display_name="Reviewer")
    pipeline = _insert(
        connection,
        "pipelines",
        organization_id=org,
        entity_type="surrogate",
        name="Default",
        is_default=True,
        current_version=1,
    )
    rows["pipeline_stages"] = stage = _insert(
        connection,
        "pipeline_stages",
        pipeline_id=pipeline,
        stage_key="new",
        slug="new",
        stage_type="intake",
        label="New",
        color="#3B82F6",
        order=1,
        is_active=True,
    )
    surrogate = _insert(
        connection,
        "surrogates",
        organization_id=org,
        surrogate_number="S10001",
        stage_id=stage,
        status_label="New",
        owner_type="user",
        owner_id=user,
        full_name="Applicant",
        email="encrypted",
        email_hash=uuid4().hex,
    )
    rows["forms"] = form = _insert(connection, "forms", organization_id=org, name="Application")
    rows["form_submissions"] = submission = _insert(
        connection,
        "form_submissions",
        organization_id=org,
        form_id=form,
        answers_json={},
    )
    rows["form_intake_links"] = link = _insert(
        connection,
        "form_intake_links",
        organization_id=org,
        form_id=form,
        slug=uuid4().hex,
    )
    rows["form_logos"] = _insert(
        connection,
        "form_logos",
        organization_id=org,
        storage_key="logo",
        filename="logo.png",
        content_type="image/png",
        file_size=1,
    )
    rows["form_field_mappings"] = _insert(
        connection,
        "form_field_mappings",
        form_id=form,
        field_key="name",
        surrogate_field="full_name",
    )
    rows["form_submission_drafts"] = _insert(
        connection,
        "form_submission_drafts",
        organization_id=org,
        form_id=form,
        surrogate_id=surrogate,
    )
    rows["form_intake_drafts"] = _insert(
        connection,
        "form_intake_drafts",
        organization_id=org,
        form_id=form,
        intake_link_id=link,
        draft_session_id=uuid4().hex,
    )
    rows["form_submission_files"] = _insert(
        connection,
        "form_submission_files",
        organization_id=org,
        submission_id=submission,
        filename="photo.png",
        storage_key="photo",
        content_type="image/png",
        file_size=1,
        checksum_sha256="a" * 64,
    )
    rows["form_submission_match_candidates"] = _insert(
        connection,
        "form_submission_match_candidates",
        organization_id=org,
        submission_id=submission,
        surrogate_id=surrogate,
        reason="identity",
    )
    rows["published_intake_versions"] = _insert(
        connection,
        "published_intake_versions",
        organization_id=org,
        form_id=form,
        intake_link_id=link,
        version=1,
        form_version_hash="a" * 64,
        form_schema_snapshot_json={},
        field_policy_snapshot_json={},
        mapping_snapshot_json=[],
        thank_you_config_snapshot_json={},
        tracking_mode_snapshot="off",
        tracking_policy_hash="b" * 64,
        embed_theme_snapshot_json={},
    )
    rows["intake_leads"] = _insert(
        connection, "intake_leads", organization_id=org, form_id=form, full_name="Applicant"
    )
    rows["lead_attribution"] = _insert(
        connection,
        "lead_attribution",
        organization_id=org,
        form_submission_id=submission,
        intake_link_id=link,
        source_surface="shared",
    )
    rows["consent_records"] = _insert(
        connection,
        "consent_records",
        organization_id=org,
        form_submission_id=submission,
        intake_link_id=link,
        consent_type="tracking",
        accepted=True,
    )
    rows["embed_sessions"] = _insert(
        connection,
        "embed_sessions",
        organization_id=org,
        intake_link_id=link,
        public_session_token_hash=uuid4().hex,
        parent_origin="https://example.com",
        expires_at=datetime(2026, 10, 4),
    )
    rows["tracking_event_logs"] = _insert(
        connection,
        "tracking_event_logs",
        organization_id=org,
        event_name="Lead",
        destination="meta",
        status="pending",
        payload_json={},
        payload_hash="a" * 64,
    )
    return rows


def test_upgrade_preserves_utc_values_and_downgrade_restores_wall_clock(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, PREVIOUS)
            columns = connection.execute(
                text("""
                SELECT table_name, column_name, is_nullable FROM information_schema.columns
                WHERE table_schema = 'public' AND data_type = 'timestamp without time zone'
                ORDER BY table_name, ordinal_position
            """)
            ).all()
            assert len(columns) == 34
            expected = []
            for sample, instant in enumerate(
                (datetime(2026, 10, 3, 23, 49), datetime(2026, 1, 3, 23, 49))
            ):
                rows = _seed_rows(connection)
                for index, (table, column, nullable) in enumerate(columns):
                    value = (
                        None
                        if sample == 1 and nullable == "YES"
                        else instant + timedelta(microseconds=index)
                    )
                    connection.execute(
                        text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),
                        {"id": rows[table], "value": value},
                    )
                    expected.append((table, column, rows[table], value))

            connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
            command.upgrade(config, REVISION)
            for table, column, row_id, value in expected:
                actual = connection.execute(
                    text(f"SELECT {column} FROM {table} WHERE id = :id"), {"id": row_id}
                ).scalar_one()
                assert actual == (value.replace(tzinfo=UTC) if value else None), (table, column)
                if actual is not None:
                    assert actual.utcoffset() is not None
            assert (
                connection.execute(
                    text("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_schema = 'public' AND data_type = 'timestamp without time zone'
            """)
                ).scalar_one()
                == 0
            )
            # now() remains an instant even when the connection's wall clock is not UTC.
            form = _insert(
                connection,
                "forms",
                organization_id=connection.execute(
                    text("SELECT organization_id FROM forms WHERE id = :id"), {"id": rows["forms"]}
                ).scalar_one(),
                name="Default timestamp",
            )
            assert connection.execute(
                text("SELECT created_at = now() FROM forms WHERE id = :id"), {"id": form}
            ).scalar_one()

            connection.execute(text("SET LOCAL TIME ZONE 'Asia/Tokyo'"))
            command.downgrade(config, PREVIOUS)
            for table, column, row_id, value in expected:
                actual = connection.execute(
                    text(f"SELECT {column} FROM {table} WHERE id = :id"), {"id": row_id}
                ).scalar_one()
                assert actual == value, (table, column)
                if actual is not None:
                    assert actual.tzinfo is None
        finally:
            transaction.rollback()
