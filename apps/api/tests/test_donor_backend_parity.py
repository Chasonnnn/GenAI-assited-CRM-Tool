import csv
import io
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db.enums import OwnerType, Role
from app.db.models import (
    Donor,
    Membership,
    Organization,
    Pipeline,
    PipelineStage,
    User,
)
from app.schemas.donor import DonorCreate, DonorUpdate
from app.services import (
    admin_export_service,
    alert_service,
    donor_service,
    workflow_triggers,
)


def _seed_donor_pipeline(
    db,
    org_id,
    donor_type: str = "egg",
) -> tuple[PipelineStage, PipelineStage]:
    pipeline = Pipeline(
        organization_id=org_id,
        entity_type=f"{donor_type}_donor",
        name=f"{donor_type.title()} Donors",
        is_default=True,
        current_version=1,
        feature_config={},
    )
    db.add(pipeline)
    db.flush()
    entry = PipelineStage(
        pipeline_id=pipeline.id,
        stage_key="new",
        slug="new",
        label="New",
        color="#3B82F6",
        stage_type="intake",
        order=1,
        is_active=True,
        is_intake_stage=True,
    )
    next_stage = PipelineStage(
        pipeline_id=pipeline.id,
        stage_key="contacted",
        slug="contacted",
        label="Contacted",
        color="#06B6D4",
        stage_type="intake",
        order=2,
        is_active=True,
        is_intake_stage=False,
    )
    db.add_all([entry, next_stage])
    db.flush()
    return entry, next_stage


def _create_donor(db, test_org, test_user, *, name: str, email: str) -> Donor:
    return donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(donor_type="egg", full_name=name, email=email),
        emit_workflow_events=False,
    )


@pytest.mark.asyncio
async def test_donor_list_filters_inclusive_creation_dates_and_supports_stable_sorting(
    db,
    test_org,
    test_user,
    authed_client,
):
    _seed_donor_pipeline(db, test_org.id)
    first = _create_donor(
        db,
        test_org,
        test_user,
        name="Zulu Donor",
        email="donor-date-zulu@example.com",
    )
    middle = _create_donor(
        db,
        test_org,
        test_user,
        name="Alpha Donor",
        email="donor-date-alpha@example.com",
    )
    last = _create_donor(
        db,
        test_org,
        test_user,
        name="Middle Donor",
        email="donor-date-middle@example.com",
    )
    first.created_at = datetime(2026, 8, 1, 23, 59, tzinfo=UTC)
    middle.created_at = datetime(2026, 8, 2, 23, 59, tzinfo=UTC)
    last.created_at = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    db.commit()

    response = await authed_client.get(
        "/donors",
        params={
            "donor_type": "egg",
            "created_from": "2026-08-02",
            "created_to": "2026-08-02",
        },
    )

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["items"]] == [str(middle.id)]

    sorted_response = await authed_client.get(
        "/donors",
        params={"donor_type": "egg", "sort_by": "full_name", "sort_order": "asc"},
    )
    assert sorted_response.status_code == 200, sorted_response.text
    assert [item["full_name"] for item in sorted_response.json()["items"]] == [
        "Alpha Donor",
        "Middle Donor",
        "Zulu Donor",
    ]


def test_donor_archive_and_restore_append_lifecycle_history(db, test_org, test_user):
    _seed_donor_pipeline(db, test_org.id)
    donor = _create_donor(
        db,
        test_org,
        test_user,
        name="Lifecycle Donor",
        email="donor-lifecycle@example.com",
    )

    donor_service.archive_donor(db, donor, test_user.id)
    restored = donor_service.restore_donor(db, donor, test_user.id)

    history = donor_service.get_status_history(db, test_org.id, donor.id)
    assert [item.reason for item in history[:2]] == ["Donor restored", "Donor archived"]
    assert all(
        item.old_stage_id == item.new_stage_id == restored.stage_id
        for item in history[:2]
    )
    assert all(item.old_status == item.new_status == restored.stage_key for item in history[:2])


@pytest.mark.parametrize(
    ("operation", "trigger_name"),
    [
        ("create", "trigger_donor_created"),
        ("update", "trigger_donor_updated"),
    ],
)
def test_donor_mutation_succeeds_when_workflow_trigger_fails(
    db,
    test_org,
    test_user,
    monkeypatch,
    caplog,
    operation,
    trigger_name,
):
    _seed_donor_pipeline(db, test_org.id)
    alerts: list[dict] = []

    def fail_trigger(*args, **kwargs):
        raise RuntimeError("synthetic workflow failure with private@example.com")

    monkeypatch.setattr(workflow_triggers, trigger_name, fail_trigger)
    monkeypatch.setattr(
        alert_service,
        "record_alert_isolated",
        lambda **kwargs: alerts.append(kwargs),
    )

    if operation == "create":
        donor = donor_service.create_donor(
            db,
            test_org.id,
            test_user.id,
            DonorCreate(
                donor_type="egg",
                full_name="Workflow Failure Donor",
                email="donor-workflow-create@example.com",
            ),
        )
    else:
        donor = _create_donor(
            db,
            test_org,
            test_user,
            name="Before Update",
            email="donor-workflow-update@example.com",
        )
        donor = donor_service.update_donor(
            db,
            donor,
            test_user.id,
            DonorUpdate(full_name="After Update"),
        )

    persisted = donor_service.get_donor(db, test_org.id, donor.id)
    assert persisted is not None
    assert persisted.full_name == donor.full_name
    assert len(alerts) == 1
    assert alerts[0]["org_id"] == test_org.id
    assert "private@example.com" not in (alerts[0].get("message") or "")
    assert "private@example.com" not in caplog.text


