import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.core.encryption import hash_email, hash_phone
from app.db.enums import ContactStatus, TaskType
from app.db.models import Surrogate, Task
from app.services import surrogate_service


def test_get_surrogate_stats_uses_at_most_two_selects(db, test_org, default_stage, test_user):
    now = datetime.now(timezone.utc)

    # Seed some surrogates.
    for i, created_at in enumerate(
        [now - timedelta(days=1), now - timedelta(days=10), now - timedelta(hours=12)]
    ):
        email = f"stats{i}@example.com"
        phone = "555-0100"
        s = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=default_stage.id,
            full_name=f"Stats User {i}",
            status_label=default_stage.label,
            email=email,
            email_hash=hash_email(email),
            phone=phone,
            phone_hash=hash_phone(phone),
            source="website",
            surrogate_number=f"S{90000 + i}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            contact_status=ContactStatus.UNREACHED.value,
            created_at=created_at,
        )
        db.add(s)
    db.flush()

    # Seed one pending task (dashboard pending count should include it).
    t = Task(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Pending task",
        task_type=TaskType.OTHER.value,
        is_completed=False,
        created_at=now,
        updated_at=now,
    )
    db.add(t)
    db.flush()

    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        surrogate_service.get_surrogate_stats(db, test_org.id)
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)

    selects = [s for s in statements if s.lstrip().lower().startswith("select")]
    assert len(selects) <= 2
