from __future__ import annotations

import sqlalchemy as sa


def test_head_schema_has_no_send_rate_slots(db) -> None:
    assert not sa.inspect(db.connection()).has_table("messaging_provider_admission")
