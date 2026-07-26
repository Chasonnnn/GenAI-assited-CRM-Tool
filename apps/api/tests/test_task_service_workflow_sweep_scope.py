from datetime import date, datetime, time, timezone
from uuid import uuid4

from app.core.encryption import hash_email
from app.db.enums import OwnerType, TaskType
from app.db.models import Organization, Surrogate, Task
from app.services import task_service
from app.utils.normalization import normalize_email


def _create_cross_org_sweep_tasks(db, test_org, test_user, default_stage):
    other_org = Organization(
        id=uuid4(),
        name="Other Organization",
        slug=f"other-org-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)

    email = normalize_email(f"sweep-{uuid4().hex[:8]}@example.com")
    surrogate = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Workflow Sweep Surrogate",
        email=email,
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()

    due_date = date(2026, 7, 25)
    valid_task = Task(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_id=surrogate.id,
        created_by_user_id=test_user.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        title="In-scope task",
        task_type=TaskType.OTHER.value,
        due_date=due_date,
        due_time=time(12, 0),
    )
    cross_org_task = Task(
        id=uuid4(),
        organization_id=other_org.id,
        surrogate_id=surrogate.id,
        created_by_user_id=test_user.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        title="Cross-organization task",
        task_type=TaskType.OTHER.value,
        due_date=due_date,
        due_time=time(12, 0),
    )
    db.add_all([valid_task, cross_org_task])
    db.flush()
    return valid_task, cross_org_task


def test_iter_tasks_due_in_window_requires_task_organization_match(
    db,
    test_org,
    test_user,
    default_stage,
):
    valid_task, cross_org_task = _create_cross_org_sweep_tasks(
        db,
        test_org,
        test_user,
        default_stage,
    )

    tasks = list(
        task_service.iter_tasks_due_in_window(
            db,
            test_org.id,
            datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 25, 23, 59, tzinfo=timezone.utc),
        )
    )

    assert [task.id for task in tasks] == [valid_task.id]
    assert cross_org_task.id not in {task.id for task in tasks}


def test_iter_overdue_tasks_requires_task_organization_match(
    db,
    test_org,
    test_user,
    default_stage,
):
    valid_task, cross_org_task = _create_cross_org_sweep_tasks(
        db,
        test_org,
        test_user,
        default_stage,
    )

    tasks = list(
        task_service.iter_overdue_tasks(
            db,
            test_org.id,
            date(2026, 7, 26),
        )
    )

    assert [task.id for task in tasks] == [valid_task.id]
    assert cross_org_task.id not in {task.id for task in tasks}
