"""Rollout inventory contains aggregate counts only and remains organization scoped."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.db.models import Appointment, Organization


def test_inventory_excludes_other_organizations_and_client_data(db, test_auth):
    path = Path(__file__).parents[1] / "scripts/scheduling_inventory.py"
    spec = importlib.util.spec_from_file_location("scheduling_inventory", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    other = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    start = datetime.now(UTC) + timedelta(days=2)
    for organization_id in (test_auth.org.id, other.id):
        db.add(
            Appointment(
                organization_id=organization_id,
                user_id=test_auth.user.id,
                client_name="Private synthetic client",
                client_email="private-client@example.test",
                client_phone="555-0100",
                client_timezone="UTC",
                scheduled_start=start,
                scheduled_end=start + timedelta(minutes=30),
                duration_minutes=30,
                meeting_mode="phone",
                status="confirmed",
                origin="legacy_unknown",
                google_event_id="ambiguous-legacy-link",
            )
        )
    db.flush()
    report = module.inventory(db.connection(), test_auth.org.id)
    assert report["links"] == {
        "linked": 1,
        "ambiguous_links": 1,
        "legacy_unknown": 1,
        "duplicate_exact_resources": 0,
    }
    assert sum(row["count"] for row in report["appointments"]) == 1
    assert "private-client" not in str(report)
    assert "Private synthetic" not in str(report)
