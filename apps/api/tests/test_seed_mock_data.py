import random
import uuid
from types import SimpleNamespace

from app.db.enums import IntendedParentStatus, SurrogateSource
from app.db.models import (
    IntendedParent,
    IntendedParentStatusHistory,
    Match,
    Membership,
    PipelineStage,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    Task,
    User,
)
from app.services import pipeline_service
from scripts import seed_mock_data


def test_seed_surrogate_sources_match_enum() -> None:
    allowed = {source.value for source in SurrogateSource}
    assert set(seed_mock_data.SURROGATE_SOURCES).issubset(allowed)


def test_seed_intended_parent_statuses_match_enum() -> None:
    allowed = {status.value for status in IntendedParentStatus}
    assert set(seed_mock_data.IP_STATUSES).issubset(allowed)


def test_create_surrogates_generates_status_history_and_activity(db, test_org, test_user) -> None:
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline.id)
        .order_by(PipelineStage.order.asc())
        .all()
    )

    seed_mock_data.create_surrogates(
        db,
        test_org.id,
        test_user.id,
        stages,
        count=8,
        activity_mode="rich_core",
    )

    surrogate_ids = [
        row[0]
        for row in db.query(Surrogate.id).filter(Surrogate.organization_id == test_org.id).all()
    ]
    assert len(surrogate_ids) == 8

    history_count = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.organization_id == test_org.id)
        .count()
    )
    assert history_count >= 8

    activity_count = (
        db.query(SurrogateActivityLog)
        .filter(SurrogateActivityLog.organization_id == test_org.id)
        .count()
    )
    assert activity_count >= 8


def test_create_intended_parents_generates_status_history(db, test_org, test_user) -> None:
    seed_mock_data.create_intended_parents(db, test_org.id, test_user.id, count=10)

    ip_count = (
        db.query(IntendedParent).filter(IntendedParent.organization_id == test_org.id).count()
    )
    assert ip_count == 10

    ip_history_count = db.query(IntendedParentStatusHistory).count()
    assert ip_history_count >= 10


def test_create_tasks_generates_open_and_completed_org_scoped_work(db, test_org, test_user) -> None:
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline.id)
        .order_by(PipelineStage.order.asc())
        .all()
    )
    seed_mock_data.create_surrogates(
        db,
        test_org.id,
        test_user.id,
        stages,
        count=5,
        activity_mode="rich_core",
    )

    seed_mock_data.create_tasks(
        db,
        org_id=test_org.id,
        users_by_role={"developer": test_user},
        count=10,
    )

    tasks = db.query(Task).filter(Task.organization_id == test_org.id).all()
    assert len(tasks) == 10
    assert {task.is_completed for task in tasks} == {False, True}
    assert all(task.surrogate_id is not None for task in tasks)


def test_create_matches_balanced_statuses(db, test_org, test_user) -> None:
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Seed Admin",
        token_version=1,
        is_active=True,
    )
    case_manager_user = User(
        id=uuid.uuid4(),
        email=f"manager-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Seed Case Manager",
        token_version=1,
        is_active=True,
    )
    db.add(admin_user)
    db.add(case_manager_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            organization_id=test_org.id,
            role="admin",
            is_active=True,
        )
    )
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=case_manager_user.id,
            organization_id=test_org.id,
            role="case_manager",
            is_active=True,
        )
    )
    db.flush()

    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline.id)
        .order_by(PipelineStage.order.asc())
        .all()
    )

    seed_mock_data.create_surrogates(
        db,
        test_org.id,
        test_user.id,
        stages,
        count=50,
        activity_mode="rich_core",
    )
    seed_mock_data.create_intended_parents(db, test_org.id, test_user.id, count=12)
    seed_mock_data.create_matches(
        db=db,
        org_id=test_org.id,
        users_by_role={
            "developer": test_user,
            "admin": admin_user,
            "case_manager": case_manager_user,
        },
        count=15,
        mode="balanced",
    )

    statuses = {
        row[0] for row in db.query(Match.status).filter(Match.organization_id == test_org.id).all()
    }
    assert {"proposed", "reviewing", "accepted", "rejected", "cancelled"}.issubset(statuses)

    accepted_surrogate_ids = [
        row[0]
        for row in db.query(Match.surrogate_id)
        .filter(
            Match.organization_id == test_org.id,
            Match.status == "accepted",
        )
        .all()
    ]
    assert len(accepted_surrogate_ids) == len(set(accepted_surrogate_ids))


