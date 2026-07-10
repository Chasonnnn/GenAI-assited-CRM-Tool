from __future__ import annotations

import warnings

from sqlalchemy.exc import SAWarning

import app.db.models  # noqa: F401
from app.db.base import Base


def test_model_metadata_has_no_unresolved_foreign_key_cycles() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", SAWarning)
        list(Base.metadata.sorted_tables)

    cycle_warnings = [
        warning
        for warning in caught
        if "unresolvable cycles" in str(warning.message).lower()
    ]
    assert cycle_warnings == []
