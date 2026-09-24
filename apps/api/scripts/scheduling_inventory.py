"""Read-only, organization-scoped scheduling rollout inventory (no client data)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def inventory(connection, organization_id: UUID) -> dict:
    scope = {"org": organization_id}
    groups = (
        connection.execute(
            text(
                "SELECT origin, status, meeting_mode, google_sync_state, count(*) AS count "
                "FROM appointments WHERE organization_id = :org "
                "GROUP BY origin, status, meeting_mode, google_sync_state "
                "ORDER BY origin, status, meeting_mode, google_sync_state"
            ),
            scope,
        )
        .mappings()
        .all()
    )
    links = (
        connection.execute(
            text(
                "SELECT count(*) FILTER (WHERE google_event_id IS NOT NULL) AS linked, "
                "count(*) FILTER (WHERE google_event_id IS NOT NULL AND "
                "(google_calendar_id IS NULL OR google_integration_id IS NULL OR "
                "google_account_email IS NULL)) AS ambiguous_links, "
                "count(*) FILTER (WHERE origin = 'legacy_unknown') AS legacy_unknown "
                "FROM appointments WHERE organization_id = :org"
            ),
            scope,
        )
        .mappings()
        .one()
    )
    duplicates = connection.execute(
        text(
            "SELECT count(*) FROM (SELECT google_integration_id, google_calendar_id, google_event_id "
            "FROM appointments WHERE organization_id = :org AND google_event_id IS NOT NULL "
            "AND google_integration_id IS NOT NULL AND google_calendar_id IS NOT NULL "
            "GROUP BY google_integration_id, google_calendar_id, google_event_id "
            "HAVING count(*) > 1) AS duplicate_links"
        ),
        scope,
    ).scalar_one()
    bindings = (
        connection.execute(
            text(
                "SELECT count(*) AS active, "
                "count(*) FILTER (WHERE write_bookings) AS booking_destinations, "
                "count(*) FILTER (WHERE check_busy AND (synced_at IS NULL OR sync_error IS NOT NULL "
                "OR synced_at < now() - interval '10 minutes')) AS unavailable_busy_sources "
                "FROM calendar_bindings WHERE organization_id = :org AND is_active"
            ),
            scope,
        )
        .mappings()
        .one()
    )
    jobs = (
        connection.execute(
            text(
                "SELECT job_type, status, count(*) AS count FROM jobs "
                "WHERE organization_id = :org AND job_type IN "
                "('appointment_google_sync', 'google_calendar_sync', 'google_calendar_watch_refresh') "
                "GROUP BY job_type, status ORDER BY job_type, status"
            ),
            scope,
        )
        .mappings()
        .all()
    )
    return {
        "organization_id": str(organization_id),
        "appointments": [dict(row) for row in groups],
        "links": {**dict(links), "duplicate_exact_resources": duplicates},
        "bindings": dict(bindings),
        "jobs": [dict(row) for row in jobs],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", required=True, type=UUID)
    args = parser.parse_args()
    from app.db.session import engine

    with engine.connect() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))
        print(json.dumps(inventory(connection, args.organization_id), indent=2))


if __name__ == "__main__":
    main()
