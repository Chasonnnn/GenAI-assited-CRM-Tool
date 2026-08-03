"""Public API contracts for organization-scoped messaging consent administration."""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
from app.main import app
from app.services import session_service


@asynccontextmanager
async def _authed_client_for_role(db, organization_id, role: Role):
    user = User(
        id=uuid.uuid4(),
        email=f"messaging-{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Messaging Consent User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization_id,
            role=role.value,
        )
    )
    db.flush()
    token = create_session_token(
        user_id=user.id,
        org_id=organization_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=organization_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _import_payload(**overrides):
    payload = {
        "phone": "+14155550121",
        "purpose": "operational",
        "affirmative": True,
        "disclosure_text": "I agree to receive process texts. Reply STOP to opt out.",
        "source": "website_intake",
        "source_reference": "lead-121",
        "occurred_at": datetime(2026, 7, 31, 20, 0, tzinfo=UTC).isoformat(),
        "idempotency_key": "lead-121-operational",
        "evidence_metadata": {"form_version": "v3"},
    }
    payload.update(overrides)
    return payload


def _revocation_payload(**overrides):
    payload = {
        "phone": "+14155550121",
        "instruction_text": "STOP",
        "route_purpose": "operational",
        "source": "staff_recorded_request",
        "source_reference": "ticket-121",
        "occurred_at": datetime(2026, 7, 31, 20, 5, tzinfo=UTC).isoformat(),
        "idempotency_key": "ticket-121-stop",
        "evidence_metadata": {},
    }
    payload.update(overrides)
    return payload


async def test_admin_imports_affirmative_consent_without_exposing_phone(authed_client):
    response = await authed_client.post(
        "/messaging/consents/import",
        json=_import_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["phone_last4"] == "0121"
    assert payload["purpose_states"] == {
        "operational": "opted_in",
        "promotional": "unknown",
    }
    assert payload["global_suppression_active"] is False
    assert payload["evidence_id"] is not None
    assert "+14155550121" not in response.text


async def test_missing_affirmative_value_remains_unknown_without_evidence(authed_client):
    request = _import_payload()
    request.pop("affirmative")
    request["disclosure_text"] = None

    response = await authed_client.post("/messaging/consents/import", json=request)

    assert response.status_code == 200
    assert response.json()["purpose_states"] == {
        "operational": "unknown",
        "promotional": "unknown",
    }
    assert response.json()["evidence_id"] is None


async def test_revocation_endpoint_classifies_stop_and_start_by_route(authed_client):
    opted_in = await authed_client.post(
        "/messaging/consents/import",
        json=_import_payload(),
    )
    assert opted_in.status_code == 200

    stopped = await authed_client.post(
        "/messaging/consents/revocations",
        json=_revocation_payload(),
    )
    assert stopped.status_code == 200
    assert stopped.json()["classification"] == "global_opt_out"
    assert stopped.json()["purpose_states"] == {
        "operational": "opted_out",
        "promotional": "opted_out",
    }
    assert stopped.json()["global_suppression_reason"] == "global_opt_out"

    restored = await authed_client.post(
        "/messaging/consents/revocations",
        json=_revocation_payload(
            instruction_text="UNSTOP",
            source_reference="ticket-121-restore",
            occurred_at=datetime(2026, 7, 31, 20, 10, tzinfo=UTC).isoformat(),
            idempotency_key="ticket-121-restore",
        ),
    )
    assert restored.status_code == 200
    assert restored.json()["classification"] == "restore"
    assert restored.json()["purpose_states"] == {
        "operational": "opted_in",
        "promotional": "opted_out",
    }
    assert restored.json()["global_suppression_active"] is False


async def test_revocation_endpoint_distinguishes_promotional_and_ambiguous_requests(
    authed_client,
):
    promotional = await authed_client.post(
        "/messaging/consents/revocations",
        json=_revocation_payload(
            phone="+14155550122",
            instruction_text="Please stop promotional offers",
            source_reference="ticket-122",
            idempotency_key="ticket-122-promotional",
        ),
    )
    assert promotional.status_code == 200
    assert promotional.json()["classification"] == "promotional_opt_out"
    assert promotional.json()["purpose_states"]["operational"] == "unknown"
    assert promotional.json()["purpose_states"]["promotional"] == "opted_out"
    assert promotional.json()["global_suppression_active"] is False

    ambiguous = await authed_client.post(
        "/messaging/consents/revocations",
        json=_revocation_payload(
            phone="+14155550123",
            instruction_text="Stop this",
            source_reference="ticket-123",
            idempotency_key="ticket-123-ambiguous",
        ),
    )
    assert ambiguous.status_code == 200
    assert ambiguous.json()["classification"] == "ambiguous_hold"
    assert ambiguous.json()["global_suppression_active"] is True
    assert ambiguous.json()["global_suppression_reason"] == "ambiguous_hold"


async def test_consent_admin_endpoints_reject_non_admin_non_developer(db, test_org):
    async with _authed_client_for_role(db, test_org.id, Role.CASE_MANAGER) as client:
        imported = await client.post(
            "/messaging/consents/import",
            json=_import_payload(),
        )
        revoked = await client.post(
            "/messaging/consents/revocations",
            json=_revocation_payload(),
        )

    assert imported.status_code == 403
    assert revoked.status_code == 403


async def test_import_rejects_cross_organization_entity_link(
    authed_client,
    db,
    test_org,
):
    del test_org
    other_org_id = uuid.uuid4()
    db.connection().exec_driver_sql(
        "INSERT INTO organizations (id, name, slug) VALUES (%s, %s, %s)",
        (other_org_id, "Other Messaging Org", f"other-messaging-{uuid.uuid4().hex[:8]}"),
    )
    other_meta_lead_id = db.connection().exec_driver_sql(
        "INSERT INTO meta_leads (organization_id, meta_lead_id) VALUES (%s, %s) RETURNING id",
        (other_org_id, f"meta-{uuid.uuid4().hex}"),
    ).scalar_one()

    response = await authed_client.post(
        "/messaging/consents/import",
        json=_import_payload(meta_lead_id=str(other_meta_lead_id)),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "The linked entity was not found in this organization"


async def test_consent_mutations_require_csrf(authed_client):
    response = await authed_client.post(
        "/messaging/consents/import",
        json=_import_payload(),
        headers={CSRF_HEADER: ""},
    )

    assert response.status_code == 403
