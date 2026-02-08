import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.core.encryption import hash_email, hash_phone
from app.db.models import Surrogate
from app.services import analytics_surrogate_service


def _collect_sql_statements(db):
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    return statements, before_cursor_execute


def _remove_sql_listener(db, listener):
    event.remove(db.bind, "before_cursor_execute", listener)


def test_get_analytics_summary_uses_single_surrogates_count_query(
    db, test_org, default_stage, test_user
):
    # Seed one surrogate so the summary isn't trivially empty.
    email = "efficiency@test.com"
    phone = "555-0100"
    s = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        stage_id=default_stage.id,
        full_name="Efficiency User",
        status_label=default_stage.label,
        email=email,
        email_hash=hash_email(email),
        phone=phone,
        phone_hash=hash_phone(phone),
        source="website",
        surrogate_number="S99999",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(s)
    db.flush()

    start = datetime.now(timezone.utc) - timedelta(days=7)
    end = datetime.now(timezone.utc) + timedelta(days=1)

    statements, listener = _collect_sql_statements(db)
    try:
        data = analytics_surrogate_service.get_analytics_summary(db, test_org.id, start, end)
    finally:
        _remove_sql_listener(db, listener)

    # Only count the surrogate-count aggregate query; exclude other queries (pipeline stages, avg time, etc.).
    surrogate_count_selects = [
        s
        for s in statements
        if "from surrogates" in s.lower()
        and "count(" in s.lower()
        and s.lstrip().lower().startswith("select")
    ]
    assert len(surrogate_count_selects) == 1

    assert data["total_surrogates"] == 1
    assert data["new_this_period"] == 1
