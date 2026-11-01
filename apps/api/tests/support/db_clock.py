"""Read the database clock for tests that bound database-assigned timestamps.

PostgreSQL and the application can disagree by tens of milliseconds, for example
when PostgreSQL runs in a local VM. Bound such timestamps with this clock instead
of datetime.now().
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def database_now(db: Session) -> datetime:
    """Return the database's current wall-clock time (not the transaction start)."""
    return db.execute(select(func.clock_timestamp())).scalar_one()
