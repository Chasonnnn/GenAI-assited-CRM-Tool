"""ORM timestamps always carry an offset through the API boundary."""

from sqlalchemy import DateTime

from app.db import models  # noqa: F401 -- register every model with Base
from app.db.base import Base


def test_all_model_timestamps_are_timezone_aware():
    naive = sorted(
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, DateTime) and not column.type.timezone
    )
    assert naive == [], f"Naive timestamp columns: {naive}"
