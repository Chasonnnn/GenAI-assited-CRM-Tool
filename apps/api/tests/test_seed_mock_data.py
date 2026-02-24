import uuid

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

    ip_count = db.query(IntendedParent).filter(IntendedParent.organization_id == test_org.id).count()
    assert ip_count == 10

    ip_history_count = db.query(IntendedParentStatusHistory).count()
    assert ip_history_count >= 10


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
        row[0]
        for row in db.query(Match.status).filter(Match.organization_id == test_org.id).all()
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
