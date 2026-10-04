"""Prepare one explicitly approved primary calendar before API/worker activation."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.models import Membership, Organization, User  # noqa: E402
from app.schemas.calendar_binding import CalendarBindingInput  # noqa: E402
from app.services import calendar_binding_service  # noqa: E402


async def prepare_primary(db, *, organization_id: UUID, user_id: UUID) -> dict:
    """Use scoped services; preserve a different existing calendar selection."""
    if not settings.SCHEDULING_V2_ENABLED:
        raise ValueError("Enable SCHEDULING_V2_ENABLED for this operator process only")
    membership = (
        db.query(Membership)
        .join(Organization, Organization.id == Membership.organization_id)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
            Organization.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if membership is None:
        raise ValueError("Active organization membership required")
    org_id = membership.organization_id
    calendars = await calendar_binding_service.discover_calendars(db, user_id=user_id)
    primary = [calendar for calendar in calendars if calendar["primary"]]
    if len(primary) != 1 or primary[0]["access_role"] not in {"owner", "writer"}:
        raise ValueError("One writable primary calendar required")
    calendar_id = primary[0]["calendar_id"]
    existing = calendar_binding_service.list_bindings(db, org_id=org_id, user_id=user_id)
    if any(binding.calendar_id != calendar_id for binding in existing):
        raise ValueError("Existing calendar selection requires separate review")
    bindings = await calendar_binding_service.replace_bindings(
        db,
        org_id=org_id,
        user_id=user_id,
        items=[CalendarBindingInput(calendar_id=calendar_id, write_bookings=True)],
    )
    binding = next(binding for binding in bindings if binding.calendar_id == calendar_id)
    projected = await calendar_binding_service.sync_binding(
        db, binding_id=binding.id, org_id=org_id
    )
    db.refresh(binding)
    if binding.synced_at is None or binding.sync_error:
        raise ValueError("Calendar snapshot is incomplete; keep production scheduling disabled")
    return {"ready": True, "projection_rows": projected, "synced_at": binding.synced_at.isoformat()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", required=True, type=UUID)
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--primary", required=True, action="store_true")
    args = parser.parse_args()
    # Provider and database exceptions can contain private data. Only emit the
    # aggregate result or exception class from this operator command.
    logging.disable(logging.CRITICAL)
    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            result = asyncio.run(
                prepare_primary(db, organization_id=args.organization_id, user_id=args.user_id)
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"ready": False, "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