def test_create_matches_is_independent_of_database_row_order(monkeypatch) -> None:
    """Identical logical seed data must choose identical match candidates."""

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return list(self.rows)

    class FakeDb:
        def __init__(self, surrogate_rows, intended_parents):
            self.surrogate_rows = surrogate_rows
            self.intended_parents = intended_parents
            self.query_count = 0

        def query(self, *entities):
            self.query_count += 1
            if self.query_count == 1:
                return FakeQuery(self.surrogate_rows)
            return FakeQuery(self.intended_parents)

        def refresh(self, instance):
            return None

    users_by_role = {
        "case_manager": SimpleNamespace(id=uuid.UUID(int=101)),
        "admin": SimpleNamespace(id=uuid.UUID(int=102)),
        "developer": SimpleNamespace(id=uuid.UUID(int=103)),
    }
    surrogate_rows = [
        (
            SimpleNamespace(id=uuid.UUID(int=index), surrogate_number=f"S{10000 + index}"),
            "ready_to_match",
        )
        for index in range(1, 9)
    ]
    intended_parents = [
        SimpleNamespace(id=uuid.UUID(int=100 + index), intended_parent_number=f"I{10000 + index}")
        for index in range(1, 7)
    ]

    selected_runs: list[list[tuple[str, str, str]]] = []

    def run(rows, ips):
        selected: list[tuple[str, str, str]] = []

        def create_match(*, surrogate_id, intended_parent_id, notes, **kwargs):
            surrogate = next(row[0] for row in surrogate_rows if row[0].id == surrogate_id)
            intended_parent = next(ip for ip in intended_parents if ip.id == intended_parent_id)
            selected.append(
                (surrogate.surrogate_number, intended_parent.intended_parent_number, notes)
            )
            return SimpleNamespace(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                intended_parent_id=intended_parent_id,
                status="proposed",
            )

        def set_status(*, match, **kwargs):
            match.status = kwargs.get("status", match.status)
            return match

        monkeypatch.setattr(
            seed_mock_data.match_service, "get_existing_match", lambda *a, **k: None
        )
        monkeypatch.setattr(seed_mock_data.match_service, "create_match", create_match)
        monkeypatch.setattr(
            seed_mock_data.match_service,
            "mark_match_reviewing_if_needed",
            lambda *, match, **kwargs: set_status(match=match, status="reviewing"),
        )
        monkeypatch.setattr(
            seed_mock_data.match_service,
            "accept_match",
            lambda *, match, **kwargs: set_status(match=match, status="accepted"),
        )
        monkeypatch.setattr(
            seed_mock_data.match_service,
            "reject_match",
            lambda *, match, **kwargs: set_status(match=match, status="rejected"),
        )
        monkeypatch.setattr(
            seed_mock_data.match_service,
            "cancel_match",
            lambda *, match, **kwargs: set_status(match=match, status="cancelled"),
        )

        random.seed(20260714)
        seed_mock_data.create_matches(
            db=FakeDb(rows, ips),
            org_id=uuid.UUID(int=999),
            users_by_role=users_by_role,
            count=10,
            mode="balanced",
        )
        selected_runs.append(selected)

    run(surrogate_rows, intended_parents)
    run(list(reversed(surrogate_rows)), list(reversed(intended_parents)))

    assert selected_runs[0] == selected_runs[1]
