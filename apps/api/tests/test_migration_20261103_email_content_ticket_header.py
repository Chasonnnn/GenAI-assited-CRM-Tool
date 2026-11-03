"""The ticket header promotion backfills existing content rows with the stitch parse."""

import json
import uuid
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

PREVIOUS = "20261012_0900_audit_work_indexes"


def test_ticket_header_column_backfills_existing_rows_and_downgrades(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        org_id, ticket_id, fallback_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        def columns():
            return {c["name"] for c in inspect(connection).get_columns("email_message_contents")}

        try:
            command.downgrade(config, PREVIOUS)
            assert "ticket_header_id" not in columns()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Header', :slug)"),
                {"id": org_id, "slug": f"header-migration-{org_id}"},
            )
            cases = {
                "sf": ({"X-SF-Ticket-ID": [str(ticket_id)]}, ticket_id),
                # Invalid and empty values fall through to the next header, as stitching does.
                "fallback": (
                    {
                        "X-SF-Ticket-ID": ["not-a-uuid"],
                        "X-OSS-Ticket-ID": [],
                        "X-CRM-Ticket-ID": [fallback_id.hex],
                    },
                    fallback_id,
                ),
                "braced": ({"X-OSS-Ticket-ID": ["{" + str(ticket_id).upper() + "}"]}, ticket_id),
                "invalid": ({"X-SF-Ticket-ID": ["garbage"]}, None),
                "non_list": ({"X-SF-Ticket-ID": str(ticket_id)}, None),
                "none": ({"Received": ["from mx"]}, None),
            }
            message_ids = {}
            for name, (headers, _expected) in cases.items():
                message_ids[name] = connection.execute(
                    text(
                        """
                        INSERT INTO email_messages
                            (organization_id, direction, fingerprint_sha256, signature_sha256)
                        VALUES (:org, 'inbound', :fp, :sig) RETURNING id
                        """
                    ),
                    {"org": org_id, "fp": uuid.uuid4().hex * 2, "sig": uuid.uuid4().hex * 2},
                ).scalar_one()
                connection.execute(
                    text(
                        """
                        INSERT INTO email_message_contents (organization_id, message_id, headers_json)
                        VALUES (:org, :message_id, CAST(:headers AS jsonb))
                        """
                    ),
                    {
                        "org": org_id,
                        "message_id": message_ids[name],
                        "headers": json.dumps(headers),
                    },
                )
            headers_before = connection.execute(
                text("SELECT message_id, headers_json FROM email_message_contents ORDER BY id")
            ).all()

            command.upgrade(config, "head")

            stored = dict(
                connection.execute(
                    text("SELECT message_id, ticket_header_id FROM email_message_contents")
                ).all()
            )
            for name, (_headers, expected) in cases.items():
                assert stored[message_ids[name]] == expected, name
            assert (
                connection.execute(
                    text("SELECT message_id, headers_json FROM email_message_contents ORDER BY id")
                ).all()
                == headers_before
            )

            command.downgrade(config, PREVIOUS)
            assert "ticket_header_id" not in columns()
            command.upgrade(config, "head")
        finally:
            transaction.rollback()
