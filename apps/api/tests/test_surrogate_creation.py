from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.enums import AlertSeverity, AlertType
from app.db.models import OrgCounter, SystemAlert
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service
from app.utils.normalization import normalize_identifier


def test_create_surrogate_repairs_stale_counter_drift_and_records_alert(
    db, test_org, test_user
):
    first = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Counter Drift First",
            email=f"counter-drift-first-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )
    second = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Counter Drift High Watermark",
            email=f"counter-drift-high-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )
    assert first.surrogate_number == "S10001"
    second.surrogate_number = "S10500"
    second.surrogate_number_normalized = normalize_identifier("S10500")
    db.commit()

    counter = (
        db.query(OrgCounter)
        .filter(
            OrgCounter.organization_id == test_org.id,
            OrgCounter.counter_type == "surrogate_number",
        )
        .one()
    )
    counter.current_value = 10000
    db.commit()

    created = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Counter Drift New",
            email=f"counter-drift-new-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )

    db.refresh(created)
    db.refresh(counter)

    assert created.surrogate_number == "S10501"
    assert counter.current_value == 10501

    alert = (
        db.query(SystemAlert)
        .filter(
            SystemAlert.organization_id == test_org.id,
            SystemAlert.alert_type == AlertType.SURROGATE_NUMBER_COUNTER_DRIFT.value,
        )
        .one()
    )

    assert alert.severity == AlertSeverity.WARN.value
    assert alert.integration_key == "surrogate_number_counter"
    assert alert.title == "Surrogate number counter drift repaired"
    assert alert.occurrence_count == 1
    assert alert.details == {
        "attempted_surrogate_number": "S10001",
        "attempted_counter_value": 10000,
        "repaired_counter_value": 10500,
        "counter_gap": 500,
    }


@pytest.mark.asyncio
async def test_create_surrogate_duplicate_email_conflict_returns_409(authed_client, monkeypatch):
    from app.routers import surrogates_write

    def _raise_duplicate_email(*_args, **_kwargs):
        orig = SimpleNamespace(
            diag=SimpleNamespace(constraint_name="uq_surrogate_email_hash_active")
        )
        raise IntegrityError("insert", {}, orig)

    monkeypatch.setattr(surrogates_write.surrogate_service, "create_surrogate", _raise_duplicate_email)

    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Duplicate Email",
            "email": f"duplicate-email-{uuid.uuid4().hex[:8]}@example.com",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A surrogate with this email already exists"


@pytest.mark.asyncio
async def test_create_surrogate_number_conflict_returns_retryable_error(
    authed_client, monkeypatch
):
    from app.routers import surrogates_write

    def _raise_number_conflict(*_args, **_kwargs):
        orig = SimpleNamespace(diag=SimpleNamespace(constraint_name="uq_surrogate_number"))
        raise IntegrityError("insert", {}, orig)

    monkeypatch.setattr(surrogates_write.surrogate_service, "create_surrogate", _raise_number_conflict)

    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Counter Conflict",
            "email": f"counter-conflict-{uuid.uuid4().hex[:8]}@example.com",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to allocate a new surrogate number. Please retry."
