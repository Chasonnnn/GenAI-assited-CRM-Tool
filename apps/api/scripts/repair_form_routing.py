"""Repair one organization's module-routing deployment window (dry run by default)."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def window_timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise argparse.ArgumentTypeError("Window timestamp must include a timezone")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", type=UUID, required=True)
    parser.add_argument("--window-start", type=window_timestamp, required=True)
    parser.add_argument("--released-at", type=window_timestamp, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.window_start > args.released_at:
        parser.error("Window start must not be after release timestamp")
    from app.db.session import SessionLocal
    from app.services.form_routing_maintenance_service import repair_routing_window

    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        result = repair_routing_window(
            db,
            org_id=args.organization_id,
            window_start=args.window_start,
            released_at=args.released_at,
            apply=args.apply,
        )
        print(json.dumps({"applied": args.apply, **result}))


if __name__ == "__main__":
    main()