def test_failed_assignment_workflow_rolls_back_before_following_update_trigger(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    _seed_donor_pipeline(db, test_org.id)
    donor = _create_donor(
        db,
        test_org,
        test_user,
        name="Assignment Workflow Donor",
        email="donor-assignment-workflow@example.com",
    )
    updated_calls: list[list[str]] = []

    def fail_assignment(db_session, *args, **kwargs):
        db_session.execute(text("SELECT 1 / 0"))

    def record_update(db_session, _donor, changed_fields):
        assert db_session.execute(text("SELECT 1")).scalar() == 1
        updated_calls.append(changed_fields)

    monkeypatch.setattr(workflow_triggers, "trigger_donor_assigned", fail_assignment)
    monkeypatch.setattr(workflow_triggers, "trigger_donor_updated", record_update)
    monkeypatch.setattr(alert_service, "record_alert_isolated", lambda **kwargs: None)

    updated = donor_service.update_donor(
        db,
        donor,
        test_user.id,
        DonorUpdate(owner_type=OwnerType.USER.value, owner_id=test_user.id),
    )

    assert updated.owner_id == test_user.id
    assert updated_calls == [["owner_id", "owner_type"]]
    assert donor_service.get_donor(db, test_org.id, donor.id) is not None


@pytest.mark.parametrize("owner_type", [OwnerType.USER.value, OwnerType.QUEUE.value])
def test_donor_export_never_resolves_foreign_tenant_owner(
    db,
    test_org,
    test_user,
    owner_type,
):
    from app.db.models import Queue

    _seed_donor_pipeline(db, test_org.id)
    donor = _create_donor(
        db,
        test_org,
        test_user,
        name="Scoped Export Donor",
        email=f"donor-export-{owner_type}@example.com",
    )
    foreign_org = Organization(
        name=f"Foreign export {owner_type}",
        slug=f"foreign-export-{owner_type}-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(foreign_org)
    db.flush()
    if owner_type == OwnerType.USER.value:
        foreign_owner = User(
            email=f"foreign-owner-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Foreign Private Owner",
            token_version=1,
            is_active=True,
        )
        db.add(foreign_owner)
        db.flush()
        db.add(
            Membership(
                user_id=foreign_owner.id,
                organization_id=foreign_org.id,
                role=Role.CASE_MANAGER.value,
                is_active=True,
            )
        )
        foreign_name = foreign_owner.display_name
        foreign_email = foreign_owner.email
    else:
        foreign_owner = Queue(
            organization_id=foreign_org.id,
            name="Foreign Private Queue",
        )
        db.add(foreign_owner)
        foreign_name = foreign_owner.name
        foreign_email = ""
    db.flush()
    donor.owner_type = owner_type
    donor.owner_id = foreign_owner.id
    db.commit()

    rows = list(
        csv.DictReader(
            io.StringIO(
                "".join(admin_export_service.stream_donors_csv(db, test_org.id))
            )
        )
    )

    row = next(item for item in rows if item["id"] == str(donor.id))
    assert foreign_name not in {row["owner_name"], row["owner_queue_name"]}
    if foreign_email:
        assert foreign_email != row["owner_email"]


def test_donor_export_rejects_a_cross_tenant_current_stage(db, test_org, test_user):
    _seed_donor_pipeline(db, test_org.id)
    donor = _create_donor(
        db,
        test_org,
        test_user,
        name="Scoped Stage Donor",
        email="donor-export-stage@example.com",
    )
    foreign_org = Organization(
        name="Foreign stage export",
        slug=f"foreign-stage-export-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(foreign_org)
    db.flush()
    foreign_pipeline = Pipeline(
        organization_id=foreign_org.id,
        entity_type="egg_donor",
        name="Private foreign donor pipeline",
        is_default=True,
        current_version=1,
        feature_config={},
    )
    db.add(foreign_pipeline)
    db.flush()
    foreign_stage = PipelineStage(
        pipeline_id=foreign_pipeline.id,
        stage_key="private_foreign_stage",
        slug="private-foreign-stage",
        label="Private Foreign Stage",
        color="#000000",
        stage_type="intake",
        order=1,
        is_active=True,
        is_intake_stage=True,
    )
    db.add(foreign_stage)
    db.flush()
    donor.stage_id = foreign_stage.id
    db.commit()
    db.expire_all()

    with pytest.raises(ValueError, match="Current stage mismatch for donor") as exc_info:
        list(admin_export_service.stream_donors_csv(db, test_org.id))

    assert foreign_stage.label not in str(exc_info.value)
    assert foreign_pipeline.name not in str(exc_info.value)
